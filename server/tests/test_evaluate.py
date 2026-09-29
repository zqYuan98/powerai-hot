"""精选校准：标注抽样、评测指标与门槛扫描、重跑不写回条目。"""
from __future__ import annotations

import pytest
import respx
from sqlalchemy import select

from app.collectors.http import PoliteClient
from app.db import SessionLocal
from app.models import EvalRun, Item, Job, Lead
from app.pipeline.collect import collect_source
from app.pipeline.evaluate import confusion, format_report, run_eval, split_of, sweep
from app.pipeline.process import process_items
from app.pipeline.tuning import Tuning, save_tuning
from tests.test_integration import api, fake_llm, mock_ccgp, seed_ccgp  # noqa: F401


def case(gold: str, *, selected: bool, score: float | None, stage: str = "analyzed", forced: bool = False) -> dict:
    return {"gold": gold, "selected": selected, "score": score, "stage": stage, "forced_reject": forced}


def test_confusion_skips_either_and_unjudged():
    cases = [
        case("select", selected=True, score=80),
        case("select", selected=False, score=50),
        case("reject", selected=True, score=70),
        case("reject", selected=False, score=None, stage="screen", forced=True),
        case("either", selected=True, score=90),
        case("select", selected=False, score=None, stage="failed"),
    ]
    m = confusion(cases, lambda c: c["selected"])
    assert (m["n"], m["tp"], m["fp"], m["fn"], m["tn"]) == (4, 1, 1, 1, 1)
    assert m["precision"] == 0.5 and m["recall"] == 0.5 and m["f1"] == 0.5


def test_sweep_keeps_forced_rejects_out():
    cases = [
        case("select", selected=True, score=80),
        case("reject", selected=False, score=95, forced=True),  # 已过截止：分数再高也不选
        case("reject", selected=False, score=55),
    ]
    rows = {r["threshold"]: r for r in sweep(cases)}
    assert rows[50]["predicted"] == 2 and rows[50]["precision"] == 0.5
    assert rows[60]["predicted"] == 1 and rows[60]["precision"] == 1.0
    assert rows[90]["predicted"] == 0 and rows[90]["recall"] == 0.0


def test_split_is_stable():
    assert split_of(10) == "holdout" and split_of(11) == "development"


@pytest.mark.db
async def test_label_then_evaluate(session, fake_llm, api):  # noqa: F811
    source = await seed_ccgp(session)
    with respx.mock(assert_all_called=False) as mock:
        mock_ccgp(mock)
        async with PoliteClient(min_interval_s=0) as client:
            out = await collect_source(session, client, source)
            await process_items(session, client, out.new_ids)

    gold = {"无人机": "select", "视频监控": "reject", "食堂": "reject"}
    seen = set()
    while (case_ := (await api.get("/api/gold/next")).json()) is not None:
        assert "score" not in case_ and "summary" not in case_  # 标注时不给看系统判断
        seen.add(case_["item_id"])
        decision = next(v for k, v in gold.items() if k in case_["title"])
        stats = (await api.put(f"/api/gold/{case_['item_id']}", json={"decision": decision})).json()
    assert len(seen) == 3 and stats["total"] == 3
    assert stats["stratum"] == {"selected": 2, "screened": 1}

    stored = await run_eval(session, mode="stored", split="all")
    m = stored.metrics
    assert stored.status == "done" and (m["tp"], m["fp"], m["tn"]) == (1, 1, 1)  # 视频监控被多选
    assert "[多选]" in format_report(stored)

    video = (await session.scalars(select(Item).where(Item.title.contains("视频监控")))).one()
    uav = (await session.scalars(select(Item).where(Item.title.contains("无人机")))).one()
    video_id, video_score, uav_id = video.id, video.score, uav.id
    await save_tuning(session, Tuning(thresholds={"T1": 90, "T1_5": 90, "T2": 90}))
    async with SessionLocal() as s:
        rerun = await run_eval(s, mode="rerun", split="all", label="门槛 90")
    assert rerun.status == "done" and rerun.metrics["precision"] == 1.0 and rerun.metrics["recall"] == 1.0
    assert rerun.params["config_hash"]

    # 重跑只在内存里判断，不写回条目和商机
    async with SessionLocal() as s:
        video = await s.get(Item, video_id)
        assert video is not None and video.selected and video.score == video_score
        lead = await s.get(Lead, uav_id)
        assert lead is not None and lead.bid_no == "GW-2026-0931"

    runs = (await api.get("/api/eval-runs")).json()
    assert [r["id"] for r in runs] == [rerun.id, stored.id] and runs[1]["metrics"]["precision"] == 0.5
    detail = (await api.get(f"/api/eval-runs/{stored.id}")).json()
    assert [e["item_id"] for e in detail["errors"]] == [video.id] and len(detail["sweep"]) > 10

    assert (await api.post("/api/eval-runs", json={"mode": "rerun"})).json()["detail"].startswith("评测已加入")
    assert (await api.post("/api/eval-runs", json={})).json()["detail"] == "已有评测在进行中"
    job = (await session.scalars(select(Job).where(Job.kind == "eval"))).one()
    assert job.max_attempts == 1  # 重跑花钱，失败不自动重试

    after = (await api.delete(f"/api/gold/{video.id}")).json()
    assert after["total"] == 2
    assert await session.scalar(select(EvalRun.id).where(EvalRun.id == stored.id))
