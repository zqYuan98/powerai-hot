import pytest

from models import schema


@pytest.fixture()
def clustered(db):
    main = schema.Article(title="官方发布", channel="大模型动态", tier="T1", scored=True,
                          curated=True, relevance_score=80, cluster_id="c1", is_cluster_main=True)
    dup = schema.Article(title="媒体转述", channel="大模型动态", tier="T2", scored=True,
                         curated=True, relevance_score=60, cluster_id="c1", is_cluster_main=False)
    solo = schema.Article(title="独立论文", channel="前沿论文", tier="T1", scored=True,
                          curated=True, relevance_score=85, cluster_id="c3", is_cluster_main=True)
    db.add_all([main, dup, solo])
    db.commit()
    return main, dup, solo


def test_articles_list_folds_cluster(client, clustered):
    main, dup, solo = clustered
    rows = client.get("/api/articles").json()["items"]
    ids = [r["id"] for r in rows]
    assert main.id in ids and solo.id in ids and dup.id not in ids  # 折叠条不出现
    got = next(r for r in rows if r["id"] == main.id)
    assert got["related_count"] == 1
    assert next(r for r in rows if r["id"] == solo.id)["related_count"] == 0


def test_articles_include_all(client, clustered):
    rows = client.get("/api/articles?include_all=true").json()["items"]
    assert len(rows) == 3


def test_cluster_expand(client, clustered):
    main, dup, _ = clustered
    rows = client.get(f"/api/articles/{main.id}/cluster").json()
    assert [r["id"] for r in rows] == [main.id, dup.id]  # T1 主条在前


def test_digest_endpoint_and_reports(admin_client, clustered, db):
    r = admin_client.post("/api/admin/digest").json()
    assert r["total"] == 2  # dup 是非主条，被日报排除；只有 main 和 solo
    lst = admin_client.get("/api/reports?type=daily").json()
    assert len(lst) == 1 and lst[0]["type"] == "daily"
    detail = admin_client.get(f"/api/reports/{lst[0]['id']}").json()
    names = [s["name"] for s in detail["sections"]]
    assert "论文研究" in names and "大模型动态" in names
    papers = next(s for s in detail["sections"] if s["name"] == "论文研究")
    assert papers["articles"][0]["title"] == "独立论文"


def test_report_404(client):
    assert client.get("/api/reports/999").status_code == 404
