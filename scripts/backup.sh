#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/e-ai}"
BACKUP_DIR="${BACKUP_DIR:-$APP_ROOT/backups}"
KEEP_DAYS="${KEEP_DAYS:-7}"
BACKUP_LABEL="${BACKUP_LABEL:-}"

if [[ -n "$BACKUP_LABEL" && ! "$BACKUP_LABEL" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "BACKUP_LABEL must match [A-Za-z0-9._-]+" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"

cd "$APP_ROOT/current/powerai-hot"
release_dir="$(readlink -f "$APP_ROOT/current")"
export IMAGE_TAG="${IMAGE_TAG:-$(basename "$release_dir")}"
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

postgres_identifier() {
  local name="$1"
  local value
  value="$(compose exec -T db printenv "$name")"
  value="${value//$'\r'/}"
  value="${value//$'\n'/}"
  if [[ ! "$value" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    echo "db container $name must match [A-Za-z_][A-Za-z0-9_]*" >&2
    exit 1
  fi
  printf '%s' "$value"
}

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
if [[ -n "$BACKUP_LABEL" ]]; then
  final="$BACKUP_DIR/powerai_hot_${stamp}_${BACKUP_LABEL}.sql.gz"
  tmp="$(mktemp "$BACKUP_DIR/.powerai_hot_${stamp}_${BACKUP_LABEL}.XXXXXX.sql.gz")"
else
  final="$BACKUP_DIR/powerai_hot_$stamp.sql.gz"
  tmp="$(mktemp "$BACKUP_DIR/.powerai_hot_$stamp.XXXXXX.sql.gz")"
fi
trap 'rm -f "$tmp"' EXIT

postgres_user="$(postgres_identifier POSTGRES_USER)"
postgres_db="$(postgres_identifier POSTGRES_DB)"

compose exec -T db pg_dump --no-owner --no-acl -U "$postgres_user" "$postgres_db" \
  | gzip -c > "$tmp"

test -s "$tmp"
gzip -t "$tmp"
mv "$tmp" "$final"
trap - EXIT

find "$BACKUP_DIR" -type f -name 'powerai_hot_*.sql.gz' -mtime +"$KEEP_DAYS" -delete
echo "backup written: $final"
