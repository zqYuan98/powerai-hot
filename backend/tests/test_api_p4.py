import pytest
from sqlalchemy.orm import sessionmaker

import services.research as res_mod
from models import schema


@pytest.fixture(autouse=True)
def _stub_research_generation(db, monkeypatch):
    monkeypatch.setattr(res_mod, "session_factory", sessionmaker(bind=db.get_bind(), future=True))
    monkeypatch.setattr(res_mod, "embed", lambda t: None)  # 离线：仅关键词检索


def test_topic_report_flow(admin_client, db):
    a = schema.Article(title="布控球边缘AI部署实践", summary="s", url="http://x/1", scored=True)
    db.add(a)
    db.commit()
    r = admin_client.post("/api/reports/topic", json={"topic": "布控球"})
    assert r.status_code == 200
    rid = r.json()["id"]
    db.expire_all()
    got = db.get(schema.Report, rid)  # TestClient 同步跑完后台任务
    assert got.status == "完成" and "布控球边缘AI部署实践" in got.content_md
    detail = admin_client.get(f"/api/reports/{rid}").json()
    assert detail["content_md"] and detail["type"] == "topic"


def test_topic_blank_rejected(admin_client):
    assert admin_client.post("/api/reports/topic", json={"topic": "  "}).status_code == 400


def test_retry_failed_topic(admin_client, db):
    admin_client.post("/api/reports/topic", json={"topic": "任意"})
    rep = db.query(schema.Report).one()
    rep.status = "失败"
    db.commit()
    r = admin_client.post(f"/api/reports/{rep.id}/retry")
    assert r.status_code == 200
    db.expire_all()
    assert db.get(schema.Report, rep.id).status == "完成"


def test_retry_daily_rejected(admin_client, db):
    rep = schema.Report(type="daily", title="今日精选 · x")
    db.add(rep)
    db.commit()
    assert admin_client.post(f"/api/reports/{rep.id}/retry").status_code == 400


def test_admin_weekly_trigger(admin_client, db):
    r = admin_client.post("/api/admin/weekly")
    assert r.status_code == 200
    db.expire_all()
    rep = db.get(schema.Report, r.json()["id"])
    assert rep.type == "weekly" and rep.status == "完成"  # stub 素材清单
