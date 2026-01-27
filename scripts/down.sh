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
REMOVE_VOLUMES=0
REMOVE_ORPHANS=0

while [ $# -gt 0 ]; do
  case "$1" in
    --no-override)
      NO_OVERRIDE=1
      ;;
    --volumes|-v)
      REMOVE_VOLUMES=1
      ;;
    --remove-orphans)
      REMOVE_ORPHANS=1
      ;;
    -h|--help)
      echo "Usage: scripts/down.sh [--no-override] [--volumes] [--remove-orphans]"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
  shift
done

COMPOSE_ARGS="-f docker-compose.yml"
if [ "$NO_OVERRIDE" -eq 0 ] && [ -f docker-compose.override.yml ]; then
  COMPOSE_ARGS="$COMPOSE_ARGS -f docker-compose.override.yml"
fi

DOWN_ARGS="down"
if [ "$REMOVE_VOLUMES" -eq 1 ]; then
  DOWN_ARGS="$DOWN_ARGS --volumes"
fi
if [ "$REMOVE_ORPHANS" -eq 1 ]; then
  DOWN_ARGS="$DOWN_ARGS --remove-orphans"
fi

docker compose $COMPOSE_ARGS $DOWN_ARGS
