#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/e-ai}"
RELEASES_DIR="$APP_ROOT/releases"
CURRENT="$APP_ROOT/current"
OPERATIONS_LOCK="${OPERATIONS_LOCK:-$APP_ROOT/releases/.operations.lock}"
BACKEND_ENV_FILE="${BACKEND_ENV_FILE:-$APP_ROOT/secrets/backend.env}"
POSTGRES_PASSWORD_FILE="${POSTGRES_PASSWORD_FILE:-$APP_ROOT/secrets/postgres_password.txt}"
RELEASE_NAME="${RELEASE_NAME:-$(date -u +%Y%m%dT%H%M%SZ)}"
SOURCE_DIR="${SOURCE_DIR:-$(pwd)}"
RELEASE_DIR="$RELEASES_DIR/$RELEASE_NAME"
MIGRATE_SQLITE_SOURCE="${MIGRATE_SQLITE_SOURCE:-}"
MIGRATION_CONTAINER_SOURCE="/migration/source.sqlite"
export COMPOSE_PROJECT_NAME=e-ai

compose() {
  docker compose --env-file "$BACKEND_ENV_FILE" "$@"
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

acquire_operations_lock() {
  exec 9>"$OPERATIONS_LOCK"
  if ! flock -n 9; then
    echo "operations lock busy: $OPERATIONS_LOCK" >&2
    exit 1
  fi
}

sha256_file() {
  local file="$1"
  local line
  line="$(sha256sum "$file")"
  printf '%s' "${line%% *}"
}

validate_previous_release() {
  local releases_real
  local previous_parent
  local previous_name

  releases_real="$(readlink -f "$RELEASES_DIR")"
  previous_parent="$(dirname "$previous")"
  previous_name="$(basename "$previous")"
  if [[ "$(readlink -f "$previous_parent")" != "$releases_real" ]]; then
    echo "current must point to a direct release under $RELEASES_DIR" >&2
    exit 1
  fi
  if [[ ! "$previous_name" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "invalid previous release name: $previous_name" >&2
    exit 1
  fi
  if [[ ! -d "$previous/powerai-hot" ]]; then
    echo "invalid previous release: $previous" >&2
    exit 1
  fi
}

backup_previous_postgres() {
  local current_now

  validate_previous_release
  current_now="$(readlink -f "$CURRENT")"
  if [[ "$current_now" != "$previous" ]]; then
    echo "current changed before predeploy backup; aborting" >&2
    exit 1
  fi
  echo "creating predeploy PostgreSQL backup for $previous before $RELEASE_NAME"
  env -u IMAGE_TAG \
    APP_ROOT="$APP_ROOT" \
    BACKEND_ENV_FILE="$BACKEND_ENV_FILE" \
    POSTGRES_PASSWORD_FILE="$POSTGRES_PASSWORD_FILE" \
    BACKUP_LABEL="before_$RELEASE_NAME" \
    "$RELEASE_DIR/powerai-hot/scripts/backup.sh"
}

backup_legacy_sqlite() {
  local final="$APP_ROOT/backups/legacy_sqlite_before_${RELEASE_NAME}.sqlite"
  local final_sha="${final}.sha256"
  local tmp=""
  local tmp_sha=""
  local cleanup_paths
  local source_hash
  local backup_hash

  if [[ -e "$final" || -e "$final_sha" ]]; then
    echo "legacy sqlite backup already exists for release: $RELEASE_NAME" >&2
    exit 1
  fi

  tmp="$(mktemp "$APP_ROOT/backups/.legacy_sqlite_before_${RELEASE_NAME}.XXXXXX.sqlite")"
  tmp_sha="$(mktemp "$APP_ROOT/backups/.legacy_sqlite_before_${RELEASE_NAME}.XXXXXX.sha256")"
  printf -v cleanup_paths '%q %q %q %q' "$tmp" "$tmp_sha" "$final" "$final_sha"
  trap "rm -f -- $cleanup_paths" EXIT

  cp -- "$MIGRATE_SQLITE_SOURCE" "$tmp"
  source_hash="$(sha256_file "$MIGRATE_SQLITE_SOURCE")"
  backup_hash="$(sha256_file "$tmp")"
  if [[ "$source_hash" != "$backup_hash" ]]; then
    echo "legacy sqlite backup checksum mismatch" >&2
    exit 1
  fi
  printf '%s  %s\n' "$backup_hash" "$(basename "$final")" > "$tmp_sha"
  chmod 0440 "$tmp"
  chmod 0440 "$tmp_sha"
  mv "$tmp" "$final"
  mv "$tmp_sha" "$final_sha"
  trap - EXIT

  echo "legacy sqlite predeploy backup written: $final"
  echo "legacy sqlite predeploy backup checksum written: $final_sha"
}

run_predeploy_data_backup() {
  if [[ -n "$previous" ]]; then
    backup_previous_postgres
    return
  fi

  if [[ -n "$MIGRATE_SQLITE_SOURCE" ]]; then
    backup_legacy_sqlite
    return
  fi

  echo "no existing database; skipping predeploy data backup"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --migrate-sqlite)
      MIGRATE_SQLITE_SOURCE="${2:?missing sqlite path}"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ ! -f "$BACKEND_ENV_FILE" ]]; then
  echo "missing backend env file: $BACKEND_ENV_FILE" >&2
  exit 1
fi
if [[ ! -f "$POSTGRES_PASSWORD_FILE" ]]; then
  echo "missing postgres password file: $POSTGRES_PASSWORD_FILE" >&2
  exit 1
fi
if [[ -n "$MIGRATE_SQLITE_SOURCE" ]]; then
  if [[ "$MIGRATE_SQLITE_SOURCE" != /* ]]; then
    echo "sqlite migration source must be an absolute host path" >&2
    exit 1
  fi
  if [[ ! -f "$MIGRATE_SQLITE_SOURCE" ]]; then
    echo "sqlite migration source must be an existing regular file" >&2
    exit 1
  fi
fi

mkdir -p "$RELEASES_DIR"
acquire_operations_lock

previous=""
if [[ -L "$CURRENT" ]]; then
  previous="$(readlink -f "$CURRENT")"
fi

if [[ -n "$MIGRATE_SQLITE_SOURCE" && ( -e "$CURRENT" || -L "$CURRENT" ) ]]; then
  echo "legacy SQLite migration is only allowed on first deploy when current does not exist" >&2
  exit 1
fi

if [[ -e "$RELEASE_DIR" ]]; then
  echo "release already exists: $RELEASE_DIR" >&2
  exit 1
fi

mkdir -p "$APP_ROOT/backups"
rsync -a \
  --exclude '.git' \
  --exclude '.hermes' \
  --exclude '.pytest_cache' \
  --exclude '__pycache__' \
  --exclude '.venv' \
  --exclude 'node_modules' \
  --exclude 'frontend/.next' \
  --exclude 'frontend/test-results' \
  --exclude '*.log' \
  --exclude '*.db' \
  --exclude '*.sqlite' \
  --exclude '.env' \
  --exclude 'backend/.env' \
  --exclude 'backend/powerai_hot.db' \
  "$SOURCE_DIR/" "$RELEASE_DIR/"

run_predeploy_data_backup

recover_failed_deploy() {
  local reason="$1"

  echo "$reason; rolling back" >&2
  if [[ -n "$previous" ]]; then
    old_tag="$(basename "$previous")"
    ln -sfn "$previous" "$CURRENT"
    cd "$previous/powerai-hot"
    export IMAGE_TAG="$old_tag"
    export COMPOSE_PROJECT_NAME=e-ai
    if ! compose build; then
      echo "rollback build failed for previous release: $previous" >&2
      return 1
    fi
    if ! compose up -d; then
      echo "rollback up failed for previous release: $previous" >&2
      return 1
    fi
    if ! wait_for_health; then
      echo "rollback health gate failed for previous release: $previous" >&2
      return 1
    fi
    return 1
  fi

  echo "no previous release to roll back to" >&2
  if ! compose down; then
    echo "candidate compose down failed for release: $RELEASE_DIR" >&2
  fi
  if [[ -L "$CURRENT" ]] && [[ "$(readlink -f "$CURRENT")" == "$RELEASE_DIR" ]]; then
    rm -f "$CURRENT"
  fi
  return 1
}

cd "$RELEASE_DIR/powerai-hot"
export BACKEND_ENV_FILE
export POSTGRES_PASSWORD_FILE
export IMAGE_TAG=$RELEASE_NAME

compose build

if [[ -n "$MIGRATE_SQLITE_SOURCE" ]]; then
  migration_summary=""
  migration_status=0
  if ! compose up -d db; then
    recover_failed_deploy "sqlite migration database startup failed" || exit 1
  fi
  if ! compose run --rm backend python -c "from models.database import init_db; init_db()"; then
    recover_failed_deploy "sqlite migration schema initialization failed" || exit 1
  fi
  if migration_summary="$(
    compose run --rm \
      --user 0:0 \
      --volume "$MIGRATE_SQLITE_SOURCE:$MIGRATION_CONTAINER_SOURCE:ro" \
      backend python -m jobs.migrate_sqlite --source "$MIGRATION_CONTAINER_SOURCE"
  )"; then
    migration_status=0
  else
    migration_status=$?
  fi
  printf '%s\n' "$migration_summary"
  if [[ "$migration_status" -ne 0 ]]; then
    recover_failed_deploy "sqlite migration command failed" || exit 1
  fi
  if ! python3 -c 'import json,sys; data=json.load(sys.stdin); sys.exit(0 if data.get("gate_passed") is True else 1)' <<<"$migration_summary"; then
    recover_failed_deploy "sqlite migration gate failed; current release unchanged" || exit 1
  fi
fi

ln -sfn "$RELEASE_DIR" "$CURRENT"
if ! compose up -d; then
  recover_failed_deploy "compose up failed" || exit 1
fi

if wait_for_health; then
  exit 0
fi

recover_failed_deploy "health gate failed" || exit 1
