# Dev Environment

This document covers common Docker troubleshooting and health inspection.

## Troubleshooting

- Rebuild without cache: `docker compose build --no-cache`
- Fix file permission issues: `docker compose exec web sh -c "ls -la /app && id"`
- Clear volumes (removes DB data): `docker compose down --volumes`
- Remove unused images/networks: `docker system prune -f`
- Recreate containers: `docker compose up -d --build`

## Health checks

- View status: `docker compose ps`
- Inspect a container: `docker inspect --format '{{json .State}}' <container>`

## Service checks

- Web app responds: `curl http://localhost:8000/`
- Postgres reachable: `docker compose exec db pg_isready -U $POSTGRES_USER`
- Redis reachable: `docker compose exec redis redis-cli -n 0 ping`
- Celery worker responsive: `docker compose exec worker celery -A config inspect ping`

## Validation

Validated locally by running:

- `docker build -t iot-hub-web -f backend/Dockerfile backend`
- `docker compose up -d --build`
