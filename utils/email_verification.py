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
