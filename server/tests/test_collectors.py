"""采集器测试：直接用 sources.yaml 里的真实配置跑样例 HTML，保证迁移后的正则没有走样。"""
from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.collectors.base import CollectorResult
from app.collectors.fulltext import extract_main
from app.collectors.http import PoliteClient, decode_html
from app.collectors.registry import build_collector
from app.collectors.textutil import canonical_url, parse_cn_datetime
from app.seed.loader import load_source_specs

SPECS = {s.key: s for s in load_source_specs()}


async def run_source(key: str, pages: dict[str, str | int]) -> CollectorResult:
    spec = SPECS[key]
    collector = build_collector(spec.key, spec.kind, spec.url, spec.config)
    with respx.mock(assert_all_called=False) as mock:
        for url, body in pages.items():
            if isinstance(body, int):
                mock.get(url).mock(return_value=httpx.Response(body))
            else:
                mock.get(url).mock(return_value=httpx.Response(200, html=body))
        mock.route().mock(return_value=httpx.Response(200, html="<html></html>"))
        async with PoliteClient(min_interval_s=0) as client:
            return await collector.fetch(client)


async def test_sgcc_parses_division_news_and_row_date():
    html = """
    <li><a href="/zxzx/gsxw/2026/07/478387.shtml">国内首套变压器故障主动防御装置投入运行</a><span>2026-07-23</span></li>
    <li><a href="/about/">关于我们</a></li>
    """
    result = await run_source("sgcc-nc", {"http://www.nc.sgcc.com.cn/zxzx/gsxw/": html})
    assert result.healthy
    assert [i.title for i in result.items] == ["国内首套变压器故障主动防御装置投入运行"]
    assert result.items[0].published_at == datetime(2026, 7, 22, 16, tzinfo=UTC)  # 北京时间零点


async def test_nea_keeps_only_official_article_links():
    html = """
    <a href="/20260724/808ea736bb9741909dd46f8cb32ea0de/c.html">国家能源局正式发布中国绿证价格指数</a>
    <a href="https://www.news.cn/politics/example.html">外站转载的一条很长的新闻标题</a>
    """
    result = await run_source("nea", {"https://www.nea.gov.cn/": html})
    assert len(result.items) == 1
    assert result.items[0].url.startswith("https://www.nea.gov.cn/20260724/")


async def test_csg_ignores_wechat_reposts():
    html = """
    <a href="/xwzx/2026/2026gsyw/202607/t20260724_356435.html">南方电网部署三季度重点工作</a>
    <a href="https://mp.weixin.qq.com/s/example">微信转载内容不会冒充官网原文</a>
    """
    result = await run_source("csg", {"https://www.csg.cn/": html})
    assert [i.title for i in result.items] == ["南方电网部署三季度重点工作"]


async def test_ccgp_filters_by_power_keywords_and_hints_tender():
    html = """
    <a href="/cggg/zygg/gkzb/202607/t20260724_1.htm">某单位食堂食材采购公开招标公告</a>
    <a href="/cggg/zygg/gkzb/202607/t20260724_2.htm">某市供电公司输电线路无人机巡检服务公开招标公告</a>
    """
    result = await run_source("ccgp", {"http://www.ccgp.gov.cn/cggg/zygg/gkzb/": html})
    assert [i.title for i in result.items] == ["某市供电公司输电线路无人机巡检服务公开招标公告"]
    assert result.items[0].channel_hint == "tender"
    # 地方公告页没 mock 到具体内容也算成功（空页），整体仍健康
    assert result.transport_status == "ok"


async def test_csg_bidding_skips_bracket_titles_and_nav():
    html = """
    <li><a href="/zbgg/1200436919.jhtml">南方电网新型配电系统供电品质管理项目招标公告</a> 2026-07-24</li>
    <li><a href="/zbgg/1200436920.jhtml">[已结束] 某变电站二次设备采购项目招标公告</a></li>
    <li><a href="/index.jhtml">采购公告</a></li>
    """
    result = await run_source("csg-bidding", {"https://www.bidding.csg.cn/zbcg/index.jhtml": html})
    assert [i.title for i in result.items] == ["南方电网新型配电系统供电品质管理项目招标公告"]
    assert result.items[0].published_at is not None


async def test_bjx_partial_failure_is_reported_not_swallowed():
    html = '<a href="https://news.bjx.com.cn/html/20260725/1459000.shtml">某省 220kV 变电站新建工程施工招标公告</a>'
    result = await run_source("bjx-tender", {
        "https://shupeidian.bjx.com.cn/zb/": html,
        "https://chuneng.bjx.com.cn/zb/": 502,
        "https://fd.bjx.com.cn/zb/": "<html></html>",
    })
    assert len(result.items) == 1
    assert result.transport_status == "partial"
    assert "chuneng" in (result.error or "")


async def test_all_lists_failing_is_an_error():
    result = await run_source("nea", {"https://www.nea.gov.cn/": 503})
    assert not result.healthy
    assert result.transport_status == "http_error"
    assert result.http_status == 503


def test_every_seed_source_builds_a_collector():
    for spec in SPECS.values():
        build_collector(spec.key, spec.kind, spec.url, spec.config)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("发布时间：2026年9月28日 10:30", datetime(2026, 9, 28, 2, 30, tzinfo=UTC)),
        ("2026-09-28", datetime(2026, 9, 27, 16, tzinfo=UTC)),
        ("3小时前", datetime(2026, 9, 28, 1, 0, tzinfo=UTC)),
        ("昨天 08:15", datetime(2026, 9, 27, 0, 15, tzinfo=UTC)),
        ("无日期", None),
    ],
)
def test_parse_cn_datetime(text, expected):
    now = datetime(2026, 9, 28, 4, 0, tzinfo=UTC)  # 北京时间 12:00
    assert parse_cn_datetime(text, now=now) == expected


def test_decode_html_falls_back_to_gb18030():
    raw = "<html><body>国家电网招标公告</body></html>".encode("gbk")
    assert "国家电网招标公告" in decode_html(raw, "text/html")


def test_canonical_url_drops_tracking():
    assert canonical_url("HTTPS://WWW.A.com/x?utm_source=1&id=2#frag") == "https://www.a.com/x?id=2"


def test_extract_main_rejects_block_pages_and_uses_selector():
    body = "正文" * 100
    ok = extract_main(f"<div class='nav'>导航</div><div id='ArtText'><p>{body}</p></div>", ("#ArtText",))
    assert ok is not None and ok.text.startswith("正文")
    blocked = extract_main(f"<div id='ArtText'>为了更好的访问体验，请进行验证{body}</div>", ("#ArtText",))
    assert blocked is None
