"""详情带 content_html；列表不带（payload 纪律）。"""
from models import schema


def _mk(db, **kw):
    a = schema.Article(title="T", channel="行业动态", url="http://x/1",
                       content_html="<p>正文</p>", scored=True, curated=True, **kw)
    db.add(a)
    db.commit()
    return a


def test_detail_returns_content_html(client, db):
    a = _mk(db)
    data = client.get(f"/api/articles/{a.id}").json()
    assert data["content_html"] == "<p>正文</p>"


def test_list_omits_content_html(client, db):
    _mk(db)
    page = client.get("/api/articles?view=all").json()
    assert page["items"] and "content_html" not in page["items"][0]
