# Dev environment (Docker)

Single source of truth for local Docker workflow.
- Quick start: `README.md`
- Validation checklist: `docs/validation.md`
- DIND demo: `scripts/dind-demo/README.md`

## Requirements

- Docker Engine/Desktop with Compose v2

## Windows notes

- Use WSL or Git Bash for `.sh` scripts.
- Keep LF line endings for `scripts/*.sh` and `backend/scripts/entrypoint.sh`.
- In Git Bash, prefix commands that include `/app` with `MSYS2_ARG_CONV_EXCL='*'`.

## Compose override

- Default: `docker-compose.override.yml` is applied automatically.
- Disable: `scripts/up.sh --no-override` and `scripts/down.sh --no-override`.

## Scripts

- Start: `scripts/up.sh [--no-override] [--profile NAME] [services...]`
  - Examples: `scripts/up.sh web db`, `scripts/up.sh --profile monitoring`
- Stop: `scripts/down.sh [--no-override] [--volumes] [--remove-orphans]`
  - `--volumes` removes DB data
- Logs: `scripts/logs.sh [-f|--follow] [-n|--tail N] [-s|--service SERVICE]...`
  - Examples: `scripts/logs.sh -f`, `scripts/logs.sh -f -s web`, `scripts/logs.sh --tail 200 db`
- Reset DB (destructive): `scripts/reset-db.sh [--no-override]`
  - Drops and recreates the DB, then runs migrations
- DB init hook: `scripts/init-db.sh`
  - Runs automatically inside Postgres on first boot when the DB volume is empty

## Troubleshooting

- Status: `docker compose ps`
- Web logs: `docker compose logs --tail 200 web`
- DB logs: `docker compose logs --tail 200 db`
- DB ready check: `docker compose exec -T db pg_isready -U $POSTGRES_USER`
- Rebuild: `docker compose build --no-cache`
- Inspect container health: `docker inspect --format '{{json .State}}' <container>`
- Fix permissions (container): `docker compose exec -T web sh -c 'ls -la /app && id'`
- Clear volumes (destructive): `docker compose down --volumes`

## Logging (direct compose)

- Follow all services: `docker compose logs -f`
- Follow one service: `docker compose logs -f web`
- Tail with timestamps: `docker compose logs --timestamps --tail 200 web`
- Logs for multiple services: `docker compose logs -f web worker`
