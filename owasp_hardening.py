from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Tuple
from urllib.parse import unquote

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

OWASP_HARDENING_ENABLED = os.getenv("OWASP_HARDENING_ENABLED", "1").lower() not in {"0", "false", "no"}
OWASP_BLOCK_SUSPICIOUS_INPUTS = os.getenv("OWASP_BLOCK_SUSPICIOUS_INPUTS", "1").lower() not in {"0", "false", "no"}
OWASP_REQUIRE_JSON_API_POSTS = os.getenv("OWASP_REQUIRE_JSON_API_POSTS", "1").lower() not in {"0", "false", "no"}
OWASP_CSP_ENABLED = os.getenv("OWASP_CSP_ENABLED", "1").lower() not in {"0", "false", "no"}
OWASP_CSP_REPORT_ONLY_ENABLED = os.getenv("OWASP_CSP_REPORT_ONLY_ENABLED", "0").lower() in {"1", "true", "yes"}
OWASP_HSTS_ENABLED = os.getenv("OWASP_HSTS_ENABLED", "1").lower() not in {"0", "false", "no"}
OWASP_HSTS_PRELOAD = os.getenv("OWASP_HSTS_PRELOAD", "0").lower() in {"1", "true", "yes"}
OWASP_HSTS_MAX_AGE = int(os.getenv("OWASP_HSTS_MAX_AGE", "31536000"))
OWASP_MAX_QUERY_LENGTH = int(os.getenv("OWASP_MAX_QUERY_LENGTH", "4096"))
OWASP_MAX_PATH_LENGTH = int(os.getenv("OWASP_MAX_PATH_LENGTH", "2048"))
OWASP_ALLOWED_HOSTS = [host.strip().lower() for host in os.getenv("OWASP_ALLOWED_HOSTS", "").split(",") if host.strip()]
OWASP_FRAME_ANCESTORS = os.getenv("OWASP_FRAME_ANCESTORS", "'self' https://huggingface.co https://*.huggingface.co")
OWASP_COOKIE_HARDENING_ENABLED = os.getenv("OWASP_COOKIE_HARDENING_ENABLED", "1").lower() not in {"0", "false", "no"}
OWASP_SECURITY_TXT_ENABLED = os.getenv("OWASP_SECURITY_TXT_ENABLED", "1").lower() not in {"0", "false", "no"}
OWASP_SECURITY_CONTACT = os.getenv("OWASP_SECURITY_CONTACT", "https://dyrakarmy-claimradar-bg.hf.space/contact")
OWASP_SECURITY_POLICY = os.getenv("OWASP_SECURITY_POLICY", "https://dyrakarmy-claimradar-bg.hf.space/privacy")
OWASP_SECURITY_EXPIRES = os.getenv("OWASP_SECURITY_EXPIRES", "2027-07-02T00:00:00Z")

DISALLOWED_METHODS = {"TRACE", "TRACK", "CONNECT"}
JSON_API_PREFIXES = ("/api/", "/auth/", "/db/", "/rate-limit/", "/monitoring/", "/security/")
NO_STORE_PREFIXES = (
    "/admin",
    "/api/admin",
    "/api/auth/whoami",
    "/api/moderation",
    "/api/db/migrate",
    "/api/sentry/test",
    "/api/telemetry/test",
    "/api/observability/ai-usage",
    "/monitoring/logs",
)
SENSITIVE_QUERY_KEYS = {"admin_key", "api_key", "auth_token", "token", "key", "password", "secret"}
SUSPICIOUS_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\.\./",
        r"\.\.\\",
        r"%2e%2e",
        r"%00",
        r"\x00",
        r"%0d",
        r"%0a",
        r"\r",
        r"\n",
        r"/etc/passwd",
        r"/proc/self",
        r"cmd=",
        r"<\s*script",
        r"<\s*iframe",
        r"javascript:",
        r"data:text/html",
        r"onerror\s*=",
        r"onload\s*=",
        r"union\s+select",
        r"\$\{\s*jndi\s*:",
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
    "object-src 'none'; base-uri 'self'; "
    f"frame-ancestors {OWASP_FRAME_ANCESTORS}; form-action 'self'",
)
CSP_REPORT_ONLY_POLICY = os.getenv("OWASP_CSP_REPORT_ONLY_POLICY", CSP_POLICY)


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


def _hsts_value() -> str:
    value = f"max-age={OWASP_HSTS_MAX_AGE}; includeSubDomains"
    if OWASP_HSTS_PRELOAD:
        value += "; preload"
    return value


def _security_headers() -> Dict[str, str]:
    headers = {
        "X-ClaimRadar-OWASP-Hardening": "enabled",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=(), fullscreen=(self)",
        "Cross-Origin-Opener-Policy": "same-origin-allow-popups",
        "Cross-Origin-Resource-Policy": "same-site",
        "Origin-Agent-Cluster": "?1",
        "X-DNS-Prefetch-Control": "off",
        "X-Download-Options": "noopen",
        "X-Permitted-Cross-Domain-Policies": "none",
        "X-XSS-Protection": "0",
    }
    if OWASP_CSP_ENABLED:
        headers["Content-Security-Policy"] = CSP_POLICY
    if OWASP_CSP_REPORT_ONLY_ENABLED:
        headers["Content-Security-Policy-Report-Only"] = CSP_REPORT_ONLY_POLICY
    if OWASP_HSTS_ENABLED:
        headers["Strict-Transport-Security"] = _hsts_value()
    return headers


def _harden_cookie_value(value: str) -> str:
    lower = value.lower()
    additions: List[str] = []
    if "secure" not in lower:
        additions.append("Secure")
    if "httponly" not in lower:
        additions.append("HttpOnly")
    if "samesite" not in lower:
        additions.append("SameSite=Lax")
    return value + ("; " + "; ".join(additions) if additions else "")


def _harden_set_cookie_headers(response: Response) -> None:
    if not OWASP_COOKIE_HARDENING_ENABLED:
        return
    hardened: List[Tuple[bytes, bytes]] = []
    for key, value in response.raw_headers:
        if key.lower() == b"set-cookie":
            text = value.decode("latin-1", errors="ignore")
            hardened.append((key, _harden_cookie_value(text).encode("latin-1", errors="ignore")))
        else:
            hardened.append((key, value))
    response.raw_headers = hardened


def _security_txt() -> str:
    return "\n".join(
        [
            f"Contact: {OWASP_SECURITY_CONTACT}",
            f"Policy: {OWASP_SECURITY_POLICY}",
            "Preferred-Languages: bg, en",
            f"Expires: {OWASP_SECURITY_EXPIRES}",
            "Canonical: https://dyrakarmy-claimradar-bg.hf.space/.well-known/security.txt",
            "",
        ]
    )


def owasp_status() -> Dict[str, Any]:
    return {
        "enabled": OWASP_HARDENING_ENABLED,
        "block_suspicious_inputs": OWASP_BLOCK_SUSPICIOUS_INPUTS,
        "require_json_api_posts": OWASP_REQUIRE_JSON_API_POSTS,
        "csp_enabled": OWASP_CSP_ENABLED,
        "csp_report_only_enabled": OWASP_CSP_REPORT_ONLY_ENABLED,
        "hsts_enabled": OWASP_HSTS_ENABLED,
        "hsts_preload": OWASP_HSTS_PRELOAD,
        "hsts_max_age": OWASP_HSTS_MAX_AGE,
        "max_query_length": OWASP_MAX_QUERY_LENGTH,
        "max_path_length": OWASP_MAX_PATH_LENGTH,
        "allowed_hosts_configured": bool(OWASP_ALLOWED_HOSTS),
        "frame_ancestors": OWASP_FRAME_ANCESTORS,
        "cookie_hardening_enabled": OWASP_COOKIE_HARDENING_ENABLED,
        "security_txt_enabled": OWASP_SECURITY_TXT_ENABLED,
        "headers": _security_headers(),
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
        for key, value in _security_headers().items():
            if key.lower() not in {existing.lower() for existing in response.headers.keys()}:
                response.headers[key] = value
        if path.startswith(NO_STORE_PREFIXES):
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
        _harden_set_cookie_headers(response)
        return response


def register_owasp_routes(app: FastAPI) -> None:
    @app.get("/security/owasp/status")
    def security_owasp_status():
        return JSONResponse({"ok": True, "owasp": owasp_status()})

    @app.get("/api/security/owasp/status")
    def api_security_owasp_status():
        return JSONResponse({"ok": True, "owasp": owasp_status()})

    @app.get("/security/owasp/headers")
    def security_owasp_headers():
        return JSONResponse({"ok": True, "headers": _security_headers()})

    @app.get("/api/security/owasp/headers")
    def api_security_owasp_headers():
        return JSONResponse({"ok": True, "headers": _security_headers()})

    @app.get("/.well-known/security.txt")
    def well_known_security_txt():
        if not OWASP_SECURITY_TXT_ENABLED:
            return JSONResponse({"ok": False, "error": "security_txt_disabled"}, status_code=404)
        return Response(_security_txt(), media_type="text/plain; charset=utf-8")
