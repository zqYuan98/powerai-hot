# PowerAI Hot Project Completion Implementation Plan

> **Execution note:** Follow test-driven development for each behavior change. Run the narrow test first, implement the minimum change, rerun the narrow test, then run the affected suite. Local workspace has no `.git` metadata, so commit checkpoints in this plan become file/test checkpoints until repository metadata is restored.

**Goal:** Complete the current PowerAI Hot remediation, deploy it to `124.220.207.16`, retire the old Hermes web route, and verify the production website over HTTPS.

**Architecture:** Keep FastAPI, React/Next.js, PostgreSQL, Docker Compose and systemd. Add a PostgreSQL-backed job queue processed by short-lived systemd invocations, Alembic migrations, an allowlisted Playwright full-text helper, quantitative content-quality gates, release capacity/certificate checks, and a reading-first frontend.

**Release sequence:** This is not one large release. Release A uses the currently healthy application containers and only fixes capacity, certificate lifecycle and the HTTPS route, with its own snapshot and rollback. Release B happens only after Release A is accepted; it contains the tested application, migration, task, content and frontend changes and has a second backup, rollback target and acceptance gate.

**Source design:** `docs/superpowers/specs/2026-07-28-project-completion-design.md`

---

## Task 0: Release A — stop the production bleeding before application changes

**Files**

- Modify: `deploy/Caddyfile`
- Add: `scripts/capacity-gate.sh`
- Add: `scripts/check-certificate.sh`
- Add: `scripts/certificate-deploy-hook.sh`
- Add: `deploy/systemd/powerai-cert-watch.service`
- Add: `deploy/systemd/powerai-cert-watch.timer`
- Add: `backend/tests/test_release_gates.py`
- Modify: `docs/PRODUCTION_RUNBOOK.md`

**Steps**

1. From `D:\powerai-hot\backend`, write and run failing parser/threshold tests for the capacity and certificate gates.
2. Implement the minimum scripts to pass the tests; configuration files use `caddy validate`, systemd verification and certificate dry-run as their executable checks.
3. On production, record the current release, containers, Caddy routes, certificate paths, renewal account, systemd units, `df`, Docker images and build cache.
4. Create a checksumed PostgreSQL backup and preserve the current Caddy file and certificate unit definitions as the Release A rollback artifacts.
5. Reclaim only Docker build cache and images proven unreferenced by the current release and two most recent releases.
6. Require at least 10 GiB free and no more than 78% root usage before continuing.
7. Rename/migrate Hermes certificate renewal service/hook names while retaining certificate files and account state; verify dry-run/staging renewal and a validated Caddy reload hook.
8. Change only the HTTPS reverse proxy for `124.220.207.16` to `127.0.0.1:8080`; do not rebuild or replace the healthy PowerAI Hot containers.
9. Verify external HTTPS title, static assets, API, login and certificate chain.
10. If any check fails, restore the saved Caddy/unit files and reload; the database and application release remain untouched.
11. Record Release A acceptance before Task 1 starts.

## Task 1: Make the baseline deterministic on Windows and Linux

**Files**

- Modify: `backend/tests/test_ops_config.py`
- Add: `.github/workflows/ci.yml`
- Modify: `backend/pytest.ini`
- Modify: `frontend/components/digest/DigestModule.tsx`
- Modify: `frontend/components/knowledge/WorkspaceCollection.tsx`
- Modify: `frontend/components/library/LibraryModule.tsx`
- Modify: `frontend/components/navigation/navConfig.ts`
- Modify: `frontend/components/report/ReportModule.tsx`

**Steps**

1. Add a platform marker or guarded import so POSIX-only lock tests skip during Windows collection but still run on Linux.
2. Run `python -m pytest backend/tests/test_ops_config.py -q`; expect a clean skip on Windows.
3. Add Linux CI jobs for the full backend suite and frontend test/typecheck/lint/build.
4. Add Windows CI for the ordinary backend suite.
5. Fix all six React hook/unused-symbol warnings without disabling rules.
6. From `D:\powerai-hot\backend`, run `python -m pytest -q`.
7. From `D:\powerai-hot\frontend`, run:
   - `npm test -- --run`
   - `npm run typecheck`
   - `npm run lint`
   - `npm run build`

## Task 2: Introduce Alembic without breaking existing databases

**Files**

- Modify: `backend/requirements.txt`
- Modify: `backend/requirements.lock`
- Add: `backend/alembic.ini`
- Add: `backend/alembic/env.py`
- Add: `backend/alembic/script.py.mako`
- Add: `backend/alembic/versions/20260728_0001_baseline.py`
- Modify: `backend/models/database.py`
- Modify: `backend/models/migrate.py`
- Add: `backend/tests/test_alembic_migrations.py`
- Add: `backend/tests/test_schema_fingerprint.py`
- Add: `backend/scripts/schema_fingerprint.py`
- Modify: `scripts/deploy.sh`

**Steps**

1. Write migration tests that upgrade an empty SQLite database and recognize an already-current schema.
2. Add Alembic with metadata from `models.schema.Base`.
3. Create a canonical schema fingerprint containing every table, column, SQL type, nullability, server default, primary/foreign/unique/check constraint and index.
4. Existing databases may be stamped only when their normalized fingerprint exactly matches the reviewed baseline; mismatch fails closed and prints the diff.
5. Restore the newest production backup into an isolated PostgreSQL database/container and run fingerprint verification, `alembic stamp`, `alembic upgrade head`, application smoke tests and a second fingerprint capture.
6. Keep `models/migrate.py` as a temporary compatibility shim that only checks/stamps through Alembic and emits no DDL.
7. Application startup only checks that the database revision equals the required head and exits unhealthy on mismatch; it never upgrades or alters schema.
8. Update deployment to run migration after backup and before switching `current`.
9. From `D:\powerai-hot\backend`, run migration/fingerprint tests on SQLite and the disposable PostgreSQL clone.

## Task 3: Build the persistent job model and repository

**Files**

- Modify: `backend/models/schema.py`
- Add: `backend/jobs/queue.py`
- Add: `backend/jobs/types.py`
- Add: `backend/alembic/versions/20260728_0002_persistent_jobs.py`
- Add: `backend/alembic/versions/20260728_0003_alert_state.py`
- Add: `backend/tests/test_job_queue.py`

**Steps**

1. Write tests for enqueue idempotency, priority ordering, due-time filtering, atomic claim, heartbeat, success, retry, terminal failure and stale-job recovery.
2. Add `PersistentJob`, persistent `AlertState` and required indexes.
3. Implement PostgreSQL claim using `FOR UPDATE SKIP LOCKED`.
4. Implement SQLite single-worker claim using a transaction-protected compare/update.
5. Ensure payload and errors are size-limited and secrets are redacted.
6. Run `python -m pytest backend/tests/test_job_queue.py -q`.

## Task 4: Migrate background work to the persistent executor

**Files**

- Add: `backend/jobs/worker.py`
- Add: `backend/api/jobs.py`
- Modify: `backend/main.py`
- Modify: `backend/api/admin.py`
- Modify: `backend/api/reports.py`
- Modify: `backend/api/cards.py`
- Modify: `backend/api/favorites.py`
- Modify: `backend/jobs/ingest.py`
- Modify: `backend/jobs/news.py`
- Modify: `backend/jobs/papers.py`
- Modify: `backend/jobs/digest.py`
- Modify: `backend/scheduler/monitor.py`
- Modify: `backend/services/research.py`
- Modify: `backend/services/cards.py`
- Add: `backend/tests/test_job_worker.py`
- Modify: affected API tests
- Modify: `scripts/run-job.sh`
- Modify: `deploy/systemd/e-ai-job@.service`
- Modify: `deploy/systemd/e-ai-news.timer`
- Modify: `deploy/systemd/e-ai-papers.timer`
- Modify: `deploy/systemd/e-ai-digest.timer`
- Add: `deploy/systemd/e-ai-worker.service`
- Add: `deploy/systemd/e-ai-worker.timer`

**Steps**

1. Write API tests asserting `202`, `job_id`, `status_url` and preserved business fields.
2. Register handlers for all job types from the design.
3. Replace `threading.Thread` and FastAPI `BackgroundTasks` calls with queue writes.
4. Add job status/list/retry endpoints with admin authorization.
5. Change news, papers, digest and existing job timers so their only action is an idempotent enqueue; only the worker executes business work.
6. Add a bounded worker command and systemd timer.
7. Use the same `/opt/e-ai/releases/.operations.lock` protocol for workers, deploy, backup, certificate changes and other maintenance; enqueue commands do not hold the lock while waiting.
8. Test API restart, worker restart, timer overlap, idempotency, retry exhaustion and stale recovery for every job type.
9. From `D:\powerai-hot\backend`, run the affected suite and then `python -m pytest -q`.

## Task 5: Add resumable historical full-text backfill

**Files**

- Add: `backend/jobs/fulltext_backfill.py`
- Modify: `backend/collector/fulltext.py`
- Modify: `backend/services/ingest.py`
- Modify: `backend/jobs/worker.py`
- Add: `backend/tests/fixtures/fulltext/*.html`
- Add: `backend/tests/test_fulltext_backfill.py`

**Steps**

1. Write tests for supported-domain selection, batching, cursor persistence, idempotent rerun, failure recording and reenrichment.
2. Add bounded backfill payload fields: source, date window, cursor, batch size and runtime budget.
3. Reuse current full-text extraction and write structured metadata.
4. Re-score and re-cluster only changed records.
5. Add an admin enqueue action and progress reporting.

## Task 6: Add the allowlisted BJX Playwright path

**Files**

- Modify: `backend/requirements.txt`
- Modify: `backend/Dockerfile`
- Add: `backend/Dockerfile.jobs`
- Add: `backend/collector/browser_fulltext.py`
- Modify: `backend/collector/fulltext.py`
- Modify: `backend/core/config.py`
- Add: `backend/tests/test_browser_fulltext.py`
- Modify: `docker-compose.yml`

**Steps**

1. Write unit tests around allowlisting, URL guard, resource blocking, timeout and fallback behavior.
2. Create `Dockerfile.jobs` and the separate `e-ai-jobs:${IMAGE_TAG}` image; the existing `e-ai-backend:${IMAGE_TAG}` image must not contain Chromium.
3. Implement a single-browser, serial, bounded batch extractor for `news.bjx.com.cn`.
4. Block downloads, media, fonts and nonessential third-party requests.
5. Always close page, context and browser in `finally`.
6. Record fallback reason when a title-only article remains.
7. Update build, capacity, retention and rollback logic to account for both image tags.
8. Run a small production-safe probe before enabling the scheduled batch.

## Task 7: Tighten weak-axis prefilter and formalize CCGP disposition

**Files**

- Modify: `backend/analyzer/prefilter.py`
- Modify: `backend/analyzer/scoring.py`
- Modify: `backend/services/ingest.py`
- Add: `backend/tests/fixtures/content_quality_gold.json`
- Modify: `backend/tests/test_prefilter.py`
- Modify: `backend/tests/test_scoring.py`
- Add: `backend/tests/test_content_quality_gate.py`
- Modify: `backend/core/config.py`

**Steps**

1. Create at least 160 fixed samples across AI, industry, cross and low-value boundaries.
2. Add a deterministic first-stage rejection for obvious weak-axis content.
3. Protect recall with domain/keyword exceptions and log rejection reasons.
4. Add a quality-gate command reporting precision, recall, cross three-condition rate and estimated model-call reduction.
5. Set CCGP to provisional `raw-only` for this release, capture the current 48-item baseline, and add metrics for raw-only, procurement-watch or curated candidate mode.
6. Enqueue a durable review job with `available_at` 30 days after the baseline. That job evaluates the accumulated window and applies the approved 0% / <5% / ≥5% rule with an auditable result.
7. Require the immediately measurable thresholds from the approved design before deployment; final CCGP disposition is explicitly a scheduled post-release acceptance item.

## Task 8: Quantify event clustering and main-source choice

**Files**

- Modify: `backend/services/clustering.py`
- Modify: `backend/services/article_feed.py`
- Modify: `backend/tests/test_clustering.py`
- Add: `backend/tests/fixtures/clustering_gold.json`
- Add: `backend/tests/test_clustering_quality_gate.py`

**Steps**

1. Add positive/negative event pairs and authoritative-source expectations.
2. Fix normalization or similarity rules needed to reach pairwise F1 ≥ 0.90.
3. Make official/first-party, complete-body and explicit-time signals deterministic in main-source choice.
4. Require main-source accuracy ≥ 95%.
5. Verify cross-pick API exposes the main item and same-event sources.

## Task 9: Complete the reading-first frontend

**Files**

- Modify: `frontend/app/globals.css`
- Modify: `frontend/components/shells/EmployeeApp.tsx`
- Modify: `frontend/components/navigation/EmployeeSidebar.tsx`
- Modify: `frontend/components/navigation/MobileNav.tsx`
- Modify: `frontend/components/navigation/navConfig.ts`
- Modify: `frontend/components/feed/FeedModule.tsx`
- Modify: `frontend/components/feed/ArticleCard.tsx`
- Add: `frontend/components/feed/ScoreBadge.tsx`
- Add: `frontend/components/feed/SourceTrust.tsx`
- Add: `frontend/components/feed/FilterBar.tsx`
- Add: `frontend/components/EmptyState.tsx`
- Modify: `frontend/lib/types.ts`
- Modify: relevant component tests
- Modify: `frontend/e2e/portal.spec.ts`

**Steps**

1. Add failing component tests for cross picks first, separated reader/admin navigation, decision reason, source trust and responsive filtering.
2. Introduce design tokens and reusable primitives.
3. Put up to three cross picks at the top, then the five feed tabs and single-column article stream.
4. Remove visible entries for requirements, industry knowledge base and graph.
5. Keep management pages under the admin shell.
6. Add desktop/mobile browser checks and rerun test/typecheck/lint/build.

## Task 10: Expand the operations center and alerts

**Files**

- Modify: `backend/api/system.py`
- Modify: `backend/api/admin.py`
- Modify: `backend/jobs/watchdog.py`
- Modify: `backend/scheduler/monitor.py`
- Modify: `frontend/components/admin/AdminModule.tsx`
- Modify: `frontend/components/admin/AxisMonitorPanel.tsx`
- Modify: `frontend/components/admin/ContentOperationsModule.tsx`
- Add/modify: monitor and admin tests

**Steps**

1. Add backend snapshots for source freshness, full-text coverage, route output, model fallback, jobs, disk, backups, certificate expiry and release version.
2. Add threshold-crossing and recovery-state persistence to avoid repeated alerts.
3. Add job queue and certificate/disk cards to the operations center.
4. Verify alert redaction and traceability to run IDs.

## Task 11: Add disk, retention and certificate release gates

**Files**

- Modify: `scripts/deploy.sh`
- Modify: `scripts/rollback.sh`
- Add: `scripts/prune-releases.sh`
- Modify: `deploy/Caddyfile`

**Steps**

1. Add tests for parsing capacity/certificate inputs and refusing unsafe states.
2. Enforce prebuild 10 GiB/78% and postdeploy 8 GiB/82% thresholds.
3. Keep current plus two previous releases and their referenced images.
4. Preserve and regression-test the certificate units and HTTPS route already accepted in Release A.
5. Validate Caddy configuration before reload and alert on expiry under 72 hours.

## Task 12: Reconcile documentation and configuration contracts

**Files**

- Modify: `README.md`
- Modify: `.env.example`
- Modify: `docs/PRODUCTION_RUNBOOK.md`
- Modify: `docs/AIHOT_REFERENCE_AND_PROJECT_AUDIT.md`
- Modify: `docs/2026-07-25-content-supply-and-ranking-remediation-plan.md`
- Add: `backend/tests/test_documentation_contract.py`
- Add: `.gitignore`

**Steps**

1. Remove stale hard-coded collector/test claims or generate them from contract data.
2. Document the three content axes, current collectors, job operations, migrations, backfill, BJX browser constraints, certificate lifecycle, release gates and rollback.
3. Add `.superpowers/`, caches, local databases, frontend build output and Playwright artifacts to `.gitignore`.
4. Run documentation/config contract tests.

## Task 13: Local release candidate verification

**Steps**

1. From `D:\powerai-hot\backend`, run `python -m pytest -q` on Windows.
2. From `D:\powerai-hot`, run the POSIX suite and PostgreSQL integration tests in Linux containers.
3. From `D:\powerai-hot\frontend`, run `npm test -- --run`, `npm run typecheck`, `npm run lint`, `npm run build` and Playwright smoke tests.
4. Build all Compose images.
5. Run migrations and application smoke tests against a disposable PostgreSQL volume.
6. Record exact command outputs and artifact versions.

## Task 14: Release B — production application deployment

**Steps**

1. Confirm Release A remains accepted: HTTPS already serves PowerAI Hot, certificate monitoring is healthy and capacity is above the prebuild gate.
2. Resolve `/opt/e-ai/current`, running containers, timers and both application image tags.
3. Record disk/Docker state and safely reclaim only build cache and verified unused images.
4. Upload the exact local release candidate.
5. Create and checksum a PostgreSQL backup.
6. Restore that backup into an isolated clone; require exact baseline fingerprint, stamp/upgrade, smoke-test and retain the evidence.
7. Run the same Alembic upgrade on production, start the candidate and complete internal health/API/frontend smoke tests.
8. Switch the application release symlink only after migration succeeds; HTTPS configuration does not change in Release B.
9. Verify HTTP/HTTPS, title, static assets, API, authentication and certificate chain from an external browser.
10. Verify timers only enqueue, worker executes, watchdog/backups/certificate monitors run, and postdeploy disk gates pass.
11. On failure, roll back the application symlink/images; restore the database only when the migration-specific rollback procedure explicitly requires it.

## Task 15: Production data remediation and final acceptance

**Steps**

1. Enqueue the 119-item supported-domain historical backfill and verify completion/recoverability.
2. Run a bounded BJX probe, then enqueue BJX historical batches if the probe passes.
3. Run reenrichment, rescoring and reclustering for changed records.
4. Execute the gold quality gates and sample live AI, industry and cross picks.
5. Confirm CCGP is provisional `raw-only`, its 48-item baseline is stored, and the durable 30-day review job exists; do not claim final CCGP disposition in this release.
6. Exercise one retryable job and one worker restart recovery.
7. Verify release rollback target and backup restore check without destructive restore.
8. Deliver the website URL, Release A and Release B IDs, test evidence, content metrics, scheduled CCGP review time, remaining operational observations and rollback command.
