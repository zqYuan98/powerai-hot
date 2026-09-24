"""Application configuration loaded from environment variables."""
from functools import lru_cache
from ipaddress import ip_network
from pathlib import Path
from typing import Annotated, List, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# backend 目录（core/ 的上一级）。SQLite 默认库锚定在这里而不是进程 cwd——
# 曾有从仓库根目录启动后端的情况，在根目录悄悄建了第二个空库，前端看似"没数据"。
_BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    app_name: str = "电力AI-hot"
    debug: bool = True
    api_prefix: str = "/api"

    # --- Authentication (validated explicitly during application startup) ---
    workspace_token: str = ""
    admin_token: str = ""
    access_mode: Literal["shared", "public_admin"] = "shared"
    session_secret: str = ""
    session_cookie_secure: bool = True
    session_ttl_seconds: int = 28800
    app_origin: str = "http://127.0.0.1:3010"
    workspace_name: str = "电力 AI 情报工作空间"
    workspace_subtitle: str = "内部情报与知识服务"
    trusted_proxy_cidrs: Annotated[List[str], NoDecode] = []

    @field_validator("trusted_proxy_cidrs", mode="before")
    @classmethod
    def _split_trusted_proxies(cls, value):
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                import json
                return json.loads(text)
            return [item.strip() for item in text.split(",") if item.strip()]
        return value

    @field_validator("trusted_proxy_cidrs")
    @classmethod
    def _validate_trusted_proxies(cls, value: List[str]) -> List[str]:
        networks: list[str] = []
        for item in value:
            try:
                networks.append(str(ip_network(item, strict=False)))
            except ValueError as exc:
                raise ValueError(f"invalid trusted proxy CIDR: {item}") from exc
        return networks

    # --- CORS ---
    # 生产从环境变量配置线上域名。pydantic-settings 对 List 只认 JSON，
    # 但运维常写逗号分隔——下面的 validator 两种写法都兼容，避免启动崩溃。
    cors_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("["):
                import json
                return json.loads(s)  # JSON 数组
            return [o.strip() for o in s.split(",") if o.strip()]
        return v

    # --- Database ---
    # 本地零配置默认 SQLite（绝对路径，与启动目录无关）；Docker/生产通过 .env 覆盖为 PostgreSQL。
    database_url: str = f"sqlite:///{(_BACKEND_DIR / 'powerai_hot.db').as_posix()}"

    # --- Redis / Celery ---
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"

    # --- AI analyzer ---
    # Default model is DeepSeek; switchable in the admin backend.
    ai_provider: str = "deepseek"  # one of: deepseek | custom | ollama
    deepseek_api_key: str = ""
    # 自定义模型：任何 OpenAI 兼容 /chat/completions 端点（第三方云或私有化 vLLM 等）。
    # URL 可填基地址（https://api.example.com/v1）或完整 chat/completions 地址。
    custom_api_url: str = ""
    custom_api_key: str = ""   # 私有化部署可留空
    custom_model: str = ""
    # 2026-07 起 DeepSeek 下线 deepseek-chat，只接受 deepseek-v4-pro / deepseek-v4-flash；
    # 仍传旧名会被接口以 HTTP 400 拒绝，评分链会静默退化成关键词规则（见 scored_by=rule）。
    deepseek_prefilter_model: str = "deepseek-v4-flash"   # 预筛用便宜档
    deepseek_scorer_model: str = "deepseek-v4-pro"        # 评分档（可在 .env 换更强档位）
    deepseek_writer_model: str = "deepseek-v4-pro"        # 卡片/周报/研报生成

    # --- Embedding（事件聚类；OpenAI 兼容接口，默认硅基流动 BGE-M3） ---
    embedding_api_url: str = "https://api.siliconflow.cn/v1/embeddings"
    embedding_api_key: str = ""
    embedding_model: str = "BAAI/bge-m3"

    # --- 推送（飞书群机器人 webhook，留空则不推送） ---
    feishu_webhook_url: str = ""

    # --- Crawler ---
    crawl_interval_hours: int = 1
    crawl_min_gap_seconds: int = 300  # ≥5 min/site per design doc
    auto_crawl_enabled: bool = False  # 生产默认由独立 CLI/systemd timer 采集
    hf_endpoint: str = "https://huggingface.co"

@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
