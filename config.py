import os


basedir = os.path.abspath(
    os.path.dirname(__file__)
)


class Config:

    # =====================================================
    # FLASK
    # =====================================================

    SECRET_KEY = (
        os.environ.get("SECRET_KEY")
        or "dev-secret-key-change-in-production"
    )


    # =====================================================
    # DATABASE
    # =====================================================

    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL")
        or
        "sqlite:///"
        +
        os.path.join(
            basedir,
            "youcut.db"
        )
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False


    # =====================================================
    MIDTRANS_MERCHANT_ID = os.environ.get("MIDTRANS_MERCHANT_ID")

    MIDTRANS_CLIENT_KEY = os.environ.get("MIDTRANS_CLIENT_KEY")

    MIDTRANS_SERVER_KEY = os.environ.get("MIDTRANS_SERVER_KEY")


    # =====================================================
    # APPLICATION URL
    #
    # Wajib menggunakan HTTPS ketika sudah production.
    #
    # Contoh:
    #
    # https://youcut.id
    #
    # Untuk testing lokal:
    #
    # https://xxxx.ngrok-free.app
    # =====================================================

    APP_BASE_URL = os.environ.get("APP_BASE_URL")


    # =====================================================
    # EMAIL / SMTP VERIFICATION
    # =====================================================

    SMTP_HOST = os.environ.get(
        "SMTP_HOST",
        "smtp.gmail.com"
    )

    SMTP_PORT = int(
        os.environ.get(
            "SMTP_PORT",
            "587"
        )
    )

    SMTP_USERNAME = os.environ.get("SMTP_USERNAME")

    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")

    MAIL_FROM = (
        os.environ.get("MAIL_FROM")
        or SMTP_USERNAME
    )

    MAIL_FROM_NAME = os.environ.get(
        "MAIL_FROM_NAME",
        "Youcut"
    )


    # =====================================================
    # VIDEO
    # =====================================================

    MAX_POTONGAN_PER_LINK = 15

    TEMP_DIR = (
        os.environ.get("TEMP_DIR")
        or os.path.join(
            basedir,
            "temp"
        )
    )

