from datetime import timedelta

from sqlalchemy.orm import sessionmaker

import services.research as res_mod
from models import schema
from services.clustering import utcnow
from services.research import create_weekly, generate_weekly


def _art(db, title, channel="行业动态", score=70, days_ago=1, **kw):
    a = schema.Article(title=title, channel=channel, relevance_score=score,
                       curated=True, is_cluster_main=True, scored=True,
                       summary=f"{title}的摘要", url=f"http://x/{title}", **kw)
    db.add(a)
    db.commit()
    a.crawled_at = utcnow() - timedelta(days=days_ago)
    db.commit()
    return a


def _bind(db, monkeypatch):
    monkeypatch.setattr(res_mod, "session_factory", sessionmaker(bind=db.get_bind(), future=True))


def test_create_weekly_idempotent_same_week(db):
    r1 = create_weekly(db)
    r2 = create_weekly(db)
    assert r1.id == r2.id and r1.type == "weekly" and r2.status == "生成中"
    assert db.query(schema.Report).count() == 1


def test_week_title_natural_week_key():
    from datetime import datetime

    from services.research import _week_title

    tue = datetime(2026, 7, 7, 10, 0)   # 2026 第28周 周二
    thu = datetime(2026, 7, 9, 18, 0)   # 同周周四
    next_mon = datetime(2026, 7, 13, 8, 0)  # 下一周周一
    assert _week_title(tue) == _week_title(thu) == "周报 · 2026 第28周"
    assert _week_title(next_mon) == "周报 · 2026 第29周"
    assert _week_title(tue) != _week_title(next_mon)


def test_generate_weekly_stub_fallback_lists_materials(db, monkeypatch):
    _bind(db, monkeypatch)
    _art(db, "国网AI巡检新进展", score=90)
    _art(db, "过期新闻", days_ago=10)          # 超7天不入选
    old = _art(db, "非精选", score=95)
    old.curated = False
    db.commit()
    r = create_weekly(db)
    generate_weekly(r.id)   # 无 Key → stub → 素材清单 markdown
    db.expire_all()
    got = db.get(schema.Report, r.id)
    assert got.status == "完成"
    assert "国网AI巡检新进展" in got.content_md
    assert "过期新闻" not in got.content_md and "非精选" not in got.content_md


def test_generate_weekly_model_output_used(db, monkeypatch):
    _bind(db, monkeypatch)
    _art(db, "要闻A")

    class Fake:
        def complete(self, system, prompt, *, max_tokens=512):
            assert "要闻A" in prompt  # 素材进入提示词
            return "## 本周要闻\n- 要闻A 值得关注"

    monkeypatch.setattr(res_mod, "get_analyzer", lambda *a, **k: Fake())
    r = create_weekly(db)
    generate_weekly(r.id)
    db.expire_all()
    assert db.get(schema.Report, r.id).content_md.startswith("## 本周要闻")


def test_generate_weekly_failure_sets_status(db, monkeypatch):
    _bind(db, monkeypatch)

    def boom(*a, **k):
        raise RuntimeError("LLM挂了")

    monkeypatch.setattr(res_mod, "get_analyzer", boom)
    r = create_weekly(db)
    generate_weekly(r.id)
    db.expire_all()
    assert db.get(schema.Report, r.id).status == "失败"
