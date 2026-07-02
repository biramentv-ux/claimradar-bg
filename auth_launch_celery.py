import os

import uvicorn
from fastapi import FastAPI

import app as app_module
from hardware_inference import configure_app_module, register_inference_routes

configure_app_module(app_module)

import launch as base_launch
import persistent_launch as persistent
from admin_dashboard import register_admin_dashboard_routes
from auth_roles import is_admin_key, register_auth_routes
from celery_queue import maybe_celery_job_store, register_celery_routes
from custom_domain import register_custom_domain_routes
from db_storage import storage
from evidence_export import register_evidence_export_routes
from external_queue import register_external_queue_routes
from jobs_api import register_job_routes
from moderation_actions import register_moderation_routes
from moderation_console import register_moderation_console_routes
from monitoring import MonitoringMiddleware
from owasp_hardening import OWASPHardeningMiddleware, register_owasp_routes
from production_observability import register_observability_routes
from rate_limit_api import register_rate_limit_routes
from security_jobs import SecurityAndRateLimitMiddleware
from telemetry_integrations import init_telemetry, register_sentry_routes, register_telemetry_routes

base_launch.job_store = maybe_celery_job_store(base_launch.job_store, app_module.DATA_DIR)
persistent.can_admin = is_admin_key

app = FastAPI(title="ClaimRadar BG Celery Layer", version="4.4-celery")
app.add_middleware(SecurityAndRateLimitMiddleware)
app.add_middleware(MonitoringMiddleware)
app.add_middleware(OWASPHardeningMiddleware)
init_telemetry(app)


def can_admin(token: str = "") -> bool:
    return is_admin_key(token)


register_custom_domain_routes(app)
register_auth_routes(app, can_admin)
register_inference_routes(app, app_module)
register_celery_routes(app, base_launch.job_store)
register_external_queue_routes(app, base_launch.job_store)
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

app.mount("/", persistent.app)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("APP_PORT", "7860")))
