# Private APT Repository

This project provides a **private APT repository** based on **nginx**, protected with **HTTP Basic Authentication**, fully **dockerized** and suitable for local development or internal use.

---

## 📌 Purpose

The goal of this setup is to:

* Host a private APT repository
* Protect it with authentication
* Run everything reproducibly via Docker
* Allow future extension with real Debian/Ubuntu packages

This repository is intended as a **foundation**, not a fully populated package mirror.

---

## 🧱 Architecture

* **nginx** — serves the repository over HTTP
* **Basic Auth** — restricts access to authorized users
* **Docker Compose** — orchestrates the service
* **Volume-mounted repo directory** — persistent storage

```
Client (apt / curl)
   ↓ (Basic Auth)
nginx (Docker)
   ↓
/repo/apt
```

---

## 📁 Directory Structure

```
repo/
├── apt/        # APT repository root (served via nginx)
├── auth/       # htpasswd credentials
├── conf/       # nginx configuration
└── Dockerfile
```

---

## 🔐 Authentication

The repository is protected using **HTTP Basic Auth**.

Example credentials (development only):

```
username: dev
password: devpass123
```

> ⚠️ Do **NOT** use these credentials in production.

---

## 🚀 Usage

### 1️⃣ Start the repository

```bash
docker compose up -d
```

Verify container status:

```bash
docker compose ps
```

---

### 2️⃣ Test access with curl

Without auth (should fail):

```bash
curl http://localhost:8080/apt/
```

With auth (should succeed):

```bash
curl -u dev:devpass123 http://localhost:8080/apt/
```

Expected response:

```
Index of /apt/
```

---

## 📦 Adding Files / Packages

At this stage, the repository may be empty — this is expected.

To verify file visibility:

```bash
touch apt/README.txt
```

Restart the container:

```bash
docker compose restart
```

Re-check:

```bash
curl -u dev:devpass123 http://localhost:8080/apt/
```

---

## 🧪 Validation Checklist

* [x] nginx running in Docker
* [x] `/apt` endpoint exposed
* [x] Basic authentication enforced
* [x] Accessible via curl
* [x] Reproducible via Docker Compose
