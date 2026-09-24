#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/e-ai}"
CURRENT="$APP_ROOT/current"
job="${1:?usage: run-job.sh <news|papers|digest|watchdog>}"

case "$job" in
  news|papers|digest|watchdog)
    ;;
  *)
    echo "unsupported job: $job" >&2
    exit 2
    ;;
esac

release_dir="$(readlink -f "$CURRENT")"
if [[ -z "$release_dir" || ! -d "$release_dir/powerai-hot" ]]; then
  echo "current release is not valid: $CURRENT" >&2
  exit 1
fi

export IMAGE_TAG="$(basename "$release_dir")"
export BACKEND_ENV_FILE="${BACKEND_ENV_FILE:-$APP_ROOT/secrets/backend.env}"
export POSTGRES_PASSWORD_FILE="${POSTGRES_PASSWORD_FILE:-$APP_ROOT/secrets/postgres_password.txt}"
export COMPOSE_PROJECT_NAME=e-ai
if [[ ! -f "$BACKEND_ENV_FILE" ]]; then
  echo "missing backend env file: $BACKEND_ENV_FILE" >&2
  exit 1
fi

compose() {
  docker compose --env-file "$BACKEND_ENV_FILE" "$@"
}

cd "$release_dir/powerai-hot"
compose run --rm --no-deps jobs python -m "jobs.$job"
