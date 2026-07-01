from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass, asdict
from typing import Any, Callable, Dict, List

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

AUTH_ENABLED = os.getenv("AUTH_ENABLED", "1").lower() not in {"0", "false", "no"}
AUTH_TOKEN_SALT = os.getenv("AUTH_TOKEN_SALT", "claimradar-bg-auth")
AUTH_KEYS_JSON = os.getenv("AUTH_KEYS_JSON", "").strip()
OWNER_KEY = os.getenv("OWNER_KEY", "").strip()
ADMIN_KEY = os.getenv("ADMIN_KEY", "").strip()
MODERATOR_KEY = os.getenv("MODERATOR_KEY", "").strip()
VIEWER_KEY = os.getenv("VIEWER_KEY", "").strip()

ROLE_LEVELS = {
    "anonymous": 0,
    "viewer": 10,
    "moderator": 20,
    "admin": 30,
    "owner": 40,
}

ROLE_PERMISSIONS = {
    "anonymous": ["public:read"],
    "viewer": ["public:read", "checks:read", "jobs:read", "metrics:read"],
    "moderator": [
        "public:read",
        "checks:read",
        "checks:moderate",
        "jobs:read",
        "jobs:cancel",
        "reports:read",
        "metrics:read",
    ],
    "admin": [
        "public:read",
        "checks:read",
        "checks:moderate",
        "checks:visibility",
        "jobs:read",
        "jobs:cancel",
        "jobs:retry",
        "jobs:cleanup",
        "reports:read",
        "logs:read",
        "metrics:read",
        "db:migrate",
        "rate_limit:reset",
    ],
    "owner": ["*"],
}


def token_hash(token: str) -> str:
    secret = AUTH_TOKEN_SALT.encode("utf-8", errors="ignore")
    msg = (token or "").encode("utf-8", errors="ignore")
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()[:18]


@dataclass
class AuthContext:
    authenticated: bool
    role: str
    subject: str
    token_hash: str
    source: str
    permissions: List[str]

    def to_public(self) -> Dict[str, Any]:
        data = asdict(self)
        if not self.authenticated:
            data["token_hash"] = ""
        return data


def normalize_role(role: str) -> str:
    role = (role or "anonymous").lower().strip()
    return role if role in ROLE_LEVELS else "anonymous"


def permissions_for_role(role: str) -> List[str]:
    role = normalize_role(role)
    if role == "owner":
        return ["*"]
    perms: List[str] = []
    for candidate, level in ROLE_LEVELS.items():
        if level <= ROLE_LEVELS[role]:
            for perm in ROLE_PERMISSIONS.get(candidate, []):
                if perm not in perms:
                    perms.append(perm)
    return perms


def anonymous_context() -> AuthContext:
    return AuthContext(False, "anonymous", "anonymous", "", "none", permissions_for_role("anonymous"))


def parse_auth_keys_json() -> List[Dict[str, str]]:
    if not AUTH_KEYS_JSON:
        return []
    try:
        data = json.loads(AUTH_KEYS_JSON)
    except Exception:
        return []
    rows: List[Dict[str, str]] = []
    if isinstance(data, dict):
        for subject, value in data.items():
            if isinstance(value, str):
                rows.append({"subject": str(subject), "role": "admin", "key": value})
            elif isinstance(value, dict):
                rows.append({
                    "subject": str(subject),
                    "role": str(value.get("role", "viewer")),
                    "key": str(value.get("key", "")),
                })
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                rows.append({
                    "subject": str(item.get("subject", item.get("name", "api-key"))),
                    "role": str(item.get("role", "viewer")),
                    "key": str(item.get("key", "")),
                })
    return [row for row in rows if row.get("key")]


def configured_keys() -> List[Dict[str, str]]:
    rows = []
    if OWNER_KEY:
        rows.append({"subject": "owner", "role": "owner", "key": OWNER_KEY, "source": "OWNER_KEY"})
    if ADMIN_KEY:
        rows.append({"subject": "admin", "role": "admin", "key": ADMIN_KEY, "source": "ADMIN_KEY"})
    if MODERATOR_KEY:
        rows.append({"subject": "moderator", "role": "moderator", "key": MODERATOR_KEY, "source": "MODERATOR_KEY"})
    if VIEWER_KEY:
        rows.append({"subject": "viewer", "role": "viewer", "key": VIEWER_KEY, "source": "VIEWER_KEY"})
    for row in parse_auth_keys_json():
        row.setdefault("source", "AUTH_KEYS_JSON")
        rows.append(row)
    return rows


def extract_token(request: Request) -> tuple[str, str]:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip(), "authorization_bearer"
    for header in ("x-api-key", "x-admin-key", "x-claimradar-admin-key"):
        value = request.headers.get(header, "")
        if value:
            return value.strip(), header
    for param in ("auth_token", "api_key", "admin_key"):
        value = request.query_params.get(param, "")
        if value:
            return value.strip(), param
    return "", "none"


def context_from_token(token: str, source: str = "manual") -> AuthContext:
    if not AUTH_ENABLED:
        return AuthContext(True, "owner", "auth-disabled", token_hash("auth-disabled"), "AUTH_ENABLED=0", permissions_for_role("owner"))
    if not token:
        return anonymous_context()
    for row in configured_keys():
        key = row.get("key", "")
        if key and hmac.compare_digest(token, key):
            role = normalize_role(row.get("role", "viewer"))
            subject = row.get("subject") or role
            return AuthContext(True, role, subject, token_hash(token), row.get("source", source), permissions_for_role(role))
    return anonymous_context()


def auth_context_from_request(request: Request) -> AuthContext:
    token, source = extract_token(request)
    return context_from_token(token, source)


def has_role(ctx: AuthContext, minimum_role: str) -> bool:
    return ROLE_LEVELS.get(ctx.role, 0) >= ROLE_LEVELS.get(normalize_role(minimum_role), 0)


def has_permission(ctx: AuthContext, permission: str) -> bool:
    return "*" in ctx.permissions or permission in ctx.permissions


def is_admin_key(token: str) -> bool:
    return has_role(context_from_token(token, "manual"), "admin")


def is_moderator_key(token: str) -> bool:
    return has_role(context_from_token(token, "manual"), "moderator")


def auth_status() -> Dict[str, Any]:
    rows = configured_keys()
    return {
        "enabled": AUTH_ENABLED,
        "roles": ROLE_LEVELS,
        "permissions": ROLE_PERMISSIONS,
        "configured_key_count": len(rows),
        "configured_roles": sorted({normalize_role(row.get("role", "viewer")) for row in rows}),
        "supports": ["Authorization: Bearer", "x-api-key", "x-admin-key", "x-claimradar-admin-key", "auth_token query"],
    }


def register_auth_routes(app: FastAPI, can_admin: Callable[[str], bool] | None = None) -> None:
    @app.get("/auth/status")
    def public_auth_status():
        return JSONResponse({"ok": True, "auth": auth_status()})

    @app.get("/api/auth/status")
    def api_auth_status():
        return JSONResponse({"ok": True, "auth": auth_status()})

    @app.get("/api/auth/whoami")
    def api_auth_whoami(request: Request):
        ctx = auth_context_from_request(request)
        return JSONResponse({"ok": True, "auth": ctx.to_public()})

    @app.get("/api/auth/roles")
    def api_auth_roles():
        return JSONResponse({"ok": True, "roles": ROLE_LEVELS, "permissions": ROLE_PERMISSIONS})

    @app.post("/api/auth/check")
    async def api_auth_check(request: Request):
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        token = str(payload.get("token", ""))
        minimum_role = str(payload.get("minimum_role", "viewer"))
        permission = str(payload.get("permission", ""))
        ctx = context_from_token(token, "body") if token else auth_context_from_request(request)
        allowed = has_role(ctx, minimum_role)
        if permission:
            allowed = allowed and has_permission(ctx, permission)
        return JSONResponse({"ok": True, "allowed": allowed, "auth": ctx.to_public()})
