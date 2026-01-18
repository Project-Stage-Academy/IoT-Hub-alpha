# Developer Onboarding — Monolithic MVP

This document provides a step-by-step guide for onboarding new developers and interns to the IoT Hub monolithic MVP project.
It allows a contributor with no prior knowledge of the project to clone the repository, start the local development environment, and access the Django Admin UI.

## Prerequisites

Make sure the following tools are installed:
- Git
- Docker
- Docker Compose v2

Verify installation:
```bash
git --version
docker --version
docker compose version
```
## 1) Clone the repository

Clone the repository and navigate to the project directory:
```bash
git clone https://github.com/Project-Stage-Academy/IoT-Hub-alpha.git
cd IoT-Hub-alpha
```
Switch to the required branch:
```bash
`git checkout task-8-project-skeleton`
```
![example-clone](images/onboarding-01-clone.png)

## 2) Create environment file
In the folder where the `.env.example` is located create `.env`
* Linux / macOS / Git Bash
```bash
cp .env.example .env
```
* Windows
```bash
copy .env.example .env
```
The .env file is used only for local development and must not be committed.
At minimum, ensure the following variables exist:
* DB_NAME
* DB_USER
* DB_PASSWORD
