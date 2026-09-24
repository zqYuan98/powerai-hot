import pytest
from sqlalchemy.orm import sessionmaker

import services.cards as cards_mod
from models import schema


@pytest.fixture(autouse=True)
def _stub_card_generation(db, monkeypatch):
    # 后台任务的新会话落到测试库；卡片内容用固定 mock
    monkeypatch.setattr(cards_mod, "session_factory", sessionmaker(bind=db.get_bind(), future=True))
    monkeypatch.setattr(cards_mod, "make_card", lambda t, s="", ct="": {
        "category": "视觉/OCR", "problem": "p", "method": "m",
        "conclusion": "c", "power_relevance": "r"})


@pytest.fixture()
def article(db):
    a = schema.Article(title="UniOCR 统一识别", summary="s", url="http://x/1")
    db.add(a)
    db.commit()
    return a


def test_favorite_creates_card_async(client, article, db):
    r = client.post(f"/api/favorites/{article.id}")
    assert r.status_code == 200
    db.expire_all()
    card = db.query(schema.KnowledgeCard).filter_by(article_id=article.id).one()
    assert card.status == "完成" and card.category == "视觉/OCR"  # TestClient 同步跑完后台任务


def test_favorite_idempotent(client, article, db):
    client.post(f"/api/favorites/{article.id}")
    r = client.post(f"/api/favorites/{article.id}")
    assert r.status_code == 200
    assert db.query(schema.Favorite).count() == 1
    assert db.query(schema.KnowledgeCard).count() == 1


def test_favorite_404(client):
    assert client.post("/api/favorites/999").status_code == 404


def test_list_favorite_ids(client, article):
    client.post(f"/api/favorites/{article.id}")
    assert client.get("/api/favorites").json() == [article.id]


def test_unfavorite_retains_card_and_refavorite_reuses_it(
    client, article, db, monkeypatch
):
    from api import favorites

    generated: list[int] = []
    monkeypatch.setattr(favorites, "generate_card", generated.append)

    first = client.post(f"/api/favorites/{article.id}")
    card_id = first.json()["card_id"]
    r = client.delete(f"/api/favorites/{article.id}")
    assert r.status_code == 200
    assert db.query(schema.Favorite).count() == 0
    assert db.query(schema.KnowledgeCard).count() == 1
    assert client.get("/api/cards").json() == []

    second = client.post(f"/api/favorites/{article.id}")
    assert second.json()["card_id"] == card_id
    assert [card["id"] for card in client.get("/api/cards").json()] == [card_id]
    assert db.query(schema.KnowledgeCard).count() == 1
    assert generated == [card_id]


def test_cards_list_search_and_note(client, article, db):
    client.post(f"/api/favorites/{article.id}")
    rows = client.get("/api/cards").json()
    assert len(rows) == 1 and rows[0]["article"]["title"] == "UniOCR 统一识别"
    assert client.get("/api/cards?category=大模型").json() == []
    assert len(client.get("/api/cards?q=UniOCR").json()) == 1

    card_id = rows[0]["id"]
    r = client.patch(f"/api/cards/{card_id}", json={"note": "读后感"})
    assert r.json()["note"] == "读后感"


def test_card_retry(admin_client, article, db):
    admin_client.post(f"/api/favorites/{article.id}")
    card = db.query(schema.KnowledgeCard).one()
    card.status = "失败"
    db.commit()
    r = admin_client.post(f"/api/cards/{card.id}/retry")
    assert r.status_code == 200
    db.expire_all()
    assert db.get(schema.KnowledgeCard, card.id).status == "完成"
