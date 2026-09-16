FROM denoland/deno:2.9.5 AS deno

FROM python:3.11-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 youcut \
    && useradd --uid 10001 --gid 10001 --create-home youcut

COPY --from=deno /usr/bin/deno /usr/local/bin/deno

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=10001:10001 . .
RUN mkdir -p /data/temp && chown -R 10001:10001 /data

USER 10001:10001

ENTRYPOINT ["python", "docker-entrypoint.py"]
