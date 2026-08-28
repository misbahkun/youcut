from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin


db = SQLAlchemy()


# =========================================================
# USER
# =========================================================

class User(UserMixin, db.Model):

    __tablename__ = "users"


    id = db.Column(
        db.Integer,
        primary_key=True
    )


    username = db.Column(
        db.String(64),
        unique=True,
        nullable=False
    )


    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )


    password_hash = db.Column(
        db.String(128),
        nullable=True
    )


    # =====================================================
    # SUBSCRIPTION
    # =====================================================

    subscription_type = db.Column(
        db.String(20),
        nullable=False,
        default="free"
    )

    # Possible values:
    #
    # free
    # basic
    # pro


    subscription_expiry = db.Column(
        db.DateTime,
        nullable=True
    )


    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )


    # =====================================================
    # EMAIL VERIFICATION
    # =====================================================

    email_verified = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )


    otp_hash = db.Column(
        db.String(64),
        nullable=True
    )


    otp_expires_at = db.Column(
        db.DateTime,
        nullable=True
    )


    otp_attempts = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )


    otp_last_sent_at = db.Column(
        db.DateTime,
        nullable=True
    )


# =========================================================
# MONTHLY USAGE
# =========================================================

class Usage(db.Model):

    __tablename__ = "usages"


    id = db.Column(
        db.Integer,
        primary_key=True
    )


    # =====================================================
    # USER
    # =====================================================

    user_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "users.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )


    # =====================================================
    # MONTH PERIOD
    #
    # Format:
    #
    # 2026-08
    #
    # Satu user hanya boleh memiliki satu record
    # untuk satu bulan.
    # =====================================================

    period = db.Column(
        db.String(7),
        nullable=False
    )


    # =====================================================
    # PROCESSING COUNT
    #
    # 1 kali video diproses = +1
    #
    # Tidak peduli menghasilkan 1 atau 10 clip.
    # =====================================================

    processing_count = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )


    # =====================================================
    # TIMESTAMPS
    # =====================================================

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )


    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )


    last_processed_at = db.Column(
        db.DateTime,
        nullable=True
    )


    # =====================================================
    # RELATIONSHIP
    # =====================================================

    user = db.relationship(
        "User",
        backref=db.backref(
            "usage_records",
            lazy=True,
            cascade="all, delete-orphan"
        )
    )


    # =====================================================
    # UNIQUE CONSTRAINT
    #
    # Contoh:
    #
    # user 1 + 2026-08
    #
    # hanya boleh ada satu record.
    # =====================================================

    __table_args__ = (

        db.UniqueConstraint(

            "user_id",

            "period",

            name=
                "uq_usage_user_period"

        ),

    )
