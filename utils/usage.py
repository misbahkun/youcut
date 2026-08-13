from datetime import datetime

from models import db, Usage


# =========================================================
# PLAN CONFIGURATION
# =========================================================

PLAN_LIMITS = {

    "free": {
        "name": "Free",
        "monthly_processing": 5,
        "max_source_minutes": 30,
        "max_quality": "720p",
    },

    "basic": {
        "name": "Basic",
        "monthly_processing": 50,
        "max_source_minutes": 120,
        "max_quality": "1080p",
    },

    "pro": {
        "name": "Pro",
        "monthly_processing": 150,
        "max_source_minutes": 180,
        "max_quality": "1080p",
    },

}


# =========================================================
# CURRENT PERIOD
# =========================================================

def get_current_period():

    return datetime.utcnow().strftime(
        "%Y-%m"
    )


# =========================================================
# EFFECTIVE PLAN
# =========================================================

def get_effective_plan(user):

    if not user:
        return "free"

    plan = (
        user.subscription_type
        or "free"
    ).lower()

    if plan not in PLAN_LIMITS:
        plan = "free"

    # Free selalu aktif.
    if plan == "free":
        return "free"

    # Subscription berbayar wajib mempunyai expiry.
    if not user.subscription_expiry:
        return "free"

    if user.subscription_expiry <= datetime.utcnow():
        return "free"

    return plan


# =========================================================
# PLAN LIMITS
# =========================================================

def get_plan_limits(user):

    plan = get_effective_plan(
        user
    )

    return PLAN_LIMITS[plan]


# =========================================================
# GET / CREATE MONTHLY USAGE
# =========================================================

def get_current_usage(user):

    if not user:
        raise ValueError(
            "User tidak valid."
        )

    period = get_current_period()

    usage = (
        Usage.query
        .filter_by(
            user_id=user.id,
            period=period
        )
        .first()
    )

    if usage:
        return usage

    usage = Usage(
        user_id=user.id,
        period=period,
        processing_count=0
    )

    db.session.add(
        usage
    )

    db.session.commit()

    return usage


# =========================================================
# CURRENT PROCESSING COUNT
# =========================================================

def get_processing_count(user):

    usage = get_current_usage(
        user
    )

    return usage.processing_count


# =========================================================
# MONTHLY LIMIT
# =========================================================

def get_monthly_limit(user):

    limits = get_plan_limits(
        user
    )

    return limits[
        "monthly_processing"
    ]


# =========================================================
# REMAINING QUOTA
# =========================================================

def get_remaining_quota(user):

    used = get_processing_count(
        user
    )

    limit = get_monthly_limit(
        user
    )

    return max(
        limit - used,
        0
    )


# =========================================================
# CHECK QUOTA
# =========================================================

def can_process(user):

    if not user:

        return {
            "allowed": False,
            "plan": "free",
            "used": 0,
            "limit": 0,
            "remaining": 0,
            "error": "User tidak valid.",
        }


    plan = get_effective_plan(
        user
    )

    used = get_processing_count(
        user
    )

    limit = get_monthly_limit(
        user
    )

    remaining = max(
        limit - used,
        0
    )


    if used >= limit:

        return {
            "allowed": False,
            "plan": plan,
            "used": used,
            "limit": limit,
            "remaining": 0,
            "error": (
                "Kuota processing bulan ini "
                "sudah habis."
            ),
        }


    return {
        "allowed": True,
        "plan": plan,
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "error": None,
    }


# =========================================================
# CONSUME ONE PROCESSING
# =========================================================

def consume_processing(user):

    quota = can_process(
        user
    )

    if not quota["allowed"]:

        return {
            "success": False,
            **quota,
        }


    usage = get_current_usage(
        user
    )


    # Double-check untuk mengurangi risiko quota
    # terlewati karena request bersamaan.
    if (
        usage.processing_count
        >=
        quota["limit"]
    ):

        return {
            "success": False,
            "plan": quota["plan"],
            "used": usage.processing_count,
            "limit": quota["limit"],
            "remaining": 0,
            "error": (
                "Kuota processing bulan ini "
                "sudah habis."
            ),
        }


    usage.processing_count += 1

    usage.last_processed_at = (
        datetime.utcnow()
    )


    db.session.commit()


    return {
        "success": True,
        "plan": quota["plan"],
        "used": usage.processing_count,
        "limit": quota["limit"],
        "remaining": max(
            quota["limit"]
            -
            usage.processing_count,
            0
        ),
        "error": None,
    }


# =========================================================
# RELEASE ONE PROCESSING
#
# Dipakai kalau processing sudah di-consume,
# tetapi FFmpeg kemudian gagal.
# =========================================================

def release_processing(user):

    usage = get_current_usage(
        user
    )


    if usage.processing_count > 0:

        usage.processing_count -= 1

        usage.updated_at = (
            datetime.utcnow()
        )


        db.session.commit()


    return {
        "success": True,
        "used": usage.processing_count,
        "limit": get_monthly_limit(
            user
        ),
        "remaining": get_remaining_quota(
            user
        ),
    }


# =========================================================
# SOURCE DURATION
# =========================================================

def get_max_source_minutes(user):

    limits = get_plan_limits(
        user
    )

    return limits[
        "max_source_minutes"
    ]


def get_max_source_seconds(user):

    return (
        get_max_source_minutes(
            user
        )
        * 60
    )


# =========================================================
# QUALITY
# =========================================================

def get_max_quality(user):

    limits = get_plan_limits(
        user
    )

    return limits[
        "max_quality"
    ]


def is_quality_allowed(
    user,
    requested_quality
):

    requested = (
        requested_quality
        or "720p"
    ).lower()


    maximum = (
        get_max_quality(
            user
        )
        .lower()
    )


    if requested == "720p":
        return True


    if requested == "1080p":
        return maximum == "1080p"


    return False


def normalize_quality(
    user,
    requested_quality
):

    requested = (
        requested_quality
        or "720p"
    ).lower()


    maximum = (
        get_max_quality(
            user
        )
        .lower()
    )


    if requested == "1080p":

        if maximum == "1080p":
            return "1080p"

        return "720p"


    return "720p"


# =========================================================
# USAGE SUMMARY
# =========================================================

def get_usage_summary(user):

    plan = get_effective_plan(
        user
    )

    limits = PLAN_LIMITS[
        plan
    ]

    usage = get_current_usage(
        user
    )

    limit = limits[
        "monthly_processing"
    ]

    used = usage.processing_count

    remaining = max(
        limit - used,
        0
    )


    return {
        "plan": plan,

        "plan_name":
            limits["name"],

        "used":
            used,

        "limit":
            limit,

        "remaining":
            remaining,

        "max_source_minutes":
            limits[
                "max_source_minutes"
            ],

        "max_quality":
            limits[
                "max_quality"
            ],

        "period":
            usage.period,

        "last_processed_at":
            usage.last_processed_at,
    }