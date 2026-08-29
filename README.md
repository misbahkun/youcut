# YouCut

YouCut is a Flask web application for downloading and clipping YouTube videos,
with user subscriptions, email verification, and Midtrans Sandbox payments.

## Features

- Manual and timeline-based video clipping.
- FFmpeg processing with individual clip and ZIP downloads.
- User accounts with email verification using a six-digit SMTP OTP.
- Monthly usage limits and Free, Basic, and Pro subscription plans.
- One-time 30-day payments through Midtrans Sandbox Snap.
- Replay-safe payment notifications verified against the Midtrans Status API.

## Requirements

- Python 3.11 or newer.
- Native `ffmpeg`, `ffprobe`, and Deno executables available on `PATH`.
- A YouTube cookies file for authenticated downloads where required.

## Run Locally

On Windows:

```powershell
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe app.py
```

Open `http://127.0.0.1:5000` in a browser. Activating the virtual environment is optional when using its Python executable directly.

## Configuration

Runtime configuration is read from environment variables. Never commit real secrets, payment credentials, cookie files, databases, or generated media.

Copy the variable names from [`.env.example`](.env.example) into your local or
server environment and provide real values for:

- `SECRET_KEY`
- `DATABASE_URL` and `APP_BASE_URL`
- `MIDTRANS_MERCHANT_ID`, `MIDTRANS_CLIENT_KEY`, and `MIDTRANS_SERVER_KEY`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `MAIL_FROM`, and `MAIL_FROM_NAME`
- `YOUTUBE_COOKIES_FILE` when a cookies file is used outside Docker Compose

The current payment integration uses Midtrans **Sandbox** endpoints. Do not use
it for production payments without adding and verifying a production-mode
configuration.

## Verification

Run the full unit test suite:

```powershell
venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

Run the focused Python syntax check:

```powershell
venv\Scripts\python.exe -m compileall -q app.py config.py models.py utils tests
```

Payment, email delivery, and clipping should also be exercised through their
real browser flows because they depend on external services and native tools.

## Deployment

The supported VPS setup uses Docker Compose with one Gunicorn worker and Caddy
for HTTPS. Persistent SQLite data and temporary job files live under the
server-side `data/` mount. Keep a single application replica because background
jobs and scheduler state are process-local.

The current deployment is served at [youcut.my.id](https://youcut.my.id). Always
follow the backup, allowlisted transfer, health-check, and rollback procedure in
[DEPLOYMENT.md](DEPLOYMENT.md) before updating the server.

## Documentation

- See [AGENTS.md](AGENTS.md) for repository architecture, development constraints, and verification guidance.
- See [DEPLOYMENT.md](DEPLOYMENT.md) for the Docker Compose, Caddy, and VPS deployment procedure.
