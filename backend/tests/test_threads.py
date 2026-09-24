from models import schema
from models.seed import RESEARCH_THREADS, seed_research_threads


def test_seed_research_threads_is_idempotent_and_uses_the_six_v2_defaults(db):
    seed_research_threads(db)
    seed_research_threads(db)

    rows = db.query(schema.ResearchThread).order_by(schema.ResearchThread.id).all()

    assert [(row.name, row.weight, row.status) for row in rows] == [
        (item["name"], item["weight"], "active") for item in RESEARCH_THREADS
    ]
    assert len(rows) == 6
    assert rows[0].description == "版面分析、表格/公式识别、文档解析（MinerU/PaddleOCR/Surya 类）、文档多模态"


def test_thread_routes_keep_existing_workspace_admin_access_matrix(client, admin_client, db):
    thread = schema.ResearchThread(
        name="文档理解与 OCR",
        description="版面分析与文档多模态。",
        keywords=["OCR", "文档理解"],
        weight=1.0,
        status="active",
    )
    db.add(thread)
    db.commit()

    assert client.get("/api/threads").status_code == 200
    assert client.get("/api/threads", params={"include_paused": "true"}).status_code == 403
    assert client.post("/api/threads", json={
        "name": "新主线", "description": "用于测试。", "keywords": ["测试"], "weight": 1,
    }).status_code == 403

    created = admin_client.post("/api/threads", json={
        "name": "新主线", "description": "用于测试。", "keywords": ["测试"], "weight": 1,
    })
    assert created.status_code == 201


def test_thread_delete_rejects_historical_article_reference(admin_client, db):
    thread = schema.ResearchThread(
        name="AI × 电力场景",
        description="电网基建中的 AI 应用。",
        keywords=["电网"],
        weight=1.0,
        status="active",
    )
    db.add(thread)
    db.flush()
    db.add(schema.Article(title="电网 AI", primary_thread_id=thread.id))
    db.commit()

    response = admin_client.delete(f"/api/threads/{thread.id}")

    assert response.status_code == 409
