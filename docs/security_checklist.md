# Security Checklist

This document provides a checklist of security-related tasks for developers.

## Pre-Demo Security Checklist

This checklist should be completed by a developer before every demo to ensure the application is secure. It should take less than 15 minutes to complete.

| # | Check                                   | Instructions                                                                                                                                                             | Status (Done/NA) |
| - | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------- |
| 1 | **Validate TLS** | Open https://localhost in browser OR run: curl -vk https://localhost | |
| 2 | **Check for exposed secrets**           | Review your local `.env` file and ensure that no secrets are hard-coded in the source code. Use `git status` to ensure no secret files are accidentally staged for commit.    |                  |
| 3 | **Validate token issuance** | Verify that a valid JWT access token is returned and expiration (`exp`) claim is present. | |
| 4 | **Verify repository access controls**   | Go to the repository settings on GitHub and ensure that only authorized team members have access.                                                                        |                  |
| 5 | **Verify rate limiting** | Send >N requests (e.g. >20 within 1 minute) to ingestion endpoint | |

---

## Rotating a Compromised Secret (Local)

If you suspect a secret in your local `.env` file has been compromised, follow these steps immediately:

1.  **Generate a new secret:** Use a password generator or a command-line tool like `openssl` to generate a new random secret.

```bash
openssl rand -hex 32
```

2.  **Update your `.env` file:** Replace the old secret with the new one in your local `.env` file.

3.  **Restart the application:** Stop and restart the Django application to ensure it picks up the new secret.

```bash
docker-compose down

docker-compose up
```

## Revoking a Dev JWT Token

- Reduce token lifetime in settings
- Rotate JWT signing key
- Restart services


## Minimal Incident Response

If you identify a security incident, follow these steps:


1.  **Contain:** Take immediate steps to prevent further damage. This may involve shutting down a service, revoking a token, or disconnecting a machine from the network.

2.  **Communicate:** Notify the project lead or a senior developer immediately. Provide a clear and concise summary of the incident.

3.  **Investigate:** Work with the team to understand the root cause and the extent of the damage.

4.  **Resolve:** Apply the necessary fixes to address the vulnerability and restore the system to a secure state.

## Scope Note

This project uses a minimal TLS setup intended for local development only.
Production-grade TLS termination (e.g. nginx + gunicorn/uvicorn workers)
is intentionally out of scope for the MVP foundation.
