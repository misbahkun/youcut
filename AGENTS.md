# Repository Guide

## Run locally

- On Windows, create `venv/` with Python 3.11 or newer, install dependencies with `venv\Scripts\python.exe -m pip install -r requirements.txt`, then run `venv\Scripts\python.exe app.py`. Recreate `venv/` if its interpreter points to a Python installation that no longer exists; activation is optional.
- Open `http://127.0.0.1:5000`. The `__main__` block creates missing tables with `db.create_all()` and starts Flask in debug mode.
- Clipping requires native `ffmpeg`, `ffprobe`, and Deno executables on `PATH`; `ffmpeg-python` does not install FFmpeg, while yt-dlp uses Deno for YouTube JavaScript challenges. Open a new shell and restart the app after changing User `PATH`.
- There is no configured test, lint, formatter, typecheck, migration, codegen, or production-server command. Do not invent one; for Python-only changes, use `venv\Scripts\python.exe -m compileall -q app.py config.py models.py utils` as the focused syntax check.

## Architecture and state

- `app.py` creates the global Flask application and also contains routes, payment integration, and background-job coordination. It starts APScheduler at import time; importing it is not side-effect free.
- `models.py` owns the SQLite schema. The default database is ignored `youcut.db`; `DATABASE_URL` overrides it. `db.create_all()` creates missing tables but is not a schema migration system.
- `utils/video_processor.py` owns yt-dlp, FFmpeg cutting, and ZIP creation; `utils/helpers.py` shells out to `ffprobe`; `utils/usage.py` owns plan limits and monthly quota mutations.
- Jobs are process-local entries in `app.py`'s `jobs` dictionary, while files live under ignored `temp/<user>/<job>/`. A restart loses job status, and multiple worker processes would not share jobs. Cleanup runs every 30 minutes and removes job directories older than one hour.
- Templates contain substantial page-specific JavaScript. Check the matching `templates/*.html` before editing similarly named files under `statics/js/`; some tracked JS files are unused or empty.
- The active PWA worker is root `service-worker.js`: `templates/base.html` registers `/sw.js`, and the Flask route serves that root file. `statics/sw.js` is not the registered worker.
- `payments.py` contains fenced Jinja/HTML rather than executable Python and is not imported by the app. Treat `templates/pricing.html` plus payment routes in `app.py` as the live pricing flow unless a task explicitly targets that artifact.

## Configuration and verification

- Runtime configuration comes directly from process environment variables; no dotenv loader is installed. Relevant keys are `SECRET_KEY`, `DATABASE_URL`, Stripe keys, Xendit keys/token/base URL, and `APP_BASE_URL`.
- Never commit `youcut.db`, `temp/`, `venv/`, or agent artifacts already listed in `.gitignore`.
- Verify route/template changes through the Flask app in a browser. A real clipping check additionally needs network access to YouTube plus working `ffmpeg`/`ffprobe`; payment checks need configured gateway credentials and webhook URLs.
- When changing a client/API contract, inspect both sides: the route in `app.py` and the inline script in its matching template. Manual and timeline flows poll shared job-status routes and depend on exact status strings and JSON fields.
