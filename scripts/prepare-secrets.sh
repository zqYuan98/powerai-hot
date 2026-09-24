#!/usr/bin/env bash
set -euo pipefail
umask 077

APP_ROOT="${APP_ROOT:-/opt/e-ai}"
SECRETS_DIR="${SECRETS_DIR:-$APP_ROOT/secrets}"
BACKEND_ENV_FILE="${BACKEND_ENV_FILE:-$SECRETS_DIR/backend.env}"
POSTGRES_PASSWORD_FILE="${POSTGRES_PASSWORD_FILE:-$SECRETS_DIR/postgres_password.txt}"
POSTGRES_USER="${POSTGRES_USER:-powerai}"
POSTGRES_DB="${POSTGRES_DB:-powerai_hot}"

validate_identifier() {
  local name="$1"
  local value="$2"
  if [[ ! "$value" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    echo "$name must match [A-Za-z_][A-Za-z0-9_]*" >&2
    exit 1
  fi
}

if [[ -z "${POSTGRES_PASSWORD:-}" ]]; then
  echo "POSTGRES_PASSWORD is required in the environment" >&2
  exit 1
fi
validate_identifier POSTGRES_USER "$POSTGRES_USER"
validate_identifier POSTGRES_DB "$POSTGRES_DB"

mkdir -p "$SECRETS_DIR"
printf '%s' "$POSTGRES_PASSWORD" > "$POSTGRES_PASSWORD_FILE"
chmod 600 "$POSTGRES_PASSWORD_FILE"

database_url="$(
  printf '%s' "$POSTGRES_PASSWORD" | \
    POSTGRES_USER_VALUE="$POSTGRES_USER" POSTGRES_DB_VALUE="$POSTGRES_DB" python3 -c '
import os
import sys
from urllib.parse import quote

user = quote(os.environ["POSTGRES_USER_VALUE"], safe="")
password = quote(sys.stdin.read(), safe="")
database = quote(os.environ["POSTGRES_DB_VALUE"], safe="")
sys.stdout.write(f"postgresql+psycopg://{user}:{password}@db:5432/{database}")
'
)"

tmp="$(mktemp "$SECRETS_DIR/backend.env.XXXXXX")"
trap 'rm -f "$tmp"' EXIT
if [[ -f "$BACKEND_ENV_FILE" ]]; then
  awk '!/^(DATABASE_URL|POSTGRES_USER|POSTGRES_DB)=/' "$BACKEND_ENV_FILE" > "$tmp"
fi
{
  cat "$tmp"
  printf 'POSTGRES_USER=%s\n' "$POSTGRES_USER"
  printf 'POSTGRES_DB=%s\n' "$POSTGRES_DB"
  printf 'DATABASE_URL=%s\n' "$database_url"
} > "$tmp.next"
mv "$tmp.next" "$BACKEND_ENV_FILE"
chmod 600 "$BACKEND_ENV_FILE"
rm -f "$tmp"
trap - EXIT
echo "secrets prepared"
