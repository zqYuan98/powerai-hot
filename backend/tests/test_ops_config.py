from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess

import pytest
from sqlalchemy.engine import make_url

try:
    import fcntl
except ModuleNotFoundError:  # Windows collection; lock behavior is exercised in Linux CI.
    fcntl = None

pytestmark = pytest.mark.skipif(
    os.name == "nt",
    reason="production shell, symlink, flock, and permission behavior is verified on Linux",
)

ROOT = Path(__file__).resolve().parents[2]
PYTHON_312_SLIM_DIGEST = "sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de"
NODE_20_ALPINE_DIGEST = "sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293"
NGINX_127_ALPINE_DIGEST = "sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10"
POSTGRES_16_ALPINE_DIGEST = "sha256:57c72fd2a128e416c7fcc499958864df5301e940bca0a56f58fddf30ffc07777"
RESTORE_REQUIRED_TABLES = (
    "sources",
    "articles",
    "requirements",
    "knowledge_items",
    "knowledge_relations",
    "subscriptions",
    "scoring_config",
    "reports",
    "favorites",
    "knowledge_cards",
    "job_runs",
    "source_runs",
)
RESTORE_ORPHAN_KEYS = (
    "articles_source_id",
    "favorites_article_id",
    "knowledge_cards_article_id",
    "requirements_source_article_id",
)
OPS_ENV_KEYS = {
    "IMAGE_TAG",
    "BACKEND_ENV_FILE",
    "POSTGRES_PASSWORD_FILE",
    "COMPOSE_PROJECT_NAME",
}
EXPECTED_RUNTIME_REQUIREMENTS = [
    "fastapi==0.139.2",
    "starlette==1.3.1",
    "uvicorn[standard]==0.34.0",
    "pydantic==2.10.4",
    "pydantic-settings==2.7.1",
    "SQLAlchemy==2.0.36",
    "APScheduler==3.10.4",
    "psycopg[binary]==3.2.3",
    "httpx==0.28.1",
    "beautifulsoup4==4.12.3",
    "feedparser==6.0.11",
    "lxml==6.1.1",
    "pip==26.1.2",
]
EXPECTED_EXECUTABLE_PATHS = {
    "powerai-hot/scripts/backup.sh",
    "powerai-hot/scripts/deploy.sh",
    "powerai-hot/scripts/prepare-secrets.sh",
    "powerai-hot/scripts/restore-check.sh",
    "powerai-hot/scripts/rollback.sh",
    "powerai-hot/scripts/run-job.sh",
}


def _normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirement_entry_name(line: str) -> str:
    name = line.split(";", 1)[0].split("==", 1)[0].strip()
    return _normalize_distribution_name(name.split("[", 1)[0])


def _requirements_txt_direct_names() -> set[str]:
    names: set[str] = set()
    for line in (ROOT / "backend/requirements.txt").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name = re.split(r"\s*(?:==|>=|<=|~=|!=|>|<)\s*", stripped, maxsplit=1)[0]
        names.add(_normalize_distribution_name(name.split("[", 1)[0]))
    return names


def _lock_requirement_blocks(lock_text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for line in lock_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line[0].isspace():
            if current:
                current.append(stripped)
            continue
        if current:
            blocks.append(" ".join(current))
        current = [stripped]
    if current:
        blocks.append(" ".join(current))
    return blocks


def _write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _clean_ops_env(**overrides: object) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in OPS_ENV_KEYS}
    env.update({key: str(value) for key, value in overrides.items()})
    return env


def _make_release(app_root: Path, name: str) -> Path:
    release = app_root / "releases" / name
    hot = release / "powerai-hot"
    hot.mkdir(parents=True)
    (hot / "docker-compose.yml").write_text("services:\n  backend:\n    image: test\n", encoding="utf-8")
    return release


def _make_rollback_app_root(tmp_path: Path) -> tuple[Path, Path, Path]:
    app_root = tmp_path / "app"
    previous = _make_release(app_root, "previous")
    target = _make_release(app_root, "target")
    current = app_root / "current"
    current.symlink_to(previous)
    secrets = app_root / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "backend.env").write_text("DEBUG=false\n", encoding="utf-8")
    (secrets / "postgres_password.txt").write_text("dummy", encoding="utf-8")
    return app_root, previous, target


def _make_restore_check_app(tmp_path: Path) -> tuple[Path, Path]:
    app_root = tmp_path / "app"
    release = app_root / "releases/20260717T010203Z"
    release_app = release / "powerai-hot"
    release_app.mkdir(parents=True)
    (release_app / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    current = app_root / "current"
    current.symlink_to(release)
    secrets = app_root / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "backend.env").write_text("DEBUG=false\n", encoding="utf-8")
    (secrets / "postgres_password.txt").write_text("dummy", encoding="utf-8")
    backup_file = tmp_path / "backup.sql.gz"
    with gzip.open(backup_file, "wt", encoding="utf-8") as handle:
        handle.write("CREATE TABLE sources(id integer);\n")
    return app_root, backup_file


def _restore_counts(**overrides: int) -> dict[str, int]:
    counts = dict.fromkeys(RESTORE_REQUIRED_TABLES, 0)
    counts.update(overrides)
    return counts


def _install_restore_check_docker(
    bin_dir: Path,
    state_path: Path,
    log_path: Path,
    *,
    present_tables: tuple[str, ...] = RESTORE_REQUIRED_TABLES,
    production_before: dict[str, int] | None = None,
    production_after: dict[str, int] | None = None,
    restored_counts: dict[str, int] | None = None,
    orphans: dict[str, int] | None = None,
) -> None:
    state = {
        "postgres_user": "custom_user",
        "postgres_db": "custom_db",
        "present_tables": list(present_tables),
        "production_before": production_before or _restore_counts(sources=3, articles=5),
        "production_after": production_after or _restore_counts(sources=3, articles=5),
        "restored_counts": restored_counts or _restore_counts(sources=1, articles=2),
        "orphans": {key: 0 for key in RESTORE_ORPHAN_KEYS} | (orphans or {}),
        "production_count_reads": 0,
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    _write_executable(
        bin_dir / "docker",
        f"""#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

state_path = Path({str(state_path)!r})
log_path = Path({str(log_path)!r})
argv = sys.argv[1:]
stdin = sys.stdin.read()
state = json.loads(state_path.read_text(encoding="utf-8"))

with log_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({{"argv": argv, "stdin_len": len(stdin)}}) + "\\n")


def save_state():
    state_path.write_text(json.dumps(state), encoding="utf-8")


def arg_after(name):
    if name not in argv:
        return None
    index = argv.index(name)
    if index + 1 >= len(argv):
        return None
    return argv[index + 1]


def psql_database():
    return arg_after("-d")


def psql_sql():
    return arg_after("-c") or ""


def print_count(value):
    if not isinstance(value, int) or value < 0:
        print(value)
        return 0
    print(value)
    return 0


if argv[:4] != ["compose", "--env-file", argv[2], "exec"]:
    sys.exit(0)

if "printenv" in argv:
    name = argv[-1]
    if name == "POSTGRES_USER":
        print(state["postgres_user"])
    elif name == "POSTGRES_DB":
        print(state["postgres_db"])
    else:
        sys.exit(1)
    sys.exit(0)

if "createdb" in argv:
    sys.exit(0)

if "dropdb" in argv:
    sys.exit(0)

if "psql" not in argv:
    sys.exit(0)

db = psql_database()
sql = psql_sql()

if not sql:
    if db == state["postgres_db"]:
        sys.exit(87)
    sys.exit(0 if stdin else 88)

if "information_schema.tables" in sql:
    requested = re.findall(r"'([A-Za-z_][A-Za-z0-9_]*)'", sql)
    present = set(state["present_tables"])
    sys.exit(print_count(sum(1 for table in requested if table in present)))

limit_match = re.search(r'FROM\\s+"([^"]+)"\\s+LIMIT\\s+0', sql)
if limit_match:
    sys.exit(0 if limit_match.group(1) in state["present_tables"] else 1)

count_match = re.search(r'COUNT\\(\\*\\)\\s+FROM\\s+"([^"]+)"', sql)
if count_match:
    table = count_match.group(1)
    if db == state["postgres_db"]:
        sweep = state["production_before"] if state["production_count_reads"] < {len(RESTORE_REQUIRED_TABLES)} else state["production_after"]
        state["production_count_reads"] += 1
        save_state()
        sys.exit(print_count(sweep[table]))
    sys.exit(print_count(state["restored_counts"][table]))

orphan_key = None
if "FROM articles" in sql and "LEFT JOIN sources" in sql:
    orphan_key = "articles_source_id"
elif "FROM favorites" in sql and "LEFT JOIN articles" in sql:
    orphan_key = "favorites_article_id"
elif "FROM knowledge_cards" in sql and "LEFT JOIN articles" in sql:
    orphan_key = "knowledge_cards_article_id"
elif "FROM requirements" in sql and "LEFT JOIN articles" in sql:
    orphan_key = "requirements_source_article_id"

if orphan_key is not None:
    sys.exit(print_count(state["orphans"][orphan_key]))

sys.exit(89)
""",
    )


def _run_restore_check(tmp_path: Path, **docker_state: object) -> tuple[subprocess.CompletedProcess[str], Path]:
    app_root, backup_file = _make_restore_check_app(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"
    _install_restore_check_docker(bin_dir, tmp_path / "docker-state.json", docker_log, **docker_state)
    env = {**os.environ, "APP_ROOT": str(app_root), "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/restore-check.sh"), str(backup_file)],
        cwd=ROOT.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed, docker_log


def _docker_calls(log_path: Path) -> list[list[str]]:
    return [json.loads(line)["argv"] for line in log_path.read_text(encoding="utf-8").splitlines()]


def _run_rollback(app_root: Path, target: Path | None, bin_dir: Path) -> subprocess.CompletedProcess[str]:
    env = _clean_ops_env(APP_ROOT=app_root, PATH=f"{bin_dir}:{os.environ['PATH']}")
    command = ["bash", str(ROOT / "scripts/rollback.sh")]
    if target is not None:
        command.append(str(target))
    return subprocess.run(
        command,
        cwd=ROOT.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _run_deploy(app_root: Path, release_name: str, source_dir: Path, bin_dir: Path) -> subprocess.CompletedProcess[str]:
    env = _clean_ops_env(
        APP_ROOT=app_root,
        RELEASE_NAME=release_name,
        SOURCE_DIR=source_dir,
        PATH=f"{bin_dir}:{os.environ['PATH']}",
    )
    return subprocess.run(
        ["bash", str(ROOT / "scripts/deploy.sh")],
        cwd=ROOT.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _install_deploy_rsync(bin_dir: Path, event_log: Path) -> None:
    _write_executable(
        bin_dir / "rsync",
        f"""#!/usr/bin/env bash
set -euo pipefail
printf 'rsync|args=%s\\n' "$*" >> {shlex.quote(str(event_log))}
dest="${{@: -1}}"
mkdir -p "$dest/powerai-hot/scripts"
cp -a {shlex.quote(str(ROOT))}/docker-compose.yml "$dest/powerai-hot/docker-compose.yml"
cp -a {shlex.quote(str(ROOT))}/scripts/backup.sh "$dest/powerai-hot/scripts/backup.sh"
""",
    )


def _install_deploy_docker(
    bin_dir: Path,
    event_log: Path,
    *,
    fail_pg_dump: bool = False,
    migration_gate_passed: bool = True,
) -> None:
    pg_dump_failure = "exit 91" if fail_pg_dump else "printf 'mock dump data\\n'; exit 0"
    gate = "true" if migration_gate_passed else "false"
    _write_executable(
        bin_dir / "docker",
        f"""#!/usr/bin/env bash
set -euo pipefail
printf 'docker|tag=%s|label=%s|cwd=%s|args=%s\\n' "${{IMAGE_TAG:-}}" "${{BACKUP_LABEL:-}}" "$PWD" "$*" >> {shlex.quote(str(event_log))}
if [[ "$*" == *"printenv POSTGRES_USER"* ]]; then
  printf 'app_user\\n'
  exit 0
fi
if [[ "$*" == *"printenv POSTGRES_DB"* ]]; then
  printf 'app_db\\n'
  exit 0
fi
if [[ "$*" == *"pg_dump"* ]]; then
  {pg_dump_failure}
fi
if [[ "$*" == *"jobs.migrate_sqlite"* ]]; then
  printf '{{"gate_passed": {gate}}}\\n'
fi
""",
    )


def _install_successful_curl(bin_dir: Path) -> None:
    _write_executable(bin_dir / "curl", "#!/usr/bin/env bash\nexit 0\n")


def _event_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def _event_index(lines: list[str], needle: str) -> int:
    for index, line in enumerate(lines):
        if needle in line:
            return index
    raise AssertionError(f"missing event containing {needle!r} in:\n" + "\n".join(lines))


def _assert_no_volume_delete(log: str) -> None:
    assert "docker volume rm" not in log
    assert " volume rm" not in log
    assert " --volumes" not in log
    assert not re.search(r"\bdown\b.*(?:\s-v\b|--volumes\b)", log)


def _assert_no_secret_leak(text: str, secret: str, label: str) -> None:
    if secret in text:
        raise AssertionError(f"secret leaked in {label}")


def _reserved_url_chars_secret() -> str:
    return "".join(("Secr", "@", "t", ":/", "%", "#", "Value"))


def _compose_service_block(compose: str, service: str) -> str:
    match = re.search(rf"^  {re.escape(service)}:\n(?P<body>.*?)(?=^  \w|^volumes:)", compose, re.MULTILINE | re.DOTALL)
    assert match is not None, f"missing compose service: {service}"
    return match.group("body")


def _mem_limit_mib(service_block: str) -> int:
    match = re.search(r"^\s+mem_limit:\s+(\d+)m\s*$", service_block, re.MULTILINE)
    assert match is not None
    return int(match.group(1))


def test_compose_production_defaults_are_safe():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    db_block = compose.split("  db:", 1)[1].split("  backend:", 1)[0]
    assert "ports:" not in db_block
    assert "POSTGRES_PASSWORD: powerai" not in compose
    assert "127.0.0.1:8080:80" in compose
    assert 'AUTO_CRAWL_ENABLED: "false"' in compose
    assert "restart: unless-stopped" in compose
    assert "max-size" in compose


def test_backend_dockerfile_installs_hashed_lock_from_configurable_pypi_index():
    dockerfile = (ROOT / "backend/Dockerfile").read_text(encoding="utf-8")
    install = re.search(r"RUN\s+pip install(?P<args>(?:[^\n\\]|\\\n\s*)*)", dockerfile)
    assert install is not None
    args = install.group("args").replace("\\\n", " ")

    assert "ARG PIP_INDEX_URL=https://pypi.org/simple" in dockerfile
    assert '--index-url "$PIP_INDEX_URL"' in args
    assert "--require-hashes" in args
    assert "--no-cache-dir" in args
    assert "-r requirements.lock" in args
    assert "trusted-host" not in dockerfile
    assert "--extra-index-url" not in dockerfile
    assert "--cert false" not in dockerfile
    assert "PIP_TRUSTED_HOST" not in dockerfile

    retries = re.search(r"--retries\s+(\d+)", args)
    timeout = re.search(r"--timeout\s+(\d+)", args)
    assert retries is not None
    assert timeout is not None
    assert int(retries.group(1)) >= 3
    assert int(timeout.group(1)) >= 30


def test_backend_dockerfile_is_legacy_builder_compatible_and_avoids_apt():
    dockerfile = (ROOT / "backend/Dockerfile").read_text(encoding="utf-8")
    failures = []

    expected_from = f"FROM python:3.12-slim@{PYTHON_312_SLIM_DIGEST}"
    if not re.search(rf"^{re.escape(expected_from)}$", dockerfile, re.MULTILINE):
        failures.append(f"Dockerfile must use pinned Python 3.12 slim base: {expected_from}")
    if "ARG PIP_INDEX_URL=https://pypi.org/simple" not in dockerfile:
        failures.append("Dockerfile must keep configurable PIP_INDEX_URL default")
    if "COPY requirements.txt requirements.lock ./" not in dockerfile:
        failures.append("multi-source COPY must target ./ for Docker legacy builder")
    if re.search(r"\bapt-get\b|\bapt\s", dockerfile):
        failures.append("Dockerfile must not run apt-get or apt")
    if "RUN useradd --create-home --shell /usr/sbin/nologin appuser" not in dockerfile:
        failures.append("Dockerfile must call useradd directly from python:3.12-slim")

    install = re.search(r"RUN\s+pip install(?P<args>(?:[^\n\\]|\\\n\s*)*)", dockerfile)
    if install is None:
        failures.append("Dockerfile must install requirements.lock with pip")
    else:
        args = install.group("args").replace("\\\n", " ")
        if "--require-hashes" not in args or "-r requirements.lock" not in args:
            failures.append("pip install must use the hash-locked requirements.lock")

    if not re.search(r"^USER appuser$", dockerfile, re.MULTILINE):
        failures.append("Dockerfile must switch to non-root USER appuser")
    if (
        'CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", '
        '"--workers", "1", "--no-proxy-headers"]'
    ) not in dockerfile:
        failures.append("Dockerfile must keep the production uvicorn CMD")

    assert not failures, "\n".join(failures)


def test_frontend_dockerfile_uses_pinned_node_base_for_all_three_stages():
    dockerfile = (ROOT / "frontend/Dockerfile").read_text(encoding="utf-8")
    expected_base = f"node:20-alpine@{NODE_20_ALPINE_DIGEST}"

    from_lines = re.findall(r"^FROM\s+(\S+)\s+AS\s+(\S+)$", dockerfile, re.MULTILINE)

    assert from_lines == [
        (expected_base, "deps"),
        (expected_base, "builder"),
        (expected_base, "runner"),
    ]
    assert re.search(r"^USER node$", dockerfile, re.MULTILINE)


def test_compose_uses_pinned_runtime_base_images_and_keeps_memory_limits():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    expected_images = {
        "db": f"postgres:16-alpine@{POSTGRES_16_ALPINE_DIGEST}",
        "nginx": f"nginx:1.27-alpine@{NGINX_127_ALPINE_DIGEST}",
    }
    for service, image in expected_images.items():
        block = _compose_service_block(compose, service)
        image_lines = re.findall(r"^\s+image:\s+(\S+)\s*$", block, re.MULTILINE)
        assert image_lines == [image]
        assert "@sha256:" in image_lines[0]

    expected_mem_limits = {
        "backend": 1024,
        "db": 768,
        "frontend": 768,
        "nginx": 128,
    }
    for service, limit in expected_mem_limits.items():
        assert _mem_limit_mib(_compose_service_block(compose, service)) == limit


def test_compose_backend_build_arg_allows_explicit_pypi_index_override():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    backend_block = compose.split("  backend:", 1)[1].split("  frontend:", 1)[0]
    assert "args:" in backend_block
    assert "PIP_INDEX_URL: ${PIP_INDEX_URL:-https://pypi.org/simple}" in backend_block


def test_requirements_lock_is_hash_pinned_and_covers_direct_dependencies():
    lock_path = ROOT / "backend/requirements.lock"
    assert lock_path.exists()
    lock_text = lock_path.read_text(encoding="utf-8")

    forbidden_patterns = (
        "-e ",
        "git+",
        "hg+",
        "svn+",
        "bzr+",
        "://",
        "--trusted-host",
        "--extra-index-url",
    )
    for pattern in forbidden_patterns:
        assert pattern not in lock_text

    requirement_blocks = _lock_requirement_blocks(lock_text)
    assert requirement_blocks
    for block in requirement_blocks:
        assert "==" in block
        assert "--hash=sha256:" in block

    locked_names = {_requirement_entry_name(block) for block in requirement_blocks}
    assert _requirements_txt_direct_names() <= locked_names
    assert "sgmllib3k" in locked_names


def test_apscheduler_is_a_pinned_direct_runtime_requirement_in_the_hash_lock():
    requirements = (ROOT / "backend/requirements.txt").read_text(encoding="utf-8").splitlines()
    assert "APScheduler==3.10.4" in requirements

    lock_text = (ROOT / "backend/requirements.lock").read_text(encoding="utf-8")
    blocks = _lock_requirement_blocks(lock_text)
    apscheduler_blocks = [block for block in blocks if _requirement_entry_name(block) == "apscheduler"]
    assert len(apscheduler_blocks) == 1
    assert apscheduler_blocks[0].startswith("apscheduler==3.10.4 ")
    assert "--hash=sha256:" in apscheduler_blocks[0]


def test_secure_pip_is_direct_hash_locked_and_inherited_by_runtime_and_dev_installs():
    requirements = (ROOT / "backend/requirements.txt").read_text(encoding="utf-8").splitlines()
    assert "pip==26.1.2" in requirements

    lock_text = (ROOT / "backend/requirements.lock").read_text(encoding="utf-8")
    blocks = _lock_requirement_blocks(lock_text)
    pip_blocks = [block for block in blocks if _requirement_entry_name(block) == "pip"]
    assert len(pip_blocks) == 1
    assert pip_blocks[0].startswith("pip==26.1.2 ")
    assert "--hash=sha256:" in pip_blocks[0]

    dev_requirements = (ROOT / "backend/requirements-dev.txt").read_text(encoding="utf-8").splitlines()
    assert "-r requirements.txt" in dev_requirements

    dockerfile = (ROOT / "backend/Dockerfile").read_text(encoding="utf-8")
    assert "--require-hashes -r requirements.lock" in dockerfile


def test_runtime_requirements_are_lf_only_and_retain_exact_pins_and_order():
    requirements_bytes = (ROOT / "backend/requirements.txt").read_bytes()
    assert b"\r" not in requirements_bytes
    assert requirements_bytes.decode("utf-8").splitlines() == EXPECTED_RUNTIME_REQUIREMENTS


def test_tracked_or_archived_executable_inventory_is_exactly_six_bash_entrypoints():
    repository_root = ROOT.parent
    tracked = subprocess.run(
        ["git", "-C", str(repository_root), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if tracked.returncode == 0:
        relative_paths = [Path(value.decode("utf-8")) for value in tracked.stdout.split(b"\0") if value]
    else:
        relative_paths = [path.relative_to(repository_root) for path in repository_root.rglob("*")]

    executable_paths = {
        path.as_posix()
        for path in relative_paths
        if (repository_root / path).is_file()
        and (repository_root / path).stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    }
    assert executable_paths == EXPECTED_EXECUTABLE_PATHS

    for relative_path in EXPECTED_EXECUTABLE_PATHS:
        script = repository_root / relative_path
        assert script.read_bytes().startswith(b"#!/usr/bin/env bash\n")


def test_systemd_timers_use_flock_and_job_wrapper():
    service = (ROOT / "deploy/systemd/e-ai-job@.service").read_text(encoding="utf-8")
    backup = (ROOT / "deploy/systemd/e-ai-backup.service").read_text(encoding="utf-8")
    job_lock = re.search(r"ExecStart=/usr/bin/flock -n (\S+) ", service)
    backup_lock = re.search(r"ExecStart=/usr/bin/flock -n (\S+) ", backup)

    assert job_lock is not None
    assert backup_lock is not None
    assert job_lock.group(1) == backup_lock.group(1) == "/opt/e-ai/releases/.operations.lock"
    assert "/run/e-ai-%i.lock" not in service
    assert "/run/e-ai-backup.lock" not in backup
    assert "flock" in service
    assert "scripts/run-job.sh %i" in service
    assert "python -m jobs.%i" not in service
    assert "WorkingDirectory=/opt/e-ai/current/powerai-hot" in service


def test_deploy_and_rollback_scripts_share_nonblocking_operations_lock():
    deploy = (ROOT / "scripts/deploy.sh").read_text(encoding="utf-8")
    rollback = (ROOT / "scripts/rollback.sh").read_text(encoding="utf-8")

    for script in (deploy, rollback):
        assert 'OPERATIONS_LOCK="${OPERATIONS_LOCK:-$APP_ROOT/releases/.operations.lock}"' in script
        assert re.search(r"exec\s+\d+>\"\$OPERATIONS_LOCK\"", script)
        assert re.search(r"flock\s+-n\s+\d+", script)
        assert "/run/e-ai-operations.lock" not in script


def test_systemd_units_verify_and_timers_embed_shanghai_timezone():
    if not shutil.which("systemd-analyze"):
        return
    units = sorted((ROOT / "deploy/systemd").glob("*.service")) + sorted((ROOT / "deploy/systemd").glob("*.timer"))
    completed = subprocess.run(
        ["systemd-analyze", "verify", *map(str, units)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert "Unknown key" not in completed.stderr
    assert completed.returncode == 0, completed.stderr

    expected = {
        "e-ai-backup.timer": "OnCalendar=*-*-* 03:30:00 Asia/Shanghai",
        "e-ai-papers.timer": "OnCalendar=*-*-* 06:10:00 Asia/Shanghai",
        "e-ai-digest.timer": "OnCalendar=*-*-* 08:00:00 Asia/Shanghai",
        "e-ai-news.timer": "OnCalendar=*-*-* 00/2:00:00 Asia/Shanghai",
    }
    for name, expression in expected.items():
        timer = (ROOT / "deploy/systemd" / name).read_text(encoding="utf-8")
        assert "TimeZone=" not in timer
        assert expression in timer
        calendar = subprocess.run(
            ["systemd-analyze", "calendar", expression.removeprefix("OnCalendar=")],
            text=True,
            capture_output=True,
            check=False,
        )
        assert calendar.returncode == 0, calendar.stderr


def test_backup_timer_calls_pg_dump_script():
    timer = (ROOT / "deploy/systemd/e-ai-backup.timer").read_text(encoding="utf-8")
    assert "Unit=e-ai-backup.service" in timer
    service = (ROOT / "deploy/systemd/e-ai-backup.service").read_text(encoding="utf-8")
    assert "scripts/backup.sh" in service
    assert "pg_dump" in (ROOT / "scripts/backup.sh").read_text(encoding="utf-8")


def test_deploy_scripts_have_shell_safety_and_do_not_delete_volumes():
    for name in ("deploy.sh", "rollback.sh", "backup.sh", "restore-check.sh"):
        text = (ROOT / f"scripts/{name}").read_text(encoding="utf-8")
        assert "set -euo pipefail" in text
        assert "docker volume rm" not in text
        assert "rm -rf /opt/e-ai/data" not in text


def test_deploy_release_is_immutable_and_excludes_local_artifacts():
    deploy = (ROOT / "scripts/deploy.sh").read_text(encoding="utf-8")
    assert '[[ -e "$RELEASE_DIR" ]]' in deploy
    assert "IMAGE_TAG=$RELEASE_NAME" in deploy
    assert "--exclude '.hermes'" in deploy
    assert "--exclude '.pytest_cache'" in deploy
    assert "--exclude '.venv'" in deploy
    assert "--exclude '*.log'" in deploy
    assert "--delete" not in deploy
    assert "MIGRATE_SQLITE_SOURCE" in deploy
    assert "jobs.migrate_sqlite" in deploy
    assert "/migration/source.sqlite" in deploy


def test_deploy_existing_release_takes_predeploy_postgres_backup_before_candidate_build(tmp_path):
    app_root = tmp_path / "app"
    release_name = "20260717T010203Z"
    previous_name = "20260716T010203Z"
    previous = _make_release(app_root, previous_name)
    current = app_root / "current"
    current.symlink_to(previous)
    secrets = app_root / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "backend.env").write_text("DEBUG=false\n", encoding="utf-8")
    (secrets / "postgres_password.txt").write_text("dummy", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    event_log = tmp_path / "events.log"
    _install_deploy_rsync(bin_dir, event_log)
    _install_deploy_docker(bin_dir, event_log)
    _install_successful_curl(bin_dir)

    env = _clean_ops_env(
        APP_ROOT=app_root,
        RELEASE_NAME=release_name,
        SOURCE_DIR=ROOT.parent,
        IMAGE_TAG="poisoned-inherited-tag",
        PATH=f"{bin_dir}:{os.environ['PATH']}",
    )
    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/deploy.sh")],
        cwd=ROOT.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    lines = _event_lines(event_log)
    rsync_index = _event_index(lines, "rsync|")
    pg_dump_index = _event_index(lines, "pg_dump")
    build_index = _event_index(lines, f"tag={release_name}|label=|cwd={app_root / 'releases' / release_name / 'powerai-hot'}|args=compose")
    assert rsync_index < pg_dump_index < build_index
    backup_line = lines[pg_dump_index]
    assert f"tag={previous_name}" in backup_line
    assert f"label=before_{release_name}" in backup_line
    assert f"cwd={app_root / 'current/powerai-hot'}" in backup_line
    assert "poisoned-inherited-tag" not in backup_line
    assert "backup written:" in completed.stdout
    assert current.resolve() == (app_root / "releases" / release_name).resolve()


def test_deploy_predeploy_postgres_backup_failure_blocks_candidate_side_effects(tmp_path):
    app_root = tmp_path / "app"
    release_name = "20260717T010204Z"
    previous = _make_release(app_root, "20260716T010203Z")
    current = app_root / "current"
    current.symlink_to(previous)
    secrets = app_root / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "backend.env").write_text("DEBUG=false\n", encoding="utf-8")
    (secrets / "postgres_password.txt").write_text("dummy", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    event_log = tmp_path / "events.log"
    _install_deploy_rsync(bin_dir, event_log)
    _install_deploy_docker(bin_dir, event_log, fail_pg_dump=True)
    _install_successful_curl(bin_dir)

    completed = _run_deploy(app_root, release_name, ROOT.parent, bin_dir)

    assert completed.returncode != 0
    assert current.resolve() == previous.resolve()
    assert (app_root / "releases" / release_name).exists()
    lines = _event_lines(event_log)
    assert any("pg_dump" in line for line in lines)
    candidate_events = [line for line in lines if f"tag={release_name}" in line]
    assert not any(" build" in line or " up -d" in line or "jobs.migrate_sqlite" in line for line in candidate_events)
    assert not any("volume rm" in line or "--volumes" in line or re.search(r"\bdown\b.*\s-v\b", line) for line in lines)


def test_deploy_first_sqlite_migration_copies_legacy_db_before_any_docker(tmp_path):
    app_root = tmp_path / "app"
    release_name = "20260717T010205Z"
    secrets = app_root / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "backend.env").write_text("DEBUG=false\n", encoding="utf-8")
    (secrets / "postgres_password.txt").write_text("dummy", encoding="utf-8")
    source_db = tmp_path / "legacy.sqlite"
    source_bytes = b"SQLite format 3\x00legacy rows"
    source_db.write_bytes(source_bytes)
    source_stat = source_db.stat()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    expected_backup = app_root / f"backups/legacy_sqlite_before_{release_name}.sqlite"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    event_log = tmp_path / "events.log"
    _install_deploy_rsync(bin_dir, event_log)
    _write_executable(
        bin_dir / "docker",
        f"""#!/usr/bin/env bash
set -euo pipefail
if [[ ! -f {shlex.quote(str(expected_backup))} ]]; then
  printf 'legacy backup missing before first docker\\n' >&2
  exit 77
fi
printf 'docker|tag=%s|cwd=%s|args=%s\\n' "${{IMAGE_TAG:-}}" "$PWD" "$*" >> {shlex.quote(str(event_log))}
if [[ "$*" == *"jobs.migrate_sqlite"* ]]; then
  printf '{{"gate_passed": true}}\\n'
fi
""",
    )
    _install_successful_curl(bin_dir)

    env = _clean_ops_env(
        APP_ROOT=app_root,
        RELEASE_NAME=release_name,
        SOURCE_DIR=ROOT.parent,
        PATH=f"{bin_dir}:{os.environ['PATH']}",
    )
    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/deploy.sh"), "--migrate-sqlite", str(source_db)],
        cwd=ROOT.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert expected_backup.read_bytes() == source_bytes
    assert hashlib.sha256(expected_backup.read_bytes()).hexdigest() == source_hash
    assert source_db.read_bytes() == source_bytes
    assert source_db.stat().st_mtime_ns == source_stat.st_mtime_ns
    assert stat.S_IMODE(expected_backup.stat().st_mode) & 0o337 == 0
    sha_file = Path(f"{expected_backup}.sha256")
    assert sha_file.exists()
    assert sha_file.read_text(encoding="utf-8") == f"{source_hash}  {expected_backup.name}\n"
    assert _event_lines(event_log)
    assert (app_root / "current").resolve() == (app_root / "releases" / release_name).resolve()


def test_deploy_first_sqlite_backup_copy_failure_blocks_docker_and_current(tmp_path):
    app_root = tmp_path / "app"
    release_name = "20260717T010206Z"
    secrets = app_root / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "backend.env").write_text("DEBUG=false\n", encoding="utf-8")
    (secrets / "postgres_password.txt").write_text("dummy", encoding="utf-8")
    backups = app_root / "backups"
    backups.mkdir(parents=True)
    backups.chmod(0o555)
    source_db = tmp_path / "legacy.sqlite"
    source_db.write_bytes(b"SQLite format 3\x00legacy rows")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    event_log = tmp_path / "events.log"
    _install_deploy_rsync(bin_dir, event_log)
    _install_deploy_docker(bin_dir, event_log)
    _install_successful_curl(bin_dir)
    try:
        env = _clean_ops_env(
            APP_ROOT=app_root,
            RELEASE_NAME=release_name,
            SOURCE_DIR=ROOT.parent,
            PATH=f"{bin_dir}:{os.environ['PATH']}",
        )
        completed = subprocess.run(
            ["bash", str(ROOT / "scripts/deploy.sh"), "--migrate-sqlite", str(source_db)],
            cwd=ROOT.parent,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        backups.chmod(0o755)

    assert completed.returncode != 0
    assert not any(line.startswith("docker|") for line in _event_lines(event_log))
    assert not (app_root / "current").exists()


def test_deploy_first_sqlite_backup_final_sha_move_failure_cleans_partial_backup(tmp_path):
    app_root = tmp_path / "app"
    release_name = "20260717T010208Z"
    secrets = app_root / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "backend.env").write_text("DEBUG=false\n", encoding="utf-8")
    (secrets / "postgres_password.txt").write_text("dummy", encoding="utf-8")
    source_db = tmp_path / "legacy.sqlite"
    source_bytes = b"SQLite format 3\x00legacy rows"
    source_db.write_bytes(source_bytes)
    source_stat = source_db.stat()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    final = app_root / f"backups/legacy_sqlite_before_{release_name}.sqlite"
    final_sha = Path(f"{final}.sha256")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    event_log = tmp_path / "events.log"
    docker_log = tmp_path / "docker.log"
    mv_state = tmp_path / "mv-count"
    _install_deploy_rsync(bin_dir, event_log)
    _write_executable(
        bin_dir / "mv",
        f"""#!/usr/bin/env bash
set -euo pipefail
state={shlex.quote(str(mv_state))}
count=0
if [[ -f "$state" ]]; then
  count="$(cat "$state")"
fi
count=$((count + 1))
printf '%s\\n' "$count" > "$state"
if [[ "$count" -eq 1 ]]; then
  exec /usr/bin/mv "$@"
fi
exit 44
""",
    )
    _write_executable(
        bin_dir / "docker",
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "$@" >> {shlex.quote(str(docker_log))}
""",
    )
    _install_successful_curl(bin_dir)

    env = _clean_ops_env(
        APP_ROOT=app_root,
        RELEASE_NAME=release_name,
        SOURCE_DIR=ROOT.parent,
        PATH=f"{bin_dir}:{os.environ['PATH']}",
    )
    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/deploy.sh"), "--migrate-sqlite", str(source_db)],
        cwd=ROOT.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert not final.exists()
    assert not final_sha.exists()
    assert not list((app_root / "backups").glob(f".legacy_sqlite_before_{release_name}.*.sqlite"))
    assert not list((app_root / "backups").glob(f".legacy_sqlite_before_{release_name}.*.sha256"))
    assert not docker_log.exists()
    assert not (app_root / "current").exists()
    assert source_db.read_bytes() == source_bytes
    assert hashlib.sha256(source_db.read_bytes()).hexdigest() == source_hash
    assert source_db.stat().st_mtime_ns == source_stat.st_mtime_ns


def test_deploy_first_release_without_sqlite_source_skips_predeploy_data_backup(tmp_path):
    app_root = tmp_path / "app"
    release_name = "20260717T010207Z"
    secrets = app_root / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "backend.env").write_text("DEBUG=false\n", encoding="utf-8")
    (secrets / "postgres_password.txt").write_text("dummy", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    event_log = tmp_path / "events.log"
    _install_deploy_rsync(bin_dir, event_log)
    _install_deploy_docker(bin_dir, event_log)
    _install_successful_curl(bin_dir)

    completed = _run_deploy(app_root, release_name, ROOT.parent, bin_dir)

    assert completed.returncode == 0, completed.stderr
    lines = _event_lines(event_log)
    assert not any("pg_dump" in line for line in lines)
    assert not list((app_root / "backups").glob("legacy_sqlite_before_*.sqlite"))
    assert "no existing database; skipping predeploy data backup" in completed.stdout
    assert (app_root / "current").resolve() == (app_root / "releases" / release_name).resolve()


def test_deploy_rejects_sqlite_migration_when_current_release_exists_before_docker(tmp_path):
    app_root = tmp_path / "app"
    release_name = "20260717T010209Z"
    previous = _make_release(app_root, "20260716T010203Z")
    current = app_root / "current"
    current.symlink_to(previous)
    secrets = app_root / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "backend.env").write_text("DEBUG=false\n", encoding="utf-8")
    (secrets / "postgres_password.txt").write_text("dummy", encoding="utf-8")
    source_db = tmp_path / "legacy.sqlite"
    source_db.write_bytes(b"SQLite format 3\x00legacy rows")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    event_log = tmp_path / "events.log"
    _install_deploy_rsync(bin_dir, event_log)
    _install_deploy_docker(bin_dir, event_log)
    _install_successful_curl(bin_dir)

    env = _clean_ops_env(
        APP_ROOT=app_root,
        RELEASE_NAME=release_name,
        SOURCE_DIR=ROOT.parent,
        PATH=f"{bin_dir}:{os.environ['PATH']}",
    )
    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/deploy.sh"), "--migrate-sqlite", str(source_db)],
        cwd=ROOT.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "first deploy" in completed.stderr
    assert current.resolve() == previous.resolve()
    assert not (app_root / "releases" / release_name).exists()
    assert not _event_lines(event_log)


def test_backup_label_adds_safe_suffix_to_backup_filename(tmp_path):
    app_root = tmp_path / "app"
    release = _make_release(app_root, "20260716T010203Z")
    current = app_root / "current"
    current.symlink_to(release)
    secrets = app_root / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "backend.env").write_text("DEBUG=false\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    event_log = tmp_path / "events.log"
    _install_deploy_docker(bin_dir, event_log)

    env = _clean_ops_env(
        APP_ROOT=app_root,
        BACKUP_LABEL="before_release-20260717.1",
        PATH=f"{bin_dir}:{os.environ['PATH']}",
    )
    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/backup.sh")],
        cwd=ROOT.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    backups = list((app_root / "backups").glob("powerai_hot_*_before_release-20260717.1.sql.gz"))
    assert len(backups) == 1
    assert re.fullmatch(r"powerai_hot_\d{8}T\d{6}Z_before_release-20260717\.1\.sql\.gz", backups[0].name)
    assert f"backup written: {backups[0]}" in completed.stdout
    assert any("pg_dump" in line for line in _event_lines(event_log))


def test_backup_rejects_unsafe_label_before_pg_dump(tmp_path):
    app_root = tmp_path / "app"
    release = _make_release(app_root, "20260716T010203Z")
    current = app_root / "current"
    current.symlink_to(release)
    secrets = app_root / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "backend.env").write_text("DEBUG=false\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    event_log = tmp_path / "events.log"
    _install_deploy_docker(bin_dir, event_log)

    env = _clean_ops_env(APP_ROOT=app_root, BACKUP_LABEL="../bad", PATH=f"{bin_dir}:{os.environ['PATH']}")
    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/backup.sh")],
        cwd=ROOT.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "BACKUP_LABEL" in completed.stderr
    assert not any("pg_dump" in line for line in _event_lines(event_log))


def test_deploy_rejects_non_absolute_sqlite_source_before_docker(tmp_path):
    app_root = tmp_path / "app"
    secrets = app_root / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "backend.env").write_text("DEBUG=false\n", encoding="utf-8")
    (secrets / "postgres_password.txt").write_text("dummy", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"
    _write_executable(bin_dir / "docker", f"#!/usr/bin/env bash\necho \"$@\" >> {docker_log}\n")
    env = {
        **os.environ,
        "APP_ROOT": str(app_root),
        "RELEASE_NAME": "20260717T000000Z",
        "SOURCE_DIR": str(ROOT.parent),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
    }

    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/deploy.sh"), "--migrate-sqlite", "relative.db"],
        cwd=ROOT.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "absolute" in completed.stderr
    assert not docker_log.exists()


@pytest.mark.skipif(fcntl is None, reason="POSIX fcntl is required for lock contention")
def test_deploy_fails_before_side_effects_when_operations_lock_is_busy(tmp_path):
    app_root = tmp_path / "app"
    release_name = "20260717T000003Z"
    previous = _make_release(app_root, "20260716T000000Z")
    current = app_root / "current"
    current.symlink_to(previous)
    secrets = app_root / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "backend.env").write_text("DEBUG=false\n", encoding="utf-8")
    (secrets / "postgres_password.txt").write_text("dummy", encoding="utf-8")
    lock_path = app_root / "releases/.operations.lock"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"
    rsync_log = tmp_path / "rsync.log"

    _write_executable(
        bin_dir / "rsync",
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "$@" >> {shlex.quote(str(rsync_log))}
dest="${{@: -1}}"
mkdir -p "$dest/powerai-hot"
cp -a {ROOT}/docker-compose.yml "$dest/powerai-hot/docker-compose.yml"
""",
    )
    _write_executable(
        bin_dir / "docker",
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "$@" >> {shlex.quote(str(docker_log))}
""",
    )
    _write_executable(bin_dir / "curl", "#!/usr/bin/env bash\nexit 0\n")

    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        completed = _run_deploy(app_root, release_name, ROOT.parent, bin_dir)

    assert completed.returncode != 0
    assert "busy" in completed.stderr.lower()
    assert current.resolve() == previous.resolve()
    assert not docker_log.exists()
    assert not rsync_log.exists()
    assert not (app_root / "releases" / release_name).exists()


def test_deploy_sqlite_migration_mounts_single_file_readonly_and_waits_for_gate(tmp_path):
    app_root = tmp_path / "app"
    secrets = app_root / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "backend.env").write_text("DEBUG=false\n", encoding="utf-8")
    (secrets / "postgres_password.txt").write_text("dummy", encoding="utf-8")
    source_db = tmp_path / "legacy.sqlite"
    source_db.write_bytes(b"SQLite format 3\x00")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"
    rsync_log = tmp_path / "rsync.log"

    _write_executable(
        bin_dir / "rsync",
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "$@" >> {rsync_log}
dest="${{@: -1}}"
mkdir -p "$dest/powerai-hot"
cp -a {ROOT}/docker-compose.yml "$dest/powerai-hot/docker-compose.yml"
mkdir -p "$dest/powerai-hot/scripts"
""",
    )
    _write_executable(
        bin_dir / "docker",
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "$@" >> {docker_log}
if [[ "$*" == *"jobs.migrate_sqlite"* ]]; then
  printf '{{"gate_passed": true}}\\n'
fi
""",
    )
    _write_executable(bin_dir / "curl", "#!/usr/bin/env bash\nexit 0\n")

    env = {
        **os.environ,
        "APP_ROOT": str(app_root),
        "RELEASE_NAME": "20260717T000001Z",
        "SOURCE_DIR": str(ROOT.parent),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
    }

    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/deploy.sh"), "--migrate-sqlite", str(source_db)],
        cwd=ROOT.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    log = docker_log.read_text(encoding="utf-8")
    assert f"{source_db}:/migration/source.sqlite:ro" in log
    assert "--user 0:0" in log
    assert "jobs.migrate_sqlite --source /migration/source.sqlite" in log
    assert f"{source_db.parent}:/migration" not in log
    assert (app_root / "current").resolve() == (app_root / "releases/20260717T000001Z").resolve()


def test_deploy_does_not_switch_current_when_sqlite_gate_fails(tmp_path):
    app_root = tmp_path / "app"
    previous = app_root / "releases/previous"
    previous.mkdir(parents=True)
    current = app_root / "current"
    current.symlink_to(previous)
    secrets = app_root / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "backend.env").write_text("DEBUG=false\n", encoding="utf-8")
    (secrets / "postgres_password.txt").write_text("dummy", encoding="utf-8")
    source_db = tmp_path / "legacy.sqlite"
    source_db.write_bytes(b"SQLite format 3\x00")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(
        bin_dir / "rsync",
        f"""#!/usr/bin/env bash
set -euo pipefail
dest="${{@: -1}}"
mkdir -p "$dest/powerai-hot"
cp -a {ROOT}/docker-compose.yml "$dest/powerai-hot/docker-compose.yml"
""",
    )
    _write_executable(
        bin_dir / "docker",
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "$*" == *"jobs.migrate_sqlite"* ]]; then
  printf '{"gate_passed": false}\n'
fi
""",
    )
    _write_executable(bin_dir / "curl", "#!/usr/bin/env bash\nexit 0\n")
    env = {
        **os.environ,
        "APP_ROOT": str(app_root),
        "RELEASE_NAME": "failed",
        "SOURCE_DIR": str(ROOT.parent),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
    }

    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/deploy.sh"), "--migrate-sqlite", str(source_db)],
        cwd=ROOT.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert current.resolve() == previous.resolve()


def test_deploy_first_sqlite_migration_process_failure_stops_candidate_and_keeps_summary(tmp_path):
    app_root = tmp_path / "app"
    release_name = "20260717T010210Z"
    release = app_root / "releases" / release_name
    current = app_root / "current"
    secrets = app_root / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "backend.env").write_text("DEBUG=false\n", encoding="utf-8")
    (secrets / "postgres_password.txt").write_text("dummy", encoding="utf-8")
    source_db = tmp_path / "legacy.sqlite"
    source_db.write_bytes(b"SQLite format 3\x00legacy rows")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"
    event_log = tmp_path / "events.log"
    summary = '{"gate_passed": false, "blocking_failures": {"conflict_tables": ["articles"]}}'

    _install_deploy_rsync(bin_dir, event_log)
    _write_executable(
        bin_dir / "docker",
        f"""#!/usr/bin/env bash
set -euo pipefail
printf 'tag=%s cwd=%s args=%s\\n' "${{IMAGE_TAG:-}}" "$PWD" "$*" >> {shlex.quote(str(docker_log))}
if [[ "$*" == *"jobs.migrate_sqlite"* ]]; then
  printf '%s\\n' {shlex.quote(summary)}
  exit 1
fi
""",
    )
    _install_successful_curl(bin_dir)

    env = _clean_ops_env(
        APP_ROOT=app_root,
        RELEASE_NAME=release_name,
        SOURCE_DIR=ROOT.parent,
        PATH=f"{bin_dir}:{os.environ['PATH']}",
    )
    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/deploy.sh"), "--migrate-sqlite", str(source_db)],
        cwd=ROOT.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    log = docker_log.read_text(encoding="utf-8")
    down_lines = [line for line in log.splitlines() if re.search(r"\bcompose .* down$", line)]
    assert down_lines
    assert all(f"tag={release_name}" in line for line in down_lines)
    assert all(f"cwd={release / 'powerai-hot'}" in line for line in down_lines)
    _assert_no_volume_delete(log)
    combined_output = completed.stdout + completed.stderr
    assert '"gate_passed": false' in combined_output
    assert '"conflict_tables": ["articles"]' in combined_output
    assert not current.exists()
    assert not current.is_symlink()
    assert release.exists()


def test_deploy_first_release_health_failure_stops_candidate_and_clears_current(tmp_path):
    app_root = tmp_path / "app"
    secrets = app_root / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "backend.env").write_text("DEBUG=false\n", encoding="utf-8")
    (secrets / "postgres_password.txt").write_text("dummy", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"
    rsync_log = tmp_path / "rsync.log"
    release_name = "20260717T000002Z"
    failed_release = app_root / "releases" / release_name
    current = app_root / "current"

    _write_executable(
        bin_dir / "rsync",
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "$@" >> {rsync_log}
dest="${{@: -1}}"
mkdir -p "$dest/powerai-hot/scripts"
cp -a {ROOT}/docker-compose.yml "$dest/powerai-hot/docker-compose.yml"
cp -a {ROOT}/scripts/backup.sh "$dest/powerai-hot/scripts/backup.sh"
""",
    )
    _write_executable(
        bin_dir / "docker",
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "$@" >> {docker_log}
""",
    )
    _write_executable(bin_dir / "curl", "#!/usr/bin/env bash\nexit 1\n")
    _write_executable(bin_dir / "sleep", "#!/usr/bin/env bash\nexit 0\n")

    env = {
        **os.environ,
        "APP_ROOT": str(app_root),
        "RELEASE_NAME": release_name,
        "SOURCE_DIR": str(ROOT.parent),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
    }

    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/deploy.sh")],
        cwd=ROOT.parent,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    log = docker_log.read_text(encoding="utf-8")
    down_lines = [
        line
        for line in log.splitlines()
        if re.search(r"^compose .* down$", line)
    ]
    assert down_lines
    assert not any(" -v" in line or " --volumes" in line for line in down_lines)
    assert "volume rm" not in log
    assert not current.exists()
    assert not current.is_symlink()
    assert failed_release.exists()


def test_deploy_candidate_up_failure_restores_previous_release(tmp_path):
    app_root = tmp_path / "app"
    previous = _make_release(app_root, "previous")
    current = app_root / "current"
    current.symlink_to(previous)
    secrets = app_root / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "backend.env").write_text("DEBUG=false\n", encoding="utf-8")
    (secrets / "postgres_password.txt").write_text("dummy", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"
    curl_log = tmp_path / "curl.log"
    rsync_log = tmp_path / "rsync.log"
    release_name = "candidate"
    candidate = app_root / "releases" / release_name

    _write_executable(
        bin_dir / "rsync",
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "$@" >> {shlex.quote(str(rsync_log))}
dest="${{@: -1}}"
mkdir -p "$dest/powerai-hot/scripts"
cp -a {ROOT}/docker-compose.yml "$dest/powerai-hot/docker-compose.yml"
cp -a {ROOT}/scripts/backup.sh "$dest/powerai-hot/scripts/backup.sh"
""",
    )
    _write_executable(
        bin_dir / "docker",
        f"""#!/usr/bin/env bash
set -euo pipefail
printf 'tag=%s cwd=%s args=%s\\n' "${{IMAGE_TAG:-}}" "$PWD" "$*" >> {shlex.quote(str(docker_log))}
if [[ "$*" == *"printenv POSTGRES_USER"* ]]; then
  printf 'app_user\\n'
  exit 0
fi
if [[ "$*" == *"printenv POSTGRES_DB"* ]]; then
  printf 'app_db\\n'
  exit 0
fi
if [[ "$*" == *"pg_dump"* ]]; then
  printf 'mock dump\\n'
  exit 0
fi
if [[ "${{IMAGE_TAG:-}}" == "candidate" && "$*" == *" up -d"* ]]; then
  exit 33
fi
""",
    )
    _write_executable(
        bin_dir / "curl",
        f"""#!/usr/bin/env bash
set -euo pipefail
printf 'tag=%s cwd=%s args=%s\\n' "${{IMAGE_TAG:-}}" "$PWD" "$*" >> {shlex.quote(str(curl_log))}
if [[ "${{IMAGE_TAG:-}}" == "previous" ]]; then
  exit 0
fi
exit 1
""",
    )
    _write_executable(bin_dir / "sleep", "#!/usr/bin/env bash\nexit 0\n")

    completed = _run_deploy(app_root, release_name, ROOT.parent, bin_dir)

    assert completed.returncode != 0
    assert current.resolve() == previous.resolve()
    assert candidate.exists()
    log_lines = docker_log.read_text(encoding="utf-8").splitlines()
    assert [line.split(" args=", 1)[1] for line in log_lines] == [
        f"compose --env-file {app_root}/secrets/backend.env exec -T db printenv POSTGRES_USER",
        f"compose --env-file {app_root}/secrets/backend.env exec -T db printenv POSTGRES_DB",
        f"compose --env-file {app_root}/secrets/backend.env exec -T db pg_dump --no-owner --no-acl -U app_user app_db",
        f"compose --env-file {app_root}/secrets/backend.env build",
        f"compose --env-file {app_root}/secrets/backend.env up -d",
        f"compose --env-file {app_root}/secrets/backend.env build",
        f"compose --env-file {app_root}/secrets/backend.env up -d",
    ]
    assert [re.search(r"tag=(\S+)", line).group(1) for line in log_lines] == [
        "previous",
        "previous",
        "previous",
        "candidate",
        "candidate",
        "previous",
        "previous",
    ]
    assert f"cwd={app_root / 'current/powerai-hot'}" in log_lines[0]
    assert f"cwd={candidate / 'powerai-hot'}" in log_lines[3]
    assert f"cwd={previous / 'powerai-hot'}" in log_lines[5]
    curl_lines = curl_log.read_text(encoding="utf-8").splitlines()
    assert len(curl_lines) == 1
    assert "tag=previous" in curl_lines[0]
    _assert_no_volume_delete("\n".join(log_lines))


def test_deploy_first_release_up_failure_stops_candidate_and_clears_current(tmp_path):
    app_root = tmp_path / "app"
    secrets = app_root / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "backend.env").write_text("DEBUG=false\n", encoding="utf-8")
    (secrets / "postgres_password.txt").write_text("dummy", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"
    rsync_log = tmp_path / "rsync.log"
    release_name = "candidate"
    candidate = app_root / "releases" / release_name
    current = app_root / "current"

    _write_executable(
        bin_dir / "rsync",
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "$@" >> {shlex.quote(str(rsync_log))}
dest="${{@: -1}}"
mkdir -p "$dest/powerai-hot"
cp -a {ROOT}/docker-compose.yml "$dest/powerai-hot/docker-compose.yml"
""",
    )
    _write_executable(
        bin_dir / "docker",
        f"""#!/usr/bin/env bash
set -euo pipefail
printf 'tag=%s cwd=%s args=%s\\n' "${{IMAGE_TAG:-}}" "$PWD" "$*" >> {shlex.quote(str(docker_log))}
if [[ "${{IMAGE_TAG:-}}" == "candidate" && "$*" == *" up -d"* ]]; then
  exit 33
fi
""",
    )
    _write_executable(bin_dir / "curl", "#!/usr/bin/env bash\nexit 1\n")
    _write_executable(bin_dir / "sleep", "#!/usr/bin/env bash\nexit 0\n")

    completed = _run_deploy(app_root, release_name, ROOT.parent, bin_dir)

    assert completed.returncode != 0
    assert not current.exists()
    assert not current.is_symlink()
    assert candidate.exists()
    log_lines = docker_log.read_text(encoding="utf-8").splitlines()
    assert [line.split(" args=", 1)[1] for line in log_lines] == [
        f"compose --env-file {app_root}/secrets/backend.env build",
        f"compose --env-file {app_root}/secrets/backend.env up -d",
        f"compose --env-file {app_root}/secrets/backend.env down",
    ]
    assert [re.search(r"tag=(\S+)", line).group(1) for line in log_lines] == [
        "candidate",
        "candidate",
        "candidate",
    ]
    assert all(f"cwd={candidate / 'powerai-hot'}" in line for line in log_lines)
    _assert_no_volume_delete("\n".join(log_lines))


def test_run_job_wrapper_allowlist_and_release_environment(tmp_path):
    app_root = tmp_path / "opt/e-ai"
    release = app_root / "releases/20260717T010203Z/powerai-hot"
    release.mkdir(parents=True)
    secrets = app_root / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "backend.env").write_text("POSTGRES_USER=custom_user\nPOSTGRES_DB=custom_db\n", encoding="utf-8")
    current = app_root / "current"
    current.parent.mkdir(parents=True, exist_ok=True)
    current.symlink_to(release.parent)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_env = tmp_path / "docker.env"
    _write_executable(
        bin_dir / "docker",
        f"""#!/usr/bin/env bash
set -euo pipefail
printf 'IMAGE_TAG=%s\\n' "$IMAGE_TAG" > {docker_env}
printf 'BACKEND_ENV_FILE=%s\\n' "$BACKEND_ENV_FILE" >> {docker_env}
printf 'POSTGRES_PASSWORD_FILE=%s\\n' "$POSTGRES_PASSWORD_FILE" >> {docker_env}
printf 'COMPOSE_PROJECT_NAME=%s\\n' "$COMPOSE_PROJECT_NAME" >> {docker_env}
printf 'ARGS=%s\\n' "$*" >> {docker_env}
""",
    )
    env = {**os.environ, "APP_ROOT": str(app_root), "PATH": f"{bin_dir}:{os.environ['PATH']}"}

    ok = subprocess.run(
        ["bash", str(ROOT / "scripts/run-job.sh"), "news"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    bad = subprocess.run(
        ["bash", str(ROOT / "scripts/run-job.sh"), "bad.module"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert ok.returncode == 0, ok.stderr
    env_text = docker_env.read_text(encoding="utf-8")
    assert "IMAGE_TAG=20260717T010203Z" in env_text
    assert f"BACKEND_ENV_FILE={app_root}/secrets/backend.env" in env_text
    assert f"POSTGRES_PASSWORD_FILE={app_root}/secrets/postgres_password.txt" in env_text
    assert "COMPOSE_PROJECT_NAME=e-ai" in env_text
    assert f"ARGS=compose --env-file {app_root}/secrets/backend.env run --rm --no-deps jobs python -m jobs.news" in env_text
    assert bad.returncode != 0
    assert "unsupported job" in bad.stderr


def test_one_shot_jobs_fit_static_memory_contract_with_persistent_services():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    run_job = (ROOT / "scripts/run-job.sh").read_text(encoding="utf-8")
    persistent_limit_mib = sum(
        _mem_limit_mib(_compose_service_block(compose, service))
        for service in ("backend", "db", "frontend", "nginx")
    )

    assert persistent_limit_mib == 2688
    assert re.search(r"\bcompose run --rm --no-deps jobs\b", run_job)
    assert _mem_limit_mib(_compose_service_block(compose, "jobs")) == 512
    assert persistent_limit_mib + 512 == 3200
    assert 3200 < int(3.6 * 1024)


def test_rollback_rebuilds_target_release_before_up_and_checks_health():
    rollback = (ROOT / "scripts/rollback.sh").read_text(encoding="utf-8")
    assert "IMAGE_TAG=" in rollback
    assert "COMPOSE_PROJECT_NAME=e-ai" in rollback
    assert 'docker compose --env-file "$BACKEND_ENV_FILE" "$@"' in rollback
    assert "compose build" in rollback
    assert "compose up -d" in rollback
    assert "for _ in" in rollback
    assert "docker volume rm" not in rollback


def test_default_rollback_uses_direct_predecessor_of_current_release(tmp_path):
    def make_app(case: str, current_name: str) -> tuple[Path, dict[str, Path], Path, Path]:
        app_root = tmp_path / case / "app"
        releases = {name: _make_release(app_root, name) for name in ("010", "020", "030")}
        current = app_root / "current"
        current.symlink_to(releases[current_name])
        secrets = app_root / "secrets"
        secrets.mkdir(parents=True)
        (secrets / "backend.env").write_text("DEBUG=false\n", encoding="utf-8")
        (secrets / "postgres_password.txt").write_text("dummy", encoding="utf-8")
        bin_dir = tmp_path / case / "bin"
        bin_dir.mkdir()
        return app_root, releases, current, bin_dir

    def install_successful_commands(bin_dir: Path, docker_log: Path) -> None:
        _write_executable(
            bin_dir / "docker",
            f"""#!/usr/bin/env bash
set -euo pipefail
printf 'tag=%s cwd=%s args=%s\\n' "${{IMAGE_TAG:-}}" "$PWD" "$*" >> {shlex.quote(str(docker_log))}
""",
        )
        _write_executable(bin_dir / "curl", "#!/usr/bin/env bash\nexit 0\n")
        _write_executable(bin_dir / "sleep", "#!/usr/bin/env bash\nexit 0\n")

    for current_name, expected_name in (("030", "020"), ("020", "010")):
        app_root, releases, current, bin_dir = make_app(f"from-{current_name}", current_name)
        docker_log = tmp_path / f"from-{current_name}" / "docker.log"
        install_successful_commands(bin_dir, docker_log)

        completed = _run_rollback(app_root, None, bin_dir)

        assert completed.returncode == 0, completed.stderr
        assert current.resolve() == releases[expected_name].resolve()
        log = docker_log.read_text(encoding="utf-8")
        assert f"tag={expected_name}" in log
        assert f"cwd={releases[expected_name] / 'powerai-hot'}" in log
        _assert_no_volume_delete(log)

    app_root, releases, current, bin_dir = make_app("from-010", "010")
    docker_log = tmp_path / "from-010" / "docker.log"
    install_successful_commands(bin_dir, docker_log)

    completed = _run_rollback(app_root, None, bin_dir)

    assert completed.returncode != 0
    assert "predecessor" in completed.stderr.lower()
    assert current.resolve() == releases["010"].resolve()
    assert not docker_log.exists()


def test_rollback_target_build_failure_keeps_previous_current_and_does_not_up(tmp_path):
    app_root, previous, target = _make_rollback_app_root(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"
    target_hot = target / "powerai-hot"

    _write_executable(
        bin_dir / "docker",
        f"""#!/usr/bin/env bash
set -euo pipefail
printf 'tag=%s cwd=%s args=%s\\n' "${{IMAGE_TAG:-}}" "$PWD" "$*" >> {shlex.quote(str(docker_log))}
if [[ "${{IMAGE_TAG:-}}" == "target" && "$*" == *" build"* ]]; then
  exit 42
fi
""",
    )
    _write_executable(bin_dir / "curl", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(bin_dir / "sleep", "#!/usr/bin/env bash\nexit 0\n")

    completed = _run_rollback(app_root, target, bin_dir)

    assert completed.returncode != 0
    assert (app_root / "current").resolve() == previous.resolve()
    log = docker_log.read_text(encoding="utf-8")
    assert " up -d" not in log
    _assert_no_volume_delete(log)


def test_rollback_rejects_target_that_is_already_current_without_docker(tmp_path):
    app_root, previous, _target = _make_rollback_app_root(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"
    _write_executable(
        bin_dir / "docker",
        f"""#!/usr/bin/env bash
set -euo pipefail
printf 'args=%s\\n' "$*" >> {shlex.quote(str(docker_log))}
""",
    )
    _write_executable(bin_dir / "curl", "#!/usr/bin/env bash\nexit 0\n")

    completed = _run_rollback(app_root, previous, bin_dir)

    assert completed.returncode != 0
    assert "already current" in completed.stderr
    assert (app_root / "current").resolve() == previous.resolve()
    assert not docker_log.exists()


@pytest.mark.skipif(fcntl is None, reason="POSIX fcntl is required for lock contention")
def test_rollback_fails_before_side_effects_when_operations_lock_is_busy(tmp_path):
    app_root = tmp_path / "app"
    target = _make_release(app_root, "010")
    current_release = _make_release(app_root, "020")
    current = app_root / "current"
    current.symlink_to(current_release)
    secrets = app_root / "secrets"
    secrets.mkdir(parents=True)
    (secrets / "backend.env").write_text("DEBUG=false\n", encoding="utf-8")
    (secrets / "postgres_password.txt").write_text("dummy", encoding="utf-8")
    lock_path = app_root / "releases/.operations.lock"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"

    _write_executable(
        bin_dir / "docker",
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "$@" >> {shlex.quote(str(docker_log))}
""",
    )
    _write_executable(bin_dir / "curl", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(bin_dir / "sleep", "#!/usr/bin/env bash\nexit 0\n")

    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        completed = _run_rollback(app_root, target, bin_dir)

    assert completed.returncode != 0
    assert "busy" in completed.stderr.lower()
    assert current.resolve() == current_release.resolve()
    assert not docker_log.exists()


def test_rollback_target_health_failure_restores_previous_service_and_current(tmp_path):
    app_root, previous, target = _make_rollback_app_root(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"
    curl_log = tmp_path / "curl.log"
    previous_hot = previous / "powerai-hot"
    target_hot = target / "powerai-hot"

    _write_executable(
        bin_dir / "docker",
        f"""#!/usr/bin/env bash
set -euo pipefail
printf 'tag=%s cwd=%s args=%s\\n' "${{IMAGE_TAG:-}}" "$PWD" "$*" >> {shlex.quote(str(docker_log))}
""",
    )
    _write_executable(
        bin_dir / "curl",
        f"""#!/usr/bin/env bash
set -euo pipefail
printf 'cwd=%s args=%s\\n' "$PWD" "$*" >> {shlex.quote(str(curl_log))}
if [[ "${{IMAGE_TAG:-}}" == "previous" ]]; then
  exit 0
fi
exit 1
""",
    )
    _write_executable(bin_dir / "sleep", "#!/usr/bin/env bash\nexit 0\n")

    completed = _run_rollback(app_root, target, bin_dir)

    assert completed.returncode != 0
    assert (app_root / "current").resolve() == previous.resolve()
    log_lines = docker_log.read_text(encoding="utf-8").splitlines()
    assert [line.split(" args=", 1)[1] for line in log_lines] == [
        f"compose --env-file {app_root}/secrets/backend.env build",
        f"compose --env-file {app_root}/secrets/backend.env up -d",
        f"compose --env-file {app_root}/secrets/backend.env build",
        f"compose --env-file {app_root}/secrets/backend.env up -d",
    ]
    assert [re.search(r"tag=(\S+)", line).group(1) for line in log_lines] == [
        "target",
        "target",
        "previous",
        "previous",
    ]
    assert f"cwd={target_hot}" in log_lines[0]
    assert f"cwd={previous_hot}" in log_lines[2]
    _assert_no_volume_delete("\n".join(log_lines))


def test_rollback_target_up_failure_restores_previous_service_and_current(tmp_path):
    app_root, previous, target = _make_rollback_app_root(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"
    previous_hot = previous / "powerai-hot"
    target_hot = target / "powerai-hot"

    _write_executable(
        bin_dir / "docker",
        f"""#!/usr/bin/env bash
set -euo pipefail
printf 'tag=%s cwd=%s args=%s\\n' "${{IMAGE_TAG:-}}" "$PWD" "$*" >> {shlex.quote(str(docker_log))}
if [[ "${{IMAGE_TAG:-}}" == "target" && "$*" == *" up -d"* ]]; then
  exit 33
fi
""",
    )
    _write_executable(bin_dir / "curl", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(bin_dir / "sleep", "#!/usr/bin/env bash\nexit 0\n")

    completed = _run_rollback(app_root, target, bin_dir)

    assert completed.returncode != 0
    assert (app_root / "current").resolve() == previous.resolve()
    log_lines = docker_log.read_text(encoding="utf-8").splitlines()
    assert [line.split(" args=", 1)[1] for line in log_lines] == [
        f"compose --env-file {app_root}/secrets/backend.env build",
        f"compose --env-file {app_root}/secrets/backend.env up -d",
        f"compose --env-file {app_root}/secrets/backend.env build",
        f"compose --env-file {app_root}/secrets/backend.env up -d",
    ]
    assert [re.search(r"tag=(\S+)", line).group(1) for line in log_lines] == [
        "target",
        "target",
        "previous",
        "previous",
    ]
    assert f"cwd={target_hot}" in log_lines[0]
    assert f"cwd={previous_hot}" in log_lines[2]
    _assert_no_volume_delete("\n".join(log_lines))


def test_postgres_secret_preparation_uses_single_restricted_source():
    script = (ROOT / "scripts/prepare-secrets.sh").read_text(encoding="utf-8")
    assert "umask 077" in script
    assert "postgres_password.txt" in script
    assert "DATABASE_URL" in script
    assert "printf '%s'" in script
    assert "set -x" not in script
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password" in compose
    assert "postgres_password.txt" in compose


def test_prepare_secrets_url_encodes_credentials_without_rewriting_password(tmp_path):
    secret = _reserved_url_chars_secret()
    env = {
        **os.environ,
        "APP_ROOT": str(tmp_path / "app"),
        "POSTGRES_USER": "custom_user",
        "POSTGRES_DB": "custom_db",
        "POSTGRES_PASSWORD": secret,
    }

    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/prepare-secrets.sh")],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    _assert_no_secret_leak(completed.stdout, secret, "stdout")
    _assert_no_secret_leak(completed.stderr, secret, "stderr")

    backend_env = tmp_path / "app/secrets/backend.env"
    password_file = tmp_path / "app/secrets/postgres_password.txt"
    env_lines = dict(
        line.split("=", 1)
        for line in backend_env.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    parsed = make_url(env_lines["DATABASE_URL"])
    if parsed.username != "custom_user":
        raise AssertionError("DATABASE_URL username did not round-trip")
    if parsed.password != secret:
        raise AssertionError("DATABASE_URL password did not round-trip")
    if parsed.database != "custom_db":
        raise AssertionError("DATABASE_URL database did not round-trip")
    if password_file.read_text(encoding="utf-8") != secret:
        raise AssertionError("password file did not preserve the original password")
    assert stat.S_IMODE(backend_env.stat().st_mode) == 0o600
    assert stat.S_IMODE(password_file.stat().st_mode) == 0o600


def test_prepare_secrets_rejects_unsafe_postgres_identifiers_without_writing(tmp_path):
    env = {
        **os.environ,
        "APP_ROOT": str(tmp_path / "app"),
        "POSTGRES_USER": "bad-user",
        "POSTGRES_DB": "custom_db",
        "POSTGRES_PASSWORD": "not-secret-for-output",
    }

    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/prepare-secrets.sh")],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "POSTGRES_USER" in completed.stderr
    assert not (tmp_path / "app/secrets/backend.env").exists()
    assert not (tmp_path / "app/secrets/postgres_password.txt").exists()


def test_restore_check_rejects_schema_only_restore_even_when_all_tables_exist(tmp_path):
    completed, docker_log = _run_restore_check(
        tmp_path,
        restored_counts=_restore_counts(),
        present_tables=RESTORE_REQUIRED_TABLES,
    )

    assert completed.returncode != 0
    assert "meaningful" in completed.stderr
    calls = _docker_calls(docker_log)
    assert any("createdb" in call for call in calls)
    assert any("dropdb" in call for call in calls)


def test_restore_check_accepts_valid_restore_and_never_writes_or_drops_production(tmp_path):
    completed, docker_log = _run_restore_check(
        tmp_path,
        present_tables=RESTORE_REQUIRED_TABLES,
        production_before=_restore_counts(sources=4, articles=9, job_runs=1),
        production_after=_restore_counts(sources=4, articles=9, job_runs=1),
        restored_counts=_restore_counts(sources=2, articles=7),
        orphans={key: 0 for key in RESTORE_ORPHAN_KEYS},
    )

    assert completed.returncode == 0, completed.stderr
    assert "verified schema, meaningful data, relationships, and unchanged production counts" in completed.stdout

    calls = _docker_calls(docker_log)
    createdb_calls = [call for call in calls if "createdb" in call]
    dropdb_calls = [call for call in calls if "dropdb" in call]
    assert len(createdb_calls) == 1
    assert len(dropdb_calls) == 1
    created_temp_db = createdb_calls[0][-1]
    dropped_temp_db = dropdb_calls[0][-1]
    assert created_temp_db == dropped_temp_db
    assert created_temp_db.startswith("restore_check_")
    assert created_temp_db != "custom_db"

    psql_calls = [call for call in calls if "psql" in call]
    restore_calls = [call for call in psql_calls if "-c" not in call]
    assert len(restore_calls) == 1
    assert restore_calls[0][restore_calls[0].index("-d") + 1] == created_temp_db
    assert all(not ("dropdb" in call and "custom_db" == call[-1]) for call in calls)
    assert all(not ("createdb" in call and "custom_db" == call[-1]) for call in calls)
    assert all(
        call[call.index("-d") + 1] != "custom_db" or "-c" in call
        for call in psql_calls
        if "-d" in call
    )


def test_restore_check_rejects_any_restored_orphan_relationship(tmp_path):
    for orphan_key in RESTORE_ORPHAN_KEYS:
        completed, docker_log = _run_restore_check(
            tmp_path / orphan_key,
            present_tables=RESTORE_REQUIRED_TABLES,
            restored_counts=_restore_counts(sources=2, articles=7),
            orphans={orphan_key: 1},
        )

        assert completed.returncode != 0, orphan_key
        assert orphan_key in completed.stderr
        assert any("dropdb" in call for call in _docker_calls(docker_log))


def test_restore_check_rejects_when_production_counts_change_during_check(tmp_path):
    completed, docker_log = _run_restore_check(
        tmp_path,
        present_tables=RESTORE_REQUIRED_TABLES,
        production_before=_restore_counts(sources=4, articles=9),
        production_after=_restore_counts(sources=4, articles=10),
        restored_counts=_restore_counts(sources=2, articles=7),
    )

    assert completed.returncode != 0
    assert "production row count changed for articles" in completed.stderr
    assert any("dropdb" in call for call in _docker_calls(docker_log))


def test_restore_check_required_tables_and_sql_identifiers_are_hardcoded_allowlisted():
    restore = (ROOT / "scripts/restore-check.sh").read_text(encoding="utf-8")
    required_block = re.search(r"required_tables=\(\n(?P<body>.*?)\n\)", restore, re.DOTALL)
    assert required_block is not None
    required_tables = tuple(re.findall(r"^\s+([a-z_]+)\s*$", required_block.group("body"), re.MULTILINE))

    assert required_tables == RESTORE_REQUIRED_TABLES
    assert "job_runs" in required_tables
    assert "source_runs" in required_tables
    assert "quote_required_table()" in restore
    assert "case \"$1\" in" in restore
    for table in RESTORE_REQUIRED_TABLES:
        assert re.search(rf"\b{re.escape(table)}\b", restore)

    sql_lines = [line for line in restore.splitlines() if re.search(r"\b(SELECT|FROM|JOIN)\b", line)]
    for line in sql_lines:
        assert "$backup_file" not in line
        assert "$1" not in line
        assert not re.search(r"\b(?:FROM|JOIN)\s+\$(?:backup_file|postgres_db|temp_db|1)\b", line)


def test_production_scripts_pass_backend_env_file_to_compose_and_use_container_db_identity(tmp_path):
    app_root = tmp_path / "app"
    secrets = app_root / "secrets"
    secrets.mkdir(parents=True)
    backend_env = secrets / "backend.env"
    backend_env.write_text("POSTGRES_USER=custom_user\nPOSTGRES_DB=custom_db\n", encoding="utf-8")
    (secrets / "postgres_password.txt").write_text("dummy", encoding="utf-8")
    release = app_root / "releases/20260717T010203Z"
    release_app = release / "powerai-hot"
    release_app.mkdir(parents=True)
    (release_app / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    current = app_root / "current"
    current.symlink_to(release)
    backup_file = tmp_path / "backup.sql.gz"
    with gzip.open(backup_file, "wt", encoding="utf-8") as handle:
        handle.write("CREATE TABLE sources(id integer);\n")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"
    rsync_log = tmp_path / "rsync.log"
    _write_executable(
        bin_dir / "rsync",
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "$@" >> {rsync_log}
dest="${{@: -1}}"
mkdir -p "$dest/powerai-hot/scripts"
cp -a {ROOT}/docker-compose.yml "$dest/powerai-hot/docker-compose.yml"
cp -a {ROOT}/scripts/backup.sh "$dest/powerai-hot/scripts/backup.sh"
""",
    )
    _write_executable(
        bin_dir / "docker",
        f"""#!/usr/bin/env bash
set -euo pipefail
echo "$@" >> {docker_log}
case "$*" in
  *"printenv POSTGRES_USER"*) printf 'custom_user\\n' ;;
  *"printenv POSTGRES_DB"*) printf 'custom_db\\n' ;;
  *"pg_dump"*) printf 'CREATE TABLE sources(id integer);\\n' ;;
  *"information_schema.tables"*) printf '12\\n' ;;
  *"LEFT JOIN"*) printf '0\\n' ;;
  *"SELECT COUNT(*) FROM"*) printf '1\\n' ;;
esac
""",
    )
    _write_executable(bin_dir / "curl", "#!/usr/bin/env bash\nexit 0\n")

    env = {
        **os.environ,
        "APP_ROOT": str(app_root),
        "RELEASE_NAME": "20260717T111111Z",
        "SOURCE_DIR": str(ROOT.parent),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
    }

    commands = [
        ["bash", str(ROOT / "scripts/deploy.sh")],
        ["bash", str(ROOT / "scripts/run-job.sh"), "news"],
        ["bash", str(ROOT / "scripts/backup.sh")],
        ["bash", str(ROOT / "scripts/restore-check.sh"), str(backup_file)],
        ["bash", str(ROOT / "scripts/rollback.sh"), str(release)],
    ]
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=ROOT.parent,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        assert completed.returncode == 0, f"{command} failed: {completed.stderr}"

    log_lines = docker_log.read_text(encoding="utf-8").splitlines()
    compose_lines = [line for line in log_lines if line.startswith("compose ")]
    assert compose_lines
    for line in compose_lines:
        assert line.startswith(f"compose --env-file {backend_env} "), line
    assert any(" build" in line for line in compose_lines)
    assert any(" up -d" in line for line in compose_lines)
    assert any(" run --rm --no-deps jobs python -m jobs.news" in line for line in compose_lines)
    assert any("pg_dump --no-owner --no-acl -U custom_user custom_db" in line for line in compose_lines)
    assert any("createdb -U custom_user --maintenance-db=custom_db " in line for line in compose_lines)
    assert any("dropdb -U custom_user --maintenance-db=custom_db --if-exists " in line for line in compose_lines)
    assert not any(" -U powerai" in line or " powerai_hot" in line for line in compose_lines)


def test_backup_uses_atomic_gzip_dump_and_restore_check_uses_temp_database():
    backup = (ROOT / "scripts/backup.sh").read_text(encoding="utf-8")
    restore = (ROOT / "scripts/restore-check.sh").read_text(encoding="utf-8")
    assert "pg_dump --no-owner --no-acl" in backup
    assert "gzip -t" in backup
    assert "mv " in backup
    assert "find \"$BACKUP_DIR\"" in backup
    assert "COMPOSE_PROJECT_NAME=e-ai" in backup
    assert "createdb" in restore
    assert "dropdb" in restore
    assert "psql" in restore
    assert "trap" in restore
    assert "articles" in restore and "sources" in restore and "knowledge_cards" in restore
