import hashlib
import secrets
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app

from models import db


OTP_LENGTH = 6
OTP_EXPIRE_MINUTES = 5
OTP_RESEND_SECONDS = 60
OTP_MAX_ATTEMPTS = 5


def _setting(name, default=None):
    value = current_app.config.get(name)
    if value in (None, ""):
        return default
    return value


def email_verification_configured():
    required = (
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "MAIL_FROM",
    )
    return all(_setting(key) for key in required)


def generate_otp():
    return f"{secrets.randbelow(900000) + 100000:06d}"


def hash_otp(user_id, otp):
    secret = _setting("SECRET_KEY", "youcut-dev-secret")
    payload = f"{secret}:{user_id}:{otp}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def mask_email(email):
    if not email or "@" not in email:
        return email or ""

    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[:1] + "*"
    else:
        masked_local = local[0] + "*" * max(len(local) - 2, 1) + local[-1]
    return f"{masked_local}@{domain}"


def _send_email(recipient, otp):
    host = _setting("SMTP_HOST")
    port = int(_setting("SMTP_PORT", 587))
    username = _setting("SMTP_USERNAME")
    password = _setting("SMTP_PASSWORD")
    mail_from = _setting("MAIL_FROM")
    mail_from_name = _setting("MAIL_FROM_NAME", "Youcut")

    subject = "Kode Verifikasi Email Youcut"
    html = f"""
    <div style=\"font-family:Arial,sans-serif;max-width:560px;margin:auto;color:#171716\">
      <div style=\"padding:28px;border:1px solid #ddd;border-radius:14px;background:#fff\">
        <h2 style=\"margin:0 0 10px\">Verifikasi Email Youcut</h2>
        <p style=\"color:#666\">Gunakan kode berikut untuk menyelesaikan pendaftaran akun Youcut:</p>
        <div style=\"font-size:34px;font-weight:800;letter-spacing:10px;padding:18px 0\">{otp}</div>
        <p style=\"color:#666\">Kode berlaku selama {OTP_EXPIRE_MINUTES} menit dan hanya dapat digunakan satu kali.</p>
        <p style=\"color:#888;font-size:13px\">Jika kamu tidak merasa mendaftar di Youcut, abaikan email ini.</p>
      </div>
    </div>
    """
    text = (
        f"Kode verifikasi Youcut: {otp}\n\n"
        f"Kode berlaku selama {OTP_EXPIRE_MINUTES} menit.\n"
        "Jika kamu tidak merasa mendaftar di Youcut, abaikan email ini."
    )

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{mail_from_name} <{mail_from}>"
    message["To"] = recipient
    message.attach(MIMEText(text, "plain", "utf-8"))
    message.attach(MIMEText(html, "html", "utf-8"))

    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=30) as server:
            server.login(username, password)
            server.sendmail(mail_from, [recipient], message.as_string())
    else:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(username, password)
            server.sendmail(mail_from, [recipient], message.as_string())


def issue_otp(user, force=False, commit=True):
    if not email_verification_configured():
        return {
            "success": False,
            "error": (
                "SMTP email verification belum dikonfigurasi. "
                "Isi SMTP_HOST, SMTP_PORT, SMTP_USERNAME, "
                "SMTP_PASSWORD, dan MAIL_FROM."
            ),
        }

    now = datetime.utcnow()

    if (
        not force
        and user.otp_last_sent_at
        and (now - user.otp_last_sent_at).total_seconds() < OTP_RESEND_SECONDS
    ):
        remaining = OTP_RESEND_SECONDS - int(
            (now - user.otp_last_sent_at).total_seconds()
        )
        return {
            "success": False,
            "error": f"Tunggu {max(remaining, 1)} detik sebelum meminta OTP lagi.",
            "retry_after": max(remaining, 1),
        }

    otp = generate_otp()
    user.otp_hash = hash_otp(user.id, otp)
    user.otp_expires_at = now + timedelta(minutes=OTP_EXPIRE_MINUTES)
    user.otp_attempts = 0
    user.otp_last_sent_at = now

    if commit:
        db.session.commit()

    try:
        _send_email(user.email, otp)
    except (OSError, smtplib.SMTPException) as exc:
        user.otp_hash = None
        user.otp_expires_at = None
        user.otp_attempts = 0
        user.otp_last_sent_at = None
        if commit:
            db.session.commit()
        return {
            "success": False,
            "error": f"Gagal mengirim email OTP: {exc}",
        }

    return {
        "success": True,
        "expires_in": OTP_EXPIRE_MINUTES * 60,
        "masked_email": mask_email(user.email),
    }


def verify_otp(user, submitted_otp):
    if not submitted_otp or not submitted_otp.isdigit() or len(submitted_otp) != OTP_LENGTH:
        return {"success": False, "error": "Kode OTP harus 6 digit."}

    if not user.otp_hash or not user.otp_expires_at:
        return {"success": False, "error": "OTP tidak tersedia. Kirim ulang kode verifikasi."}

    if user.otp_attempts >= OTP_MAX_ATTEMPTS:
        user.otp_hash = None
        user.otp_expires_at = None
        user.otp_attempts = 0
        db.session.commit()
        return {"success": False, "error": "Batas percobaan OTP tercapai. Kirim OTP baru."}

    if user.otp_expires_at <= datetime.utcnow():
        user.otp_hash = None
        user.otp_expires_at = None
        user.otp_attempts = 0
        db.session.commit()
        return {"success": False, "error": "OTP sudah kedaluwarsa. Kirim OTP baru."}

    expected = hash_otp(user.id, submitted_otp.strip())

    if not secrets.compare_digest(expected, user.otp_hash):
        user.otp_attempts += 1
        db.session.commit()
        remaining = max(OTP_MAX_ATTEMPTS - user.otp_attempts, 0)
        return {
            "success": False,
            "error": f"Kode OTP salah. Sisa percobaan: {remaining}.",
        }

    user.email_verified = True
    user.otp_hash = None
    user.otp_expires_at = None
    user.otp_attempts = 0
    user.otp_last_sent_at = None
    db.session.commit()

    return {"success": True}


def send_payment_notification(
    recipient,
    username,
    plan,
    amount,
    order_id,
    status,
    expiry_date=None,
):
    if not email_verification_configured():
        return False

    host = str(_setting("SMTP_HOST"))
    port = int(_setting("SMTP_PORT", 587))
    username_smtp = str(_setting("SMTP_USERNAME"))
    password_smtp = str(_setting("SMTP_PASSWORD"))
    mail_from = str(_setting("MAIL_FROM"))
    mail_from_name = str(_setting("MAIL_FROM_NAME", "Youcut"))

    plan_title = str(plan).capitalize() if plan else "Free"
    try:
        formatted_amount = f"Rp{int(float(amount)):,}".replace(",", ".")
    except (ValueError, TypeError):
        formatted_amount = f"Rp{amount}"

    if status == "success":
        subject = f"[Youcut] Pembayaran Berhasil — Paket {plan_title}"
        expiry_str = (
            expiry_date.strftime("%d %B %Y")
            if isinstance(expiry_date, datetime)
            else str(expiry_date or "30 Hari ke depan")
        )
        badge_color = "#10b981"
        badge_text = "PEMBAYARAN BERHASIL"
        headline = "Terima kasih atas pembayaran Anda!"
        subheadline = f"Akun Youcut Anda telah resmi di-upgrade ke paket <strong>{plan_title}</strong>."
        detail_rows = f"""
            <tr><td style="padding:8px 0;color:#666">Order ID</td><td style="padding:8px 0;font-weight:bold;text-align:right;color:#111">{order_id}</td></tr>
            <tr><td style="padding:8px 0;color:#666">Paket</td><td style="padding:8px 0;font-weight:bold;text-align:right;color:#111">{plan_title}</td></tr>
            <tr><td style="padding:8px 0;color:#666">Total Pembayaran</td><td style="padding:8px 0;font-weight:bold;text-align:right;color:#10b981">{formatted_amount}</td></tr>
            <tr><td style="padding:8px 0;color:#666">Berlaku Hingga</td><td style="padding:8px 0;font-weight:bold;text-align:right;color:#111">{expiry_str}</td></tr>
        """
        plain_text = (
            f"Halo {username},\n\n"
            f"Pembayaran Anda untuk Paket {plan_title} sebesar {formatted_amount} telah BERHASIL diverifikasi!\n"
            f"Order ID: {order_id}\n"
            f"Berlaku hingga: {expiry_str}\n\n"
            f"Terima kasih telah berlangganan Youcut!\n"
            f"Buka aplikasi: https://youcut.my.id\n"
        )
    elif status == "pending":
        subject = f"[Youcut] Menunggu Pembayaran — Paket {plan_title}"
        badge_color = "#f59e0b"
        badge_text = "MENUNGGU PEMBAYARAN"
        headline = "Pesanan Anda Sedang Menunggu Pembayaran"
        subheadline = f"Tagihan pesanan paket <strong>{plan_title}</strong> telah dibuat. Silakan selesaikan pembayaran."
        detail_rows = f"""
            <tr><td style="padding:8px 0;color:#666">Order ID</td><td style="padding:8px 0;font-weight:bold;text-align:right;color:#111">{order_id}</td></tr>
            <tr><td style="padding:8px 0;color:#666">Paket</td><td style="padding:8px 0;font-weight:bold;text-align:right;color:#111">{plan_title}</td></tr>
            <tr><td style="padding:8px 0;color:#666">Total Tagihan</td><td style="padding:8px 0;font-weight:bold;text-align:right;color:#f59e0b">{formatted_amount}</td></tr>
        """
        plain_text = (
            f"Halo {username},\n\n"
            f"Tagihan pesanan Anda untuk Paket {plan_title} sebesar {formatted_amount} sedang menunggu pembayaran.\n"
            f"Order ID: {order_id}\n\n"
            f"Silakan selesaikan pembayaran Anda via Midtrans agar paket langsung aktif secara otomatis.\n"
        )
    else:
        return False

    html = f"""
    <div style="background-color:#f4f5f7;padding:30px 15px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#171716">
      <div style="max-width:540px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb;box-shadow:0 4px 6px -1px rgba(0,0,0,0.05)">
        <div style="background:#0f172a;padding:24px 30px;text-align:center">
          <span style="color:#ffffff;font-size:20px;font-weight:800;letter-spacing:2px">YOUCUT</span>
        </div>
        <div style="padding:30px">
          <div style="display:inline-block;padding:4px 12px;border-radius:20px;background:{badge_color};color:#ffffff;font-size:11px;font-weight:700;letter-spacing:1px;margin-bottom:16px">
            {badge_text}
          </div>
          <h2 style="margin:0 0 10px;font-size:20px;color:#0f172a">{headline}</h2>
          <p style="margin:0 0 24px;color:#475569;font-size:14px;line-height:1.5">Halo <strong>{username}</strong>, {subheadline}</p>
          
          <table style="width:100%;border-collapse:collapse;border-top:1px solid #e2e8f0;border-bottom:1px solid #e2e8f0;margin-bottom:24px;font-size:14px">
            <tbody>
              {detail_rows}
            </tbody>
          </table>

          <div style="text-align:center;margin-top:20px">
            <a href="https://youcut.my.id" style="display:inline-block;background:#2563eb;color:#ffffff;padding:12px 28px;text-decoration:none;border-radius:8px;font-size:14px;font-weight:600">Buka Youcut</a>
          </div>
        </div>
        <div style="background:#f8fafc;padding:16px 30px;text-align:center;border-top:1px solid #e2e8f0;font-size:12px;color:#94a3b8">
          Jika Anda tidak merasa melakukan transaksi ini, silakan hubungi tim support Youcut.
        </div>
      </div>
    </div>
    """

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{mail_from_name} <{mail_from}>"
    message["To"] = recipient
    message.attach(MIMEText(plain_text, "plain", "utf-8"))
    message.attach(MIMEText(html, "html", "utf-8"))

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=20) as server:
                server.login(username_smtp, password_smtp)
                server.sendmail(mail_from, [recipient], message.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=20) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(username_smtp, password_smtp)
                server.sendmail(mail_from, [recipient], message.as_string())
        return True
    except Exception as exc:
        if current_app:
            current_app.logger.error("Gagal mengirim email notifikasi payment: %s", exc)
        return False
