# YouCut

YouCut is a Flask web application for downloading and clipping YouTube videos.

## Features

- Manual and timeline-based video clipping.
- FFmpeg processing with individual clip and ZIP downloads.
- User accounts, monthly usage limits, subscription plans, and payment integrations.

## Requirements

- Python 3.11 or newer.
- Native `ffmpeg`, `ffprobe`, and Deno executables available on `PATH`.

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

## Documentation

- See [AGENTS.md](AGENTS.md) for repository architecture, development constraints, and verification guidance.
- See [DEPLOYMENT.md](DEPLOYMENT.md) for the Docker Compose, Caddy, and VPS deployment procedure.
