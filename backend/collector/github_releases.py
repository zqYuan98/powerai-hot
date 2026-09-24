"""GitHub Releases Atom collector for project release monitoring."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import re
import time
from collections.abc import Callable

import httpx

from collector.base import BaseCollector, CollectorResult, RawArticle
from collector.http_utils import USER_AGENT, is_feed_response, is_json_response, parse_datetime

# 按 seed.py 的六条研究方向分组。全库信噪比最高的信源类型（生产实测 PaddleOCR
# avg 78 / 10 条全精选、MinerU avg 55），故重点扩容。
# 只收录实测确有 GitHub Releases 的仓库 —— sam2 / Qwen3 / Qwen2.5-VL / CogVLM
# 只打 tag 或只发 HF，Releases 源为空，收录了也永远是 0 条。
DEFAULT_REPOSITORIES = [
    # 文档理解与 OCR
    "PaddlePaddle/PaddleOCR",
    "opendatalab/MinerU",
    "VikParuchuri/marker",
    "VikParuchuri/surya",
    "JaidedAI/EasyOCR",
    "breezedeus/CnOCR",
    # 目标检测与缺陷识别
    "ultralytics/ultralytics",
    "open-mmlab/mmdetection",
    "open-mmlab/mmyolo",
    "open-mmlab/mmsegmentation",
    "IDEA-Research/GroundingDINO",
    "roboflow/supervision",
    # 多模态大模型
    "OpenGVLab/InternVL",
    # 边缘部署与模型压缩
    "NVIDIA/TensorRT-LLM",
    "Tencent/ncnn",
    "microsoft/onnxruntime",
    "openvinotoolkit/openvino",
    "airockchip/rknn-toolkit2",
    # 大模型与推理基础设施
    "vllm-project/vllm",
    "sgl-project/sglang",
    "ggml-org/llama.cpp",
    "huggingface/transformers",
    "comfyanonymous/ComfyUI",
]

MAX_RETRIES = 2
RETRY_DELAYS = (0.5, 1.5)


def _safe_error(message: object) -> str:
    text = str(message or "GitHub releases request failed")
    text = re.sub(r"://[^/@\s]+@", "://<redacted>@", text)
    text = re.sub(r"(?i)(token|key|secret|password)=([^&\s]+)", r"\1=<redacted>", text)
    return text[:500]


def _retryable_http_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code <= 599


_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _qualified_title(repo: str, title: str) -> str:
    """把「v0.26.0」这类裸版本号补成「vllm-project/vllm v0.26.0」。

    两个理由：① 预筛只拿得到 title/content，裸版本号没有任何 AI 信号，会被判
    「无关」直接打回（实测 vllm/sglang/llama.cpp/onnxruntime 的新发布全军覆没）；
    ② 信息流卡片上单看「b10107」对读者毫无意义。
    仓名已在标题里出现时（如「ONNX Runtime v1.28.0」不含仓名但「MinerU 2.0」含）
    不重复拼接。
    """
    name = repo.split("/")[-1]
    if name.casefold() in title.casefold():
        return title
    return f"{repo} {title}"


def _sort_key(article: RawArticle) -> datetime:
    """按发布时间排序；缺时间的条目沉底而不是抛 TypeError。"""
    published = article.published_at
    if published is None:
        return _EPOCH
    if published.tzinfo is None:
        return published.replace(tzinfo=timezone.utc)
    return published


class GitHubReleasesCollector(BaseCollector):
    source_name = "GitHub Releases"
    source_url = "https://github.com"
    domain = "github.com"
    channel = "大模型动态"
    tier = "T1"
    group = "news"

    def __init__(
        self,
        *,
        repositories: list[str] | None = None,
        limit: int = 30,
        per_repo_limit: int = 3,
        sleep: Callable[[float], None] = time.sleep,
        max_workers: int = 4,
    ) -> None:
        self.repositories = repositories or DEFAULT_REPOSITORIES
        self.limit = limit
        self.per_repo_limit = max(1, per_repo_limit)
        self._sleep = sleep
        self.max_workers = max(1, max_workers)

    def fetch(self) -> CollectorResult:
        items: list[RawArticle] = []
        errors: list[CollectorResult] = []
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(self.repositories) or 1)) as executor:
            futures = {executor.submit(self._fetch_repo, repo): repo for repo in self.repositories}
            for future in as_completed(futures):
                repo = futures[future]
                result = future.result()
                if result.transport_status != "ok" or result.parse_status not in {"ok", "empty"}:
                    result.error_summary = _safe_error(f"{repo}:{result.transport_status}/{result.parse_status}:{result.error_summary or ''}")
                    errors.append(result)
                    continue
                # 每仓只取最近 per_repo_limit 条。旧实现在累计条数达到 limit 时直接 break
                # 并取消其余仓库 —— 先返回的两三个仓永远占满配额，列表里靠后的仓从未进过库
                # （生产 8 个仓只有 4 个出现过数据）。扩容仓库列表必须先去掉这个提前退出。
                items.extend(result.items[: self.per_repo_limit])
        if items:
            # 跨仓按发布时间排序，让「最新的发布」竞争配额，而不是「最快返回的仓」。
            # 无发布时间的条目排在最后（部分仓的 Atom 回退路径可能缺 published）。
            items.sort(key=_sort_key, reverse=True)
            return CollectorResult.ok(items=items[: self.limit])
        if errors:
            first = errors[0]
            summary = "; ".join(result.error_summary or "failed" for result in errors)
            if any(result.transport_status == "http_error" for result in errors):
                http_result = next(result for result in errors if result.transport_status == "http_error")
                return CollectorResult.http_error(http_result.http_status or 0, summary)
            if all(result.transport_status == "timeout" for result in errors):
                return CollectorResult.timeout(summary)
            if first.parse_status in {"schema_error", "parse_error"}:
                return CollectorResult(
                    transport_status=first.transport_status,
                    parse_status=first.parse_status,
                    http_status=first.http_status,
                    error_summary=summary,
                )
            return CollectorResult.network_error(summary)
        return CollectorResult.ok(items=[])

    def _fetch_repo(self, repo: str) -> CollectorResult:
        api_result = self._fetch_repo_api(repo)
        if api_result.transport_status == "ok" and api_result.parse_status in {"ok", "empty"}:
            return api_result
        if api_result.transport_status == "http_error" and api_result.http_status == 404:
            return api_result
        if (
            api_result.transport_status in {"timeout", "network_error"}
            or (
                api_result.transport_status == "http_error"
                and api_result.http_status is not None
                and _retryable_http_status(api_result.http_status)
            )
            or api_result.parse_status in {"schema_error", "parse_error"}
        ):
            return self._fetch_repo_atom(repo)
        return api_result

    def _request_with_retry(
        self,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, int] | None = None,
        follow_redirects: bool = True,
    ) -> tuple[CollectorResult | None, httpx.Response | None]:
        resp = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = httpx.get(url, headers=headers, params=params, timeout=15, follow_redirects=follow_redirects)
            except httpx.TimeoutException as exc:
                if attempt < MAX_RETRIES:
                    self._sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])
                    continue
                return CollectorResult.timeout(_safe_error(exc)), None
            except httpx.TransportError as exc:
                if attempt < MAX_RETRIES:
                    self._sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])
                    continue
                return CollectorResult.network_error(_safe_error(exc)), None
            except httpx.HTTPError as exc:
                return CollectorResult.network_error(_safe_error(exc)), None
            if _retryable_http_status(resp.status_code) and attempt < MAX_RETRIES:
                self._sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])
                continue
            break
        if resp is None:
            return CollectorResult.network_error("GitHub releases request failed"), None
        if resp.status_code >= 400:
            return CollectorResult.http_error(resp.status_code, f"HTTP {resp.status_code}"), resp
        return None, resp

    def _fetch_repo_api(self, repo: str) -> CollectorResult:
        url = f"https://api.github.com/repos/{repo}/releases"
        request_error, resp = self._request_with_retry(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
            params={"per_page": max(1, min(int(self.limit or 1), 10))},
            follow_redirects=True,
        )
        if request_error is not None:
            return request_error
        if resp is None:
            return CollectorResult.network_error("GitHub releases request failed")
        if not is_json_response(resp.headers):
            return CollectorResult.schema_error("GitHub releases API response is not JSON")
        try:
            payload = resp.json()
        except ValueError as exc:
            return CollectorResult.parse_error(str(exc))
        if not isinstance(payload, list):
            return CollectorResult.schema_error("GitHub releases API response is not a list")

        items: list[RawArticle] = []
        for release in payload:
            if not isinstance(release, dict):
                return CollectorResult.schema_error("GitHub releases API item is not an object")
            if release.get("draft"):
                continue
            title = (release.get("name") or release.get("tag_name") or "").strip()
            link = (release.get("html_url") or "").strip()
            if not title or not link:
                continue
            release_id = release.get("id")
            published_at = release.get("published_at") or release.get("created_at")
            items.append(
                RawArticle(
                    title=_qualified_title(repo, title),
                    url=link,
                    content=release.get("body") or "",
                    channel=self.channel,
                    source_name=f"GitHub Releases: {repo}",
                    source_url=f"https://github.com/{repo}",
                    source_domain=self.domain,
                    source_external_id=str(release_id) if release_id is not None else "",
                    published_at=parse_datetime(published_at),
                    provenance={
                        "repository": repo,
                        "api_url": url,
                        "prerelease": bool(release.get("prerelease")),
                    },
                    # 仓库清单是人工挑定的，发布必然相关；跳过通用相关性预筛。
                    meta={"trusted_relevance": True},
                )
            )
        return CollectorResult.ok(items=items)

    def _fetch_repo_atom(self, repo: str) -> CollectorResult:
        url = f"https://github.com/{repo}/releases.atom"
        request_error, resp = self._request_with_retry(
            url,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        if request_error is not None:
            return request_error
        if resp is None:
            return CollectorResult.network_error("GitHub releases request failed")
        if not is_feed_response(resp.headers):
            return CollectorResult.schema_error("GitHub releases response is not XML")
        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError as exc:
            return CollectorResult.parse_error(str(exc))
        return self._parse_atom_entries(repo, url, root)

    def _parse_atom_entries(self, repo: str, url: str, root: ET.Element) -> CollectorResult:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items: list[RawArticle] = []
        for entry in root.findall("atom:entry", ns):
            title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
            entry_id = (entry.findtext("atom:id", default="", namespaces=ns) or "").strip()
            updated = entry.findtext("atom:updated", default="", namespaces=ns)
            link_node = entry.find("atom:link", ns)
            link = link_node.attrib.get("href") if link_node is not None else ""
            content = (entry.findtext("atom:content", default="", namespaces=ns) or "").strip()
            if not title or not link:
                continue
            items.append(RawArticle(
                title=_qualified_title(repo, title),
                url=link,
                content=content,
                channel=self.channel,
                source_name=f"GitHub Releases: {repo}",
                source_url=f"https://github.com/{repo}",
                source_domain=self.domain,
                source_external_id=entry_id,
                published_at=parse_datetime(updated),
                provenance={"repository": repo, "feed_url": url},
                meta={"trusted_relevance": True},
            ))
        return CollectorResult.ok(items=items)
