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
FOLLOW=0
TAIL="200"
SERVICES=""

while [ $# -gt 0 ]; do
  case "$1" in
    --no-override)
      NO_OVERRIDE=1
      ;;
    -f|--follow)
      FOLLOW=1
      ;;
    -n|--tail)
      shift
      if [ -z "$1" ]; then
        echo "Missing value for --tail."
        exit 1
      fi
      TAIL="$1"
      ;;
    -s|--service)
      shift
      if [ -z "$1" ]; then
        echo "Missing value for --service."
        exit 1
      fi
      SERVICES="$SERVICES $1"
      ;;
    -h|--help)
      echo "Usage: scripts/logs.sh [--no-override] [-f] [-n N] [-s SERVICE]..."
      exit 0
      ;;
    *)
      SERVICES="$SERVICES $1"
      ;;
  esac
  shift
done

COMPOSE_ARGS=""
if [ -f docker-compose.yml ]; then
  COMPOSE_ARGS="-f docker-compose.yml"
fi

if [ "$NO_OVERRIDE" -eq 0 ] && [ -f docker-compose.override.yml ]; then
  if [ -n "$COMPOSE_ARGS" ]; then
    COMPOSE_ARGS="$COMPOSE_ARGS -f docker-compose.override.yml"
  else
    COMPOSE_ARGS="-f docker-compose.override.yml"
  fi
fi

if [ -z "$COMPOSE_ARGS" ]; then
  echo "No compose files found (docker-compose.yml or docker-compose.override.yml)."
  exit 1
fi

LOG_ARGS="logs --timestamps --tail $TAIL"
if [ "$FOLLOW" -eq 1 ]; then
  LOG_ARGS="$LOG_ARGS -f"
fi

docker compose $COMPOSE_ARGS $LOG_ARGS $SERVICES
