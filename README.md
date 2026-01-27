# IoT Catalog Hub

[![CI](https://github.com/Project-Stage-Academy/IoT-Hub-alpha/actions/workflows/ci.yml/badge.svg?branch=task-10-CI-pipeline)](https://github.com/Project-Stage-Academy/IoT-Hub-alpha/actions/workflows/ci.yml)

IoT Catalog Hub is a modular platform designed for IoT device management, telemetry ingestion, and event-driven automation. This repository contains the MVP monolith built with Django and PostgreSQL, containerized for a seamless developer experience.

---

## 🛠 Tech Stack

- **Backend:** Python 3.13, Django 5.2.10  
- **Database:** PostgreSQL 15  
- **Orchestration:** Docker, Docker Compose  
- **Documentation:** DBML for schema design  

---

## 🚀 Quick Start Guide

Follow these instructions to get the project up and running on your local machine.

### 1. Prerequisites

Ensure you have the following installed:

- Docker Desktop (includes Docker Compose)  
- Git  

### 2. Clone the Repository

```bash
git clone <your-repository-url>
cd iot-catalog-hub
```
## Api style guide

[Api style guide](docs/readme-api.md)

### 3. Environment Setup

The application relies on environment variables defined in a `.env` file. Create your local version from the provided template:

```bash
cp .env.example .env
```


> **Note:** The default values in `.env.example` are pre-configured to work with the Docker Compose setup immediately.

---

### 4. Launch with Docker Compose

Build the images and start the services. The setup includes a healthcheck on `http://localhost:8000/health/` to verify the web service is responsive:

```bash
docker compose down --remove-orphans
docker compose up -d --build
```


### 5. Initialize the Database

For detailed database setup, schema description, and operations guide, please refer to the [Database Documentation](docs/readme-database.md).

Run migrations to set up the database:

```bash
# Apply database migrations
docker compose run --rm migrate
```

To initialize roles and users, see the [Admin Documentation](docs/admin.md).

## Docker Skeleton (Current)

The compose file includes placeholders for `redis`, `worker`, `prometheus`, and `grafana`. These services are intentionally minimal and marked with TODOs for teammates to complete.

Basic local build (Dockerfile only):

```bash
docker build -t iot-hub-web -f backend/Dockerfile backend
```

## 🔗 Access Points

| Service      | URL                        |
|-------------|----------------------------|
| Web API      | http://localhost:8000/     |
| Admin Panel  | http://localhost:8000/admin/ |
| Health Check | http://localhost:8000/health/ |

---

## 🛑 Stopping the Application

### To stop all services and keep the data:

```bash
docker compose stop
```
## Api style guide

[Api style guide](docs/readme-api.md)

### 3. Environment Setup

The application relies on environment variables defined in a `.env` file. Create your local version from the provided template:

```bash
cp .env.example .env
```


> **Note:** The default values in `.env.example` are pre-configured to work with the Docker Compose setup immediately.

---

### 4. Launch with Docker Compose

Build the images and start the services. The setup includes a healthcheck on `http://localhost:8000/health/` to verify the web service is responsive:

```bash
scripts/up.sh
```

> **Note:** The dev override (`docker-compose.override.yml`) is applied automatically.  
> **Windows:** Run the scripts via WSL or Git Bash (PowerShell/CMD won't run `sh` scripts).  
> **Git Bash:** If a command includes a Linux path like `/app`, prefix it with `MSYS2_ARG_CONV_EXCL='*'` to avoid path conversion.

### Entrypoint scripts (line endings)

Docker runs `backend/scripts/entrypoint.sh` inside Linux containers. Docker will only execute it if:
- The file exists at `backend/scripts/entrypoint.sh` (bind-mounted to `/app/scripts/entrypoint.sh`).
- The file uses LF line endings (not CRLF).
- The executable bit is set in git.

If you see errors like `/bin/sh^M: bad interpreter` or `no such file or directory`, convert the file to LF in your editor and commit it. Configure git to keep LF for shell scripts:

```bash
git config core.autocrlf false   # Windows
git config core.autocrlf input   # macOS/Linux
git update-index --chmod=+x backend/scripts/entrypoint.sh
```

### Scripts quick reference

Run these from the repo root. On Windows use WSL or Git Bash (PowerShell/CMD will not run `sh` scripts).

- Start stack (builds if needed): `scripts/up.sh`
- Start without dev override: `scripts/up.sh --no-override`
- Start only specific services: `scripts/up.sh web db`
- Start optional profiles: `scripts/up.sh --profile monitoring`
- Stop containers: `scripts/down.sh`
- Stop and remove volumes: `scripts/down.sh --volumes`
- Tail logs: `scripts/logs.sh -f -s web`
- Reset database (drops and recreates): `scripts/reset-db.sh`

`scripts/init-db.sh` is a Postgres init hook used automatically on first boot when the DB volume is empty.
For full options and platform notes, see `docs/dev-environment.md`.

### 4a. DIND Demo

This demo runs Docker-in-Docker. It requires `--privileged` and is not for production use.

```bash
docker build -t iot-hub-dind-demo scripts/dind-demo
docker run --privileged --name iot-hub-dind-demo -d iot-hub-dind-demo
docker exec -it iot-hub-dind-demo docker ps
```

To stop and remove the demo container:

```bash
docker rm -f iot-hub-dind-demo
```

### 5. Initialize the Database

For detailed database setup, schema description, and operations guide, please refer to the [Database Documentation](docs/readme-database.md).

Run migrations and create an administrative account to access the dashboard:

```bash
# Apply database migrations
docker compose run --rm migrate

# Create a superuser
docker compose exec web python manage.py createsuperuser
```

## Docker Skeleton (Current)

The compose file includes placeholders for `redis`, `worker`, `prometheus`, and `grafana`. These services are intentionally minimal and marked with TODOs for teammates to complete.

Basic local build (Dockerfile only):

```bash
docker build -t iot-hub-web -f backend/Dockerfile backend
```

## 🔗 Access Points

| Service      | URL                        |
|-------------|----------------------------|
| Web API      | http://localhost:8000/     |
| Admin Panel  | http://localhost:8000/admin/ |
| Health Check | http://localhost:8000/health/ |

---

## 🛑 Stopping the Application

### To stop all services and keep the data:

```bash
scripts/down.sh
```

### To shut down and remove containers:

```bash
scripts/down.sh --volumes
```

## 📂 Documentation & Contributing

Detailed information about the project's internal structure and guidelines can be found here:

- **Database Schema:** Detailed entity-relationship descriptions and field specifications  
- **Team Roles:** Overview of internship roles and responsibilities  
- **Contributing Guide:** Rules for branching, commits, and Pull Requests  

---

## 🛠 Project Workflow

The current stage is a monolith MVP. Future development includes:

- Splitting into microservices (Telemetry Ingestor, Rule Engine, etc.)  
- Implementing CI/CD pipelines via GitHub Actions
