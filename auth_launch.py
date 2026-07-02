import os

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import app as app_module
import launch as base_launch
import persistent_launch as persistent
from admin_dashboard import register_admin_dashboard_routes
from auth_roles import is_admin_key, register_auth_routes
from custom_domain import register_custom_domain_routes
from db_storage import storage
from evidence_export import register_evidence_export_routes
from jobs_api import register_job_routes
from monitoring import MonitoringMiddleware
from rate_limit_api import register_rate_limit_routes
from security_jobs import SecurityAndRateLimitMiddleware

persistent.can_admin = is_admin_key

app = FastAPI(title="ClaimRadar BG Auth Layer", version="3.7-evidence-export")
app.add_middleware(SecurityAndRateLimitMiddleware)
app.add_middleware(MonitoringMiddleware)


def can_admin(admin_key: str = "") -> bool:
    return is_admin_key(admin_key)


def migrate_jsonl_to_db() -> dict:
    files = {
        app_module.CHECKS_FILE: "checks",
        app_module.FEEDBACK_FILE: "feedback",
        persistent.Path("data/abuse_reports.jsonl"): "reports",
        persistent.Path("data/visibility.jsonl"): "visibility",
        persistent.Path("data/jobs.jsonl"): "jobs",
    }
    counts = {}
    for path, label in files.items():
        rows = persistent._original_read_jsonl(path, limit=10000)
        count = 0
        for row in reversed(rows):
            if storage.write_jsonl_mirror(persistent.Path(path).name, row):
                count += 1
        counts[label] = count
    return counts


register_custom_domain_routes(app)
register_auth_routes(app, can_admin)
register_rate_limit_routes(app, can_admin)
register_job_routes(
    app,
    base_launch.job_store,
    can_admin,
    base_launch.run_check_job,
    base_launch.run_ai_verdict_job,
    base_launch.run_real_check_job,
)
register_admin_dashboard_routes(app, can_admin, storage, base_launch.job_store, persistent._original_read_jsonl)
register_evidence_export_routes(app, can_admin, storage, persistent._original_read_jsonl, base_launch.visibility_for)


@app.post("/api/db/migrate-jsonl")
async def auth_db_migrate_jsonl(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not can_admin(str(payload.get("admin_key", ""))):
        return JSONResponse({"ok": False, "error": "invalid_admin_key"}, status_code=403)
    if not storage.configured:
        return JSONResponse({"ok": False, "error": "database_not_configured"}, status_code=400)
    counts = migrate_jsonl_to_db()
    return JSONResponse({"ok": True, "migrated": counts, "db": storage.status()})


app.mount("/", persistent.app)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("APP_PORT", "7860")))
