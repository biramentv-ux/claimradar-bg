from __future__ import annotations

import os
import re
from typing import Any, Dict
from urllib.parse import unquote

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

OWASP_HARDENING_ENABLED = os.getenv("OWASP_HARDENING_ENABLED", "1").lower() not in {"0", "false", "no"}
OWASP_BLOCK_SUSPICIOUS_INPUTS = os.getenv("OWASP_BLOCK_SUSPICIOUS_INPUTS", "1").lower() not in {"0", "false", "no"}
OWASP_REQUIRE_JSON_API_POSTS = os.getenv("OWASP_REQUIRE_JSON_API_POSTS", "1").lower() not in {"0", "false", "no"}
OWASP_CSP_ENABLED = os.getenv("OWASP_CSP_ENABLED", "1").lower() not in {"0", "false", "no"}
OWASP_HSTS_ENABLED = os.getenv("OWASP_HSTS_ENABLED", "1").lower() not in {"0", "false", "no"}
OWASP_HSTS_MAX_AGE = int(os.getenv("OWASP_HSTS_MAX_AGE", "31536000"))
OWASP_MAX_QUERY_LENGTH = int(os.getenv("OWASP_MAX_QUERY_LENGTH", "4096"))
OWASP_MAX_PATH_LENGTH = int(os.getenv("OWASP_MAX_PATH_LENGTH", "2048"))
OWASP_ALLOWED_HOSTS = [host.strip().lower() for host in os.getenv("OWASP_ALLOWED_HOSTS", "").split(",") if host.strip()]

DISALLOWED_METHODS = {"TRACE", "TRACK", "CONNECT"}
JSON_API_PREFIXES = ("/api/", "/auth/", "/db/", "/rate-limit/", "/monitoring/", "/security/")
NO_STORE_PREFIXES = ("/admin", "/api/admin", "/api/auth/whoami", "/api/moderation", "/api/db/migrate", "/monitoring/logs")
SENSITIVE_QUERY_KEYS = {"admin_key", "api_key", "auth_token", "token", "key", "password", "secret"}
SUSPICIOUS_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\.\./",
        r"\.\.\\",
        r"%2e%2e",
        r"%00",
        r"\x00",
        r"/etc/passwd",
        r"/proc/self",
        r"cmd=",
        r"<\s*script",
        r"javascript:",
        r"data:text/html",
    ]
]

CSP_POLICY = os.getenv(
    "OWASP_CSP_POLICY",
    "default-src 'self' https: data: blob:; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https:; "
    "style-src 'self' 'unsafe-inline' https:; "
    "img-src 'self' data: https: blob:; "
    "font-src 'self' data: https:; "
    "connect-src 'self' https: wss:; "
    "media-src 'self' data: blob: https:; "
    "object-src 'none'; base-uri 'self'; frame-ancestors 'self'; form-action 'self'",
)


def _json_error(error: str, status_code: int, **extra: Any) -> JSONResponse:
    payload = {"ok": False, "error": error, **extra}
    return JSONResponse(payload, status_code=status_code)


def _host_allowed(host: str) -> bool:
    if not OWASP_ALLOWED_HOSTS:
        return True
    host = (host or "").split(":", 1)[0].lower()
    for allowed in OWASP_ALLOWED_HOSTS:
        if host == allowed or (allowed.startswith("*.") and host.endswith(allowed[1:])):
            return True
    return False


def _contains_suspicious_input(value: str) -> bool:
    decoded = unquote(unquote(value or ""))
    return any(pattern.search(value or "") or pattern.search(decoded) for pattern in SUSPICIOUS_PATTERNS)


def _redact_query(query: str) -> str:
    if not query:
        return ""
    parts = []
    for item in query.split("&"):
        key = item.split("=", 1)[0].lower()
        if key in SENSITIVE_QUERY_KEYS or any(token in key for token in SENSITIVE_QUERY_KEYS):
            parts.append(f"{key}=***")
        else:
            parts.append(item[:160])
    return "&".join(parts)


def owasp_status() -> Dict[str, Any]:
    return {
        "enabled": OWASP_HARDENING_ENABLED,
        "block_suspicious_inputs": OWASP_BLOCK_SUSPICIOUS_INPUTS,
        "require_json_api_posts": OWASP_REQUIRE_JSON_API_POSTS,
        "csp_enabled": OWASP_CSP_ENABLED,
        "hsts_enabled": OWASP_HSTS_ENABLED,
        "hsts_max_age": OWASP_HSTS_MAX_AGE,
        "max_query_length": OWASP_MAX_QUERY_LENGTH,
        "max_path_length": OWASP_MAX_PATH_LENGTH,
        "allowed_hosts_configured": bool(OWASP_ALLOWED_HOSTS),
        "controls": {
            "API1_BOLA": "object-level access is enforced for private checks/exports and admin-only resources",
            "API2_Broken_Authentication": "role-aware API keys and Bearer token support; no hardcoded secrets",
            "API3_BOPLA": "export bundles are shaped and private objects require admin/owner access",
            "API4_Resource_Consumption": "request size guard, rate limits, job text caps, path/query caps",
            "API5_BFLA": "admin/moderator routes require function-level role checks",
            "API6_Sensitive_Business_Flows": "abuse/moderation/jobs routes are rate limited and audited",
            "API7_SSRF": "search provider layer uses official source whitelist and this layer blocks suspicious URI payloads",
            "API8_Security_Misconfiguration": "CSP, HSTS, no-store, no-sniff, method blocking, header hardening",
            "API9_Inventory": "status endpoints and README enumerate public/admin/API surface",
            "API10_Unsafe_API_Consumption": "third-party API outputs are treated as evidence with quality scoring and fallback behavior",
        },
    }


class OWASPHardeningMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not OWASP_HARDENING_ENABLED:
            return await call_next(request)

        path = request.url.path or "/"
        query = request.url.query or ""
        method = request.method.upper()
        host = request.headers.get("host", "")

        if method in DISALLOWED_METHODS:
            return _json_error("method_not_allowed_by_security_policy", 405, method=method)
        if len(path) > OWASP_MAX_PATH_LENGTH:
            return _json_error("path_too_long", 414, max_path_length=OWASP_MAX_PATH_LENGTH)
        if len(query) > OWASP_MAX_QUERY_LENGTH:
            return _json_error("query_too_long", 414, max_query_length=OWASP_MAX_QUERY_LENGTH)
        if not _host_allowed(host):
            return _json_error("host_not_allowed", 400)
        if OWASP_BLOCK_SUSPICIOUS_INPUTS and (_contains_suspicious_input(path) or _contains_suspicious_input(query)):
            return _json_error("suspicious_input_blocked", 400, query=_redact_query(query))
        if OWASP_REQUIRE_JSON_API_POSTS and method in {"POST", "PUT", "PATCH"} and path.startswith(JSON_API_PREFIXES):
            content_length = int(request.headers.get("content-length") or "0")
            content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
            allowed = {"application/json", "multipart/form-data", "application/x-www-form-urlencoded", ""}
            if content_length > 0 and content_type not in allowed:
                return _json_error("unsupported_api_content_type", 415, content_type=content_type or "missing")

        response = await call_next(request)
        response.headers["X-ClaimRadar-OWASP-Hardening"] = "enabled"
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin-allow-popups")
        response.headers.setdefault("X-DNS-Prefetch-Control", "off")
        response.headers.setdefault("X-Download-Options", "noopen")
        if OWASP_CSP_ENABLED and "content-security-policy" not in {k.lower() for k in response.headers.keys()}:
            response.headers["Content-Security-Policy"] = CSP_POLICY
        if OWASP_HSTS_ENABLED:
            response.headers["Strict-Transport-Security"] = f"max-age={OWASP_HSTS_MAX_AGE}; includeSubDomains"
        if path.startswith(NO_STORE_PREFIXES):
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
        return response


def register_owasp_routes(app: FastAPI) -> None:
    @app.get("/security/owasp/status")
    def security_owasp_status():
        return JSONResponse({"ok": True, "owasp": owasp_status()})

    @app.get("/api/security/owasp/status")
    def api_security_owasp_status():
        return JSONResponse({"ok": True, "owasp": owasp_status()})
