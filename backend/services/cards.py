"""知识卡片生成任务：收藏/重试时在后台线程执行，自开会话。

session_factory 为模块级属性，测试用 monkeypatch 注入测试库的 sessionmaker。
"""
from __future__ import annotations

import logging

from models import schema
from models.database import SessionLocal
from analyzer.card_maker import make_card

log = logging.getLogger("cards")

session_factory = SessionLocal


def generate_card(card_id: int) -> None:
    """按卡片 ID 生成内容并更新状态；任何异常置「失败」，不向上抛。"""
    db = session_factory()
    try:
        card = db.get(schema.KnowledgeCard, card_id)
        if card is None:
            return
        article = db.get(schema.Article, card.article_id)
        if article is None:
            card.status = "失败"
            db.commit()
            return
        try:
            data = make_card(article.title, article.summary or "", article.content or "")
            card.category = data["category"]
            card.problem = data["problem"]
            card.method = data["method"]
            card.conclusion = data["conclusion"]
            card.power_relevance = data["power_relevance"]
            card.status = "完成"
        except Exception as e:
            log.warning("卡片生成失败 card_id=%s: %s", card_id, e)
            card.status = "失败"
        db.commit()
    finally:
        db.close()
