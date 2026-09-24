#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/e-ai}"
RELEASES_DIR="$APP_ROOT/releases"
CURRENT="$APP_ROOT/current"
OPERATIONS_LOCK="${OPERATIONS_LOCK:-$APP_ROOT/releases/.operations.lock}"
TARGET="${1:-}"
export COMPOSE_PROJECT_NAME=e-ai
export BACKEND_ENV_FILE="${BACKEND_ENV_FILE:-$APP_ROOT/secrets/backend.env}"
export POSTGRES_PASSWORD_FILE="${POSTGRES_PASSWORD_FILE:-$APP_ROOT/secrets/postgres_password.txt}"

compose() {
  docker compose --env-file "$BACKEND_ENV_FILE" "$@"
}

acquire_operations_lock() {
  if [[ ! -d "$RELEASES_DIR" ]]; then
    echo "releases directory not found: $RELEASES_DIR" >&2
    exit 1
  fi
  exec 9>"$OPERATIONS_LOCK"
  if ! flock -n 9; then
    echo "operations lock busy: $OPERATIONS_LOCK" >&2
    exit 1
  fi
}

wait_for_health() {
  for _ in {1..30}; do
    if curl -fsS http://127.0.0.1:8080/health >/dev/null; then
      return 0
    fi
    sleep 2
  done
  return 1
}

restore_previous() {
  echo "restoring previous release: $previous" >&2
  ln -sfn "$previous" "$CURRENT"
  cd "$previous/powerai-hot"
  IMAGE_TAG="$(basename "$previous")"
  export IMAGE_TAG

  if ! compose build; then
    echo "failed to rebuild previous release during rollback recovery" >&2
    return 1
  fi
  if ! compose up -d; then
    echo "failed to restart previous release during rollback recovery" >&2
    return 1
  fi
  if ! wait_for_health; then
    echo "previous release health gate failed during rollback recovery" >&2
    return 1
  fi

  echo "previous release restored after rollback target failure" >&2
  return 0
}

cleanup_failed_target_without_previous() {
  echo "no previous release to restore; stopping failed rollback target" >&2
  cd "$TARGET/powerai-hot"
  IMAGE_TAG="$(basename "$TARGET")"
  export IMAGE_TAG

  if ! compose down; then
    echo "failed to stop failed rollback target" >&2
  fi
  if [[ -L "$CURRENT" ]] && [[ "$(readlink -f "$CURRENT" 2>/dev/null || true)" == "$TARGET" ]]; then
    rm -f "$CURRENT"
  fi
}

fail_and_restore() {
  echo "$1" >&2
  if [[ -n "$previous" ]]; then
    if ! restore_previous; then
      echo "rollback target failed and previous release restoration failed" >&2
    fi
  else
    cleanup_failed_target_without_previous
  fi
  exit 1
}

acquire_operations_lock
releases_real="$(readlink -f "$RELEASES_DIR")"

previous=""
if [[ -e "$CURRENT" || -L "$CURRENT" ]]; then
  if ! previous="$(readlink -f "$CURRENT")"; then
    echo "current release cannot be resolved: $CURRENT" >&2
    exit 1
  fi
  if [[ ! -d "$previous/powerai-hot" ]]; then
    echo "current release is not an E-AI release: $previous" >&2
    exit 1
  fi
  if [[ "$(dirname "$previous")" != "$releases_real" ]]; then
    echo "current release is not under releases directory: $previous" >&2
    exit 1
  fi
fi

if [[ -z "$TARGET" ]]; then
  if [[ -z "$previous" ]]; then
    echo "current release not found; cannot choose default rollback target" >&2
    exit 1
  fi
  current_name="$(basename "$previous")"
  predecessor=""
  found_current=0
  while IFS= read -r release_name; do
    if [[ "$release_name" == "$current_name" ]]; then
      found_current=1
      break
    fi
    predecessor="$release_name"
  done < <(find "$RELEASES_DIR" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | LC_ALL=C sort)

  if [[ "$found_current" -ne 1 ]]; then
    echo "current release is not listed in releases directory: $previous" >&2
    exit 1
  fi
  if [[ -z "$predecessor" ]]; then
    echo "no predecessor release before current: $current_name" >&2
    exit 1
  fi
  TARGET="$RELEASES_DIR/$predecessor"
fi
if [[ -z "$TARGET" || ! -d "$TARGET" ]]; then
  echo "rollback target not found" >&2
  exit 1
fi
if [[ ! -d "$TARGET/powerai-hot" ]]; then
  echo "rollback target is not an E-AI release: $TARGET" >&2
  exit 1
fi
TARGET="$(readlink -f "$TARGET")"
if [[ "$(dirname "$TARGET")" != "$releases_real" ]]; then
  echo "rollback target is not under releases directory: $TARGET" >&2
  exit 1
fi
if [[ -n "$previous" && "$TARGET" == "$previous" ]]; then
  echo "rollback target is already current: $TARGET" >&2
  exit 1
fi

if [[ ! -f "$BACKEND_ENV_FILE" ]]; then
  echo "missing backend env file: $BACKEND_ENV_FILE" >&2
  exit 1
fi
if [[ ! -f "$POSTGRES_PASSWORD_FILE" ]]; then
  echo "missing postgres password file: $POSTGRES_PASSWORD_FILE" >&2
  exit 1
fi

cd "$TARGET/powerai-hot"
IMAGE_TAG="$(basename "$TARGET")"
export IMAGE_TAG
if ! compose build; then
  echo "rollback target build failed; current release unchanged" >&2
  exit 1
fi

ln -sfn "$TARGET" "$CURRENT"
if ! compose up -d; then
  fail_and_restore "rollback target compose up failed"
fi
if ! wait_for_health; then
  fail_and_restore "rollback health gate failed"
fi

exit 0
