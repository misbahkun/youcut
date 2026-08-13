import os
import shutil

cookies_file = os.environ.get("YOUTUBE_COOKIES_FILE")
if cookies_file:
    runtime_cookies_file = "/tmp/youtube-cookies.txt"
    shutil.copyfile(cookies_file, runtime_cookies_file)
    os.chmod(runtime_cookies_file, 0o600)
    os.environ["YOUTUBE_COOKIES_FILE"] = runtime_cookies_file

from app import app
from models import db


with app.app_context():
    db.create_all()

# One worker is required because jobs and APScheduler state are process-local.
os.execvp(
    "gunicorn",
    [
        "gunicorn",
        "--workers",
        "1",
        "--bind",
        "0.0.0.0:8000",
        "--timeout",
        "600",
        "app:app",
    ],
)
