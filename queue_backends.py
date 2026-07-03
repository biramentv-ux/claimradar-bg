from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from external_queue import (
    JOB_EXECUTION_MODE,
    QUEUE_BATCH_SIZE,
    QUEUE_POLL_SECONDS,
    QUEUE_STALE_RUNNING_SECONDS,
    QUEUE_WORKER_ID,
    QueueBackedJobStore,
)

QUEUE_BACKEND = os.getenv("QUEUE_BACKEND", "jsonl").strip().lower()


def build_external_job_store(data_dir: Path) -> Any:
    if QUEUE_BACKEND in {"postgres", "supabase", "db"}:
        from postgres_queue import PostgresQueueBackedJobStore

        return PostgresQueueBackedJobStore()
    return QueueBackedJobStore(data_dir)


def maybe_external_job_store(current_store: Any, data_dir: Path) -> Any:
    if JOB_EXECUTION_MODE in {"external", "hybrid"}:
        return build_external_job_store(data_dir)
    return current_store


def queue_backend_status(store: Any) -> Dict[str, Any]:
    is_external = type(store).__name__ in {"QueueBackedJobStore", "PostgresQueueBackedJobStore"}
    status: Dict[str, Any] = {
        "enabled": JOB_EXECUTION_MODE in {"external", "hybrid"},
        "execution_mode": JOB_EXECUTION_MODE,
        "queue_backend": QUEUE_BACKEND,
        "store_type": type(store).__name__,
        "external_store_active": is_external,
        "poll_seconds": QUEUE_POLL_SECONDS,
        "batch_size": QUEUE_BATCH_SIZE,
        "stale_running_seconds": QUEUE_STALE_RUNNING_SECONDS,
        "worker_id_example": QUEUE_WORKER_ID,
    }
    if is_external:
        status["stats"] = store.stats()
        status["heartbeats"] = store.worker_heartbeats(limit=10)
    return status


def register_queue_backend_routes(app: FastAPI, job_store: Any) -> None:
    @app.get("/queue/status")
    def queue_status():
        return JSONResponse({"ok": True, "queue": queue_backend_status(job_store)})

    @app.get("/api/queue/status")
    def api_queue_status():
        return JSONResponse({"ok": True, "queue": queue_backend_status(job_store)})
