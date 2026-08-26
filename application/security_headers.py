"""HTTP security response headers for the Web UI / API.

Pure ASGI middleware (not BaseHTTPMiddleware): Starlette's BaseHTTPMiddleware
buffers/re-streams bodies and breaks FileResponse with
"Response content longer than Content-Length" (e.g. /api/graph iframe).

CloudFront can layer Managed-SecurityHeadersPolicy as well; CSP is defined
here so Google Sign-In and same-origin APIs keep working.
"""

from __future__ import annotations

import json
import logging
import os

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


def _s3_connect_src_hosts() -> str:
    """Allow browser→S3 presigned PUT used by RAG uploads.

    Without these, CSP blocks ``fetch(presignedUrl)`` as ``Failed to fetch``.
    Host wildcards only match one DNS label, so regional path-style and
    virtual-hosted forms are listed explicitly from config.json.
    """
    region = "us-west-2"
    bucket = ""
    try:
        cfg_path = os.path.join(os.path.dirname(__file__), "config.json")
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
        region = (cfg.get("region") or region).strip() or region
        bucket = (cfg.get("s3_bucket") or "").strip()
    except Exception:
        logger.debug("CSP S3 hosts: using defaults (config.json unread)", exc_info=True)

    hosts = [
        f"https://s3.{region}.amazonaws.com",
        f"https://*.s3.{region}.amazonaws.com",
        "https://*.s3.amazonaws.com",
        "https://s3.amazonaws.com",
    ]
    if bucket:
        hosts.append(f"https://{bucket}.s3.{region}.amazonaws.com")
        hosts.append(f"https://{bucket}.s3.amazonaws.com")
    return " ".join(hosts)


# Allow Google Identity Services (GSI) while locking down everything else.
# frame-src includes 'self' so Knowledge Graph modals can iframe HTML
# (without 'self' the graph iframe is blank).
# connect-src includes S3 so RAG can PUT directly to presigned URLs.
_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' https://accounts.google.com https://apis.google.com; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob: https:; "
    "font-src 'self' data:; "
    "connect-src 'self' https://accounts.google.com https://oauth2.googleapis.com "
    f"https://www.googleapis.com {_s3_connect_src_hosts()}; "
    "frame-src 'self' https://accounts.google.com; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "object-src 'none'"
)

# Graph HTML loads vis-network from unpkg + inline scripts; must be frameable by this app.
_GRAPH_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://unpkg.com; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob: https:; "
    "font-src 'self' data:; "
    "connect-src 'self' https://unpkg.com; "
    "frame-ancestors 'self'; "
    "base-uri 'self'; "
    "object-src 'none'"
)

_BASE_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
    (b"content-security-policy", _CONTENT_SECURITY_POLICY.encode("latin-1")),
]

_GRAPH_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"SAMEORIGIN"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
    (b"content-security-policy", _GRAPH_CONTENT_SECURITY_POLICY.encode("latin-1")),
]

_HSTS = (b"strict-transport-security", b"max-age=31536000; includeSubDomains")


def _viewer_is_https(scope: Scope) -> bool:
    headers = {k.lower(): v for k, v in scope.get("headers", [])}
    proto = (
        headers.get(b"cloudfront-forwarded-proto")
        or headers.get(b"x-forwarded-proto")
        or scope.get("scheme", "")
        or b""
    )
    if isinstance(proto, bytes):
        proto = proto.decode("latin-1", errors="ignore")
    return str(proto).lower() == "https"


def _is_graph_html(scope: Scope) -> bool:
    """Exact Knowledge graph HTML (not /status|/query|/rebuild)."""
    path = scope.get("path") or "/"
    path = path.rstrip("/") or "/"
    return path == "/api/graph"


def _header_names(headers: list[tuple[bytes, bytes]]) -> set[bytes]:
    return {name.lower() for name, _ in headers}


class SecurityHeadersMiddleware:
    """Attach baseline security headers; HSTS only for HTTPS viewers."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        is_graph = _is_graph_html(scope)
        add_https = _viewer_is_https(scope)
        extra = _GRAPH_HEADERS if is_graph else _BASE_HEADERS

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                if is_graph:
                    # Force framing/CSP suitable for same-origin iframe + unpkg.
                    drop = {b"x-frame-options", b"content-security-policy"}
                    headers = [(n, v) for n, v in headers if n.lower() not in drop]
                existing = _header_names(headers)
                for name, value in extra:
                    if name not in existing:
                        headers.append((name, value))
                        existing.add(name)
                if add_https and b"strict-transport-security" not in existing:
                    headers.append(_HSTS)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)
