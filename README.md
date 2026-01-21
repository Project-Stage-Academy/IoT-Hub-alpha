# IoT Catalog Hub

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
docker compose stop
```

### To shut down and remove containers:

```bash
docker compose down
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
