# VPS Deployment

## DNS and firewall

1. In Dewabiz DNS, add an `A` record with host `@`, value `43.163.106.159`, and priority blank or `0`. Leave existing Dewabiz nameservers unchanged when they are already authoritative. Do not add an `AAAA` record.
2. In the Tencent security group, allow TCP 80 and 443 from the public internet. Restrict TCP 22 to the administrator's trusted source IP.

## First deployment

1. Install Docker Engine and the Compose plugin for Ubuntu using the current official Docker documentation: <https://docs.docker.com/engine/install/ubuntu/>.
2. Create the application directories and grant the container user ownership:

   ```sh
   sudo mkdir -p /srv/youcut/data/temp
   sudo chown -R 10001:10001 /srv/youcut/data
   ```

3. Transfer only the required source into `/srv/youcut`: application Python files, `utils/`, `templates/`, `statics/`, `service-worker.js`, `requirements.txt`, `Dockerfile`, `docker-entrypoint.py`, `compose.yaml`, `Caddyfile`, and `.env.example`. Exclude `.env`, databases, `data/`, `temp/`, `venv/`, `.git/`, `.codegraph/`, `.omo/`, `.playwright-mcp/`, and `.sisyphus/`. Create `.env` on the VPS from `.env.example` rather than transferring local secrets.
4. Set real production secrets and protect the file:

   ```sh
   cd /srv/youcut
   sudo install -m 600 -o "$USER" -g "$USER" /dev/null .env
   editor .env
   ```

5. Build and start the services:

   ```sh
   docker compose build --pull
   docker compose up -d
   docker compose logs --tail=100 app caddy
   curl --fail --silent --show-error https://youcut.my.id/healthz
   ```

The health response must be `{"status":"ok"}` over trusted HTTPS; do not use `curl -k`.

## Updates and rollback

Before every update, stop writes and create a timestamped data backup outside `/srv/youcut`, then verify its checksum:

```sh
docker compose stop app
sudo tar -C /srv/youcut -czf "/srv/youcut-data-$(date +%Y%m%d%H%M%S).tar.gz" data
sha256sum /srv/youcut-data-*.tar.gz
```

Transfer the same allowlisted application files, run `docker compose build --pull` and `docker compose up -d`, then check logs and HTTPS health. Roll back application files/image to the previous known-good version separately from persistent `data/`; restore data only when a data recovery is explicitly required.

## Operational limits

Gunicorn must remain at one worker: jobs and APScheduler state are in memory and are not shared across processes. Restarts lose job status. SQLite limits concurrent write scaling, `db.create_all()` only creates missing tables and is not a migration system, and this topology must not be scaled to multiple app replicas without redesigning those constraints.
