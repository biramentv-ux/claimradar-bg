import os

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import app as app_module
from hardware_inference import configure_app_module, register_inference_routes

configure_app_module(app_module)

import launch as base_launch
import persistent_launch as persistent
from admin_dashboard import register_admin_dashboard_routes
from auth_roles import is_admin_key, register_auth_routes
from custom_domain import register_custom_domain_routes
from db_storage import storage
from evidence_export import register_evidence_export_routes
from jobs_api import register_job_routes
from local_ai_runtime import register_local_ai_runtime_routes
from local_archive import register_local_archive_routes
from local_desktop_ui import register_desktop_ui_routes
from local_evidence_router import register_local_evidence_routes
from local_hardware_benchmark import register_hardware_benchmark_routes
from local_llm_engine import register_local_llm_routes
from local_model_downloads import register_model_download_routes
from local_model_manager import register_local_model_manager_routes
from local_model_manager_static import register_local_model_manager_static_routes
from local_storage_sqlite import register_local_sqlite_routes
from local_transcription import register_local_transcription_routes
from moderation_actions import register_moderation_routes
from moderation_console import register_moderation_console_routes
from monitoring import MonitoringMiddleware
from owasp_hardening import OWASPHardeningMiddleware, register_owasp_routes
from production_observability import register_observability_routes
from queue_backends import maybe_external_job_store, register_queue_backend_routes
from rate_limit_api import register_rate_limit_routes
from security_jobs import SecurityAndRateLimitMiddleware
from supabase_auth_ui import register_supabase_auth_ui_routes
from telemetry_integrations import init_telemetry, register_sentry_routes, register_telemetry_routes

base_launch.job_store = maybe_external_job_store(base_launch.job_store, app_module.DATA_DIR)
persistent.can_admin = is_admin_key

app = FastAPI(title="ClaimRadar BG Auth Layer", version="5.1-desktop-local-platform")
app.add_middleware(SecurityAndRateLimitMiddleware)
app.add_middleware(MonitoringMiddleware)
app.add_middleware(OWASPHardeningMiddleware)
init_telemetry(app)


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
register_supabase_auth_ui_routes(app)
register_desktop_ui_routes(app)
register_local_ai_runtime_routes(app)
register_local_model_manager_static_routes(app)
register_local_model_manager_routes(app)
register_model_download_routes(app)
register_local_llm_routes(app)
register_local_transcription_routes(app)
register_local_sqlite_routes(app)
register_local_archive_routes(app)
register_local_evidence_routes(app)
register_hardware_benchmark_routes(app)
register_inference_routes(app, app_module)
register_queue_backend_routes(app, base_launch.job_store)
register_observability_routes(app, can_admin, base_launch.job_store, storage, persistent._original_read_jsonl)
register_telemetry_routes(app)
register_sentry_routes(app, can_admin)
register_owasp_routes(app)
register_rate_limit_routes(app, can_admin)
register_job_routes(app, base_launch.job_store, can_admin, base_launch.run_check_job, base_launch.run_ai_verdict_job, base_launch.run_real_check_job)
register_admin_dashboard_routes(app, can_admin, storage, base_launch.job_store, persistent._original_read_jsonl)
register_evidence_export_routes(app, can_admin, storage, persistent._original_read_jsonl, base_launch.visibility_for)
register_moderation_routes(app, can_admin, persistent._original_read_jsonl)
register_moderation_console_routes(app, can_admin, persistent._original_read_jsonl)


@app.post("/api/db/migrate-jsonl")
async def auth_db_migrate_jsonl(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    token = str(payload.get("admin_key", ""))
    if not can_admin(token):
        return JSONResponse({"ok": False, "error": "invalid_admin_key"}, status_code=403)
    if not storage.configured:
        return JSONResponse({"ok": False, "error": "database_not_configured"}, status_code=400)
    counts = migrate_jsonl_to_db()
    return JSONResponse({"ok": True, "migrated": counts, "db": storage.status()})


app.mount("/", persistent.app)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("APP_PORT", "7860")))
