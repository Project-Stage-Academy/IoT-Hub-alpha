# Documentation Validation Note
Date: 2026-01-25

Steps:
- `git clone <repo>`
- `cp .env.example .env`
- `scripts/up.sh`
- `docker compose run --rm migrate`
- Verified:
  - http://localhost:8000/ responds
  - http://localhost:8000/admin/ responds
  - `docker compose ps` shows `db` and `web` healthy
- Override (dev):
  - `docker compose exec -T web printenv DJANGO_SETTINGS_MODULE`
  - `docker compose exec -T web sh -c 'ls -la /app | head'` (PowerShell/WSL)
  - `MSYS2_ARG_CONV_EXCL='*' docker compose exec -T web sh -c 'ls -la /app | head'` (Git Bash)
  - `docker compose exec -T web python manage.py collectstatic --noinput`
- Scripts:
  - `scripts/logs.sh -f -s web`
  - `scripts/reset-db.sh`
  - `scripts/down.sh`
- DIND demo:
  - `docker build -t iot-hub-dind-demo scripts/dind-demo`
  - `docker run --privileged --name iot-hub-dind-demo -d iot-hub-dind-demo`
  - `docker exec -it iot-hub-dind-demo docker ps`

Notes:
- On Windows, ensure LF line endings for `backend/scripts/entrypoint.sh` to avoid `/bin/sh^M`.
