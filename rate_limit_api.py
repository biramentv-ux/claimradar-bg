from __future__ import annotations

from typing import Any, Callable, Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from security_jobs import rate_limit_status, rate_limiter, safe_identity


def register_rate_limit_routes(app: FastAPI, can_admin: Callable[[str], bool]) -> None:
    """Expose safe status and admin reset endpoints for the in-memory rate limiter."""

    async def parse_payload(request: Request) -> Dict[str, Any]:
        try:
            data = await request.json()
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @app.get("/rate-limit/status")
    def public_rate_limit_status():
        return JSONResponse({"ok": True, "rate_limit": rate_limit_status()})

    @app.get("/api/rate-limit/status")
    def api_rate_limit_status():
        return JSONResponse({"ok": True, "rate_limit": rate_limit_status()})

    @app.post("/api/rate-limit/reset")
    async def api_rate_limit_reset(request: Request):
        payload = await parse_payload(request)
        if not can_admin(str(payload.get("admin_key", ""))):
            return JSONResponse({"ok": False, "error": "invalid_admin_key"}, status_code=403)
        identity = str(payload.get("identity", "")).strip()
        identity_hash = str(payload.get("identity_hash", "")).strip()
        scope = str(payload.get("scope", "")).strip()
        all_keys = bool(payload.get("all", False))
        if identity and not identity_hash:
            identity_hash = safe_identity(identity)
        result = rate_limiter.reset(identity_hash=identity_hash, scope=scope, all_keys=all_keys)
        return JSONResponse({"ok": True, "reset": result, "rate_limit": rate_limit_status()})
