#!/usr/bin/env bash
set -euo pipefail

backup_file="${1:?usage: restore-check.sh /path/to/backup.sql.gz}"
APP_ROOT="${APP_ROOT:-/opt/e-ai}"

if [[ ! -f "$backup_file" ]]; then
  echo "backup must be an existing regular file" >&2
  exit 1
fi
gzip -t "$backup_file"

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

postgres_user=""
postgres_db=""
temp_db="restore_check_$(date -u +%Y%m%d%H%M%S)_$$"
cleanup() {
  if [[ -z "$postgres_user" || -z "$postgres_db" ]]; then
    return 0
  fi
  compose exec -T db dropdb -U "$postgres_user" --maintenance-db="$postgres_db" --if-exists "$temp_db" >/dev/null 2>&1 || true
}
trap cleanup EXIT

postgres_user="$(postgres_identifier POSTGRES_USER)"
postgres_db="$(postgres_identifier POSTGRES_DB)"

required_tables=(
  sources
  articles
  requirements
  knowledge_items
  knowledge_relations
  subscriptions
  scoring_config
  reports
  favorites
  knowledge_cards
  job_runs
  source_runs
)

fail() {
  echo "restore check failed: $*" >&2
  exit 1
}

quote_required_table() {
  case "$1" in
    sources|articles|requirements|knowledge_items|knowledge_relations|subscriptions|scoring_config|reports|favorites|knowledge_cards|job_runs|source_runs)
      printf '"%s"' "$1"
      ;;
    *)
      fail "internal unsupported table"
      ;;
  esac
}

parse_count() {
  local label="$1"
  local value="$2"
  value="${value//$'\r'/}"
  if [[ ! "$value" =~ ^[[:space:]]*([0-9]+)[[:space:]]*$ ]]; then
    fail "$label did not return a non-negative integer"
  fi
  printf '%s' "${BASH_REMATCH[1]}"
}

query_count() {
  local database="$1"
  local label="$2"
  local sql="$3"
  local output
  output="$(
    compose exec -T db psql -U "$postgres_user" -d "$database" -qAt -v ON_ERROR_STOP=1 -c "$sql"
  )"
  parse_count "$label" "$output"
}

count_table_rows() {
  local database="$1"
  local table="$2"
  local quoted_table
  quoted_table="$(quote_required_table "$table")"
  query_count "$database" "$table row count" "SELECT COUNT(*) FROM $quoted_table;"
}

capture_table_counts() {
  local database="$1"
  local target_name="$2"
  local -n target="$target_name"
  local table
  target=()
  for table in "${required_tables[@]}"; do
    target["$table"]="$(count_table_rows "$database" "$table")"
  done
}

check_orphan_count() {
  local label="$1"
  local sql="$2"
  local count
  count="$(query_count "$temp_db" "$label orphan count" "$sql")"
  if (( count != 0 )); then
    fail "$label orphan count is $count"
  fi
}

declare -A production_counts_before
declare -A production_counts_after
declare -A restored_counts
capture_table_counts "$postgres_db" production_counts_before

compose exec -T db createdb -U "$postgres_user" --maintenance-db="$postgres_db" "$temp_db"
gzip -dc "$backup_file" | compose exec -T db psql -U "$postgres_user" -d "$temp_db" -v ON_ERROR_STOP=1 -q

quoted_tables="$(printf "'%s'," "${required_tables[@]}")"
quoted_tables="${quoted_tables%,}"
found="$(query_count "$temp_db" "required table count" "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name IN ($quoted_tables);")"
if [[ "$found" != "${#required_tables[@]}" ]]; then
  fail "missing required tables"
fi

for table in "${required_tables[@]}"; do
  quoted_table="$(quote_required_table "$table")"
  compose exec -T db psql -U "$postgres_user" -d "$temp_db" -q -v ON_ERROR_STOP=1 \
    -c "SELECT 1 FROM $quoted_table LIMIT 0;" >/dev/null
done

capture_table_counts "$temp_db" restored_counts
if (( restored_counts[sources] <= 0 || restored_counts[articles] <= 0 )); then
  fail "restored backup is not meaningful (sources=${restored_counts[sources]}, articles=${restored_counts[articles]})"
fi

check_orphan_count \
  "articles_source_id" \
  "SELECT COUNT(*) FROM articles a LEFT JOIN sources s ON a.source_id = s.id WHERE a.source_id IS NOT NULL AND s.id IS NULL;"
check_orphan_count \
  "favorites_article_id" \
  "SELECT COUNT(*) FROM favorites f LEFT JOIN articles a ON f.article_id = a.id WHERE a.id IS NULL;"
check_orphan_count \
  "knowledge_cards_article_id" \
  "SELECT COUNT(*) FROM knowledge_cards k LEFT JOIN articles a ON k.article_id = a.id WHERE a.id IS NULL;"
check_orphan_count \
  "requirements_source_article_id" \
  "SELECT COUNT(*) FROM requirements r LEFT JOIN articles a ON r.source_article_id = a.id WHERE r.source_article_id IS NOT NULL AND a.id IS NULL;"

capture_table_counts "$postgres_db" production_counts_after
for table in "${required_tables[@]}"; do
  if [[ "${production_counts_before[$table]}" != "${production_counts_after[$table]}" ]]; then
    fail "production row count changed for $table (before=${production_counts_before[$table]}, after=${production_counts_after[$table]})"
  fi
done

echo "restore check passed: verified schema, meaningful data, relationships, and unchanged production counts"
