# Validation

Use this checklist to confirm the local Docker stack is healthy.
Prereq: stack is running (see `docs/dev-environment.md`).

## Checklist

- `docker compose ps` shows `db` and `web` healthy
- `curl http://localhost:8000/health/`
- `docker compose run --rm migrate` completes
- `scripts/logs.sh -f -s web` shows no obvious errors

## Last validated
  
- Cold start: `scripts/up.sh`
- Rebuild: `docker compose build --no-cache`
- Volume persistence: `scripts/down.sh` then `scripts/up.sh` and verify DB data remains

## Optional

- DIND demo: `scripts/dind-demo/README.md`
