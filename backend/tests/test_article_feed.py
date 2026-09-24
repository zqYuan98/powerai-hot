"""Article feed pagination, filtering and aggregate contracts."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import base64
import json

from sqlalchemy import inspect

from models import schema
from services.article_feed import FeedQuery, encode_cursor


def _seed_articles(db, count: int = 35, *, same_time: bool = False) -> list[schema.Article]:
    base = datetime(2026, 7, 11, 8, 0, 0)
    rows = []
    for index in range(count):
        row = schema.Article(
            title=f"分页情报 {index:02d}",
            summary=f"摘要 {index}",
            tags=["分页", "储能" if index % 2 == 0 else "电网"],
            channel="行业动态",
            kind="资讯",
            scored=True,
            curated=True,
            relevance_score=80 - (index % 5),
            crawled_at=base if same_time else base - timedelta(minutes=index),
            is_cluster_main=True,
        )
        rows.append(row)
    db.add_all(rows)
    db.commit()
    return rows


def test_articles_returns_bounded_page(client, db) -> None:
    _seed_articles(db, 35)

    response = client.get("/api/articles", params={"sort": "latest"})

    assert response.status_code == 200
    page = response.json()
    assert len(page["items"]) == 30
    assert page["total"] == 35
    assert page["has_more"] is True
    assert isinstance(page["next_cursor"], str)


def test_articles_seek_cursor_has_no_duplicates_with_equal_timestamps(client, db) -> None:
    _seed_articles(db, 35, same_time=True)

    first = client.get("/api/articles", params={"limit": 20, "sort": "latest"}).json()
    second = client.get(
        "/api/articles",
        params={"limit": 20, "sort": "latest", "cursor": first["next_cursor"]},
    ).json()

    first_ids = [row["id"] for row in first["items"]]
    second_ids = [row["id"] for row in second["items"]]
    assert first_ids == sorted(first_ids, reverse=True)
    assert set(first_ids).isdisjoint(second_ids)
    assert len(first_ids + second_ids) == 35
    assert second["has_more"] is False
    assert second["next_cursor"] is None


def test_cursor_timestamp_is_utc_epoch_microseconds(db) -> None:
    article = schema.Article(
        id=99, title="UTC 游标", scored=True, curated=True,
        crawled_at=datetime(2026, 1, 2, 3, 4, 5, 6000),
    )

    cursor = encode_cursor(FeedQuery(sort="latest"), article)
    raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
    payload = json.loads(raw)

    expected = int(datetime(2026, 1, 2, 3, 4, 5, 6000, tzinfo=timezone.utc).timestamp() * 1_000_000)
    assert payload["t"] == expected


def test_feed_folds_cluster_members_but_counts_related_sources(client, db) -> None:
    main = schema.Article(
        title="主条", channel="行业动态", scored=True, curated=True,
        relevance_score=90, cluster_id="cluster-a", is_cluster_main=True,
    )
    duplicate = schema.Article(
        title="簇成员", channel="行业动态", scored=True, curated=True,
        relevance_score=70, cluster_id="cluster-a", is_cluster_main=False,
    )
    db.add_all([main, duplicate])
    db.commit()

    page = client.get("/api/articles").json()

    assert page["total"] == 1
    assert [row["id"] for row in page["items"]] == [main.id]
    assert page["items"][0]["related_count"] == 1


def test_filters_are_applied_before_pagination(client, db) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add_all([
        schema.Article(
            title="储能精选", summary="目标摘要", tags=["储能", "示范"], channel="行业动态",
            kind="案例", scored=True, curated=True, relevance_score=91,
            published_at=now - timedelta(hours=2), crawled_at=now - timedelta(hours=1),
        ),
        schema.Article(
            title="旧储能精选", tags=["储能"], channel="行业动态", kind="案例",
            scored=True, curated=True, relevance_score=95,
            published_at=now - timedelta(days=8), crawled_at=now - timedelta(days=7),
        ),
        schema.Article(
            title="储能噪音", tags=["储能"], channel="行业动态", kind="案例",
            scored=False, curated=False, relevance_score=0, crawled_at=now,
        ),
        schema.Article(
            title="其他频道", tags=["储能"], channel="AI洞察", kind="案例",
            scored=True, curated=True, relevance_score=99, crawled_at=now,
        ),
    ])
    db.commit()

    page = client.get("/api/articles", params={
        "channel": "行业动态", "q": "目标", "kind": "案例", "min_score": 80,
        "view": "curated", "window": "24h", "tag": "储能", "sort": "score",
    }).json()

    assert page["total"] == 1
    assert [row["title"] for row in page["items"]] == ["储能精选"]


def test_noise_defaults_to_latest_sort(client, db) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add_all([
        schema.Article(title="旧噪音", scored=False, curated=False, relevance_score=99, crawled_at=now - timedelta(hours=1)),
        schema.Article(title="新噪音", scored=False, curated=False, relevance_score=1, crawled_at=now),
    ])
    db.commit()

    page = client.get("/api/articles", params={"view": "noise"}).json()

    assert [row["title"] for row in page["items"]] == ["新噪音", "旧噪音"]


def test_cursor_rejects_bad_payload_and_query_mismatch(client, db) -> None:
    _seed_articles(db, 3)
    first = client.get("/api/articles", params={"limit": 1, "sort": "latest"}).json()

    assert client.get("/api/articles", params={"cursor": "%%%", "sort": "latest"}).status_code == 422
    mismatch = client.get("/api/articles", params={
        "cursor": first["next_cursor"], "sort": "latest", "q": "different",
    })
    assert mismatch.status_code == 422


def test_cursor_rejects_out_of_range_timestamp(client, db) -> None:
    _seed_articles(db, 1)
    query = FeedQuery(sort="latest")
    payload = {"v": 1, "sort": "latest", "fp": query.fingerprint(), "t": 10**100, "id": 1}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    cursor = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    response = client.get("/api/articles", params={"cursor": cursor, "sort": "latest"})

    assert response.status_code == 422


def test_channel_counts_share_filters_but_ignore_current_channel(client, db) -> None:
    db.add_all([
        schema.Article(title="行业精选", channel="行业动态", scored=True, curated=True, tags=["储能"]),
        schema.Article(title="AI精选", channel="AI洞察", scored=True, curated=True, tags=["储能"]),
        schema.Article(title="AI噪音", channel="AI洞察", scored=False, curated=False, tags=["储能"]),
    ])
    db.commit()

    rows = client.get("/api/articles/channels", params={
        "channel": "行业动态", "view": "curated", "tag": "储能",
    }).json()

    assert [row["name"] for row in rows] == [
        "行业动态", "国网规划", "招标公告", "AI洞察", "政策法规", "前沿论文", "大模型动态", "落地案例",
    ]
    counts = {row["name"]: row["count"] for row in rows}
    assert counts["行业动态"] == 1
    assert counts["AI洞察"] == 1


def test_static_feed_routes_are_not_captured_by_article_id(client, anonymous_client, db) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(schema.Article(
        title="热点", channel="行业动态", scored=True, curated=True,
        relevance_score=90, crawled_at=now, published_at=now,
    ))
    db.commit()

    freshness = client.get("/api/articles/freshness")
    hotspots = client.get("/api/articles/hotspots")

    assert freshness.status_code == 200
    assert set(freshness.json()) == {"latest_crawled_at", "added_24h", "curated_24h"}
    assert hotspots.status_code == 200
    assert hotspots.json()[0]["title"] == "热点"
    assert anonymous_client.get("/api/articles/freshness").status_code == 401
    assert anonymous_client.get("/api/articles/hotspots").status_code == 401


def test_default_page_stays_small_with_large_dataset(client, db) -> None:
    _seed_articles(db, 1000)

    response = client.get("/api/articles")

    assert response.status_code == 200
    assert len(response.json()["items"]) == 30
    assert len(response.content) < 250_000


def test_hotspots_consider_all_recent_candidates(client, db) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(schema.Article(
        title="older but hottest", channel="industry", scored=True, curated=True,
        relevance_score=100, crawled_at=now - timedelta(hours=2), published_at=now - timedelta(hours=2),
    ))
    db.add_all([
        schema.Article(
            title=f"new low score {index}", channel="industry", scored=True, curated=True,
            relevance_score=1, crawled_at=now - timedelta(minutes=index), published_at=now - timedelta(minutes=index),
        )
        for index in range(201)
    ])
    db.commit()

    response = client.get("/api/articles/hotspots", params={"limit": 1})

    assert response.status_code == 200
    assert response.json()[0]["title"] == "older but hottest"


def test_subscription_hits_are_bounded_and_do_not_require_full_feed(client, db) -> None:
    db.add(schema.Subscription(user_id="me", keywords=["储能", "智能电网"]))
    for index in range(8):
        db.add(schema.Article(
            title=f"储能项目 {index}", channel="行业动态", scored=True, curated=True,
            relevance_score=90 - index, is_cluster_main=True,
        ))
    db.add(schema.Article(
        title="储能噪音", channel="行业动态", scored=False, curated=False,
        is_cluster_main=True,
    ))
    db.commit()

    response = client.get("/api/subscriptions/hits", params={"limit": 3})

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 3
    assert all(row["keyword"] == "储能" for row in rows)
    assert all(row["article"]["curated"] is True for row in rows)


def test_article_feed_indexes_exist(db) -> None:
    indexes = {row["name"]: row["column_names"] for row in inspect(db.get_bind()).get_indexes("articles")}

    assert indexes["ix_articles_feed_latest"] == ["channel", "scored", "crawled_at", "id"]
    assert indexes["ix_articles_feed_curated_score"] == [
        "channel", "curated", "scored", "relevance_score", "crawled_at", "id",
    ]
    assert indexes["ix_articles_published_at"] == ["published_at"]


def test_feed_filters_by_axis(client, db) -> None:
    """双轴筛选：只返回指定轴的条目。"""
    base = datetime(2026, 7, 20, 8, 0, 0)
    for index, axis in enumerate(["交叉", "交叉", "AI", "行业", "弱"]):
        db.add(schema.Article(
            title=f"轴测试 {index}", channel="行业动态", kind="资讯",
            scored=True, curated=True, relevance_score=70, is_cluster_main=True,
            axis=axis, cross_score=80 if axis == "交叉" else 10,
            crawled_at=base - timedelta(minutes=index),
        ))
    db.commit()

    page = client.get("/api/articles", params={"axis": "交叉", "view": "all"}).json()
    assert [item["axis"] for item in page["items"]] == ["交叉", "交叉"]

    page = client.get("/api/articles", params={"axis": "行业", "view": "all"}).json()
    assert [item["title"] for item in page["items"]] == ["轴测试 3"]


def test_feed_rejects_unknown_axis(client, db) -> None:
    assert client.get("/api/articles", params={"axis": "不存在"}).status_code == 422


def test_article_out_exposes_axis_fields(client, db) -> None:
    db.add(schema.Article(
        title="双轴字段", channel="行业动态", scored=True, curated=True,
        relevance_score=70, axis="交叉", cross_score=82, is_cluster_main=True,
        crawled_at=datetime(2026, 7, 20, 9, 0, 0),
    ))
    db.commit()
    item = client.get("/api/articles", params={"view": "all"}).json()["items"][0]
    assert item["axis"] == "交叉" and item["cross_score"] == 82


def test_axis_monitor_reports_power_supply_ratio(admin_client, db) -> None:
    """双轴监控：行业侧供给占比是「是否退化成纯 AI 资讯站」的单一观测指标。

    时间基准必须相对 now：trend 只统计 cutoff 之后的条目，写死日期的话
    这个断言只在写它的那一周成立，之后会无声过期成一颗定时炸弹。
    """
    base = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    source = schema.Source(
        name="监控测试源", url="https://axis.example", tier="T1",
        name_key=schema.normalize_source_name("监控测试源"),
        url_key=schema.normalize_source_url("https://axis.example"),
    )
    db.add(source)
    db.flush()
    for index, axis in enumerate(["交叉", "行业", "AI", "AI", "弱"]):
        db.add(schema.Article(
            title=f"监控 {index}", channel="行业动态", scored=True, source_id=source.id,
            curated=(axis == "交叉"), relevance_score=70, is_cluster_main=True,
            axis=axis, cross_score=80 if axis == "交叉" else 10,
            crawled_at=base - timedelta(minutes=index),
        ))
    db.commit()

    data = admin_client.get("/api/admin/axis", params={"days": 7}).json()
    # 交叉 1 + 行业 1，共 5 条 -> 40%
    assert data["power_supply_ratio"] == 40.0
    by_axis = {row["axis"]: row for row in data["by_axis"]}
    assert by_axis["交叉"]["count"] == 1 and by_axis["交叉"]["curated"] == 1
    assert by_axis["AI"]["count"] == 2
    source_row = next(row for row in data["by_source"] if row["source"] == "监控测试源")
    assert source_row["cross"] == 1 and source_row["ai"] == 2 and source_row["power"] == 1
    assert data["trend"] and sum(day["cross"] for day in data["trend"]) == 1


def test_axis_monitor_requires_admin(client, db) -> None:
    assert client.get("/api/admin/axis").status_code in (401, 403)


def test_sources_health_exposes_noise_and_value(admin_client, db) -> None:
    """信源健康要能回答「该不该砍」，而不只是「抓没抓到」。

    回归动因：实测有信源连抓 155 条、last_status 一直 ok，却 80% 判噪音、
    零精选，纯耗预算；只看抓取状态完全看不出来。
    """
    source = schema.Source(
        name="噪音源", url="https://noise.example", tier="T2", status="已采纳",
        name_key=schema.normalize_source_name("噪音源"),
        url_key=schema.normalize_source_url("https://noise.example"),
    )
    db.add(source)
    db.flush()
    base = datetime(2026, 7, 20, 8, 0, 0)
    for index in range(4):
        db.add(schema.Article(
            title=f"噪音 {index}", channel="行业动态", source_id=source.id,
            scored=True, curated=False, axis="弱", relevance_score=10,
            noise_reason="预筛判定无关（无关）" if index < 3 else None,
            crawled_at=base - timedelta(minutes=index),
        ))
    db.commit()

    rows = admin_client.get("/api/admin/sources/health").json()
    row = next(item for item in rows if item["name"] == "噪音源")
    assert row["article_count"] == 4
    assert row["noise_pct"] == 75
    assert row["curated_count"] == 0
    assert row["power_count"] == 0


def test_cross_picks_ranks_by_cross_score(client, db) -> None:
    """交叉精选按交叉分排序，且只收交叉轴的已精选条目。"""
    base = datetime(2026, 7, 20, 8, 0, 0)
    rows = [
        ("高交叉", "交叉", 92, True),
        ("低交叉", "交叉", 55, True),
        ("交叉未精选", "交叉", 88, False),
        ("纯AI", "AI", 20, True),
    ]
    for index, (title, axis, cs, curated) in enumerate(rows):
        db.add(schema.Article(
            title=title, channel="行业动态", scored=True, curated=curated,
            axis=axis, cross_score=cs, relevance_score=60, is_cluster_main=True,
            crawled_at=base - timedelta(minutes=index),
        ))
    db.commit()

    items = client.get("/api/articles/cross-picks", params={"limit": 5}).json()
    assert [item["title"] for item in items] == ["高交叉", "低交叉"]
    assert items[0]["cross_score"] == 92


def test_cross_picks_excludes_noise(client, db) -> None:
    db.add(schema.Article(
        title="交叉但是噪音", channel="行业动态", scored=True, curated=True,
        axis="交叉", cross_score=95, relevance_score=60, is_cluster_main=True,
        noise_reason="预筛判定无关（无关）",
        crawled_at=datetime(2026, 7, 20, 9, 0, 0),
    ))
    db.commit()
    assert client.get("/api/articles/cross-picks").json() == []


def test_reader_feed_views_enforce_the_noise_boundary(client, db) -> None:
    """噪音只能出现在审计视图，不能混入精选或普通已评分信息流。"""
    now = datetime(2026, 7, 20, 10, 0, 0)
    db.add_all([
        schema.Article(
            title="正常精选", channel="行业动态", scored=True, curated=True,
            relevance_score=80, is_cluster_main=True, crawled_at=now,
        ),
        schema.Article(
            title="脏状态精选噪音", channel="行业动态", scored=True, curated=True,
            relevance_score=90, noise_reason="预筛判定无关（无关）",
            is_cluster_main=True, crawled_at=now - timedelta(minutes=1),
        ),
        schema.Article(
            title="已评分噪音", channel="行业动态", scored=True, curated=False,
            relevance_score=20, noise_reason="预筛判定无关（无关）",
            is_cluster_main=True, crawled_at=now - timedelta(minutes=2),
        ),
        schema.Article(
            title="未评分噪音", channel="行业动态", scored=False, curated=False,
            relevance_score=0, noise_reason="预筛判定无关（无关）",
            is_cluster_main=True, crawled_at=now - timedelta(minutes=3),
        ),
    ])
    db.commit()

    curated = client.get("/api/articles", params={"view": "curated"}).json()
    all_scored = client.get("/api/articles", params={"view": "all"}).json()
    noise = client.get("/api/articles", params={"view": "noise"}).json()

    assert [item["title"] for item in curated["items"]] == ["正常精选"]
    assert [item["title"] for item in all_scored["items"]] == ["正常精选"]
    assert {item["title"] for item in noise["items"]} == {"脏状态精选噪音", "已评分噪音", "未评分噪音"}


def test_hotspots_never_include_noise_even_if_curated(client, db) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(schema.Article(
        title="噪音热点", channel="行业动态", scored=True, curated=True,
        relevance_score=100, hot=True, noise_reason="预筛判定无关（无关）",
        published_at=now, crawled_at=now, is_cluster_main=True,
    ))
    db.commit()

    assert client.get("/api/articles/hotspots").json() == []
