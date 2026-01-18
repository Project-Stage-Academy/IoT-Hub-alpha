# Troubleshooting Guide — Monolithic MVP

This document describes common issues that may occur when running the IoT Hub monolithic MVP and provides step-by-step guidance to diagnose and resolve them.

The guide is intended for interns and contributors operating the project in local or staging environments.

---

## General diagnostics checklist

Before troubleshooting a specific problem, always start with these basic checks:

```bash
docker compose ps
docker compose logs backend --tail=200
docker compose logs db --tail=200
```

These commands help verify:
- which containers are running,
- whether any service is restarting or unhealthy,
- recent errors from the application or database.

---

## 1) Database connection errors

### Symptoms
- Backend fails to start with `psycopg2.OperationalError`
- Errors such as:
  - `could not connect to server`
  - `connection refused`
  - `database does not exist`
- Automatic migrations fail on startup

### Diagnostics
```bash
docker compose ps
docker compose logs db --tail=200
docker compose logs backend --tail=200
```

### Common causes
- `.env` file is missing or not loaded
- Incorrect `DB_NAME`, `DB_USER`, or `DB_PASSWORD`
- PostgreSQL container is not healthy yet
- Corrupted local database volume

### Resolution
```bash
docker compose down -v
docker compose up -d --build
```

---

## 2) Celery worker failures (if enabled)

### Symptoms
- Background tasks are not executed
- Celery worker container exits or keeps restarting
- Errors related to Redis or RabbitMQ connection

### Diagnostics
```bash
docker compose logs worker --tail=200
docker compose logs broker --tail=200
```

### Resolution
```bash
docker compose restart broker worker
```

---

## 3) Healthcheck failures

### Symptoms
- Containers repeatedly restart
- Services appear as `unhealthy`
- Dependent services fail to start

### Diagnostics
```bash
docker inspect --format='{{.State.Health.Status}}' iot_hub_db
docker compose logs db --tail=200
```

### Resolution
```bash
docker compose down
docker compose up -d
```

---

## 4) Application is running but not reachable

### Symptoms
- Containers are running
- Browser cannot open `http://localhost:8000/`

### Diagnostics
```bash
docker compose logs backend --tail=200
docker compose ps
```

### Resolution
```bash
docker compose restart backend
```

---

## 5) Capturing logs for debugging

### Export logs
```bash
docker compose logs backend > backend.log
docker compose logs db > db.log
```

Attach these logs when reporting issues.

---

## Summary

Most issues during onboarding and development are caused by:
- missing or incorrect environment variables,
- database startup timing,
- stale Docker volumes,
- service dependency ordering.

    

