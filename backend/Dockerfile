FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VENV_PATH=/opt/venv

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN python -m venv $VENV_PATH \
    && $VENV_PATH/bin/pip install --no-cache-dir --upgrade pip \
    && $VENV_PATH/bin/pip install --no-cache-dir -r requirements.txt

COPY . .

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VENV_PATH=/opt/venv

ARG BUILD_VERSION=dev
ARG BUILD_REVISION=unknown
ARG BUILD_CREATED=unknown
LABEL org.opencontainers.image.title="IoT Hub Alpha" \
      org.opencontainers.image.version=$BUILD_VERSION \
      org.opencontainers.image.revision=$BUILD_REVISION \
      org.opencontainers.image.created=$BUILD_CREATED \
      org.opencontainers.image.source="repo"

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder $VENV_PATH $VENV_PATH
ENV PATH="$VENV_PATH/bin:$PATH"

COPY --from=builder /app /app

RUN chmod +x /app/scripts/entrypoint.sh \
    && adduser --disabled-password --gecos "" django \
    && chown -R django:django /app
USER django

# Development only - in production this should be replaced with gunicorn.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
