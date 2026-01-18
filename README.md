# IoT-Catalog-Hub


## Short description

IoT Catalog Hub is a microservice catalog of IoT devices that provides telemetry ingestion, trigger rules, and message routing. The platform enables device registration, real-time telemetry collection and storage, definition of business rules that react to events, and routing of messages to consumers such as alerts, automation logic, or archival storage.

https://drive.google.com/file/d/1LE-NLDsWG7-AySHRq68_kEkrvKi0QT9n/view?usp=sharing

## Tech stack

Django as API Gateway and admin UI. Python agents for telemetry ingestion via MQTT or HTTP. Java service for rule evaluation. Scala service for streaming processing and aggregation. PostgreSQL or TimescaleDB for metadata and time-series storage. Kafka or RabbitMQ as the messaging broker. Docker and Docker Compose for local development. CI/CD with GitHub Actions or GitLab CI. Observability via Prometheus and Grafana.

## Quick start

### 1. Clone the Repository

```bash
git clone <repo-url>
cd iot-catalog-hub
```

### 2. Environment Setup

The application relies on environment variables defined in a `.env` file. Create your local version from the provided template:

```bash
cd backend
cp .env.example .env
```


> **Note:** The default values in `.env.example` are pre-configured to work with the Docker Compose setup immediately.

---

### 3. Launch with Docker Compose

Build the images and start the services. The setup includes a healthcheck mechanism to ensure the database is ready before the backend starts:

```bash
docker compose up -d --build
```


### 4. Initialize the Database

Run migrations and create an administrative account to access the dashboard:

```bash
# Apply database migrations
docker compose exec backend python manage.py migrate

# Create a superuser
docker compose exec backend python manage.py createsuperuser
```


## Access Points

| Service      | URL                        |
|-------------|----------------------------|
| Web API      | http://localhost:8000/     |
| Admin Panel  | http://localhost:8000/admin/ |

---

## Project workflow

Develop the MVP as a monolith to validate core flows. Then split into microservices for Auth & API Gateway, Device Registry, Telemetry Ingestor, Rule Engine, Stream Aggregator, Worker and Notification Service. Package services as .deb for controlled deployment, build Docker images that install those packages, and automate the pipeline in CI to push artifacts to an internal APT repository and container registry.

## Deliverables

A working MVP and microservice stack in staging. CI pipelines that build .deb packages and Docker images. An internal APT repository with packaged services. Orchestration demo using a docker:dind container. Device simulation scripts and end-to-end integration tests. Documentation including architecture diagrams and OpenAPI specs.

## Contributing

Follow the repository guidelines for branching, testing and CI. Open a pull request for feature work and include tests and documentation for changes.
