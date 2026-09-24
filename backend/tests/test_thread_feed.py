from models import schema


def _thread(name: str) -> schema.ResearchThread:
    return schema.ResearchThread(name=name, description=f"{name} 描述", keywords=[name], weight=1.0, status="active")


def _article(title: str, thread_id: int | None) -> schema.Article:
    return schema.Article(
        title=title,
        primary_thread_id=thread_id,
        relevance_score=80,
        curated=True,
        scored=True,
        is_cluster_main=True,
    )


def test_article_thread_filter_and_summary_include_horizon(client, db):
    first = _thread("文档理解")
    second = _thread("边缘部署")
    db.add_all([first, second])
    db.flush()
    db.add_all([_article("OCR 工具", first.id), _article("量化部署", second.id), _article("通识资讯", None)])
    db.commit()

    filtered = client.get("/api/articles", params={"thread_id": first.id}).json()
    summary = client.get("/api/threads/summary").json()

    assert [item["title"] for item in filtered["items"]] == ["OCR 工具"]
    assert summary == [
        {"id": first.id, "name": "文档理解", "count": 1},
        {"id": second.id, "name": "边缘部署", "count": 1},
        {"id": None, "name": "视野", "count": 1},
    ]
