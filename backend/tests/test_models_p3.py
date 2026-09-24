from models import schema


def test_favorite_roundtrip(db):
    a = schema.Article(title="t")
    db.add(a)
    db.commit()
    f = schema.Favorite(article_id=a.id)
    db.add(f)
    db.commit()
    assert db.get(schema.Favorite, f.id).article_id == a.id


def test_card_defaults(db):
    a = schema.Article(title="t")
    db.add(a)
    db.commit()
    c = schema.KnowledgeCard(article_id=a.id)
    db.add(c)
    db.commit()
    got = db.get(schema.KnowledgeCard, c.id)
    assert got.status == "生成中" and got.category == "其他" and got.note is None


def test_writer_role_config():
    from core.config import settings
    # deepseek-chat 已于 2026-07 下线，接口只认 deepseek-v4-pro / deepseek-v4-flash。
    assert settings.deepseek_writer_model == "deepseek-v4-pro"
