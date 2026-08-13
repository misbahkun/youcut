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
    # STRIPE
    #
    # Masih dipertahankan untuk kompatibilitas
    # dengan kode lama.
    # =====================================================

    STRIPE_PUBLIC_KEY = os.environ.get(
        "STRIPE_PUBLISHABLE_KEY"
    )

    STRIPE_SECRET_KEY = os.environ.get(
        "STRIPE_SECRET_KEY"
    )

    STRIPE_WEBHOOK_SECRET = os.environ.get(
        "STRIPE_WEBHOOK_SECRET"
    )


    # =====================================================
    # XENDIT
    # =====================================================

    XENDIT_SECRET_KEY = os.environ.get(
        "XENDIT_SECRET_KEY"
    )

    XENDIT_WEBHOOK_TOKEN = os.environ.get(
        "XENDIT_WEBHOOK_TOKEN"
    )

    XENDIT_API_BASE_URL = os.environ.get(
        "XENDIT_API_BASE_URL"
    ) or "https://api.xendit.co"


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

    APP_BASE_URL = os.environ.get(
        "APP_BASE_URL"
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

