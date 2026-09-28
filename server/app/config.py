"""运行配置：全部来自环境变量（或 server/.env），启动时一次性校验。

只放「部署相关」的值；业务可调参数（画像、权重、阈值）在数据库 settings 表，
由设置页修改、管线实时读取。
"""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVER_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=SERVER_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "postgresql+asyncpg://powerai:powerai@127.0.0.1:5432/powerai"
    timezone: str = "Asia/Shanghai"

    # --- 单用户鉴权 ---
    app_password: str = ""
    session_secret: str = ""  # Base64URL，解码后 ≥32 字节
    session_ttl_days: int = 30
    cookie_secure: bool = False

    # --- LLM（任意 OpenAI 兼容端点，默认 DeepSeek） ---
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    # 2026-07 起 deepseek-chat 已下线；2026-09 起 deepseek-v4-flash 改名 deepseek-flash（旧名仍可用）。
    llm_model_fast: str = "deepseek-flash"   # 初筛 + 精读（关闭推理，约 3 秒/条）
    llm_model_pro: str = "deepseek-v4-pro"   # 日报导语、事件综述（低强度推理）
    llm_model_analyze: str = ""              # 精读单独换模型时填写，留空用 fast
    # 是否发送 DeepSeek 的推理开关（thinking / reasoning_effort）；其他 OpenAI 兼容服务不认时设为 false
    llm_thinking_control: bool = True
    llm_timeout_s: float = 120.0
    llm_concurrency: int = 6
    # 每百万 token 价格（元，按高峰价换算），用于估算费用；{"model": [输入价, 输出价]}
    llm_prices: dict[str, tuple[float, float]] = Field(
        default_factory=lambda: {"deepseek-flash": (2.1, 8.5), "deepseek-v4-pro": (9.4, 28.1)}
    )

    # --- Embedding（OpenAI 兼容 /embeddings，默认硅基流动 BGE-M3） ---
    embedding_base_url: str = "https://api.siliconflow.cn/v1"
    embedding_api_key: str = ""
    embedding_model: str = "BAAI/bge-m3"

    # --- 推送 ---
    feishu_webhook_url: str = ""
    public_base_url: str = "http://127.0.0.1:3000"  # 推送消息里的站内链接

    # --- worker ---
    worker_enabled_schedules: bool = True
    backup_dir: Path = SERVER_DIR / "backups"
    backup_keep_days: int = 14

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def analyze_model(self) -> str:
        return self.llm_model_analyze or self.llm_model_fast

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def embedding_enabled(self) -> bool:
        return bool(self.embedding_api_key)

    @property
    def session_key(self) -> bytes:
        raw = self.session_secret.rstrip("=")
        return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))

    @model_validator(mode="after")
    def _check_security(self) -> Settings:
        if self.env != "prod":
            if not self.session_secret:
                # 开发环境给一个固定密钥，避免每次重启掉登录
                self.session_secret = base64.urlsafe_b64encode(b"dev-only-session-secret-32-bytes!").decode()
            return self
        if len(self.app_password) < 12:
            raise ValueError("APP_PASSWORD 至少 12 位")
        try:
            key = self.session_key
        except ValueError as exc:
            raise ValueError("SESSION_SECRET 必须是 Base64URL 编码") from exc
        if len(key) < 32:
            raise ValueError("SESSION_SECRET 解码后至少 32 字节（openssl rand -base64 48）")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
