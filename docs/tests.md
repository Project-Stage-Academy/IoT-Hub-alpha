# Test Guide

This guide describes how tests are organized, how to run them locally, and how to add new tests.

## Test Layout

- `backend/tests/models/`: unit tests for model behavior and validation
- `backend/tests/api/`: API tests using Django test client
- `backend/tests/integration/`: multi-component tests (database + domain flow)
- `backend/tests/smoke/`: fast, high-signal checks for demos
- `backend/tests/utils/`: shared helpers for tests
- `backend/tests/fixtures/`: sample JSON fixtures for tests

## Run Tests Locally

From a dev container or Docker Compose:

```bash
docker compose run web pytest -q --maxfail=1 --cov=backend --cov-report=xml
```

If you are running directly on the host:

```bash
cd backend
pytest -q --maxfail=1 --cov=. --cov-report=xml:coverage.xml
```

## Smoke Tests

Smoke tests are small, fast checks meant to run before demos.

```bash
pytest backend/tests/smoke
```

## Writing New Tests

### Patterns

- Prefer factories or fixtures over inline object setup.
- Keep unit tests pure (no network calls, no external services).
- For integration tests, use the test DB and deterministic data.
- Use explicit assertions for error cases (status codes, validation errors).

### Naming Conventions

- Unit tests: `backend/tests/models/test_<area>.py`
- Integration tests: `backend/tests/integration/test_<flow>.py`
- Smoke tests: `backend/tests/smoke/test_<critical_flow>.py`
- API tests: `backend/tests/api/test_<resource>_api.py`

### Quality Checklist

1. Fixtures are reusable (no duplication across tests).
2. No external network calls in unit tests.
3. Factories are used for model setup.
4. Error cases are asserted explicitly.
5. Tests are deterministic (no random timeouts or sleeps).
