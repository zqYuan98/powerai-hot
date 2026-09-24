"""Trusted-proxy identity contract for process-local rate limits."""

from pathlib import Path
import re

import pytest
from starlette.requests import Request

from core.config import Settings, settings
from core.rate_limit import SlidingWindowLimiter, _client_identity


def _request(peer: str, forwarded_for: str | None = None) -> Request:
    headers = []
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode("ascii")))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "path": "/api/admin/digest",
            "raw_path": b"/api/admin/digest",
            "query_string": b"",
            "headers": headers,
            "client": (peer, 12345),
            "server": ("backend", 8000),
        }
    )


def _nginx_location_body(config: str, location: str) -> str:
    pattern = rf"location\s+{re.escape(location)}\s*\{{(?P<body>.*?)^\s*\}}"
    match = re.search(pattern, config, re.MULTILINE | re.DOTALL)
    assert match is not None, f"missing nginx location {location}"
    return match.group("body")


def test_untrusted_peer_cannot_spoof_forwarded_identity(monkeypatch):
    monkeypatch.setitem(settings.__dict__, "trusted_proxy_cidrs", ["10.42.0.10/32"])

    identity = _client_identity(_request("203.0.113.9", "198.51.100.7"))

    assert identity == "203.0.113.9"


def test_trusted_proxy_uses_valid_leftmost_forwarded_client(monkeypatch):
    monkeypatch.setitem(settings.__dict__, "trusted_proxy_cidrs", ["10.42.0.10/32"])

    identity = _client_identity(
        _request("10.42.0.10", " 198.51.100.7, 10.42.0.1")
    )

    assert identity == "198.51.100.7"


def test_trusted_proxy_uses_real_client_from_caddy_forwarded_chain(monkeypatch):
    monkeypatch.setitem(settings.__dict__, "trusted_proxy_cidrs", ["10.42.0.10/32"])

    identity = _client_identity(
        _request("10.42.0.10", "198.51.100.7, 127.0.0.1")
    )

    assert identity == "198.51.100.7"


def test_malformed_forwarded_identity_falls_back_to_trusted_peer(monkeypatch):
    monkeypatch.setitem(settings.__dict__, "trusted_proxy_cidrs", ["10.42.0.10/32"])

    identity = _client_identity(
        _request("10.42.0.10", "not-an-ip, 198.51.100.7")
    )

    assert identity == "10.42.0.10"


def test_distinct_clients_behind_trusted_proxy_get_distinct_buckets(monkeypatch):
    monkeypatch.setitem(settings.__dict__, "trusted_proxy_cidrs", ["10.42.0.10/32"])
    limiter = SlidingWindowLimiter(limit=1, window_seconds=60)
    first = _client_identity(_request("10.42.0.10", "198.51.100.7"))
    second = _client_identity(_request("10.42.0.10", "198.51.100.8"))

    assert limiter.allow("digest", first) is True
    assert limiter.allow("digest", second) is True
    assert limiter.allow("digest", first) is False


def test_trusted_proxy_cidrs_accept_comma_separated_networks():
    candidate = Settings(
        _env_file=None,
        trusted_proxy_cidrs="10.42.0.10/32, 2001:db8::/48",
    )

    assert candidate.trusted_proxy_cidrs == ["10.42.0.10/32", "2001:db8::/48"]


def test_trusted_proxy_cidrs_accept_plain_environment_value(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", "10.42.0.10/32")

    candidate = Settings(_env_file=None)

    assert candidate.trusted_proxy_cidrs == ["10.42.0.10/32"]


def test_trusted_proxy_cidrs_reject_invalid_network():
    with pytest.raises(ValueError, match="trusted proxy"):
        Settings(_env_file=None, trusted_proxy_cidrs="not-a-network")


def test_compose_derives_proxy_trust_from_overrideable_network_variables():
    root = Path(__file__).resolve().parents[2]
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    dockerfile = (root / "backend" / "Dockerfile").read_text(encoding="utf-8")

    assert 'TRUSTED_PROXY_CIDRS: "${NGINX_PROXY_IP:-10.42.0.10}/32"' in compose
    assert 'ipv4_address: "${NGINX_PROXY_IP:-10.42.0.10}"' in compose
    assert compose.count("${NGINX_PROXY_IP:") == 3
    assert 'subnet: "${POWERAI_NETWORK_SUBNET:' in compose
    assert "must contain NGINX_PROXY_IP" in compose
    assert '"--no-proxy-headers"' in dockerfile


def test_caddy_overwrites_forwarded_headers_at_public_edge():
    root = Path(__file__).resolve().parents[2]
    caddyfile = (root / "deploy" / "Caddyfile").read_text(encoding="utf-8")

    assert "reverse_proxy 127.0.0.1:8080 {" in caddyfile
    assert "header_up X-Forwarded-For {remote_host}" in caddyfile
    assert "header_up X-Forwarded-Proto {scheme}" in caddyfile
    assert "header_up X-Forwarded-Host {host}" in caddyfile
    assert "{http.request.header.X-Forwarded-For}" not in caddyfile


@pytest.mark.parametrize("location", ["= /health", "/api/", "/"])
def test_nginx_preserves_caddy_forwarded_identity_for_backend(location):
    root = Path(__file__).resolve().parents[2]
    nginx = (root / "nginx.conf").read_text(encoding="utf-8")
    location_body = _nginx_location_body(nginx, location)

    assert "proxy_set_header X-Forwarded-For $remote_addr;" not in location_body
    assert "proxy_set_header X-Forwarded-Proto $scheme;" not in location_body
    assert (
        "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;"
        in location_body
    )
    assert (
        "proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;"
        in location_body
    )
    assert "proxy_set_header X-Real-IP $http_x_forwarded_for;" in location_body
