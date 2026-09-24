"""Signed session primitives and explicit startup security validation."""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
import time
from typing import Any, Literal


SessionRole = Literal["workspace", "admin"]

_ROLES = frozenset(("workspace", "admin"))
_BASE64URL_RE = re.compile(r"^[A-Za-z0-9_-]+={0,2}$")
_PLACEHOLDER_MARKERS = (
    "change-me",
    "changeme",
    "default",
    "example",
    "placeholder",
    "replace-me",
    "replace_with",
)


def _decode_base64url(value: str) -> bytes:
    if not isinstance(value, str) or not _BASE64URL_RE.fullmatch(value):
        raise ValueError("SESSION_SECRET must be Base64URL encoded")
    unpadded = value.rstrip("=")
    if "=" in unpadded:
        raise ValueError("SESSION_SECRET must be Base64URL encoded")
    try:
        return base64.b64decode(
            unpadded + "=" * (-len(unpadded) % 4),
            altchars=b"-_",
            validate=True,
        )
    except (binascii.Error, ValueError) as exc:
        raise ValueError("SESSION_SECRET must be Base64URL encoded") from exc


def _is_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    return any(marker in normalized for marker in _PLACEHOLDER_MARKERS)


def validate_security_config(
    config: Any | None = None,
    *,
    workspace_token: str | None = None,
    admin_token: str | None = None,
    session_secret: str | None = None,
    session_ttl_seconds: int | None = None,
) -> None:
    """Validate security roots without coupling validation to Settings creation."""
    if config is None and (
        workspace_token is None
        or admin_token is None
        or session_secret is None
        or session_ttl_seconds is None
    ):
        from core.config import settings

        config = settings

    if config is not None:
        if any(
            value is not None
            for value in (
                workspace_token,
                admin_token,
                session_secret,
                session_ttl_seconds,
            )
        ):
            raise TypeError("pass either config or explicit security values")
        workspace_token = getattr(config, "workspace_token", None)
        admin_token = getattr(config, "admin_token", None)
        session_secret = getattr(config, "session_secret", None)
        session_ttl_seconds = getattr(config, "session_ttl_seconds", None)

    if not isinstance(workspace_token, str) or len(workspace_token) < 24:
        raise ValueError("WORKSPACE_TOKEN must be at least 24 characters")
    if not isinstance(admin_token, str) or len(admin_token) < 24:
        raise ValueError("ADMIN_TOKEN must be at least 24 characters")
    if workspace_token == admin_token:
        raise ValueError("WORKSPACE_TOKEN and ADMIN_TOKEN must differ")
    if not isinstance(session_secret, str):
        raise ValueError("SESSION_SECRET must be Base64URL encoded")
    if type(session_ttl_seconds) is not int or session_ttl_seconds <= 0:
        raise ValueError("SESSION_TTL_SECONDS must be a positive integer")

    secret_bytes = _decode_base64url(session_secret)
    if len(secret_bytes) < 32:
        raise ValueError("SESSION_SECRET must decode to at least 32 bytes")
    if session_secret in (workspace_token, admin_token):
        raise ValueError("SESSION_SECRET and access tokens must differ")

    decoded_text = secret_bytes.decode("utf-8", errors="ignore")
    if any(
        _is_placeholder(value)
        for value in (workspace_token, admin_token, session_secret, decoded_text)
    ):
        raise ValueError("Security values cannot use example, default, or placeholder values")


def _encode_base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def encode_session(
    role: SessionRole,
    secret: str,
    *,
    now: int | None = None,
    ttl: int = 28800,
) -> str:
    """Create a compact, signed session value for a workspace or admin role."""
    if role not in _ROLES:
        raise ValueError("session role must be workspace or admin")
    if type(ttl) is not int or ttl <= 0:
        raise ValueError("session ttl must be a positive integer")
    issued_at = int(time.time()) if now is None else now
    if type(issued_at) is not int:
        raise ValueError("session timestamp must be an integer")

    key = _decode_base64url(secret)
    payload = _encode_base64url(
        json.dumps(
            {"v": 1, "role": role, "iat": issued_at, "exp": issued_at + ttl},
            separators=(",", ":"),
        ).encode("utf-8")
    )
    signature = hmac.new(key, payload.encode("ascii"), hashlib.sha256).digest()
    return f"{payload}.{_encode_base64url(signature)}"


def decode_session(
    value: str | None,
    secret: str,
    *,
    now: int | None = None,
) -> dict[str, int | str] | None:
    """Verify and decode a session value, returning ``None`` for any bad input."""
    try:
        if not isinstance(value, str) or value.count(".") != 1:
            return None
        payload, encoded_signature = value.split(".", 1)
        if not payload or not encoded_signature:
            return None

        key = _decode_base64url(secret)
        supplied_signature = _decode_base64url(encoded_signature)
        expected_signature = hmac.new(
            key, payload.encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return None

        raw_payload = _decode_base64url(payload)
        data = json.loads(raw_payload.decode("utf-8"))
        if not isinstance(data, dict) or set(data) != {"v", "role", "iat", "exp"}:
            return None
        if type(data["v"]) is not int or data["v"] != 1:
            return None
        if type(data["role"]) is not str or data["role"] not in _ROLES:
            return None
        if type(data["iat"]) is not int or type(data["exp"]) is not int:
            return None
        if data["exp"] <= data["iat"]:
            return None

        current_time = int(time.time()) if now is None else now
        if type(current_time) is not int or current_time >= data["exp"]:
            return None
        return data
    except (ArithmeticError, UnicodeError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None
