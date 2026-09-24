from analyzer.scoring import DEFAULT_CONFIG
from models import schema
from services.config_store import get_scoring_config, put_scoring_config, recompute_all


def test_get_returns_defaults_when_empty(db):
    assert get_scoring_config(db) == DEFAULT_CONFIG


def test_put_merges_and_persists(db):
    put_scoring_config(db, {"hot_score": 90})
    cfg = get_scoring_config(db)
    assert cfg["hot_score"] == 90
    assert cfg["dim_weights"] == DEFAULT_CONFIG["dim_weights"]  # 未改的保持默认


def test_put_partial_nested_dict_merges(db):
    """只传一个频道的阈值，其余频道不能被抹掉（冒烟发现的浅合并 bug）。"""
    put_scoring_config(db, {"channel_thresholds": {"前沿论文": 85}})
    cfg = get_scoring_config(db)
    assert cfg["channel_thresholds"]["前沿论文"] == 85
    assert cfg["channel_thresholds"]["行业动态"] == 60


def test_get_merges_stale_nested_dict_with_defaults(db):
    """P2 之前存下的配置读出来必须既补回新维度、又丢掉废弃维度。

    回归动因：get 原来是浅合并，一行 P2 之前的 dim_weights（只有旧的 relevance）
    会造成两种静默降级 ——
      缺键不补：ai_relevance / power_relevance 权重变 0，双轴对质量分完全失效；
      旧键不删：废弃的 relevance 仍占 30 权重却匹配不到维度值，只推高分母，
                把加权均值整体稀释约 23%。
    两种都不报错，只是分数悄悄变低。
    """
    stale = {"relevance": 30, "firsthand": 50, "utility": 20, "impact": 15, "depth": 15}
    db.add(schema.ScoringConfig(key="scoring", value={"dim_weights": stale}))
    db.commit()

    weights = get_scoring_config(db)["dim_weights"]
    assert weights["firsthand"] == 50                       # 存量覆盖生效
    assert "relevance" not in weights                       # 废弃维度被丢弃
    for key in ("ai_relevance", "power_relevance"):          # 新维度补回默认权重
        assert weights[key] == DEFAULT_CONFIG["dim_weights"][key]
    assert set(weights) == set(DEFAULT_CONFIG["dim_weights"])


def test_stale_dim_key_does_not_dilute_quality(db):
    """废弃维度残留会拉低所有文章的质量分——从分数侧再钉一遍，不只看配置形状。"""
    from analyzer.scoring import compute_quality

    dims = {"firsthand": 80, "ai_relevance": 90, "power_relevance": 40,
            "utility": 60, "impact": 50, "depth": 70}
    clean = compute_quality(dims, "T1", "资讯", DEFAULT_CONFIG)

    db.add(schema.ScoringConfig(key="scoring", value={
        "dim_weights": {**DEFAULT_CONFIG["dim_weights"], "relevance": 30},
    }))
    db.commit()

    assert compute_quality(dims, "T1", "资讯", get_scoring_config(db)) == clean


def test_put_rejects_unknown_key(db):
    import pytest
    with pytest.raises(ValueError):
        put_scoring_config(db, {"bad_key": 1})


def test_recompute_all(db):
    dims = {"firsthand": 80, "ai_relevance": 90, "power_relevance": 40, "utility": 60, "impact": 50, "depth": 70}
    a = schema.Article(title="a", kind="资讯", tier="T1", scored=True,
                       dim_scores=dims, channel="行业动态", relevance_score=0)
    b = schema.Article(title="b", scored=False, channel="行业动态")  # 未评分：跳过
    db.add_all([a, b])
    db.commit()

    stats = recompute_all(db)
    assert stats["recomputed"] == 1
    db.refresh(a)
    assert a.relevance_score == 66          # 见 test_scoring 的算式
    assert a.curated is True                # 66 >= 60
    assert a.hot is False                   # 66 < 80

    # 调高阈值与 hot 线后重算，精选状态随之变化
    put_scoring_config(db, {"channel_thresholds": {**DEFAULT_CONFIG["channel_thresholds"], "行业动态": 80},
                            "hot_score": 65})
    recompute_all(db)
    db.refresh(a)
    assert a.curated is False
    assert a.hot is True


def test_recompute_matches_ingest_scale_when_threads_active(db):
    """重算与入库必须用同一把尺子。

    回归动因：recompute_all 原来无条件用 quality 写 relevance_score，
    而 ingest 在有激活研究方向时写的是 learn_score。两者共用一列，
    重算过的文章与新采集的文章分数不可比，信息流排序会错乱。
    """
    from models.schema import ResearchThread, normalize_thread_name
    from services.ingest import _apply_thread_score

    thread = ResearchThread(
        name="视觉检测", name_key=normalize_thread_name("视觉检测"),
        description="d", keywords=["缺陷识别"], weight=1.0, status="active",
    )
    db.add(thread)
    dims = {"firsthand": 80, "ai_relevance": 90, "power_relevance": 40,
            "utility": 60, "impact": 50, "depth": 70}
    article = schema.Article(title="缺陷识别新方法", kind="资讯", tier="T1", scored=True,
                             dim_scores=dims, channel="行业动态", relevance_score=0)
    db.add(article)
    db.commit()

    recompute_all(db)
    db.refresh(article)
    recomputed = article.relevance_score

    expected = _apply_thread_score(article, {"dims": dims}, [thread], get_scoring_config(db))
    assert recomputed == expected


def test_recompute_never_recommends_noise_or_rule_fallbacks(db):
    dims = {"firsthand": 100, "ai_relevance": 100, "power_relevance": 100,
            "utility": 100, "impact": 100, "depth": 100}
    noise = schema.Article(
        title="噪音", scored=True, scored_by="unscored", curated=True, hot=True,
        noise_reason="预筛判定无关（无关）", dim_scores=dims,
        channel="行业动态", relevance_score=100,
    )
    fallback = schema.Article(
        title="规则回退", scored=True, scored_by="rule", curated=True, hot=True,
        dim_scores=dims, channel="行业动态", relevance_score=100,
    )
    db.add_all([noise, fallback])
    db.commit()

    recompute_all(db)
    db.refresh(noise)
    db.refresh(fallback)

    assert noise.curated is False and noise.hot is False
    assert fallback.curated is False and fallback.hot is False
