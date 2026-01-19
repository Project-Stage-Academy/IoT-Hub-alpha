# CI pipeline

GitHub Actions to run  CI pipeline on pushes and pull requests.

## Jobs and ordering

1. Lint
   - Runs `black --check` and `flake8` on the `backend` package.
   - Validates `docs/api.yaml` using Spectral.
   - Uploads `docs/api.yaml` as a workflow artifact.
2. Tests (depends on Lint)
   - Runs `pytest` with coverage output in `coverage.xml`.
   - Uploads `coverage.xml` and  as a workflow artifact.
3. Build (depends on Tests)
   - Builds the Django Docker image from `backend/Dockerfile` as a smoke build (no push).

The workflow uses a minimal Python matrix (3.10 and 3.11). Dependency caching is enabled via the
`actions/setup-python` pip cache to speed up repeat runs.

## Run locally

From the repository root:

```bash
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
pip install -r backend/requirements-dev.txt

black --check backend
flake8 backend
npx --yes @stoplight/spectral-cli lint docs/api_test.yaml

cd backend
pytest -q --cov=. --cov-report=xml:../coverage.xml
cd -

docker build -f backend/Dockerfile -t iot-hub-backend:ci backend
```
