"""Employee source-submission workflow tests."""

import threading

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.dto import SourceSubmissionCreate
from api.sources import OpmlImport, import_opml
from core import urlguard
from models.database import Base
from models import schema
from api.sources import create_source_submission
from conftest import ADMIN_TOKEN, WORKSPACE_TOKEN


@pytest.fixture()
def public_dns(monkeypatch):
    """Keep tests deterministic for public fixture hosts without weakening IP checks."""
    original = urlguard._is_blocked_ip

    def allow_known_public(host: str) -> bool:
        if host in {"example.com", "openai.com"}:
            return False
        return original(host)

    monkeypatch.setattr(urlguard, "_is_blocked_ip", allow_known_public)


def _payload(**overrides):
    body = {
        "name": "示例员工信源",
        "url": "https://example.com/feed.xml",
        "type": "网站",
        "reason": "业务参考来源",
    }
    body.update(overrides)
    return body


def test_workspace_submission_is_always_pending(client, db, public_dns):
    response = client.post("/api/sources/submissions", json=_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "待审核"
    assert body["submitted_by"] == "workspace"
    row = db.query(schema.Source).one()
    assert row.status == "待审核"
    assert row.submitted_by == "workspace"


def test_submission_rejects_activation_input_without_creating_source(client, db, public_dns):
    response = client.post(
        "/api/sources/submissions",
        json=_payload(active=True),
    )

    assert response.status_code == 422
    assert db.query(schema.Source).count() == 0


def test_submission_rejects_duplicate_normalized_url_or_name(client, db, public_dns):
    first = client.post(
        "/api/sources/submissions",
        json=_payload(name="  重复信源  ", url=" https://example.com/feed.xml "),
    )
    assert first.status_code == 201

    duplicate_name = client.post(
        "/api/sources/submissions",
        json=_payload(name="重复信源", url="https://openai.com/feed.xml"),
    )
    duplicate_url = client.post(
        "/api/sources/submissions",
        json=_payload(name="另一个名字", url="https://example.com/feed.xml"),
    )

    assert duplicate_name.status_code == 409
    assert duplicate_url.status_code == 409
    assert db.query(schema.Source).count() == 1
    assert db.query(schema.Source).one().name == "重复信源"


@pytest.mark.parametrize(
    "payloads",
    [
        (
            _payload(name="并发同名", url="https://example.com/feed-a.xml"),
            _payload(name="并发同名", url="https://openai.com/feed-b.xml"),
        ),
        (
            _payload(name="并发链接一", url="https://example.com/shared.xml"),
            _payload(name="并发链接二", url="https://example.com/shared.xml"),
        ),
    ],
)
def test_concurrent_submissions_cannot_create_duplicate_rows(
    tmp_path, public_dns, payloads
):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'source-race.db'}",
        connect_args={"check_same_thread": False, "timeout": 15},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    barrier = threading.Barrier(2)

    class CoordinatedSession:
        def __init__(self, session):
            self._session = session

        def scalars(self, statement):
            result = self._session.scalars(statement)
            barrier.wait(timeout=10)
            return result

        def __getattr__(self, name):
            return getattr(self._session, name)

    results = []

    def submit(payload):
        session = Session()
        try:
            result = create_source_submission(
                payload=SourceSubmissionCreate(**payload),
                db=CoordinatedSession(session),
            )
            results.append(("ok", result.id))
        except HTTPException as exc:
            results.append(("http", exc.status_code))
        finally:
            session.close()

    threads = [threading.Thread(target=submit, args=(payload,)) for payload in payloads]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)

    assert sorted(results) == [("http", 409), ("ok", 1)]
    verify = Session()
    try:
        assert verify.query(schema.Source).count() == 1
    finally:
        verify.close()


@pytest.mark.parametrize(
    "url",
    ["not-a-url", "file:///etc/passwd", "http://127.0.0.1/feed", "http://192.168.1.1/feed"],
)
def test_submission_rejects_invalid_or_private_urls(client, db, public_dns, url):
    response = client.post("/api/sources/submissions", json=_payload(url=url))

    assert response.status_code == 400
    assert db.query(schema.Source).count() == 0


@pytest.mark.parametrize(
    "body",
    [
        _payload(name="   "),
        _payload(url="   "),
        _payload(name="n" * 201),
        _payload(url="https://example.com/" + "u" * 501),
        _payload(reason="r" * 2001),
        _payload(type="other"),
    ],
)
def test_submission_validates_trimmed_lengths_and_type(client, db, public_dns, body):
    response = client.post("/api/sources/submissions", json=body)

    assert response.status_code == 422
    assert db.query(schema.Source).count() == 0


def test_workspace_lists_only_workspace_submissions_and_cannot_manage_sources(
    client, admin_client, db, public_dns
):
    db.add_all(
        [
            schema.Source(
                name="员工提报",
                url="https://example.com/employee.xml",
                type="RSS",
                status="待审核",
                submitted_by="workspace",
            ),
            schema.Source(
                name="管理员信源",
                url="https://openai.com/admin.xml",
                status="已采纳",
                submitted_by="admin",
            ),
        ]
    )
    db.commit()

    rows = client.get("/api/sources/submissions")
    assert rows.status_code == 200
    assert [row["name"] for row in rows.json()] == ["员工提报"]
    assert admin_client.get("/api/sources/submissions").status_code == 200

    assert client.get("/api/sources").status_code == 403
    assert client.post("/api/sources", json=_payload()).status_code == 403
    assert client.post("/api/sources/1/status", params={"status": "已采纳"}).status_code == 403
    assert client.delete("/api/sources/1").status_code == 403
    assert db.query(schema.Source).count() == 2


def test_admin_direct_source_management_remains_available(admin_client, public_dns):
    response = admin_client.post(
        "/api/sources?active=true",
        json=_payload(name="管理员直采", url="https://openai.com/admin.xml"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "已采纳"
    assert body["submitted_by"] == "admin"
    assert admin_client.get("/api/sources").status_code == 200
    source_id = body["id"]
    assert admin_client.post(
        f"/api/sources/{source_id}/status", params={"status": "待审核"}
    ).status_code == 200
    assert admin_client.delete(f"/api/sources/{source_id}").status_code == 204


def test_opml_malformed_url_is_reported_without_server_error(admin_client):
    response = admin_client.post(
        "/api/sources/import-opml",
        json={
            "opml": (
                '<opml><body><outline text="malformed" '
                'xmlUrl="http://[::1"/></body></opml>'
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 0 and len(body["errors"]) == 1


def test_concurrent_opml_imports_report_key_conflict_without_duplicate_rows(
    tmp_path, public_dns
):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'opml-race.db'}",
        connect_args={"check_same_thread": False, "timeout": 15},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    barrier = threading.Barrier(2)

    class CoordinatedQuery:
        def __init__(self, query):
            self._query = query

        def all(self):
            result = self._query.all()
            barrier.wait(timeout=10)
            return result

        def __getattr__(self, name):
            return getattr(self._query, name)

    class CoordinatedSession:
        def __init__(self, session):
            self._session = session

        def query(self, *entities):
            return CoordinatedQuery(self._session.query(*entities))

        def __getattr__(self, name):
            return getattr(self._session, name)

    payload = OpmlImport(
        opml=(
            '<opml><body><outline text="并发 OPML" '
            'xmlUrl="https://example.com/opml-race.xml"/></body></opml>'
        )
    )
    results = []

    def import_feed():
        session = Session()
        try:
            result = import_opml(payload, db=CoordinatedSession(session))
            results.append(("ok", result["imported"]))
        except HTTPException as exc:
            results.append(("http", exc.status_code))
        finally:
            session.close()

    threads = [threading.Thread(target=import_feed) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)

    assert sorted(results) == [("http", 409), ("ok", 1)]
    verify = Session()
    try:
        assert verify.query(schema.Source).count() == 1
    finally:
        verify.close()


def test_anonymous_cannot_submit_or_read_sources(anonymous_client):
    assert anonymous_client.post("/api/sources/submissions", json=_payload()).status_code == 401
    assert anonymous_client.get("/api/sources/submissions").status_code == 401
    assert anonymous_client.get("/api/sources").status_code == 401


def test_workspace_header_is_not_admin_header(anonymous_client):
    response = anonymous_client.get(
        "/api/sources",
        headers={"X-Workspace-Token": WORKSPACE_TOKEN},
    )
    assert response.status_code == 403
    assert ADMIN_TOKEN != WORKSPACE_TOKEN
