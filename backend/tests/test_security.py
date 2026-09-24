"""对抗式审查发现的修复回归测试。"""
import pytest

from core.config import settings
from core.sqlutil import escape_like
from core.urlguard import validate_feed_url
from services.config_store import put_scoring_config
from conftest import ADMIN_TOKEN


# --- 鉴权（发现 #2） ---

def test_admin_fails_closed_when_token_unset(anonymous_client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "")
    assert anonymous_client.get("/api/admin/scoring").status_code == 503


def test_admin_blocked_without_token(anonymous_client):
    assert anonymous_client.get("/api/admin/scoring").status_code == 401
    assert anonymous_client.post("/api/admin/digest").status_code == 401


def test_admin_ok_with_token(anonymous_client):
    r = anonymous_client.get("/api/admin/scoring", headers={"X-Admin-Token": ADMIN_TOKEN})
    assert r.status_code == 200


def test_admin_wrong_token_rejected(anonymous_client):
    assert anonymous_client.get(
        "/api/admin/scoring", headers={"X-Admin-Token": "wrong"}
    ).status_code == 401


def test_business_read_requires_workspace(anonymous_client):
    assert anonymous_client.get("/api/articles").status_code == 401


def test_source_submit_guarded(anonymous_client):
    r = anonymous_client.post(
        "/api/sources",
        json={"name": "x", "type": "网站", "url": "https://x.com"},
    )
    assert r.status_code == 401


# --- CORS 逗号兼容（发现 #4） ---

def test_cors_origins_comma_string():
    from core.config import Settings
    s = Settings(cors_origins="https://a.com, https://b.com")
    assert s.cors_origins == ["https://a.com", "https://b.com"]


def test_cors_origins_json_string():
    from core.config import Settings
    s = Settings(cors_origins='["https://a.com"]')
    assert s.cors_origins == ["https://a.com"]


# --- 文章序列化 NULL 容错（发现 #5） ---

def test_article_out_tolerates_nulls():
    from api.dto import ArticleOut
    out = ArticleOut.model_validate(
        {"id": 1, "title": "t", "tags": None, "channel": None, "relevance_score": None, "scored": None})
    assert out.tags == [] and out.channel == "行业动态" and out.relevance_score == 0


# --- SSRF / 本地文件读取（发现 1） ---

def test_urlguard_blocks_file_scheme():
    with pytest.raises(ValueError):
        validate_feed_url("file:///C:/E-AI/powerai-hot/backend/.env")


def test_urlguard_blocks_loopback_and_private():
    for u in ["http://127.0.0.1/x", "http://localhost/x", "http://169.254.169.254/latest",
              "http://192.168.1.1/x", "http://10.0.0.1/feed"]:
        with pytest.raises(ValueError):
            validate_feed_url(u)


def test_urlguard_allows_public_https(monkeypatch):
    monkeypatch.setattr(
        "core.urlguard.socket.getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 0))],
    )
    validate_feed_url("https://openai.com/blog/rss.xml")  # 固定公网 DNS 夹具，不依赖宿主解析


def test_rss_collector_refuses_file_url(monkeypatch):
    from collector.rss import RssCollector
    # 即便坏 URL 混入库，采集器自身也拒抓
    result = RssCollector("file:///etc/passwd").fetch()
    assert result.transport_status == "ok"
    assert result.parse_status == "schema_error"


# --- 评分配置投毒 / NaN（发现 2） ---

def test_config_rejects_non_numeric_value(db):
    with pytest.raises(ValueError):
        put_scoring_config(db, {"hot_score": "boom"})


def test_config_rejects_nested_bad_value(db):
    with pytest.raises(ValueError):
        put_scoring_config(db, {"dim_weights": {"relevance": "x"}})


def test_config_rejects_out_of_range(db):
    with pytest.raises(ValueError):
        put_scoring_config(db, {"hot_score": 999})
    with pytest.raises(ValueError):
        put_scoring_config(db, {"cluster_threshold": 5})  # 阈值须 0-1


def test_config_rejects_nan(db):
    with pytest.raises(ValueError):
        put_scoring_config(db, {"hot_score": float("nan")})


def test_config_accepts_valid(db):
    cfg = put_scoring_config(db, {"hot_score": 75,
                                  "dim_weights": {"ai_relevance": 40}})
    assert cfg["hot_score"] == 75 and cfg["dim_weights"]["ai_relevance"] == 40


def test_config_rejects_unknown_dim_key(db):
    """拼错的维度名必须报错，不能返回 200 之后被静默丢弃。

    回归动因：`relevance` 在 P2 已拆成 ai_relevance / power_relevance，
    但子键此前不查白名单，写进去只会被读取端忽略，调用方毫无察觉。
    """
    with pytest.raises(ValueError):
        put_scoring_config(db, {"dim_weights": {"relevance": 40}})


# --- LIKE 通配符转义（发现 7） ---

def test_escape_like():
    assert escape_like("100%") == "100\\%"
    assert escape_like("a_b") == "a\\_b"
    assert escape_like("x\\y") == "x\\\\y"
