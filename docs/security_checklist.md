# Security Checklist

## Secrets Handling

### Local Development

For local development, secrets are stored in a `.env` file in the root of the project. This file is ignored by Git and should never be committed. A `.env.example` file is provided to show the required environment variables.

To set up your local environment:

1.  Copy the `.env.example` file to `.env`: `cp .env.example .env`
2.  Fill in the required secret values in the `.env` file.

**Never commit the `.env` file to version control.**

### CI/CD

In CI/CD environments, secrets should be stored as encrypted secrets or environment variables within the CI/CD platform's secret management system.

- **GitHub Actions**: Use [Encrypted Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets) to store secrets. These secrets are made available as environment variables in the workflow. See the `.github/workflows/ci.yml` file for an example of how secrets are used.

### Prohibited Values

The following values must never be committed to the repository in any form:

-   `SECRET_KEY`
-   `DATABASE_URL` or its components (password, etc.)
-   `CELERY_BROKER_URL`
-   API keys
-   Other credentials
