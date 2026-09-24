from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx
import pytest

from collector.aihot import AihotCollector
from collector.aggregator import AggregatorCollector
from collector.csg_bidding import SouthernGridBiddingCollector
from collector.frontier import FrontierSnapshotCollector
from collector.gov_procurement import GovProcurementCollector
from collector.arxiv import ArxivCollector
from collector.github_releases import GitHubReleasesCollector
from collector.hf_papers import HFPapersCollector
from collector.http_utils import USER_AGENT
from collector.nea import NeaCollector
from collector.sgcc_news import SgccNewsCollector
from collector.southern_grid import SouthernGridCollector


class FakeResponse:
    def __init__(self, *, status_code=200, headers=None, data=None, text="", url="https://example.com/"):
        self.status_code = status_code
        self.headers = headers or {"content-type": "application/json"}
        self._data = data
        self.text = text
        self.content = text.encode("utf-8")
        self.url = url

    def json(self):
        if isinstance(self._data, Exception):
            raise self._data
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", self.url)
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("request failed", request=request, response=response)


def test_state_grid_collector_parses_official_division_news(monkeypatch):
    html = """
    <a href="/zxzx/gsxw/2026/07/478387.shtml">国内首套变压器故障主动防御装置投入运行</a>
    <a href="/about/">关于我们</a>
    """
    monkeypatch.setattr(
        "collector.sgcc_news.httpx.get",
        lambda url, **kwargs: FakeResponse(text=html, url=url, headers={"content-type": "text/html"}),
    )

    result = SgccNewsCollector(limit=5).fetch()

    assert result.parse_status == "ok"
    assert len(result.items) == 1
    item = result.items[0]
    assert item.title == "国内首套变压器故障主动防御装置投入运行"
    assert item.url == "http://www.nc.sgcc.com.cn/zxzx/gsxw/2026/07/478387.shtml"
    assert item.published_at.isoformat() == "2026-07-01T00:00:00+00:00"
    assert item.source_name == "国家电网"


def test_nea_collector_keeps_official_articles_and_policy_channel(monkeypatch):
    html = """
    <a href="/20260724/808ea736bb9741909dd46f8cb32ea0de/c.html">国家能源局正式发布中国绿证价格指数</a>
    <a href="https://www.news.cn/politics/example.html">外站转载</a>
    """
    monkeypatch.setattr(
        "collector.nea.httpx.get",
        lambda url, **kwargs: FakeResponse(text=html, url=url, headers={"content-type": "text/html"}),
    )

    result = NeaCollector(limit=5).fetch()

    assert result.parse_status == "ok"
    assert [item.title for item in result.items] == ["国家能源局正式发布中国绿证价格指数"]
    assert result.items[0].channel == "政策法规"
    assert result.items[0].published_at.isoformat() == "2026-07-24T00:00:00+00:00"


def test_southern_grid_news_collector_only_uses_csg_news_links(monkeypatch):
    html = """
    <a href="/xwzx/2026/2026gsyw/202607/t20260724_356435.html">南方电网部署三季度重点工作</a>
    <a href="https://mp.weixin.qq.com/s/example">微信转载内容不会冒充官网原文</a>
    """
    monkeypatch.setattr(
        "collector.southern_grid.httpx.get",
        lambda url, **kwargs: FakeResponse(text=html, url=url, headers={"content-type": "text/html"}),
    )

    result = SouthernGridCollector(limit=5).fetch()

    assert result.parse_status == "ok"
    assert [item.url for item in result.items] == [
        "https://www.csg.cn/xwzx/2026/2026gsyw/202607/t20260724_356435.html"
    ]
    assert result.items[0].published_at.isoformat() == "2026-07-24T00:00:00+00:00"


def test_government_procurement_filters_for_power_and_ai_projects(monkeypatch):
    html = """
    <a href="/cggg/zygg/gkzb/202607/t20260724_1.htm">某单位食堂食材采购公开招标公告</a>
    <a href="/cggg/zygg/gkzb/202607/t20260724_2.htm">城市新能源电力调度智能平台公开招标公告</a>
    """
    monkeypatch.setattr(
        "collector.gov_procurement.httpx.get",
        lambda url, **kwargs: FakeResponse(text=html, url=url, headers={"content-type": "text/html"}),
    )

    result = GovProcurementCollector(limit=5).fetch()

    assert result.parse_status == "ok"
    assert [item.title for item in result.items] == ["城市新能源电力调度智能平台公开招标公告"]
    assert result.items[0].channel == "招标公告"
    assert result.items[0].published_at.isoformat() == "2026-07-24T00:00:00+00:00"


def test_southern_grid_bidding_collector_maps_procurement_notices(monkeypatch):
    html = """
    <a href="/zbgg/1200436919.jhtml">南方电网新型配电系统供电品质管理项目招标公告</a>
    <a href="/index.jhtml">采购公告</a>
    """
    monkeypatch.setattr(
        "collector.csg_bidding.httpx.get",
        lambda url, **kwargs: FakeResponse(text=html, url=url, headers={"content-type": "text/html"}),
    )

    result = SouthernGridBiddingCollector(limit=5).fetch()

    assert result.parse_status == "ok"
    assert [item.title for item in result.items] == ["南方电网新型配电系统供电品质管理项目招标公告"]
    assert result.items[0].channel == "招标公告"
    assert result.items[0].source_name == "南方电网供应链"


def test_frontier_snapshot_maps_github_trending_to_cases(monkeypatch):
    payload = {
        "generated_at": "2026-07-24T15:54:23.668882",
        "source": {"id": "github-daily"},
        "items": [
            {
                "source": "GitHub Trending Daily",
                "title": "org/plain-web-server",
                "url": "https://github.com/org/plain-web-server",
                "original_summary": "A conventional static web server",
                "chinese_summary": "普通静态网页服务器",
                "meta": {"language": "Rust", "stars": 9999},
            },
            {
                "source": "GitHub Trending Daily",
                "title": "org/grid-vision",
                "url": "https://github.com/org/grid-vision",
                "original_summary": "Power-grid visual inspection toolkit",
                "chinese_summary": "电网视觉巡检工具集",
                "meta": {"language": "Python", "stars": 1200},
            }
        ],
    }
    monkeypatch.setattr(
        "collector.frontier.httpx.get",
        lambda url, **kwargs: FakeResponse(data=payload, url=url),
    )

    result = FrontierSnapshotCollector(limit=5).fetch()

    assert result.parse_status == "ok"
    item = result.items[0]
    assert item.title == "org/grid-vision"
    assert item.content == "电网视觉巡检工具集"
    assert item.channel == "落地案例"
    assert item.kind == "案例"
    assert item.source_external_id == "org/grid-vision"
    assert item.meta["lock_channel"] is True


def test_aihot_default_public_items_endpoint_normalizes_time_and_provenance(monkeypatch):
    payload = {
        "count": 1,
        "hasNext": False,
        "nextCursor": None,
        "items": [
            {
                "id": "a1",
                "title": "AIHOT selected: OpenAI OCR model",
                "title_en": "OpenAI OCR model",
                "summary": "summary",
                "url": "https://example.com/original",
                "permalink": "https://aihot.virxact.com/items/a1",
                "publishedAt": "2026-07-17T08:00:00+08:00",
                "category": "models",
                "source": "AI HOT source",
                "selected": True,
            }
        ],
    }
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse(data=payload)

    monkeypatch.setattr("collector.aihot.httpx.get", fake_get)

    result = AihotCollector(limit=12).fetch()

    assert result.transport_status == "ok"
    assert result.parse_status == "ok"
    parsed = urlsplit(captured["url"])
    params = captured["kwargs"]["params"]
    since = datetime.fromisoformat(params["since"].replace("Z", "+00:00"))
    assert parsed.scheme == "https"
    assert parsed.netloc == "aihot.virxact.com"
    assert parsed.path == "/api/public/items"
    assert params["mode"] == "selected"
    assert params["take"] == 12
    assert params["since"].endswith("Z")
    assert since.tzinfo == timezone.utc
    assert captured["kwargs"]["headers"] == {"User-Agent": USER_AGENT, "Accept": "application/json"}
    item = result.items[0]
    assert item.url == "https://example.com/original"
    assert item.published_at.isoformat() == "2026-07-17T00:00:00+00:00"
    assert item.source_external_id == "a1"
    assert item.source_name == "AI HOT source"
    assert item.provenance["detail_url"] == "https://aihot.virxact.com/items/a1"
    assert item.provenance["attribution"] == "AIHOT public API"


def test_aggregator_rejects_bad_content_type(monkeypatch):
    monkeypatch.setattr(
        "collector.aggregator.httpx.get",
        lambda *a, **k: FakeResponse(headers={"content-type": "text/html"}, text="<html></html>"),
    )

    result = AggregatorCollector(url="https://agg.test/latest-24h.json").fetch()

    assert result.transport_status == "ok"
    assert result.parse_status == "schema_error"


def test_aggregator_default_timeout_falls_back_to_jsdelivr(monkeypatch):
    payload = {"items": [{"id": "1", "title": "fallback works", "url": "https://example.com/1"}]}
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if "raw.githubusercontent.com" in url:
            raise httpx.ReadTimeout("raw github timed out")
        return FakeResponse(data=payload, url=url)

    monkeypatch.setattr("collector.aggregator.httpx.get", fake_get)

    result = AggregatorCollector(limit=5).fetch()

    assert result.parse_status == "ok"
    assert [item.title for item in result.items] == ["fallback works"]
    assert calls == [
        "https://raw.githubusercontent.com/SuYxh/ai-news-aggregator/main/data/latest-24h.json",
        "https://cdn.jsdelivr.net/gh/SuYxh/ai-news-aggregator@main/data/latest-24h.json",
    ]


def test_aggregator_latest_24h_maps_source_and_canonical_url(monkeypatch):
    payload = {
        "generated_at": "2026-07-17T00:00:00Z",
        "window_hours": 24,
        "total_items": 1,
        "site_count": 1,
        "source_count": 1,
        "site_stats": {},
        "items": [
            {
                "id": "x1",
                "site_id": "example",
                "site_name": "Example Site",
                "source": "Example Feed",
                "title": "vLLM releases a new version",
                "url": "https://example.com/a?utm_source=x",
                "published_at": "2026-07-16T23:30:00Z",
                "first_seen_at": "2026-07-16T23:31:00Z",
                "last_seen_at": "2026-07-16T23:45:00Z",
                "title_original": "vLLM releases a new version",
                "title_en": "vLLM release",
                "title_zh": "vLLM released a new version",
                "title_bilingual": "vLLM release / vLLM released a new version",
            }
        ],
    }
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse(headers={"content-type": "text/plain; charset=utf-8"}, data=payload)

    monkeypatch.setattr("collector.aggregator.httpx.get", fake_get)

    result = AggregatorCollector().fetch()

    assert result.parse_status == "ok"
    assert captured["url"] == "https://raw.githubusercontent.com/SuYxh/ai-news-aggregator/main/data/latest-24h.json"
    assert captured["kwargs"]["headers"] == {"User-Agent": USER_AGENT, "Accept": "application/json"}
    item = result.items[0]
    assert item.url == "https://example.com/a"
    assert item.source_name == "Example Site"
    assert item.source_url == "https://example.com"
    assert item.source_domain == "example.com"
    assert item.source_external_id == "x1"
    assert item.published_at.isoformat() == "2026-07-16T23:30:00+00:00"
    assert item.provenance["aggregator"] == "ai-news-aggregator"
    assert item.provenance["site_id"] == "example"
    assert item.provenance["feed_url"] == captured["url"]


def test_github_releases_fetch_repo_uses_rest_api_with_bounded_request(monkeypatch):
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse(data=[])

    monkeypatch.setattr("collector.github_releases.httpx.get", fake_get)

    result = GitHubReleasesCollector(repositories=["org/repo"], limit=99)._fetch_repo("org/repo")

    assert result.transport_status == "ok"
    assert result.parse_status == "empty"
    assert captured["url"] == "https://api.github.com/repos/org/repo/releases"
    assert captured["kwargs"]["params"] == {"per_page": 10}
    assert captured["kwargs"]["headers"] == {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
    }


def test_github_releases_rest_maps_release_list_and_skips_drafts(monkeypatch):
    payload = [
        {
            "id": 101,
            "name": "draft release",
            "tag_name": "v0.9.0",
            "html_url": "https://github.com/org/repo/releases/tag/v0.9.0",
            "published_at": "2026-07-16T00:00:00Z",
            "created_at": "2026-07-15T00:00:00Z",
            "draft": True,
            "prerelease": False,
            "body": "hidden",
        },
        {
            "id": 102,
            "name": "",
            "tag_name": "v1.0.0-rc1",
            "html_url": "https://github.com/org/repo/releases/tag/v1.0.0-rc1",
            "published_at": None,
            "created_at": "2026-07-17T01:02:03Z",
            "draft": False,
            "prerelease": True,
            "body": "release candidate",
        },
        {
            "id": 103,
            "name": "Stable release",
            "tag_name": "v1.0.0",
            "html_url": "https://github.com/org/repo/releases/tag/v1.0.0",
            "published_at": "2026-07-17T02:03:04Z",
            "created_at": "2026-07-17T01:00:00Z",
            "draft": False,
            "prerelease": False,
            "body": "stable body",
        },
    ]
    monkeypatch.setattr("collector.github_releases.httpx.get", lambda *a, **k: FakeResponse(data=payload))

    result = GitHubReleasesCollector(repositories=["org/repo"], limit=5)._fetch_repo("org/repo")

    assert result.transport_status == "ok"
    assert result.parse_status == "ok"
    # 标题统一补仓名前缀（裸版本号对预筛和读者都无意义）
    assert [item.title for item in result.items] == ["org/repo v1.0.0-rc1", "org/repo Stable release"]
    prerelease = result.items[0]
    assert prerelease.url == "https://github.com/org/repo/releases/tag/v1.0.0-rc1"
    assert prerelease.content == "release candidate"
    assert prerelease.source_external_id == "102"
    assert prerelease.published_at.isoformat() == "2026-07-17T01:02:03+00:00"
    assert prerelease.source_name == "GitHub Releases: org/repo"
    assert prerelease.source_url == "https://github.com/org/repo"
    assert prerelease.source_domain == "github.com"
    assert prerelease.provenance["repository"] == "org/repo"
    assert prerelease.provenance["api_url"] == "https://api.github.com/repos/org/repo/releases"
    assert prerelease.provenance["prerelease"] is True
    stable = result.items[1]
    assert stable.content == "stable body"
    assert stable.source_external_id == "103"
    assert stable.published_at.isoformat() == "2026-07-17T02:03:04+00:00"
    assert stable.provenance["prerelease"] is False


@pytest.mark.parametrize(
    "failure",
    [
        httpx.TimeoutException("temporary timeout"),
        httpx.ConnectError("temporary connect failure"),
        FakeResponse(status_code=429, data={"message": "rate limited"}),
        FakeResponse(status_code=500, data={"message": "server error"}),
    ],
)
def test_github_releases_rest_transient_failure_retries_then_falls_back_to_atom(monkeypatch, failure):
    atom = """<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>tag:github.com,2008:Repository/1/v1.0.0</id>
        <title>retry fallback works</title>
        <updated>2026-07-17T01:02:03Z</updated>
        <link href="https://github.com/org/repo/releases/tag/v1.0.0"/>
        <content type="html">Release body</content>
      </entry>
    </feed>"""
    calls = []
    sleeps = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if url.startswith("https://api.github.com/"):
            if isinstance(failure, Exception):
                raise failure
            return failure
        return FakeResponse(headers={"content-type": "application/atom+xml"}, text=atom)

    monkeypatch.setattr("collector.github_releases.httpx.get", fake_get)

    result = GitHubReleasesCollector(repositories=["org/repo"], limit=5, sleep=sleeps.append, max_workers=1).fetch()

    assert result.transport_status == "ok"
    assert result.parse_status == "ok"
    assert [item.title for item in result.items] == ["org/repo retry fallback works"]
    assert calls == [
        "https://api.github.com/repos/org/repo/releases",
        "https://api.github.com/repos/org/repo/releases",
        "https://api.github.com/repos/org/repo/releases",
        "https://github.com/org/repo/releases.atom",
    ]
    assert sleeps == [0.5, 1.5]


def test_github_releases_rest_404_does_not_retry_or_fall_back(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return FakeResponse(status_code=404, headers={"content-type": "application/json"}, data={"message": "not found"})

    monkeypatch.setattr("collector.github_releases.httpx.get", fake_get)

    result = GitHubReleasesCollector(repositories=["org/missing"], sleep=lambda _: None, max_workers=1).fetch()

    assert result.transport_status == "http_error"
    assert result.http_status == 404
    assert calls == ["https://api.github.com/repos/org/missing/releases"]


@pytest.mark.parametrize(
    "api_response",
    [
        FakeResponse(data={"unexpected": "shape"}),
        FakeResponse(data=ValueError("bad json")),
    ],
)
def test_github_releases_rest_schema_or_json_error_falls_back_to_atom_without_retry(monkeypatch, api_response):
    atom = """<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>tag:github.com,2008:Repository/1/v1.0.0</id>
        <title>atom fallback</title>
        <updated>2026-07-17T01:02:03Z</updated>
        <link href="https://github.com/org/repo/releases/tag/v1.0.0"/>
        <content type="html">Release body</content>
      </entry>
    </feed>"""
    calls = []
    sleeps = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if url.startswith("https://api.github.com/"):
            return api_response
        return FakeResponse(headers={"content-type": "application/atom+xml"}, text=atom)

    monkeypatch.setattr("collector.github_releases.httpx.get", fake_get)

    result = GitHubReleasesCollector(repositories=["org/repo"], limit=5, sleep=sleeps.append, max_workers=1).fetch()

    assert result.transport_status == "ok"
    assert result.parse_status == "ok"
    assert [item.title for item in result.items] == ["org/repo atom fallback"]
    assert calls == [
        "https://api.github.com/repos/org/repo/releases",
        "https://github.com/org/repo/releases.atom",
    ]
    assert sleeps == []


def test_github_releases_keeps_success_when_another_repo_fails(monkeypatch):
    payload = [
        {
            "id": 202,
            "name": "successful repo",
            "tag_name": "v2.0.0",
            "html_url": "https://github.com/org/good/releases/tag/v2.0.0",
            "published_at": "2026-07-17T01:02:03Z",
            "created_at": "2026-07-17T00:00:00Z",
            "draft": False,
            "prerelease": False,
            "body": "Release body",
        }
    ]

    def fake_get(url, **kwargs):
        if "/org/bad/" in url:
            raise httpx.ConnectError("network down for token=secret")
        return FakeResponse(data=payload)

    monkeypatch.setattr("collector.github_releases.httpx.get", fake_get)

    result = GitHubReleasesCollector(
        repositories=["org/bad", "org/good"],
        sleep=lambda _: None,
        max_workers=1,
    ).fetch()

    assert result.transport_status == "ok"
    assert result.parse_status == "ok"
    assert [item.title for item in result.items] == ["org/good successful repo"]


def test_github_releases_gives_every_repo_a_share(monkeypatch):
    """每仓限额而不是「先到先得占满 limit」。

    回归旧缺陷：达到 limit 就 break 并取消其余仓库，导致靠后的仓永远不进库
    （生产 8 个仓只有 4 个出现过数据）。
    """
    repos = [f"org/repo{i}" for i in range(5)]

    def fake_get(url, *a, **k):
        repo = url.split("/repos/")[1].rsplit("/releases", 1)[0]
        return FakeResponse(data=[
            {
                "id": index,
                "name": f"{repo} r{index}",
                "tag_name": f"v{index}",
                "html_url": f"https://github.com/{repo}/releases/tag/v{index}",
                "published_at": f"2026-07-{10 + index:02d}T00:00:00Z",
                "created_at": f"2026-07-{10 + index:02d}T00:00:00Z",
                "draft": False,
                "prerelease": False,
                "body": "body",
            }
            for index in range(10)
        ])

    monkeypatch.setattr("collector.github_releases.httpx.get", fake_get)

    result = GitHubReleasesCollector(
        repositories=repos, limit=99, per_repo_limit=2, max_workers=1
    ).fetch()

    assert result.transport_status == "ok"
    per_repo = Counter(item.source_name for item in result.items)
    assert len(per_repo) == len(repos), "每个仓库都应有产出"
    assert set(per_repo.values()) == {2}, "每仓恰好取 per_repo_limit 条"


def test_github_releases_limit_keeps_newest_across_repos(monkeypatch):
    """总量超限时按发布时间截断，而不是按仓库返回顺序。"""

    def fake_get(url, *a, **k):
        repo = url.split("/repos/")[1].rsplit("/releases", 1)[0]
        day = 20 if repo.endswith("new") else 1
        return FakeResponse(data=[{
            "id": 1,
            "name": f"{repo} release",
            "tag_name": "v1",
            "html_url": f"https://github.com/{repo}/releases/tag/v1",
            "published_at": f"2026-07-{day:02d}T00:00:00Z",
            "created_at": f"2026-07-{day:02d}T00:00:00Z",
            "draft": False,
            "prerelease": False,
            "body": "body",
        }])

    monkeypatch.setattr("collector.github_releases.httpx.get", fake_get)

    result = GitHubReleasesCollector(
        repositories=["org/old", "org/new"], limit=1, per_repo_limit=5, max_workers=1
    ).fetch()

    assert [item.source_name for item in result.items] == ["GitHub Releases: org/new"]


def test_github_releases_qualifies_bare_version_titles(monkeypatch):
    """裸版本号标题要补上仓名，否则预筛看不出任何 AI 信号会判为无关。"""
    monkeypatch.setattr("collector.github_releases.httpx.get", lambda *a, **k: FakeResponse(data=[{
        "id": 1,
        "name": "v0.26.0",
        "tag_name": "v0.26.0",
        "html_url": "https://github.com/vllm-project/vllm/releases/tag/v0.26.0",
        "published_at": "2026-07-20T00:00:00Z",
        "created_at": "2026-07-20T00:00:00Z",
        "draft": False,
        "prerelease": False,
        "body": "body",
    }]))

    result = GitHubReleasesCollector(
        repositories=["vllm-project/vllm"], limit=5
    )._fetch_repo("vllm-project/vllm")

    assert [item.title for item in result.items] == ["vllm-project/vllm v0.26.0"]


def test_github_releases_does_not_duplicate_repo_name_in_title(monkeypatch):
    monkeypatch.setattr("collector.github_releases.httpx.get", lambda *a, **k: FakeResponse(data=[{
        "id": 1,
        "name": "MinerU 2.0",
        "tag_name": "v2.0",
        "html_url": "https://github.com/opendatalab/MinerU/releases/tag/v2.0",
        "published_at": "2026-07-20T00:00:00Z",
        "created_at": "2026-07-20T00:00:00Z",
        "draft": False,
        "prerelease": False,
        "body": "body",
    }]))

    result = GitHubReleasesCollector(
        repositories=["opendatalab/MinerU"], limit=5
    )._fetch_repo("opendatalab/MinerU")

    assert [item.title for item in result.items] == ["MinerU 2.0"]


def test_github_releases_marks_items_trusted_relevance(monkeypatch):
    """人工挑定的仓库清单 -> trusted_relevance，用于跳过通用相关性预筛。"""
    monkeypatch.setattr("collector.github_releases.httpx.get", lambda *a, **k: FakeResponse(data=[{
        "id": 1,
        "name": "v0.26.0",
        "tag_name": "v0.26.0",
        "html_url": "https://github.com/vllm-project/vllm/releases/tag/v0.26.0",
        "published_at": "2026-07-20T00:00:00Z",
        "created_at": "2026-07-20T00:00:00Z",
        "draft": False,
        "prerelease": False,
        "body": "body",
    }]))

    result = GitHubReleasesCollector(
        repositories=["vllm-project/vllm"], limit=5
    )._fetch_repo("vllm-project/vllm")

    assert result.items[0].meta["trusted_relevance"] is True


def test_hf_papers_returns_collector_result_with_mirror_hint(monkeypatch):
    """国内直连 huggingface.co 会 Network is unreachable —— 错误里要带出修复办法。"""
    def boom(*a, **k):
        raise httpx.ConnectError("[Errno 101] Network is unreachable")

    monkeypatch.setattr("collector.hf_papers.httpx.get", boom)
    result = HFPapersCollector(limit=3).fetch()

    assert result.transport_status == "network_error"
    assert "HF_ENDPOINT" in (result.error_summary or "")


def test_hf_papers_maps_daily_papers(monkeypatch):
    payload = [{
        "publishedAt": "2026-07-20T00:00:00.000Z",
        "paper": {"id": "2607.00001", "title": "A Vision Model",
                  "summary": "abstract", "authors": [{"name": "A"}]},
    }]
    monkeypatch.setattr("collector.hf_papers.httpx.get",
                        lambda *a, **k: FakeResponse(data=payload))

    result = HFPapersCollector(limit=3).fetch()

    assert result.parse_status == "ok"
    assert [item.title for item in result.items] == ["A Vision Model"]
    assert result.items[0].kind == "论文"


def test_arxiv_returns_collector_result_on_http_error(monkeypatch):
    monkeypatch.setattr("collector.arxiv.httpx.get",
                        lambda *a, **k: FakeResponse(status_code=503, text=""))
    result = ArxivCollector(limit=3).fetch()

    assert result.transport_status == "http_error"
    assert result.http_status == 503


def test_every_collector_returns_collector_result():
    """契约防回归：采集器一律返回 CollectorResult，禁止裸 list。

    裸 list 会让 ingest 把「失败」当成「没有新内容」，信源健康显示绿灯——
    北极星招标子站就是这样挂了很久没人发现。
    """
    import inspect

    from collector import (
        aggregator, aihot, arxiv, bjx, csg_bidding, frontier, github_releases,
        gov_procurement, hf_papers, nea, rss, sgcc_news, southern_grid,
    )

    modules = [aggregator, aihot, arxiv, bjx, csg_bidding, frontier, github_releases,
               gov_procurement, hf_papers, nea, rss, sgcc_news, southern_grid]
    offenders = []
    for module in modules:
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ != module.__name__ or not hasattr(obj, "fetch"):
                continue
            annotation = inspect.signature(obj.fetch).return_annotation
            if "CollectorResult" not in str(annotation):
                offenders.append(f"{module.__name__}.{obj.__name__} -> {annotation}")
    assert not offenders, f"这些采集器未返回 CollectorResult：{offenders}"
