from sqlalchemy.orm import sessionmaker

import services.research as res_mod
from models import schema
from services.research import _topic_materials, create_topic, generate_topic


def _art(db, title, summary="", emb=None, score=70):
    a = schema.Article(title=title, summary=summary, relevance_score=score,
                       scored=True, embedding=emb, url=f"http://x/{title}")
    db.add(a)
    db.commit()
    return a


def _bind(db, monkeypatch):
    monkeypatch.setattr(res_mod, "session_factory", sessionmaker(bind=db.get_bind(), future=True))


def test_topic_materials_keyword_and_vector(db, monkeypatch):
    kw = _art(db, "无人机巡检招标动态")                     # 关键词命中
    sem = _art(db, "UAV inspection defect model", emb=[1.0, 0.0])  # 仅向量命中
    _art(db, "无关内容", emb=[0.0, 1.0])
    monkeypatch.setattr(res_mod, "embed", lambda t: [1.0, 0.0])
    got = _topic_materials(db, "无人机巡检")
    ids = [a.id for a in got]
    assert kw.id in ids and sem.id in ids
    assert ids.count(sem.id) == 1  # 去重


def test_topic_materials_embed_failure_keyword_only(db, monkeypatch):
    kw = _art(db, "无人机巡检要闻")
    def boom(t):
        raise RuntimeError("embedding挂了")
    monkeypatch.setattr(res_mod, "embed", boom)
    got = _topic_materials(db, "无人机巡检")
    assert [a.id for a in got] == [kw.id]


def test_create_and_generate_topic_stub(db, monkeypatch):
    _bind(db, monkeypatch)
    monkeypatch.setattr(res_mod, "embed", lambda t: None)
    _art(db, "无人机巡检白皮书")
    r = create_topic(db, "无人机巡检")
    assert r.status == "生成中" and r.topic == "无人机巡检"
    generate_topic(r.id)
    db.expire_all()
    got = db.get(schema.Report, r.id)
    assert got.status == "完成" and "无人机巡检白皮书" in got.content_md


def test_generate_topic_failure_sets_status(db, monkeypatch):
    _bind(db, monkeypatch)
    monkeypatch.setattr(res_mod, "embed", lambda t: None)
    def boom(*a, **k):
        raise RuntimeError("LLM挂了")
    monkeypatch.setattr(res_mod, "get_analyzer", boom)
    r = create_topic(db, "任意主题")
    generate_topic(r.id)
    db.expire_all()
    assert db.get(schema.Report, r.id).status == "失败"
