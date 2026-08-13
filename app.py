import os
import uuid
import threading
import time

from datetime import datetime, timedelta
from functools import wraps

import requests
import stripe

from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    request,
    jsonify,
    send_file,
    send_from_directory,
    abort,
    make_response,
)

from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)

from flask_bcrypt import Bcrypt

from apscheduler.schedulers.background import (
    BackgroundScheduler
)
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config

from models import (
    db,
    User,
)

from utils.video_processor import (
    download_youtube,
    cut_video_ffmpeg,
    create_zip,
)

from utils.helpers import (
    get_video_duration,
    cleanup_temp_folder,
)

from utils.usage import (
    PLAN_LIMITS,
    get_effective_plan,
    get_usage_summary,
    can_process,
    consume_processing,
    release_processing,
    get_max_source_seconds,
    get_max_source_minutes,
    is_quality_allowed,
)


# =========================================================
# FLASK APPLICATION
# =========================================================

app = Flask(
    __name__,
    static_folder="statics",
    static_url_path="/statics",
)

app.config.from_object(Config)

app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1,
)


# =========================================================
# EXTENSIONS
# =========================================================

db.init_app(app)

bcrypt = Bcrypt(app)

login_manager = LoginManager(app)

login_manager.login_view = "login"


# =========================================================
# STRIPE
#
# Dipertahankan untuk kompatibilitas route lama.
# Pricing baru menggunakan Xendit.
# =========================================================

stripe_secret = app.config.get(
    "STRIPE_SECRET_KEY"
)

if stripe_secret:
    stripe.api_key = stripe_secret


# =========================================================
# XENDIT CONFIGURATION
# =========================================================

XENDIT_API_BASE_URL = os.environ.get(
    "XENDIT_API_BASE_URL",
    "https://api.xendit.co",
)

XENDIT_SECRET_KEY = os.environ.get(
    "XENDIT_SECRET_KEY"
)

XENDIT_WEBHOOK_TOKEN = os.environ.get(
    "XENDIT_WEBHOOK_TOKEN"
)

APP_BASE_URL = os.environ.get(
    "APP_BASE_URL"
)


# =========================================================
# XENDIT PLANS
# =========================================================

XENDIT_PLANS = {

    "basic": {

        "name":
            "Basic",

        "amount":
            29000,

        "description":
            "Youcut Basic Monthly Subscription",

    },

    "pro": {

        "name":
            "Pro",

        "amount":
            59000,

        "description":
            "Youcut Pro Monthly Subscription",

    },

}


# =========================================================
# BACKGROUND SCHEDULER
# =========================================================

scheduler = BackgroundScheduler()


# =========================================================
# IN-MEMORY JOB STORAGE
# =========================================================

jobs = {}

jobs_lock = threading.Lock()


# =========================================================
# API LOGIN PROTECTION
# =========================================================

def api_login_required(function):

    @wraps(function)
    def decorated_function(
        *args,
        **kwargs
    ):

        if not current_user.is_authenticated:

            return jsonify(
                {
                    "error":
                        "Anda harus login terlebih dahulu.",

                    "login_required":
                        True,

                    "login_url":
                        url_for(
                            "login",
                            next=request.path
                        ),
                }
            ), 401


        return function(
            *args,
            **kwargs
        )


    return decorated_function


# =========================================================
# TEMP CLEANUP
# =========================================================

def cleanup_old_temp():

    now = time.time()

    base = app.config[
        "TEMP_DIR"
    ]


    if not os.path.exists(
        base
    ):

        return


    for uid in os.listdir(
        base
    ):

        user_path = os.path.join(
            base,
            uid
        )


        if not os.path.isdir(
            user_path
        ):

            continue


        for job_id in os.listdir(
            user_path
        ):

            job_path = os.path.join(
                user_path,
                job_id
            )


            if not os.path.isdir(
                job_path
            ):

                continue


            mtime = os.path.getmtime(
                job_path
            )


            if (
                now - mtime > 3600
            ):

                cleanup_temp_folder(
                    job_path
                )


scheduler.add_job(
    cleanup_old_temp,
    "interval",
    minutes=30,
    id="cleanup_temp",
    replace_existing=True,
)

scheduler.start()


# =========================================================
# PWA SERVICE WORKER
# =========================================================

@app.route("/sw.js")
def service_worker():

    return send_from_directory(

        app.root_path,

        "service-worker.js",

        mimetype=
            "application/javascript",

    )

# =========================================================
# USER LOADER
# =========================================================

@login_manager.user_loader
def load_user(user_id):

    try:

        return db.session.get(
            User,
            int(user_id)
        )

    except (
        TypeError,
        ValueError
    ):

        return None


# =========================================================
# PUBLIC PAGES
# =========================================================

@app.get("/healthz")
def healthz():

    return jsonify(
        status="ok"
    ), 200


@app.route("/")
def index():

    return render_template(
        "index.html"
    )


@app.route("/about")
def about():

    return render_template(
        "about.html"
    )


# =========================================================
# USAGE API
# =========================================================

@app.route("/api/usage")
@login_required
def usage_api():

    try:

        summary = get_usage_summary(
            current_user
        )


        return jsonify(
            {
                "success":
                    True,

                **summary,
            }
        )


    except Exception as exc:

        db.session.rollback()


        return jsonify(
            {
                "success":
                    False,

                "error":
                    str(exc),
            }
        ), 500


# =========================================================
# CLIPPING PAGES
# =========================================================

@app.route("/clipping/")
@login_required
def clipping():

    return redirect(
        url_for(
            "manual_cut"
        )
    )


@app.route("/clipping/manual")
@login_required
def manual_cut():

    return render_template(
        "clipping_manual.html"
    )


@app.route("/clipping/timeline")
@login_required
def timeline_cut():

    return render_template(
        "clipping_timeline.html"
    )


# =========================================================
# GENERAL CLIP DOWNLOAD
# =========================================================

@app.route(
    "/api/download_clip/<job_id>/<int:index>"
)
@api_login_required
def download_clip(
    job_id,
    index
):

    uid = current_user.get_id()


    job_folder = os.path.join(

        app.config["TEMP_DIR"],

        str(uid),

        job_id,

    )


    path = os.path.join(

        job_folder,

        f"clip_{index + 1}.mp4",

    )


    if not os.path.exists(
        path
    ):

        abort(404)


    return send_file(

        path,

        as_attachment=True,

        download_name=
            f"clip_{index + 1}.mp4",

    )


# =========================================================
# MANUAL CREATE JOB
# =========================================================

@app.route(
    "/api/manual/create_job",
    methods=["POST"]
)
@api_login_required
def manual_create_job():

    data = request.get_json(
        silent=True
    )


    if not data:

        return jsonify(
            {
                "error":
                    "Data request tidak valid."
            }
        ), 400


    youtube_url = data.get(
        "youtube_url"
    )


    cuts = data.get(
        "cuts",
        []
    )


    quality = data.get(
        "quality",
        "720p"
    )


    orientation = data.get(
        "orientation",
        "landscape"
    )


    if not youtube_url:

        return jsonify(
            {
                "error":
                    "Link YouTube wajib diisi."
            }
        ), 400


    if not cuts:

        return jsonify(
            {
                "error":
                    "Minimal satu potongan diperlukan."
            }
        ), 400


    if len(cuts) > app.config[
        "MAX_POTONGAN_PER_LINK"
    ]:

        return jsonify(
            {
                "error":
                    "Maksimal 15 potongan per link."
            }
        ), 400


    # =====================================================
    # QUALITY
    # =====================================================

    if not is_quality_allowed(
        current_user,
        quality
    ):

        plan = get_effective_plan(
            current_user
        )


        maximum_quality = (
            PLAN_LIMITS[
                plan
            ]["max_quality"]
        )


        return jsonify(
            {
                "error":
                    (
                        f"Paket {plan.upper()} "
                        f"maksimal menggunakan "
                        f"{maximum_quality}."
                    ),

                "upgrade_required":
                    True,

                "current_plan":
                    plan,

                "max_quality":
                    maximum_quality,
            }
        ), 403


    # =====================================================
    # QUOTA
    # =====================================================

    quota = can_process(
        current_user
    )


    if not quota["allowed"]:

        return jsonify(
            {
                "error":
                    quota["error"],

                "quota_exceeded":
                    True,

                "plan":
                    quota["plan"],

                "used":
                    quota["used"],

                "limit":
                    quota["limit"],

                "remaining":
                    quota["remaining"],
            }
        ), 429


    uid = current_user.get_id()

    job_id = str(
        uuid.uuid4()
    )


    job_folder = os.path.join(

        app.config["TEMP_DIR"],

        str(uid),

        job_id,

    )


    os.makedirs(
        job_folder,
        exist_ok=True
    )


    job = {

        "id":
            job_id,

        "user_id":
            str(uid),

        "status":
            "downloading",

        "progress":
            0,

        "folder":
            job_folder,

        "timer":
            None,

        "outputs":
            [],

        "zip_path":
            None,

        "usage_consumed":
            False,

    }


    with jobs_lock:

        jobs[
            job_id
        ] = job


    thread = threading.Thread(

        target=process_manual_cut,

        args=(

            job_id,

            youtube_url,

            cuts,

            quality,

            orientation,

        ),

        daemon=True

    )


    thread.start()


    return jsonify(
        {
            "job_id":
                job_id
        }
    )


# =========================================================
# MANUAL PROCESS
# =========================================================

def process_manual_cut(
    job_id,
    youtube_url,
    cuts,
    quality,
    orientation
):

    with jobs_lock:

        job = jobs.get(
            job_id
        )


        if not job:

            return


        job_folder = job[
            "folder"
        ]


        user_id = job[
            "user_id"
        ]


    try:

        job[
            "status"
        ] = "downloading"


        # =================================================
        # DOWNLOAD
        # =================================================

        video_path = download_youtube(

            youtube_url,

            job_folder,

            quality

        )


        job[
            "progress"
        ] = 20


        # =================================================
        # USER + DURATION + QUOTA
        # =================================================

        with app.app_context():

            user = db.session.get(
                User,
                int(user_id)
            )


            if not user:

                raise RuntimeError(
                    "User tidak ditemukan."
                )


            duration = get_video_duration(
                video_path
            )


            max_seconds = (
                __import__(
                    "utils.usage",
                    fromlist=[
                        "get_max_source_seconds"
                    ]
                )
                .get_max_source_seconds(
                    user
                )
            )


            if duration > max_seconds:

                max_minutes = (
                    __import__(
                        "utils.usage",
                        fromlist=[
                            "get_max_source_minutes"
                        ]
                    )
                    .get_max_source_minutes(
                        user
                    )
                )


                raise RuntimeError(

                    (
                        "Durasi video terlalu panjang "
                        f"untuk paket "
                        f"{get_effective_plan(user).upper()}. "
                        f"Maksimal {max_minutes} menit."
                    )

                )


            consume_result = (
                consume_processing(
                    user
                )
            )


            if not consume_result[
                "success"
            ]:

                raise RuntimeError(
                    consume_result["error"]
                )


            job[
                "usage_consumed"
            ] = True


        # =================================================
        # FFMPEG
        # =================================================

        total = len(cuts)


        for idx, cut in enumerate(
            cuts
        ):

            start = float(
                cut["start"]
            )


            end = float(
                cut["end"]
            )


            if start < 0:

                raise RuntimeError(
                    "Start time tidak valid."
                )


            if end <= start:

                raise RuntimeError(
                    "End time harus lebih besar dari start time."
                )


            if end > duration:

                raise RuntimeError(
                    "End time melebihi durasi video."
                )


            out_name = (
                f"clip_{idx + 1}.mp4"
            )


            out_path = os.path.join(

                job_folder,

                out_name,

            )


            cut_video_ffmpeg(

                video_path,

                out_path,

                start,

                end,

                orientation,

                quality,

            )


            job[
                "outputs"
            ].append(
                out_name
            )


            job[
                "progress"
            ] = (

                20

                +

                int(
                    (
                        (idx + 1)
                        /
                        total
                    )
                    * 70
                )

            )


        zip_path = os.path.join(

            job_folder,

            "all_clips.zip"

        )


        create_zip(

            job_folder,

            zip_path

        )


        job[
            "zip_path"
        ] = "all_clips.zip"


        job[
            "status"
        ] = "completed"


        job[
            "progress"
        ] = 100


        job[
            "timer"
        ] = threading.Timer(

            600,

            cleanup_temp_folder,

            args=[
                job_folder
            ]

        )


        job[
            "timer"
        ].daemon = True


        job[
            "timer"
        ].start()


    except Exception as exc:

        if job.get(
            "usage_consumed"
        ):

            try:

                with app.app_context():

                    user = db.session.get(
                        User,
                        int(user_id)
                    )


                    if user:

                        release_processing(
                            user
                        )


            except Exception:

                db.session.rollback()


            job[
                "usage_consumed"
            ] = False


        job[
            "status"
        ] = "error"


        job[
            "error"
        ] = str(exc)


# =========================================================
# MANUAL STATUS
# =========================================================

@app.route(
    "/api/manual/job_status/<job_id>"
)
@api_login_required
def manual_job_status(
    job_id
):

    with jobs_lock:

        job = jobs.get(
            job_id
        )


        if not job:

            return jsonify(
                {
                    "status":
                        "not_found"
                }
            ), 404


        if str(
            job.get(
                "user_id"
            )
        ) != str(
            current_user.get_id()
        ):

            return jsonify(
                {
                    "error":
                        "Akses ditolak."
                }
            ), 403


        return jsonify(
            {
                "status":
                    job.get(
                        "status",
                        "unknown"
                    ),

                "progress":
                    job.get(
                        "progress",
                        0
                    ),

                "outputs":
                    job.get(
                        "outputs",
                        []
                    ),

                "zip_path":
                    job.get(
                        "zip_path"
                    ),

                "error":
                    job.get(
                        "error",
                        ""
                    ),
            }
        )


# =========================================================
# MANUAL ZIP
# =========================================================

@app.route(
    "/api/manual/download_zip/<job_id>"
)
@api_login_required
def download_zip(
    job_id
):

    uid = current_user.get_id()


    job_folder = os.path.join(

        app.config["TEMP_DIR"],

        str(uid),

        job_id

    )


    zip_path = os.path.join(

        job_folder,

        "all_clips.zip"

    )


    if not os.path.exists(
        zip_path
    ):

        abort(404)


    with jobs_lock:

        job = jobs.get(
            job_id
        )


        if job and job.get(
            "timer"
        ):

            job[
                "timer"
            ].cancel()


    response = make_response(

        send_file(

            zip_path,

            as_attachment=True,

            download_name=
                "youcut_clips.zip"

        )

    )


    @response.call_on_close
    def cleanup():

        cleanup_temp_folder(
            job_folder
        )


        with jobs_lock:

            jobs.pop(
                job_id,
                None
            )


    return response


# =========================================================
# TIMELINE CREATE
# =========================================================

@app.route(
    "/api/timeline/create_job",
    methods=["POST"]
)
@api_login_required
def timeline_create_job():

    data = request.get_json(
        silent=True
    )


    if not data:

        return jsonify(
            {
                "error":
                    "Data request tidak valid."
            }
        ), 400


    youtube_url = data.get(
        "youtube_url"
    )


    quality = data.get(
        "quality",
        "720p"
    )


    orientation = data.get(
        "orientation",
        "landscape"
    )


    if not youtube_url:

        return jsonify(
            {
                "error":
                    "Link YouTube wajib diisi."
            }
        ), 400


    if not is_quality_allowed(
        current_user,
        quality
    ):

        plan = get_effective_plan(
            current_user
        )


        maximum_quality = (
            PLAN_LIMITS[
                plan
            ]["max_quality"]
        )


        return jsonify(
            {
                "error":
                    (
                        f"Paket {plan.upper()} "
                        f"maksimal menggunakan "
                        f"{maximum_quality}."
                    ),

                "upgrade_required":
                    True,

                "current_plan":
                    plan,

                "max_quality":
                    maximum_quality,
            }
        ), 403


    quota = can_process(
        current_user
    )


    if not quota["allowed"]:

        return jsonify(
            {
                "error":
                    quota["error"],

                "quota_exceeded":
                    True,

                "plan":
                    quota["plan"],

                "used":
                    quota["used"],

                "limit":
                    quota["limit"],

                "remaining":
                    quota["remaining"],
            }
        ), 429


    uid = current_user.get_id()

    job_id = str(
        uuid.uuid4()
    )


    job_folder = os.path.join(

        app.config["TEMP_DIR"],

        str(uid),

        job_id,

    )


    os.makedirs(
        job_folder,
        exist_ok=True
    )


    job = {

        "id":
            job_id,

        "user_id":
            str(uid),

        "status":
            "downloading",

        "progress":
            0,

        "folder":
            job_folder,

        "video_path":
            None,

        "duration":
            0,

        "timer":
            None,

        "outputs":
            [],

        "zip_path":
            None,

        "usage_consumed":
            False,

    }


    with jobs_lock:

        jobs[
            job_id
        ] = job


    thread = threading.Thread(

        target=process_timeline_download,

        args=(

            job_id,

            youtube_url,

            quality,

        ),

        daemon=True

    )


    thread.start()


    return jsonify(

        {
            "job_id":
                job_id,

            "redirect":
                url_for(
                    "timeline_edit",

                    job_id=
                        job_id,

                    quality=
                        quality,

                    orientation=
                        orientation,

                ),
        }
    )


# =========================================================
# TIMELINE DOWNLOAD
# =========================================================

def process_timeline_download(
    job_id,
    youtube_url,
    quality
):

    with jobs_lock:

        job = jobs.get(
            job_id
        )


        if not job:

            return


        folder = job[
            "folder"
        ]


        user_id = job[
            "user_id"
        ]


    stop_progress = (
        threading.Event()
    )


    def update_progress():

        while not stop_progress.is_set():

            with jobs_lock:

                current_job = jobs.get(
                    job_id
                )


                if (

                    current_job

                    and

                    current_job[
                        "status"
                    ] ==
                    "downloading"

                    and

                    current_job[
                        "progress"
                    ] <
                    90

                ):

                    current_job[
                        "progress"
                    ] += 5


            time.sleep(2)


    try:

        job[
            "status"
        ] = "downloading"


        job[
            "progress"
        ] = 5


        progress_thread = threading.Thread(

            target=update_progress,

            daemon=True

        )


        progress_thread.start()


        video_path = download_youtube(

            youtube_url,

            folder,

            quality

        )


        stop_progress.set()


        job[
            "progress"
        ] = 100


        with app.app_context():

            user = db.session.get(
                User,
                int(user_id)
            )


            if not user:

                raise RuntimeError(
                    "User tidak ditemukan."
                )


            duration = get_video_duration(
                video_path
            )


            max_seconds = (
                __import__(
                    "utils.usage",
                    fromlist=[
                        "get_max_source_seconds"
                    ]
                )
                .get_max_source_seconds(
                    user
                )
            )


            if duration > max_seconds:

                max_minutes = (
                    __import__(
                        "utils.usage",
                        fromlist=[
                            "get_max_source_minutes"
                        ]
                    )
                    .get_max_source_minutes(
                        user
                    )
                )


                raise RuntimeError(

                    (
                        "Durasi video terlalu panjang "
                        f"untuk paket "
                        f"{get_effective_plan(user).upper()}. "
                        f"Maksimal {max_minutes} menit."
                    )
                )


            consume_result = (
                consume_processing(
                    user
                )
            )


            if not consume_result[
                "success"
            ]:

                raise RuntimeError(
                    consume_result["error"]
                )


            job[
                "usage_consumed"
            ] = True


        job[
            "video_path"
        ] = video_path


        job[
            "duration"
        ] = duration


        job[
            "status"
        ] = "ready"


    except Exception as exc:

        stop_progress.set()


        if job.get(
            "usage_consumed"
        ):

            try:

                with app.app_context():

                    user = db.session.get(
                        User,
                        int(user_id)
                    )


                    if user:

                        release_processing(
                            user
                        )


            except Exception:

                db.session.rollback()


            job[
                "usage_consumed"
            ] = False


        job[
            "status"
        ] = "error"


        job[
            "error"
        ] = str(exc)


# =========================================================
# TIMELINE EDIT
# =========================================================

@app.route(
    "/timeline/edit/<job_id>"
)
@login_required
def timeline_edit(
    job_id
):

    quality = request.args.get(
        "quality",
        "720p"
    )


    orientation = request.args.get(
        "orientation",
        "landscape"
    )


    with jobs_lock:

        job = jobs.get(
            job_id
        )


        if not job:

            abort(404)


        if str(
            job.get(
                "user_id"
            )
        ) != str(
            current_user.get_id()
        ):

            abort(403)


        if job[
            "status"
        ] != "ready":

            abort(404)


    return render_template(

        "timeline_edit.html",

        job_id=
            job_id,

        duration=
            job["duration"],

        quality=
            quality,

        orientation=
            orientation,

    )


# =========================================================
# TIMELINE VIDEO
# =========================================================

@app.route(
    "/api/timeline/get_video/<job_id>"
)
@api_login_required
def serve_timeline_video(
    job_id
):

    uid = current_user.get_id()


    with jobs_lock:

        job = jobs.get(
            job_id
        )


        if not job:

            abort(404)


        if str(
            job.get(
                "user_id"
            )
        ) != str(uid):

            abort(403)


        video_path = job.get(
            "video_path"
        )


    if not video_path:

        abort(404)


    if not os.path.exists(
        video_path
    ):

        abort(404)


    return send_file(

        video_path,

        mimetype=
            "video/mp4",

        conditional=True,

    )


# =========================================================
# TIMELINE CUT
# =========================================================

@app.route(
    "/api/timeline/cut",
    methods=["POST"]
)
@api_login_required
def timeline_cut_process():

    data = request.get_json(
        silent=True
    )


    if not data:

        return jsonify(
            {
                "error":
                    "Data request tidak valid."
            }
        ), 400


    job_id = data.get(
        "job_id"
    )


    cuts = data.get(
        "cuts",
        []
    )


    quality = data.get(
        "quality",
        "720p"
    )


    orientation = data.get(
        "orientation",
        "landscape"
    )


    if not job_id:

        return jsonify(
            {
                "error":
                    "Job ID diperlukan."
            }
        ), 400


    if not cuts:

        return jsonify(
            {
                "error":
                    "Minimal satu potongan diperlukan."
            }
        ), 400


    if len(cuts) > app.config[
        "MAX_POTONGAN_PER_LINK"
    ]:

        return jsonify(
            {
                "error":
                    "Maksimal 15 potongan."
            }
        ), 400


    if not is_quality_allowed(
        current_user,
        quality
    ):

        plan = get_effective_plan(
            current_user
        )


        maximum_quality = (
            PLAN_LIMITS[
                plan
            ]["max_quality"]
        )


        return jsonify(
            {
                "error":
                    (
                        f"Paket {plan.upper()} "
                        f"maksimal menggunakan "
                        f"{maximum_quality}."
                    ),

                "upgrade_required":
                    True,
            }
        ), 403


    with jobs_lock:

        job = jobs.get(
            job_id
        )


        if not job:

            return jsonify(
                {
                    "error":
                        "Job tidak ditemukan."
                }
            ), 404


        if str(
            job.get(
                "user_id"
            )
        ) != str(
            current_user.get_id()
        ):

            return jsonify(
                {
                    "error":
                        "Akses ditolak."
                }
            ), 403


        if job[
            "status"
        ] != "ready":

            return jsonify(
                {
                    "error":
                        "Job tidak siap."
                }
            ), 400


        video_path = job[
            "video_path"
        ]


        job_folder = job[
            "folder"
        ]


        duration = job[
            "duration"
        ]


        job[
            "status"
        ] = "processing"


        job[
            "outputs"
        ] = []


    try:

        for idx, cut in enumerate(
            cuts
        ):

            start = float(
                cut["start"]
            )


            end = float(
                cut["end"]
            )


            if start < 0:

                raise RuntimeError(
                    "Start time tidak valid."
                )


            if end <= start:

                raise RuntimeError(
                    "End time harus lebih besar dari start time."
                )


            if end > duration:

                raise RuntimeError(
                    "End time melebihi durasi video."
                )


            out_name = (
                f"clip_{idx + 1}.mp4"
            )


            out_path = os.path.join(

                job_folder,

                out_name

            )


            cut_video_ffmpeg(

                video_path,

                out_path,

                start,

                end,

                orientation,

                quality

            )


            job[
                "outputs"
            ].append(
                out_name
            )


            job[
                "progress"
            ] = int(

                (
                    (idx + 1)
                    /
                    len(cuts)
                )
                * 100

            )


        zip_path = os.path.join(

            job_folder,

            "all_clips.zip"

        )


        create_zip(

            job_folder,

            zip_path

        )


        job[
            "zip_path"
        ] = "all_clips.zip"


        job[
            "status"
        ] = "completed"


        job[
            "progress"
        ] = 100


        job[
            "timer"
        ] = threading.Timer(

            600,

            cleanup_temp_folder,

            args=[
                job_folder
            ]

        )


        job[
            "timer"
        ].daemon = True


        job[
            "timer"
        ].start()


        return jsonify(
            {
                "status":
                    "completed",

                "outputs":
                    job[
                        "outputs"
                    ],

                "zip_path":
                    job[
                        "zip_path"
                    ],
            }
        )


    except Exception as exc:

        if job.get(
            "usage_consumed"
        ):

            try:

                with app.app_context():

                    user = db.session.get(
                        User,
                        int(
                            current_user.get_id()
                        )
                    )


                    if user:

                        release_processing(
                            user
                        )


            except Exception:

                db.session.rollback()


            job[
                "usage_consumed"
            ] = False


        job[
            "status"
        ] = "error"


        job[
            "error"
        ] = str(exc)


        return jsonify(
            {
                "error":
                    str(exc)
            }
        ), 500


# =========================================================
# TIMELINE SINGLE CUT
# =========================================================

def process_timeline_operation(
    operation_id
):

    with jobs_lock:

        job = jobs.get(
            operation_id
        )


        if not job:

            return


        video_path = job["video_path"]
        job_folder = job["folder"]
        cuts = job["cuts"]
        quality = job["quality"]
        orientation = job["orientation"]
        create_archive = job["create_archive"]


        job["status"] = "processing"


    try:

        for idx, cut in enumerate(
            cuts
        ):

            out_name = f"clip_{idx + 1}.mp4"


            cut_video_ffmpeg(
                video_path,
                os.path.join(
                    job_folder,
                    out_name
                ),
                cut["start"],
                cut["end"],
                orientation,
                quality
            )


            with jobs_lock:

                job["outputs"].append(
                    out_name
                )


                job["progress"] = int(
                    ((idx + 1) / len(cuts))
                    * (90 if create_archive else 100)
                )


        zip_name = None


        if create_archive:

            zip_name = "all_clips.zip"


            create_zip(
                job_folder,
                os.path.join(
                    job_folder,
                    zip_name
                )
            )


        timer = threading.Timer(
            600,
            cleanup_temp_folder,
            args=[job_folder]
        )


        timer.daemon = True


        with jobs_lock:

            job["zip_path"] = zip_name
            job["status"] = "completed"
            job["progress"] = 100
            job["timer"] = timer


        timer.start()


    except Exception as exc:

        with jobs_lock:

            job["status"] = "error"
            job["error"] = str(exc)

@app.route(
    "/api/timeline/cut_single",
    methods=["POST"]
)
@api_login_required
def timeline_cut_single():

    data = request.get_json(
        silent=True
    )


    if not data:

        return jsonify(
            {
                "error":
                    "Data request tidak valid."
            }
        ), 400


    job_id = data.get(
        "job_id"
    )


    try:

        start = float(
            data["start"]
        )


        end = float(
            data["end"]
        )


    except (
        KeyError,
        ValueError,
        TypeError
    ):

        return jsonify(
            {
                "error":
                    "Start/end tidak valid."
            }
        ), 400


    quality = data.get(
        "quality",
        "720p"
    )


    orientation = data.get(
        "orientation",
        "landscape"
    )


    if not job_id:

        return jsonify(
            {
                "error":
                    "Job ID diperlukan."
            }
        ), 400


    if not is_quality_allowed(
        current_user,
        quality
    ):

        plan = get_effective_plan(
            current_user
        )


        maximum_quality = (
            PLAN_LIMITS[
                plan
            ]["max_quality"]
        )


        return jsonify(
            {
                "error":
                    (
                        f"Paket {plan.upper()} "
                        f"maksimal menggunakan "
                        f"{maximum_quality}."
                    ),

                "upgrade_required":
                    True,
            }
        ), 403


    with jobs_lock:

        job = jobs.get(
            job_id
        )


        if not job:

            return jsonify(
                {
                    "error":
                        "Job tidak ditemukan."
                }
            ), 404


        if str(
            job.get(
                "user_id"
            )
        ) != str(
            current_user.get_id()
        ):

            return jsonify(
                {
                    "error":
                        "Akses ditolak."
                }
            ), 403


        if job[
            "status"
        ] != "ready":

            return jsonify(
                {
                    "error":
                        "Job tidak siap."
                }
            ), 400


        duration = job[
            "duration"
        ]


        if start < 0:

            return jsonify(
                {
                    "error":
                        "Start time tidak valid."
                }
            ), 400


        if end <= start:

            return jsonify(
                {
                    "error":
                        "End time harus lebih besar dari start time."
                }
            ), 400


        if end > duration:

            return jsonify(
                {
                    "error":
                        "End time melebihi durasi video."
                }
            ), 400


        video_path = job[
            "video_path"
        ]


        operation_id = str(
            uuid.uuid4()
        )


        operation_folder = os.path.join(
            app.config["TEMP_DIR"],
            str(current_user.get_id()),
            operation_id
        )


        os.makedirs(
            operation_folder,
            exist_ok=True
        )


        jobs[operation_id] = {
            "id": operation_id,
            "user_id": str(current_user.get_id()),
            "status": "processing",
            "progress": 0,
            "folder": operation_folder,
            "video_path": video_path,
            "cuts": [{"start": start, "end": end}],
            "quality": quality,
            "orientation": orientation,
            "create_archive": False,
            "timer": None,
            "outputs": [],
            "zip_path": None,
            "error": "",
        }


    threading.Thread(
        target=process_timeline_operation,
        args=(operation_id,),
        daemon=True
    ).start()


    return jsonify(
        {
            "job_id": operation_id
        }
    ), 202


# =========================================================
# TIMELINE ZIP
# =========================================================

@app.route(
    "/api/timeline/download_all_zip",
    methods=["POST"]
)
@api_login_required
def timeline_download_all_zip():

    data = request.get_json(
        silent=True
    )


    if not data:

        return jsonify(
            {
                "error":
                    "Data request tidak valid."
            }
        ), 400


    job_id = data.get(
        "job_id"
    )


    cuts = data.get(
        "cuts",
        []
    )


    quality = data.get(
        "quality",
        "720p"
    )


    orientation = data.get(
        "orientation",
        "landscape"
    )


    if not job_id:

        return jsonify(
            {
                "error":
                    "Job ID diperlukan."
            }
        ), 400


    if not cuts:

        return jsonify(
            {
                "error":
                    "Minimal satu potongan diperlukan."
            }
        ), 400


    if len(cuts) > app.config[
        "MAX_POTONGAN_PER_LINK"
    ]:

        return jsonify(
            {
                "error":
                    "Maksimal 15 potongan."
            }
        ), 400


    if not is_quality_allowed(
        current_user,
        quality
    ):

        plan = get_effective_plan(
            current_user
        )


        maximum_quality = (
            PLAN_LIMITS[
                plan
            ]["max_quality"]
        )


        return jsonify(
            {
                "error":
                    (
                        f"Paket {plan.upper()} "
                        f"maksimal menggunakan "
                        f"{maximum_quality}."
                    ),

                "upgrade_required":
                    True,
            }
        ), 403


    with jobs_lock:

        job = jobs.get(
            job_id
        )


        if not job:

            return jsonify(
                {
                    "error":
                        "Job tidak ditemukan."
                }
            ), 404


        if str(
            job.get(
                "user_id"
            )
        ) != str(
            current_user.get_id()
        ):

            return jsonify(
                {
                    "error":
                        "Akses ditolak."
                }
            ), 403


        if job[
            "status"
        ] != "ready":

            return jsonify(
                {
                    "error":
                        "Job tidak siap."
                }
            ), 400


        video_path = job[
            "video_path"
        ]


        job_folder = job[
            "folder"
        ]


        duration = job[
            "duration"
        ]


    try:

        operation_cuts = []


        for cut in cuts:

            start = float(cut["start"])
            end = float(cut["end"])


            if start < 0:

                return jsonify(
                    {"error": "Start time tidak valid."}
                ), 400


            if end <= start:

                return jsonify(
                    {"error": "End time harus lebih besar dari start time."}
                ), 400


            if end > duration:

                return jsonify(
                    {"error": "End time melebihi durasi video."}
                ), 400


            operation_cuts.append(
                {"start": start, "end": end}
            )


    except (
        KeyError,
        ValueError,
        TypeError
    ):

        return jsonify(
            {"error": "Start/end tidak valid."}
        ), 400


    operation_id = str(uuid.uuid4())


    operation_folder = os.path.join(
        app.config["TEMP_DIR"],
        str(current_user.get_id()),
        operation_id
    )


    os.makedirs(
        operation_folder,
        exist_ok=True
    )


    with jobs_lock:

        jobs[operation_id] = {
            "id": operation_id,
            "user_id": str(current_user.get_id()),
            "status": "processing",
            "progress": 0,
            "folder": operation_folder,
            "video_path": video_path,
            "cuts": operation_cuts,
            "quality": quality,
            "orientation": orientation,
            "create_archive": True,
            "timer": None,
            "outputs": [],
            "zip_path": None,
            "error": "",
        }


    threading.Thread(
        target=process_timeline_operation,
        args=(operation_id,),
        daemon=True
    ).start()


    return jsonify(
        {"job_id": operation_id}
    ), 202


# =========================================================
# REGISTER
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if current_user.is_authenticated:

        return redirect(
            url_for("index")
        )


    if request.method == "POST":

        username = request.form[
            "username"
        ]


        email = request.form[
            "email"
        ]


        password = request.form[
            "password"
        ]


        existing_user = (

            User.query

            .filter(

                (

                    User.email == email

                )

                |

                (

                    User.username ==
                    username

                )

            )

            .first()

        )


        if existing_user:

            return render_template(

                "register.html",

                error=
                    "Username atau email sudah digunakan."

            )


        hashed = (

            bcrypt

            .generate_password_hash(
                password
            )

            .decode(
                "utf-8"
            )

        )


        user = User(

            username=
                username,

            email=
                email,

            password_hash=
                hashed,

            subscription_type=
                "free",

        )


        db.session.add(
            user
        )


        db.session.commit()


        login_user(
            user
        )


        next_page = request.args.get(
            "next"
        )


        return redirect(

            next_page

            or

            url_for(
                "index"
            )

        )


    return render_template(
        "register.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if current_user.is_authenticated:

        return redirect(
            url_for("index")
        )


    if request.method == "POST":

        email = request.form[
            "email"
        ]


        password = request.form[
            "password"
        ]


        user = (

            User.query

            .filter_by(
                email=email
            )

            .first()

        )


        if (

            user

            and

            bcrypt.check_password_hash(

                user.password_hash,

                password

            )

        ):

            login_user(
                user
            )


            next_page = (

                request.args.get(
                    "next"
                )

                or

                request.form.get(
                    "next"
                )

            )


            return redirect(

                next_page

                or

                url_for(
                    "index"
                )

            )


        return render_template(

            "login.html",

            error=
                "Email atau password salah"

        )


    return render_template(
        "login.html"
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
@login_required
def logout():

    logout_user()

    return redirect(
        url_for("index")
    )


# =========================================================
# PRICING
# =========================================================

@app.route("/pricing")
def pricing():

    return render_template(
        "pricing.html",
        stripe_public_key=
            app.config.get(
                "STRIPE_PUBLIC_KEY"
            )
    )


# =========================================================
# XENDIT HELPERS
# =========================================================

def create_xendit_reference(
    user_id,
    plan
):

    return (
        f"YC-{user_id}-"
        f"{plan.upper()}-"
        f"{uuid.uuid4().hex[:12]}"
    )


def parse_xendit_reference(
    reference_id
):

    if not reference_id:

        return None, None


    parts = str(
        reference_id
    ).split("-")


    if len(parts) != 4:

        return None, None


    if parts[0] != "YC":

        return None, None


    try:

        user_id = int(
            parts[1]
        )

    except (
        TypeError,
        ValueError
    ):

        return None, None


    plan = parts[2].lower()


    if plan not in XENDIT_PLANS:

        return None, None


    return user_id, plan


# =========================================================
# NEXT MONTH ANCHOR
# =========================================================

def get_next_anchor_date():

    now = datetime.utcnow()


    if now.month == 12:

        year = now.year + 1
        month = 1

    else:

        year = now.year
        month = now.month + 1


    day = min(
        now.day,
        28
    )


    return datetime(

        year=year,

        month=month,

        day=day,

        hour=0,

        minute=0,

        second=0,

        microsecond=0,

    )


# =========================================================
# CREATE XENDIT SUBSCRIPTION
# =========================================================

@app.route(
    "/create-xendit-subscription",
    methods=["POST"]
)
@login_required
def create_xendit_subscription():

    if not XENDIT_SECRET_KEY:

        return jsonify(
            {
                "error":
                    "XENDIT_SECRET_KEY belum dikonfigurasi."
            }
        ), 500


    if not APP_BASE_URL:

        return jsonify(
            {
                "error":
                    "APP_BASE_URL belum dikonfigurasi."
            }
        ), 500


    data = request.get_json(
        silent=True
    )


    if not data:

        return jsonify(
            {
                "error":
                    "Request tidak valid."
            }
        ), 400


    plan = str(
        data.get(
            "plan",
            ""
        )
    ).lower()


    if plan not in XENDIT_PLANS:

        return jsonify(
            {
                "error":
                    "Paket tidak tersedia."
            }
        ), 400


    # =====================================================
    # ACTIVE SUBSCRIPTION
    # =====================================================

    if (

        current_user.subscription_type
        in
        ("basic", "pro")

        and

        current_user.subscription_expiry

        and

        current_user.subscription_expiry
        >
        datetime.utcnow()

    ):

        return jsonify(
            {
                "error":
                    "Subscription kamu masih aktif."
            }
        ), 409


    plan_data = XENDIT_PLANS[
        plan
    ]


    reference_id = (
        create_xendit_reference(
            current_user.id,
            plan
        )
    )


    anchor_date = (
        get_next_anchor_date()
    )


    # =====================================================
    # XENDIT PAYMENT SESSION
    # =====================================================

    payload = {

        "reference_id":
            reference_id,


        "session_type":
            "SUBSCRIPTION",


        "mode":
            "PAYMENT_LINK",


        "amount":
            plan_data["amount"],


        "currency":
            "IDR",


        "country":
            "ID",


        "locale":
            "id",


        "customer": {

            "reference_id":
                f"YOUCUT-{current_user.id}",

            "type":
                "INDIVIDUAL",

            "email":
                current_user.email,

            "individual_detail": {

                "given_names":
                    current_user.username

            },

        },


        "description":
            plan_data[
                "description"
            ],


        "subscription": {

            "schedule": {

                "interval":
                    "MONTH",

                "interval_count":
                    1,

                "total_recurrence":
                    12,

                "anchor_date":
                    anchor_date.isoformat(),

                "retry_interval":
                    "DAY",

                "retry_interval_count":
                    1,

                "total_retry":
                    3,

                "failed_attempt_notifications":
                    [
                        1,
                        2,
                        3
                    ]

            },


            "immediate_payment":
                True,


            "failed_cycle_action":
                "RESUME"

        },


        "success_return_url":
            (
                APP_BASE_URL.rstrip("/")
                +
                "/pricing?payment=success"
            ),


        "cancel_return_url":
            (
                APP_BASE_URL.rstrip("/")
                +
                "/pricing?payment=cancelled"
            ),

    }


    endpoint = (
        XENDIT_API_BASE_URL.rstrip("/")
        +
        "/sessions"
    )


    headers = {

        "Content-Type":
            "application/json",

        "Accept":
            "application/json",

        "api-version":
            "2026-01-01",

    }


    try:

        response = requests.post(

            endpoint,

            json=payload,

            headers=headers,

            auth=(
                XENDIT_SECRET_KEY,
                ""
            ),

            timeout=30,

        )


    except requests.RequestException as exc:

        return jsonify(
            {
                "error":
                    (
                        "Gagal menghubungi Xendit: "
                        f"{exc}"
                    )
            }
        ), 502


    try:

        result = response.json()

    except ValueError:

        result = {
            "message":
                response.text
        }


    if not response.ok:

        return jsonify(
            {
                "error":
                    result.get(
                        "message",
                        "Xendit menolak request."
                    ),

                "details":
                    result,

            }
        ), response.status_code


    payment_link_url = (
        result.get(
            "payment_link_url"
        )
    )


    if not payment_link_url:

        return jsonify(
            {
                "error":
                    (
                        "Xendit tidak "
                        "mengembalikan "
                        "payment_link_url."
                    ),

                "details":
                    result,

            }
        ), 502


    return jsonify(
        {
            "success":
                True,

            "payment_link_url":
                payment_link_url,

            "payment_session_id":
                result.get(
                    "payment_session_id"
                ),

            "recurring_plan_id":
                result.get(
                    "recurring_plan_id"
                ),

            "reference_id":
                reference_id,

            "plan":
                plan,

        }
    )


# =========================================================
# XENDIT WEBHOOK
# =========================================================

@app.route(
    "/webhooks/xendit",
    methods=["POST"]
)
def xendit_webhook():

    if not XENDIT_WEBHOOK_TOKEN:

        return (
            "Webhook token belum dikonfigurasi.",
            500
        )


    received_token = request.headers.get(
        "x-callback-token"
    )


    if (
        not received_token
        or
        received_token
        !=
        XENDIT_WEBHOOK_TOKEN
    ):

        return (
            "Unauthorized",
            401
        )


    payload = request.get_json(
        silent=True
    )


    if not payload:

        return (
            "Invalid JSON",
            400
        )


    event = payload.get(
        "event"
    )


    data = payload.get(
        "data",
        {}
    )


    # =====================================================
    # PAYMENT SESSION COMPLETED
    #
    # Hanya dicatat.
    # Status plan utama kita konfirmasi dari
    # recurring_plan.activated.
    # =====================================================

    if event == (
        "payment_session.completed"
    ):

        return jsonify(
            {
                "received":
                    True
            }
        )


    # =====================================================
    # PAYMENT SESSION EXPIRED
    # =====================================================

    if event == (
        "payment_session.expired"
    ):

        return jsonify(
            {
                "received":
                    True
            }
        )


    # =====================================================
    # RECURRING PLAN ACTIVATED
    # =====================================================

    if event == (
        "recurring_plan.activated"
    ):

        reference_id = data.get(
            "reference_id"
        )


        user_id, plan = (
            parse_xendit_reference(
                reference_id
            )
        )


        if not user_id or not plan:

            return (
                "Invalid reference_id",
                400
            )


        user = db.session.get(
            User,
            user_id
        )


        if not user:

            return (
                "User not found",
                404
            )


        now = datetime.utcnow()


        user.subscription_type = (
            plan
        )


        # Initial access begins once the plan
        # is actually activated.

        user.subscription_expiry = (

            now

            +

            timedelta(
                days=31
            )

        )


        db.session.commit()


        return jsonify(
            {
                "received":
                    True
            }
        )


    # =====================================================
    # RECURRING CYCLE SUCCEEDED
    # =====================================================

    if event == (
        "recurring.cycle.succeeded"
    ):

        reference_id = data.get(
            "reference_id"
        )


        user_id, plan = (
            parse_xendit_reference(
                reference_id
            )
        )


        if not user_id or not plan:

            return (
                "Invalid reference_id",
                400
            )


        user = db.session.get(
            User,
            user_id
        )


        if not user:

            return (
                "User not found",
                404
            )


        cycle_type = data.get(
            "type"
        )


        # Xendit can emit a cycle succeeded
        # for the immediate payment when
        # immediate_payment=true.
        #
        # The plan activation webhook already
        # grants the first period, so do not
        # extend the period a second time.

        if cycle_type == "IMMEDIATE":

            return jsonify(
                {
                    "received":
                        True
                }
            )


        now = datetime.utcnow()


        user.subscription_type = (
            plan
        )


        if (

            user.subscription_expiry
            and

            user.subscription_expiry
            >
            now

        ):

            user.subscription_expiry = (

                user.subscription_expiry

                +

                timedelta(
                    days=31
                )

            )

        else:

            user.subscription_expiry = (

                now

                +

                timedelta(
                    days=31
                )

            )


        db.session.commit()


        return jsonify(
            {
                "received":
                    True
            }
        )


    # =====================================================
    # RECURRING CYCLE FAILED
    # =====================================================

    if event == (
        "recurring.cycle.failed"
    ):

        reference_id = data.get(
            "reference_id"
        )


        user_id, plan = (
            parse_xendit_reference(
                reference_id
            )
        )


        if not user_id:

            return (
                "Invalid reference_id",
                400
            )


        user = db.session.get(
            User,
            user_id
        )


        if not user:

            return (
                "User not found",
                404
            )


        # We don't immediately revoke access if
        # the current paid period has not expired.

        if (

            not user.subscription_expiry
            or

            user.subscription_expiry
            <=
            datetime.utcnow()

        ):

            user.subscription_type = (
                "free"
            )

            user.subscription_expiry = (
                None
            )


            db.session.commit()


        return jsonify(
            {
                "received":
                    True
            }
        )


    # =====================================================
    # RECURRING PLAN INACTIVATED
    # =====================================================

    if event == (
        "recurring.plan.inactivated"
    ):

        reference_id = data.get(
            "reference_id"
        )


        user_id, plan = (
            parse_xendit_reference(
                reference_id
            )
        )


        if not user_id:

            return (
                "Invalid reference_id",
                400
            )


        user = db.session.get(
            User,
            user_id
        )


        if not user:

            return (
                "User not found",
                404
            )


        if (

            not user.subscription_expiry
            or

            user.subscription_expiry
            <=
            datetime.utcnow()

        ):

            user.subscription_type = (
                "free"
            )

            user.subscription_expiry = (
                None
            )


            db.session.commit()


        return jsonify(
            {
                "received":
                    True
            }
        )


    # =====================================================
    # OTHER EVENTS
    # =====================================================

    return jsonify(
        {
            "received":
                True
        }
    )


# =========================================================
# OLD STRIPE CHECKOUT
#
# Dipertahankan agar route lama tidak hilang.
# Pricing baru tidak memakai route ini.
# =========================================================

@app.route(
    "/create-checkout-session",
    methods=["POST"]
)
@login_required
def create_checkout_session():

    if not stripe.api_key:

        return jsonify(
            {
                "error":
                    "Stripe tidak dikonfigurasi."
            }
        ), 503


    data = request.get_json(
        silent=True
    )


    if not data:

        return jsonify(
            {
                "error":
                    "Request tidak valid."
            }
        ), 400


    price_id = data.get(
        "price_id"
    )


    if not price_id:

        return jsonify(
            {
                "error":
                    "Price ID tidak ditemukan."
            }
        ), 400


    try:

        checkout_session = (
            stripe.checkout.Session.create(

                payment_method_types=[
                    "card"
                ],

                line_items=[

                    {
                        "price":
                            price_id,

                        "quantity":
                            1,

                    }

                ],

                mode=
                    "subscription",

                success_url=(

                    url_for(
                        "pricing_success",
                        _external=True
                    )

                    +

                    "?session_id="
                    +
                    "{CHECKOUT_SESSION_ID}"

                ),

                cancel_url=
                    url_for(
                        "pricing",
                        _external=True
                    ),

                customer_email=
                    current_user.email,

                metadata={
                    "user_id":
                        str(
                            current_user.id
                        )
                },

            )
        )


        return jsonify(
            {
                "id":
                    checkout_session.id
            }
        )


    except Exception as exc:

        return jsonify(
            {
                "error":
                    str(exc)
            }
        ), 403


# =========================================================
# STRIPE SUCCESS
# =========================================================

@app.route(
    "/pricing/success"
)
@login_required
def pricing_success():

    return redirect(
        url_for(
            "pricing",
            payment="success"
        )
    )
# =========================================================
# MOCK PURCHASE
# =========================================================
#
# TEMPORARY DEVELOPMENT FEATURE
#
# Ini bukan payment gateway.
# User Free dianggap telah membeli paket
# setelah menekan "Beli Paket Ini".
#
# Tidak ada uang yang diproses.
# =========================================================

@app.route(
    "/api/mock-purchase",
    methods=["POST"]
)
@login_required
def mock_purchase():

    data = request.get_json(
        silent=True
    )


    if not data:

        return jsonify(
            {
                "success": False,
                "error":
                    "Request tidak valid."
            }
        ), 400


    plan = str(
        data.get(
            "plan",
            ""
        )
    ).strip().lower()


    # -----------------------------------------------------
    # Hanya Basic / Pro yang boleh dibeli
    # -----------------------------------------------------

    if plan not in (
        "basic",
        "pro"
    ):

        return jsonify(
            {
                "success": False,
                "error":
                    "Paket tidak tersedia."
            }
        ), 400


    # -----------------------------------------------------
    # Hanya user Free yang boleh menggunakan
    # mock purchase.
    # -----------------------------------------------------

    current_plan = (
        current_user.subscription_type
        or
        "free"
    ).lower()


    if current_plan != "free":

        return jsonify(
            {
                "success": False,
                "error":
                    (
                        "Akun ini sudah memiliki "
                        "paket berbayar."
                    ),

                "current_plan":
                    current_plan,
            }
        ), 409


    # -----------------------------------------------------
    # Aktifkan paket selama 30 hari.
    # -----------------------------------------------------

    current_user.subscription_type = plan

    current_user.subscription_expiry = (
        datetime.utcnow()
        +
        timedelta(days=30)
    )


    try:

        db.session.commit()


    except Exception as exc:

        db.session.rollback()


        return jsonify(
            {
                "success": False,
                "error":
                    (
                        "Gagal mengaktifkan paket: "
                        f"{exc}"
                    )
            }
        ), 500


    # -----------------------------------------------------
    # Ambil konfigurasi paket
    # -----------------------------------------------------

    plan_config = PLAN_LIMITS.get(
        plan
    )


    return jsonify(
        {
            "success": True,

            "message":
                (
                    f"Paket "
                    f"{plan_config['name']} "
                    "berhasil diaktifkan."
                ),

            "plan":
                plan,

            "plan_name":
                plan_config["name"],

            "expires_at":
                current_user
                    .subscription_expiry
                    .isoformat(),

            "limit":
                plan_config[
                    "monthly_processing"
                ],

            "max_source_minutes":
                plan_config[
                    "max_source_minutes"
                ],

            "max_quality":
                plan_config[
                    "max_quality"
                ],
        }
    )

# =========================================================
# STRIPE WEBHOOK
# =========================================================

@app.route(
    "/stripe/webhook",
    methods=["POST"]
)
def stripe_webhook():

    webhook_secret = (
        app.config.get(
            "STRIPE_WEBHOOK_SECRET"
        )
    )


    if not webhook_secret:

        return (
            "Stripe webhook disabled.",
            503
        )


    payload = request.get_data(
        as_text=True
    )


    sig_header = request.headers.get(
        "Stripe-Signature"
    )


    try:

        event = stripe.Webhook.construct_event(

            payload,

            sig_header,

            webhook_secret

        )


    except ValueError:

        return (
            "Invalid payload",
            400
        )


    except stripe.error.SignatureVerificationError:

        return (
            "Invalid signature",
            400
        )


    if (
        event["type"]
        ==
        "checkout.session.completed"
    ):

        stripe_session = (
            event["data"]["object"]
        )


        metadata = (
            stripe_session.get(
                "metadata",
                {}
            )
        )


        try:

            user_id = int(
                metadata[
                    "user_id"
                ]
            )

        except (
            KeyError,
            TypeError,
            ValueError
        ):

            return (
                "Invalid metadata",
                400
            )


        user = db.session.get(
            User,
            user_id
        )


        if (

            user

            and

            stripe_session.get(
                "subscription"
            )

        ):

            user.subscription_type = (
                "pro"
            )


            user.subscription_expiry = (

                datetime.utcnow()

                +

                timedelta(
                    days=30
                )

            )


            db.session.commit()


    return "", 200


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(404)
def not_found(error):

    return render_template(
        "404.html"
    ), 404


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    with app.app_context():

        db.create_all()


    app.run(
        debug=True
    )
