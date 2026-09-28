"""数据库集成测试：采集入库 → 处理 → 归并 → API → 日报，以及队列与鉴权。LLM 用桩替身。"""
from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
import respx
from sqlalchemy import func, select

from app.collectors.http import PoliteClient
from app.config import settings
from app.db import SessionLocal
from app.models import Digest, Item, Job, Lead, Source, SourceRun, Story
from app.models.enums import DigestKind
from app.pipeline import analyze as analyze_mod
from app.pipeline.collect import collect_source, due_sources
from app.pipeline.llm_schemas import AnalyzeOutput, ScreenOutput, ScreenRow
from app.pipeline.process import process_items
from app.pipeline.stories import recompute_heat
from app.pipeline.tuning import Tuning, load_tuning, save_tuning
from app.seed.loader import load_source_specs, sync_sources
from app.worker import queue

pytestmark = pytest.mark.db

TENDER_HTML = """
<li><a href="/cggg/zygg/gkzb/202609/t20260927_1.htm">国网某省电力公司输电线路无人机巡检服务公开招标公告</a></li>
<li><a href="/cggg/zygg/gkzb/202609/t20260927_2.htm">某市供电局220kV变电站视频监控系统改造采购项目公开招标公告</a></li>
<li><a href="/cggg/zygg/gkzb/202609/t20260927_3.htm">某供电公司职工食堂食材采购项目公开招标公告</a></li>
"""
DETAIL_1 = """<div class="vF_detail_content"><p>国网某省电力公司输电线路无人机巡检服务公开招标公告。
招标编号：GW-2026-0931。招标人：国网某省电力有限公司。覆盖 500kV 线路，预算金额 1280.5 万元。
投标截止时间：2026年10月15日 09:30。投标人须具备电力设施承装类资质。</p>
<p>其余说明文字其余说明文字其余说明文字其余说明文字其余说明文字其余说明文字其余说明文字。</p></div>"""


def fake_analysis(title: str) -> AnalyzeOutput:
    if "无人机" in title:
        return AnalyzeOutput.model_validate({
            "title_zh": "某省输电线路无人机巡检服务招标，预算1280万",
            "summary": "国网某省电力公司招标输电线路无人机巡检服务，覆盖500kV线路，预算1280.5万元，10月15日截止。",
            "reason": "与智能运检业务直接对口的在招项目",
            "action": "10月15日前投标，准备无人机巡检业绩",
            "channel": "tender", "province": "某省", "tags": ["无人机巡检", "输电线路"],
            "event_key": "some-province-uav-inspection-tender",
            "scores": {"relevance": 10, "opportunity": 9, "certainty": 9, "timeliness": 9, "impact": 6},
            "lead": {"project_name": "输电线路无人机巡检服务", "owner": "国网某省电力有限公司",
                     "bid_no": "GW-2026-0931", "amount_wan": 1280.5, "voltage_kv": 500,
                     "deadline": "2026-10-15 09:30", "stage": "tendering", "biz_line": "inspection_ai",
                     "match_score": 92, "winner": "瞎编的中标人"},
        })
    return AnalyzeOutput.model_validate({
        "title_zh": "某市220kV变电站视频监控改造采购", "summary": "视频监控系统改造。", "reason": "对口",
        "channel": "tender", "scores": {"relevance": 8, "opportunity": 7, "certainty": 8, "timeliness": 7, "impact": 3},
        "lead": {"amount_wan": 99999, "stage": "tendering", "biz_line": "inspection_ai", "match_score": 70},
    })


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    async def fake_complete_json(*, task: str, schema: type, user: str, **_: object) -> object:
        calls.append(task)
        if schema is ScreenOutput:
            n = user.count("\n") + 1
            return ScreenOutput(results=[ScreenRow(i=i, relevant=True, channel="industry") for i in range(1, n + 1)])
        title = next(line for line in user.splitlines() if line.startswith("标题："))
        return fake_analysis(title)

    monkeypatch.setattr(analyze_mod, "complete_json", fake_complete_json)
    return calls


async def seed_ccgp(session) -> Source:
    await sync_sources(session, [s for s in load_source_specs() if s.key == "ccgp"])
    return (await session.scalars(select(Source).where(Source.key == "ccgp"))).one()


def mock_ccgp(mock: respx.MockRouter) -> None:
    mock.get("http://www.ccgp.gov.cn/cggg/zygg/gkzb/").mock(return_value=httpx.Response(200, html=TENDER_HTML))
    mock.get("http://www.ccgp.gov.cn/cggg/dfgg/gkzb/").mock(return_value=httpx.Response(200, html="<html/>"))
    mock.get("http://www.ccgp.gov.cn/cggg/zygg/gkzb/202609/t20260927_1.htm").mock(
        return_value=httpx.Response(200, html=DETAIL_1))
    mock.route().mock(return_value=httpx.Response(404))


async def test_seed_sync_keeps_user_toggles(session):
    await sync_sources(session)
    src = (await session.scalars(select(Source).where(Source.key == "nea"))).one()
    src.enabled, src.interval_min = False, 999
    await session.commit()
    await sync_sources(session)
    await session.refresh(src)
    assert (src.enabled, src.interval_min) == (False, 999)
    assert await session.scalar(select(func.count()).select_from(Source)) == len(load_source_specs())


async def test_collect_upserts_and_records_health(session):
    source = await seed_ccgp(session)
    with respx.mock(assert_all_called=False) as mock:
        mock_ccgp(mock)
        async with PoliteClient(min_interval_s=0) as client:
            first = await collect_source(session, client, source)
            second = await collect_source(session, client, source)
    assert first.healthy and len(first.new_ids) == 3  # 食堂那条在处理阶段由规则拦截
    assert second.new_ids == []  # 第二次只刷新 last_seen_at
    runs = (await session.scalars(select(SourceRun).order_by(SourceRun.id))).all()
    assert [r.new_count for r in runs] == [3, 0]
    assert source.fail_streak == 0 and source.last_ok_at is not None
    assert (await session.scalars(select(Item.channel))).all() == ["tender"] * 3


async def test_failing_source_backs_off(session):
    source = await seed_ccgp(session)
    with respx.mock(assert_all_called=False) as mock:
        mock.route().mock(return_value=httpx.Response(503))
        async with PoliteClient(min_interval_s=0) as client:
            out = await collect_source(session, client, source)
    assert not out.healthy and source.fail_streak == 1
    later = datetime.now(UTC) + timedelta(minutes=source.interval_min + 1)
    assert source not in await due_sources(session, later)  # 失败后间隔翻倍
    assert source in await due_sources(session, later + timedelta(minutes=source.interval_min))


async def test_full_pipeline(session, fake_llm):
    source = await seed_ccgp(session)
    with respx.mock(assert_all_called=False) as mock:
        mock_ccgp(mock)
        async with PoliteClient(min_interval_s=0) as client:
            out = await collect_source(session, client, source)
            stats = await process_items(session, client, out.new_ids)

    assert stats.screened_out == 1 and stats.analyzed == 2 and stats.failed == 0
    assert stats.fulltext == 1
    assert "screen" not in fake_llm  # 招标平台信源免初筛

    uav = (await session.scalars(select(Item).where(Item.title.contains("无人机")))).one()
    assert uav.selected and uav.score and uav.score > 80
    lead = await session.get(Lead, uav.id)
    assert lead is not None
    assert lead.bid_no == "GW-2026-0931" and float(lead.amount_wan or 0) == 1280.5 and lead.voltage_kv == 500
    assert lead.winner is None and "winner" in lead.dropped_fields  # 原文没有的中标人被 grounding 丢弃
    assert lead.deadline_at is not None

    video = (await session.scalars(select(Item).where(Item.title.contains("视频监控")))).one()
    video_lead = await session.get(Lead, video.id)
    assert video_lead is not None and video_lead.amount_wan is None  # 编造的金额被丢弃
    assert (await session.scalar(select(func.count()).select_from(Story))) == 2

    canteen = (await session.scalars(select(Item).where(Item.title.contains("食堂")))).one()
    assert canteen.status == "screened_out"


async def test_same_bid_number_merges_and_prefers_t1(session, fake_llm):
    await sync_sources(session, [s for s in load_source_specs() if s.key in ("ccgp", "bjx-tender")])
    ccgp, bjx = (await session.scalars(select(Source).order_by(Source.key.desc()))).all()
    assert (ccgp.key, bjx.key) == ("ccgp", "bjx-tender")
    now = datetime.now(UTC)
    body = DETAIL_1.replace("<p>", "").replace("</p>", "")
    media = Item(source_id=bjx.id, tier=bjx.tier, url="https://news.bjx.com.cn/html/20260927/1.shtml",
                 url_hash="a" * 64, title="转载：国网某省输电线路无人机巡检服务招标", content_text=body,
                 channel="tender", first_seen_at=now)
    official = Item(source_id=ccgp.id, tier=ccgp.tier, url="https://www.ccgp.gov.cn/x.htm", url_hash="b" * 64,
                    title="国网某省电力公司输电线路无人机巡检服务公开招标公告", content_text=body,
                    channel="tender", first_seen_at=now)
    session.add_all([media, official])
    await session.commit()
    async with PoliteClient(min_interval_s=0) as client:
        await process_items(session, client, [media.id, official.id])
    await session.refresh(media)
    await session.refresh(official)
    assert media.story_id == official.story_id
    assert official.is_story_lead and not media.is_story_lead
    story = await session.get(Story, official.story_id)
    assert story is not None and story.source_count == 2 and story.key == "bid:gw20260931"
    assert await recompute_heat(session) == 1
    await session.refresh(story)
    assert story.heat > 19


async def test_tuning_threshold_really_applies(session, fake_llm):
    # 无人机条目加权原始分 88.5：默认 T1 系数 1.2 下必进精选；系数改 1.0、门槛改 95 后必须落选
    await save_tuning(session, Tuning(tier_coef={"T1": 1.0, "T1_5": 1.0, "T2": 1.0},
                                      thresholds={"T1": 95, "T1_5": 95, "T2": 95}))
    assert (await load_tuning(session)).thresholds["T1"] == 95
    source = await seed_ccgp(session)
    with respx.mock(assert_all_called=False) as mock:
        mock_ccgp(mock)
        async with PoliteClient(min_interval_s=0) as client:
            out = await collect_source(session, client, source)
            stats = await process_items(session, client, out.new_ids)
    assert stats.analyzed == 2 and stats.selected == 0


async def test_llm_config_error_marks_failed_without_fake_scores(session, monkeypatch):
    from app.llm.client import LlmError

    async def broken(**_: object) -> object:
        raise LlmError("HTTP 400 配置/额度故障（不会自愈）", retryable=False)

    monkeypatch.setattr(analyze_mod, "complete_json", broken)
    source = await seed_ccgp(session)
    with respx.mock(assert_all_called=False) as mock:
        mock_ccgp(mock)
        async with PoliteClient(min_interval_s=0) as client:
            out = await collect_source(session, client, source)
            stats = await process_items(session, client, out.new_ids)
    assert stats.failed == 2 and stats.analyzed == 0
    failed = (await session.scalars(select(Item).where(Item.status == "failed"))).all()
    assert all(i.score is None and i.attempts == 3 for i in failed)  # 不自动重试、不冒充分数


# ---------- 队列 ----------

async def test_queue_dedupe_and_concurrent_claim(session):
    assert await queue.enqueue(session, "collect", {"source_id": 1}, dedupe_key="collect:x") is not None
    assert await queue.enqueue(session, "collect", {"source_id": 1}, dedupe_key="collect:x") is None
    for n in range(5):
        await queue.enqueue(session, "process", {"n": n})
    await session.commit()

    async def claim_one(worker: str) -> int | None:
        async with SessionLocal() as s:
            job = await queue.claim(s, worker)
            return job.id if job else None

    claimed = await asyncio.gather(*(claim_one(f"w{n}") for n in range(8)))
    got = [c for c in claimed if c is not None]
    assert len(got) == len(set(got)) == 6


async def test_queue_retry_then_fail_and_recover(session):
    await queue.enqueue(session, "x", max_attempts=2)
    await session.commit()
    job = await queue.claim(session, "w")
    assert job is not None
    await queue.fail(session, job, "boom")
    assert job.status == "queued" and job.run_after > datetime.now(UTC)
    job.run_after = datetime.now(UTC)
    await session.commit()
    job = await queue.claim(session, "w")
    assert job is not None
    await queue.fail(session, job, "boom again")
    assert job.status == "failed"
    # 同一 dedupe_key 在前一个任务结束后可以再次入队
    await queue.enqueue(session, "y", dedupe_key="k")
    await session.commit()
    stale = await queue.claim(session, "w")
    assert stale is not None
    stale.heartbeat_at = datetime.now(UTC) - timedelta(hours=1)
    await session.commit()
    assert await queue.recover_stale(session) == 1
    assert await queue.enqueue(session, "y", dedupe_key="k") is None
    assert await session.scalar(select(func.count()).select_from(Job)) == 2


# ---------- API ----------

@pytest.fixture
async def api():
    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_api_feed_detail_leads_and_digest(session, fake_llm, api):
    source = await seed_ccgp(session)
    with respx.mock(assert_all_called=False) as mock:
        mock_ccgp(mock)
        async with PoliteClient(min_interval_s=0) as client:
            out = await collect_source(session, client, source)
            await process_items(session, client, out.new_ids)

    r = await api.get("/api/items", params={"view": "selected", "limit": 1})
    assert r.status_code == 200
    page = r.json()
    assert len(page["items"]) == 1 and page["next_cursor"]
    r2 = await api.get("/api/items", params={"view": "selected", "limit": 1, "cursor": page["next_cursor"]})
    assert r2.json()["items"][0]["id"] != page["items"][0]["id"]

    etag = r.headers["etag"]
    r304 = await api.get("/api/items", params={"view": "selected", "limit": 1}, headers={"If-None-Match": etag})
    assert r304.status_code == 304

    uav_id = next(i["id"] for i in page["items"] + r2.json()["items"] if "无人机" in i["title"])
    detail = (await api.get(f"/api/items/{uav_id}")).json()
    assert detail["lead"]["bid_no"] == "GW-2026-0931" and detail["dims"]["relevance"] == 10
    assert detail["content_html"]

    leads = (await api.get("/api/leads", params={"sort": "amount", "min_voltage_kv": 220})).json()
    assert leads["total"] == 1 and leads["items"][0]["lead"]["voltage_kv"] == 500
    r = await api.patch(f"/api/leads/{uav_id}", json={"follow_status": "following", "follow_note": "已联系"})
    assert r.json()["follow_status"] == "following"
    assert (await api.get("/api/leads", params={"follow": "following"})).json()["total"] == 1

    await api.patch(f"/api/items/{uav_id}", json={"starred": True})
    assert len((await api.get("/api/items", params={"view": "starred"})).json()["items"]) == 1
    assert len((await api.get("/api/items", params={"view": "screened"})).json()["items"]) == 1
    assert (await api.get("/api/items/search", params={"q": "无人机"})).json()[0]["id"] == uav_id

    meta = (await api.get("/api/meta")).json()
    assert meta["llm_enabled"] is False and len(meta["channels"]) == 9
    sources = (await api.get("/api/sources")).json()
    assert sources[0]["runs_24h"] == 1 and sources[0]["new_7d"] == 3

    today = datetime.now(settings.tz).date() + timedelta(days=1)  # 窗口覆盖到当前时刻
    async with SessionLocal() as s:
        from app.digest.builder import build_digest
        digest = await build_digest(s, DigestKind.DAILY, today)
    assert digest.issue_no == 1 and digest.content["stats"]["items"] == 2
    d = (await api.get(f"/api/digests/daily/{today.isoformat()}")).json()
    assert d["sections"][0]["name"] == "商机速递" and len(d["sections"][0]["items"]) == 2
    assert d["overview"] is None  # 未配置模型时不编导语
    assert "（本期完）" in d["markdown"]
    assert await session.scalar(select(func.count()).select_from(Digest)) == 1


async def test_auth_required_when_password_set(session, api, monkeypatch):
    monkeypatch.setattr(settings, "app_password", "correct horse battery")
    assert (await api.get("/api/items")).status_code == 401
    assert (await api.post("/api/auth/login", json={"password": "wrong"})).status_code == 401
    r = await api.post("/api/auth/login", json={"password": "correct horse battery"})
    assert r.status_code == 200 and "pa_session" in r.cookies
    assert (await api.get("/api/items")).status_code == 200
    tampered = r.cookies["pa_session"][:-2] + "xx"
    api.cookies.set("pa_session", tampered)
    assert (await api.get("/api/items")).status_code == 401


def test_daily_window_is_beijing_morning():
    from app.digest.builder import daily_window

    start, end = daily_window(date(2026, 9, 28))
    assert end.astimezone(UTC) == datetime(2026, 9, 28, 0, 0, tzinfo=UTC)
    assert (end - start) == timedelta(days=1)
