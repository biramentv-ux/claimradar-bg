import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

import app as app_module
import launch as base_launch
from db_storage import storage
from security_jobs import SecurityAndRateLimitMiddleware

_original_append_jsonl = app_module.append_jsonl
_original_read_jsonl = app_module.read_jsonl
SCHEMA_FILE = Path("supabase/schema.sql")


def db_aware_append_jsonl(path: Path, obj: dict):
    # Keep JSONL as local backup, mirror to Postgres when DATABASE_URL is configured.
    _original_append_jsonl(path, obj)
    try:
        storage.write_jsonl_mirror(Path(path).name, obj)
    except Exception:
        pass


def db_aware_read_jsonl(path: Path, limit=200):
    try:
        rows = storage.read_jsonl_mirror(Path(path).name, limit)
        if rows is not None:
            return rows
    except Exception:
        pass
    return _original_read_jsonl(path, limit)


app_module.append_jsonl = db_aware_append_jsonl
app_module.read_jsonl = db_aware_read_jsonl

outer_app = FastAPI(title="ClaimRadar BG Persistent Layer", version="2.7-postgres-persistent-storage")
outer_app.add_middleware(SecurityAndRateLimitMiddleware)


def can_admin(admin_key: str = "") -> bool:
    configured = getattr(app_module, "ADMIN_KEY", "") or os.getenv("ADMIN_KEY", "")
    return bool(configured and admin_key and admin_key == configured)


def migrate_jsonl_to_db() -> dict:
    files = {
        app_module.CHECKS_FILE: "checks",
        app_module.FEEDBACK_FILE: "feedback",
        Path("data/abuse_reports.jsonl"): "reports",
        Path("data/visibility.jsonl"): "visibility",
        Path("data/jobs.jsonl"): "jobs",
    }
    counts = {}
    for path, label in files.items():
        rows = _original_read_jsonl(path, limit=10000)
        count = 0
        for row in reversed(rows):
            if storage.write_jsonl_mirror(Path(path).name, row):
                count += 1
        counts[label] = count
    return counts


@outer_app.get("/db/status")
def db_status():
    status = storage.status()
    return JSONResponse({
        "ok": True,
        "storage": "postgres" if status.get("connected") else "jsonl_fallback",
        **status,
    })


@outer_app.get("/api/db/status")
def db_status_alias():
    return db_status()


@outer_app.get("/api/db/schema")
def db_schema():
    if not SCHEMA_FILE.exists():
        return JSONResponse({"ok": False, "error": "schema_file_missing"}, status_code=404)
    return Response(SCHEMA_FILE.read_text(encoding="utf-8"), media_type="text/plain; charset=utf-8")


@outer_app.post("/api/db/migrate-jsonl")
async def db_migrate_jsonl(request: Request):
    payload = await request.json()
    if not can_admin(str(payload.get("admin_key", ""))):
        return JSONResponse({"ok": False, "error": "invalid_admin_key"}, status_code=403)
    if not storage.configured:
        return JSONResponse({"ok": False, "error": "database_not_configured"}, status_code=400)
    counts = migrate_jsonl_to_db()
    return JSONResponse({"ok": True, "migrated": counts, "db": storage.status()})


outer_app.mount("/", base_launch.app)
app = outer_app


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("APP_PORT", "7860")))
