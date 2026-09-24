# E-AI Production Runbook

Target host: Ubuntu 24.04, 4 vCPU, 3.6 GiB RAM, Docker Compose, Caddy.

## Layout

- App root: `/opt/e-ai`
- Current release: `/opt/e-ai/current`
- Releases: `/opt/e-ai/releases/<timestamp>`
- Secrets: `/opt/e-ai/secrets/backend.env`
- Backups: `/opt/e-ai/backups`

Do not commit `backend.env`, SQLite production dumps, pg dumps, or any API key.

## First Deploy

1. Install Docker, Docker Compose, Caddy, and systemd units support on the host.
2. Run `sudo scripts/prepare-secrets.sh` or create `/opt/e-ai/secrets/backend.env` and `/opt/e-ai/secrets/postgres_password.txt` with mode `0600`.
3. Set at minimum `DEBUG=false`, strong `WORKSPACE_TOKEN`, `ADMIN_TOKEN`, `SESSION_SECRET`, `APP_ORIGIN=http://124.220.207.16`, `SESSION_COOKIE_SECURE=false`, and `DATABASE_URL=postgresql+psycopg://...@db:5432/powerai_hot`. Set `ACCESS_MODE=public_admin` only for a deliberately public single-administrator deployment; it bypasses browser authentication for every management route. Bind a domain and enable HTTPS before setting secure cookies in production.
4. Install Caddy as the only public entry:
   `sudo cp deploy/Caddyfile /etc/caddy/Caddyfile && sudo systemctl reload caddy`
5. Run `scripts/deploy.sh` from the repository root.
6. Install and enable systemd timers:
   `sudo cp deploy/systemd/e-ai-* /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now e-ai-news.timer e-ai-papers.timer e-ai-digest.timer e-ai-watchdog.timer e-ai-backup.timer`

Compose binds nginx only to `127.0.0.1:8080`; Caddy is the only public HTTP(S) entry.

For a first deploy without `--migrate-sqlite`, no existing database is expected and the deploy skips the predeploy data backup explicitly.

## SQLite Migration

SQLite migration is only for the first deploy from the legacy SQLite database into an empty PostgreSQL volume. Do not use it to migrate an already-running production PostgreSQL database. If `/opt/e-ai/current` already exists, `scripts/deploy.sh --migrate-sqlite ...` fails before Docker build, startup, or migration.

Copy the old SQLite DB read-only to the host, then run:

```bash
scripts/deploy.sh --migrate-sqlite /opt/e-ai/migration/legacy.sqlite
```

The deploy script requires an absolute existing regular file. Before any Docker build, migration, or `/opt/e-ai/current` switch, it copies the source to `/opt/e-ai/backups/legacy_sqlite_before_<release>.sqlite`, makes the backup read-only, and writes `/opt/e-ai/backups/legacy_sqlite_before_<release>.sqlite.sha256`. The checksum file uses standard `sha256sum` format and names the final backup file.

If the SQLite backup or checksum fails, deploy stops before Docker is called and before `current` changes. After that backup succeeds, deploy mounts only the source file read-only into the migration container, initializes the PostgreSQL schema, runs the migration gate, and switches `/opt/e-ai/current` only when `gate_passed=true`. The command prints JSON with pre/post counts, inserted/skipped/conflict counts, and relationship checks. Re-running must not duplicate rows.

If the migration command exits non-zero, prints invalid JSON, or reports `gate_passed` other than `true`, deploy exits non-zero, prints any captured migration summary for diagnosis, stops the candidate Compose stack with `compose down`, preserves named Docker volumes, keeps the candidate release directory for inspection, and does not create or switch `/opt/e-ai/current`. The migration data transaction is rolled back on gate failure, so a corrected first deploy can be retried against the preserved PostgreSQL volume.

## Verification

```bash
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://124.220.207.16/api/rss.xml
docker compose ps
scripts/run-job.sh news
scripts/run-job.sh watchdog
```

Use `/api/system/status` with an admin session or `X-Admin-Token` to inspect latest jobs, freshness, degradation ratio, and failed sources.

## Backup And Restore Check

Run `scripts/backup.sh` daily through the timer or manually. Backups are retained for 7 days by default.

Every deploy after the first release creates a release-bound PostgreSQL backup after the candidate release is copied and before candidate build, migration, or cutover. These files are named `/opt/e-ai/backups/powerai_hot_<UTC stamp>_before_<release>.sql.gz`. If this predeploy backup fails, deploy exits non-zero, keeps `current` on the previous release, does not build or start the candidate, and leaves the candidate release directory for inspection.

Validate a backup without touching production data:

```bash
scripts/restore-check.sh /opt/e-ai/backups/powerai_hot_<timestamp>.sql.gz
```

## Rollback

`scripts/rollback.sh` points `/opt/e-ai/current` to the previous release and restarts Compose. It does not delete Docker volumes. If a future release introduces a destructive schema change, restore the matching database backup before starting the old release.

## Fault Injection

- Model outage: remove `DEEPSEEK_API_KEY` or force 429/5xx in tests; raw articles should still insert and `scored_by` should become `rule` or `unscored/degraded`.
- Source outage: block one collector URL; `/api/system/status` should show a failed source while other sources continue.
- Stale job: leave a `job_runs.status=running` row older than 2 hours; `python -m jobs.watchdog` marks it failed.
