#!/usr/bin/env sh
set -e

export DOCKER_TLS_CERTDIR=""

if ! command -v dockerd >/dev/null 2>&1; then
  echo "dockerd is required."
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose is required."
  exit 1
fi

mkdir -p /var/log
DOCKERD_LOG="/var/log/dockerd.log"
dockerd-entrypoint.sh --host=unix:///var/run/docker.sock > "$DOCKERD_LOG" 2>&1 &

i=1
max_attempts=120
until [ -S /var/run/docker.sock ] && docker info >/dev/null 2>&1; do
  if [ "$i" -ge "$max_attempts" ]; then
    echo "dockerd did not become ready in time."
    tail -n 200 "$DOCKERD_LOG" || true
    exit 1
  fi
  i=$((i + 1))
  sleep 1
done

docker compose -f /demo/demo-compose.yml up -d
docker compose -f /demo/demo-compose.yml ps

echo "DIND demo stack is running. This container will stay alive for the demo."
tail -f /var/log/dockerd.log
