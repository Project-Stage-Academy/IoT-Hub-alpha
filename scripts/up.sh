#!/usr/bin/env sh
set -e

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose is required."
  exit 1
fi

NO_OVERRIDE=0
PROFILES=""
SERVICES=""

while [ $# -gt 0 ]; do
  case "$1" in
    --no-override)
      NO_OVERRIDE=1
      ;;
    --profile)
      shift
      if [ -z "$1" ]; then
        echo "Missing value for --profile."
        exit 1
      fi
      PROFILES="$PROFILES --profile $1"
      ;;
    -h|--help)
      echo "Usage: scripts/up.sh [--no-override] [--profile NAME] [services...]"
      exit 0
      ;;
    *)
      SERVICES="$SERVICES $1"
      ;;
  esac
  shift
done

COMPOSE_ARGS="-f docker-compose.yml"
if [ "$NO_OVERRIDE" -eq 0 ] && [ -f docker-compose.override.yml ]; then
  COMPOSE_ARGS="$COMPOSE_ARGS -f docker-compose.override.yml"
fi

docker compose $COMPOSE_ARGS $PROFILES up -d --build $SERVICES
