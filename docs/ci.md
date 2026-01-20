# CI pipeline

GitHub Actions to run  CI pipeline on pushes and pull requests.

## Jobs and ordering

1. Lint
   - Runs `black --check` and `flake8` on the backend package 
     (`.flake8` in the project root defines the settings used for these checks).
   - Validates `docs/api.yaml` using Spectral.
     (`.spectral.yml` in the project root defines the rules on Spectral warnings.)
      Fails the job and logs issues if Spectral finds problems in `api.yaml`
   - Uploads `docs/api.yaml` as a workflow artifact.
2. Tests (depends on Lint)
   - Runs `pytest` with coverage output in `coverage.xml` and `coverage.html` .
   - Uploads `coverage.xml` and `coverage.html`  as a workflow artifact.
3. Build (depends on Tests)
   - Builds the Django Docker image from `backend/Dockerfile` as a smoke build (no push).
4. Updates the status badge in README.md to show passing or failing based on the workflow result.


The workflow uses a Python matrix for future extensibility, 
but currently only runs 3.13 because it is the latest.

Dependency caching is enabled via the
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

## Future Extensions

### Debian Package Building
To add . deb packaging: 
1. Add a new job `package:` after the `build:` job with `needs: build`
2. Install `dpkg-dev`, `debhelper`, and other packaging tools
3. Run package build commands and upload . deb as artifact

### Required Secrets for Future Jobs
Configure the following secrets in GitHub Settings → Secrets and variables → Actions: 

- `DOCKER_REGISTRY_USER`: Docker Hub username for pushing images
- `DOCKER_REGISTRY_TOKEN`: Docker Hub access token or password
- `APT_REPO_DEPLOY_KEY`: SSH private key for deploying . deb packages to apt repository
- `APT_REPO_URL`: URL of the apt repository server

Example usage in workflow:
```
- name: Login to Docker Hub
   uses: docker/login-action@v3
   with:
      username: ${{ secrets.DOCKER_REGISTRY_USER }}
      password: ${{ secrets.DOCKER_REGISTRY_TOKEN }}
```
