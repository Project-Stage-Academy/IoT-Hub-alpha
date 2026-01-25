# Dev Environment

This document covers common Docker troubleshooting and health inspection.

## Compose override (development)

The repo includes `docker-compose.override.yml` for local development.

Usage:
- Default: `docker compose up -d --build` (override is applied automatically).
- Disable override: `docker compose -f docker-compose.yml up -d --build`.

Behavior:
- `./backend:/app` is mounted for live reload with Django's dev server.
- `DJANGO_SETTINGS_MODULE` is forced to `config.settings.local` for `web`, `worker`, and `migrate`.
- `collectstatic` and migrations still run, but they write into your local `backend/` tree.

Common pitfalls:
- If files do not reload, restart the `web` container; on Docker Desktop, ensure the repo is file-shared.
- If `collectstatic` creates unexpected files, clean `backend/staticfiles/` locally.
- If migrations do not apply, run `docker compose run --rm migrate` after code changes.

## Convenience scripts

Run from the repo root. If the scripts are not executable, use `chmod +x scripts/*.sh`.
Windows users: run the scripts via WSL or Git Bash (PowerShell/CMD will not run `sh` scripts).
Line endings: ensure scripts use LF (not CRLF) on Linux/macOS to avoid `/bin/sh^M` errors.
Git Bash note: when a command includes a Linux path like `/app`, prefix it with `MSYS2_ARG_CONV_EXCL='*'` to avoid path conversion.

- Start (builds if needed): `scripts/up.sh`
- Start without override: `scripts/up.sh --no-override`
- Stop containers (keep volumes): `scripts/down.sh`
- Stop and remove volumes: `scripts/down.sh --volumes`
- Reset database and rerun migrations: `scripts/reset-db.sh`
- Tail logs: `scripts/logs.sh -f`
- Tail logs for a service: `scripts/logs.sh -f -s web`

## Troubleshooting

- Rebuild without cache: `docker compose build --no-cache`
- Fix file permission issues: `docker compose exec -T web sh -c 'ls -la /app && id'`
- Clear volumes (removes DB data): `docker compose down --volumes`
- Remove unused images/networks: `docker system prune -f`
- Recreate containers: `docker compose up -d --build`
- Healthcheck failed (web): `docker compose logs --tail=200 web` and verify `http://localhost:8000/health/`
- DB not ready: `docker compose logs --tail=200 db` and `docker compose exec -T db sh -c 'pg_isready -U $POSTGRES_USER'`
- Migrations stuck: `docker compose run --rm migrate` then restart `web`

## Health checks

- View status: `docker compose ps`
- Inspect a container: `docker inspect --format '{{json .State}}' <container>`

## Service checks

- Web app responds: `curl http://localhost:8000/`
- Postgres reachable: `docker compose exec -T db sh -c 'pg_isready -U $POSTGRES_USER'`
- Redis reachable: `docker compose exec redis redis-cli -n 0 ping`
- Celery worker responsive: `docker compose exec worker celery -A config inspect ping`

## Validation

Validated locally by running:

- `docker build -t iot-hub-web -f backend/Dockerfile backend`
- `docker compose up -d --build`
