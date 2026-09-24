from sqlalchemy.orm import sessionmaker

import services.cards as cards_mod
from models import schema
from services.cards import generate_card


def _setup(db, monkeypatch):
    """让后台任务的新会话落在测试库上。"""
    monkeypatch.setattr(cards_mod, "session_factory", sessionmaker(bind=db.get_bind(), future=True))
    a = schema.Article(title="UniOCR 统一文本识别", summary="一个模型做所有OCR任务")
    db.add(a)
    db.commit()
    c = schema.KnowledgeCard(article_id=a.id)
    db.add(c)
    db.commit()
    return a, c


def test_generate_card_success(db, monkeypatch):
    a, c = _setup(db, monkeypatch)
    monkeypatch.setattr(cards_mod, "make_card", lambda t, s="", ct="": {
        "category": "视觉/OCR", "problem": "p", "method": "m",
        "conclusion": "c", "power_relevance": "r"})
    generate_card(c.id)
    db.expire_all()
    got = db.get(schema.KnowledgeCard, c.id)
    assert got.status == "完成" and got.category == "视觉/OCR" and got.problem == "p"


def test_generate_card_failure_sets_status(db, monkeypatch):
    a, c = _setup(db, monkeypatch)
    def boom(t, s="", ct=""):
        raise RuntimeError("LLM挂了")
    monkeypatch.setattr(cards_mod, "make_card", boom)
    generate_card(c.id)
    db.expire_all()
    assert db.get(schema.KnowledgeCard, c.id).status == "失败"


def test_generate_card_missing_id_noop(db, monkeypatch):
    monkeypatch.setattr(cards_mod, "session_factory", sessionmaker(bind=db.get_bind(), future=True))
    generate_card(9999)  # 不抛异常
