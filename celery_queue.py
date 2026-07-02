from __future__ import annotations

import json
import os
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import FastAPI
from fastapi.responses import JSONResponse

import app as app_module

CELERY_ENABLED = os.getenv("CELERY_ENABLED", "1").lower() not in {"0", "false", "no"}
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0")).strip()
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL).strip()
CELERY_QUEUE_NAME = os.getenv("CELERY_QUEUE_NAME", "claimradar")
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "0").lower() in {"1", "true", "yes"}
CELERY_TASK_TIME_LIMIT = int(os.getenv("CELERY_TASK_TIME_LIMIT", "900"))
CELERY_TASK_SOFT_TIME_LIMIT = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "840"))
CELERY_WORKER_PREFETCH_MULTIPLIER = int(os.getenv("CELERY_WORKER_PREFETCH_MULTIPLIER", "1"))
CELERY_TASK_ACKS_LATE = os.getenv("CELERY_TASK_ACKS_LATE", "1").lower() not in {"0", "false", "no"}
CELERY_TASK_REJECT_ON_WORKER_LOST = os.getenv("CELERY_TASK_REJECT_ON_WORKER_LOST", "1").lower() not in {"0", "false", "no"}
CELERY_RESULT_EXPIRES_SECONDS = int(os.getenv("CELERY_RESULT_EXPIRES_SECONDS", "86400"))
JOB_RESULT_MAX_CHARS = int(os.getenv("JOB_RESULT_MAX_CHARS", "50000"))
TERMINAL_STATUSES = {"done", "failed", "cancelled"}

try:
    from celery import Celery
except Exception:
    Celery = None  # type: ignore


def _broker_kind(url: str) -> str:
    lower = (url or "").lower()
    if lower.startswith("redis://") or lower.startswith("rediss://"):
        return "redis"
    if lower.startswith("amqp://") or lower.startswith("pyamqp://"):
        return "rabbitmq"
    if lower.startswith("memory://"):
        return "memory"
    return "custom" if lower else "missing"


def _append_jsonl(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")


def _read_jsonl(path: Path, limit: int = 10000) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]:
        try:
            item = json.loads(line)
            if isinstance(item, dict):
                rows.append(item)
        except json.JSONDecodeError:
            continue
    return rows


def _latest_by_id(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        job_id = row.get("id") or row.get("job_id")
        if job_id:
            latest[str(job_id)] = row
    return latest


def _preview_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    preview: Dict[str, Any] = {}
    for key, value in (payload or {}).items():
        if isinstance(value, str):
            preview[key] = value[:300]
        elif isinstance(value, (int, float, bool)) or value is None:
            preview[key] = value
        else:
            preview[key] = str(type(value).__name__)
    return preview


def _trim_result(result: Dict[str, Any]) -> Dict[str, Any]:
    def trim(value: Any):
        if isinstance(value, str) and len(value) > JOB_RESULT_MAX_CHARS:
            return value[:JOB_RESULT_MAX_CHARS] + "\n...[trimmed]"
        if isinstance(value, dict):
            return {key: trim(val) for key, val in value.items()}
        if isinstance(value, list):
            return [trim(item) for item in value]
        return value
    return trim(result or {})


def build_celery_app():
    if Celery is None:
        return None
    celery = Celery("claimradar_bg", broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)
    celery.conf.update(
        task_default_queue=CELERY_QUEUE_NAME,
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        result_expires=CELERY_RESULT_EXPIRES_SECONDS,
        task_track_started=True,
        task_time_limit=CELERY_TASK_TIME_LIMIT,
        task_soft_time_limit=CELERY_TASK_SOFT_TIME_LIMIT,
        worker_prefetch_multiplier=CELERY_WORKER_PREFETCH_MULTIPLIER,
        task_acks_late=CELERY_TASK_ACKS_LATE,
        task_reject_on_worker_lost=CELERY_TASK_REJECT_ON_WORKER_LOST,
        task_always_eager=CELERY_TASK_ALWAYS_EAGER,
        task_store_eager_result=CELERY_TASK_ALWAYS_EAGER,
        broker_connection_retry_on_startup=True,
    )
    return celery


celery_app = build_celery_app()


def celery_config() -> Dict[str, Any]:
    return {
        "enabled": CELERY_ENABLED,
        "available": celery_app is not None,
        "broker_kind": _broker_kind(CELERY_BROKER_URL),
        "result_backend_kind": _broker_kind(CELERY_RESULT_BACKEND),
        "queue_name": CELERY_QUEUE_NAME,
        "task_always_eager": CELERY_TASK_ALWAYS_EAGER,
        "task_time_limit": CELERY_TASK_TIME_LIMIT,
        "task_soft_time_limit": CELERY_TASK_SOFT_TIME_LIMIT,
        "worker_prefetch_multiplier": CELERY_WORKER_PREFETCH_MULTIPLIER,
        "task_acks_late": CELERY_TASK_ACKS_LATE,
        "task_reject_on_worker_lost": CELERY_TASK_REJECT_ON_WORKER_LOST,
        "result_expires_seconds": CELERY_RESULT_EXPIRES_SECONDS,
    }


def _task_functions() -> Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]]:
    try:
        from hardware_inference import configure_app_module
        configure_app_module(app_module)
    except Exception:
        pass
    import launch as base_launch
    return {"check": base_launch.run_check_job, "ai_verdict": base_launch.run_ai_verdict_job, "real_check": base_launch.run_real_check_job}


class CeleryBackedJobStore:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_file = self.data_dir / "jobs.jsonl"
        self.payloads_file = self.data_dir / "job_payloads.jsonl"

    def _jobs(self) -> Dict[str, Dict[str, Any]]:
        return _latest_by_id(_read_jsonl(self.jobs_file, limit=100000))

    def _payloads(self) -> Dict[str, Dict[str, Any]]:
        return _latest_by_id(_read_jsonl(self.payloads_file, limit=100000))

    def persist(self, job: Dict[str, Any]) -> None:
        _append_jsonl(self.jobs_file, job)

    def next_attempt(self, parent_id: str | None) -> int:
        if not parent_id:
            return 1
        parent = self.get(parent_id) or {}
        return int(parent.get("attempt") or 1) + 1

    def create(self, job_type: str, payload: Dict[str, Any], fn: Callable[[Dict[str, Any]], Dict[str, Any]] | None = None, parent_id: str | None = None) -> Dict[str, Any]:
        job_id = uuid.uuid4().hex[:12]
        now = time.time()
        job = {"id": job_id, "type": job_type, "status": "queued", "progress": 0, "created_at": now, "updated_at": now, "started_at": None, "finished_at": None, "duration_seconds": None, "parent_id": parent_id, "attempt": self.next_attempt(parent_id), "cancel_requested": False, "payload_preview": _preview_payload(payload), "result": None, "error": None, "celery_task_id": None, "execution_mode": "celery", "broker_kind": _broker_kind(CELERY_BROKER_URL), "events": [{"ts": now, "status": "queued", "message": "Job queued for Celery worker"}]}
        _append_jsonl(self.payloads_file, {"id": job_id, "type": job_type, "payload": payload, "parent_id": parent_id, "created_at": now})
        self.persist(job)
        if celery_app is None:
            return self.update(job_id, status="failed", progress=100, finished_at=time.time(), error="celery_not_available", event="Celery dependency not available") or job
        try:
            async_result = celery_app.send_task("claimradar.run_job", args=[job_id, job_type, payload], queue=CELERY_QUEUE_NAME)
            return self.update(job_id, celery_task_id=async_result.id, event=f"Submitted to Celery: {async_result.id}") or job
        except Exception as exc:
            return self.update(job_id, status="failed", progress=100, finished_at=time.time(), error=str(exc)[:1000], event="Celery submit failed") or job

    def update(self, job_id: str, **patch: Any) -> Optional[Dict[str, Any]]:
        job = self.get(job_id)
        if not job:
            return None
        event_message = patch.pop("event", None)
        job.update(patch)
        now = time.time()
        job["updated_at"] = now
        if job.get("started_at") and job.get("finished_at"):
            job["duration_seconds"] = round(float(job["finished_at"]) - float(job["started_at"]), 3)
        if event_message:
            job.setdefault("events", []).append({"ts": now, "status": job.get("status"), "message": event_message})
            job["events"] = job["events"][-25:]
        self.persist(job)
        return job

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._jobs().get(job_id)

    def payload_for(self, job_id: str) -> Optional[Dict[str, Any]]:
        rec = self._payloads().get(job_id)
        payload = rec.get("payload") if rec else None
        return payload if isinstance(payload, dict) else None

    def recent(self, limit: int = 50, status: str = "", job_type: str = "") -> List[Dict[str, Any]]:
        rows = sorted(self._jobs().values(), key=lambda j: j.get("updated_at", 0), reverse=True)
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if job_type:
            rows = [row for row in rows if row.get("type") == job_type]
        return rows[:limit]

    def stats(self) -> Dict[str, Any]:
        jobs = list(self._jobs().values())
        status_counts = Counter(str(job.get("status", "unknown")) for job in jobs)
        type_counts = Counter(str(job.get("type", "unknown")) for job in jobs)
        durations = [float(job.get("duration_seconds") or 0) for job in jobs if job.get("duration_seconds")]
        return {"execution_mode": "celery", "total": len(jobs), "status_counts": dict(status_counts), "type_counts": dict(type_counts), "running": status_counts.get("running", 0), "queued": status_counts.get("queued", 0), "failed": status_counts.get("failed", 0), "cancelled": status_counts.get("cancelled", 0), "done": status_counts.get("done", 0), "avg_duration_seconds": round(sum(durations) / len(durations), 3) if durations else 0, "max_duration_seconds": round(max(durations), 3) if durations else 0, "celery": celery_config()}

    def cancel(self, job_id: str, reason: str = "cancelled_by_admin") -> Optional[Dict[str, Any]]:
        job = self.get(job_id)
        if not job:
            return None
        if job.get("status") in TERMINAL_STATUSES:
            return job
        celery_task_id = str(job.get("celery_task_id") or "")
        if celery_app is not None and celery_task_id:
            try:
                celery_app.control.revoke(celery_task_id)
            except Exception:
                pass
        if job.get("status") == "queued":
            return self.update(job_id, status="cancelled", progress=100, cancel_requested=True, error=reason, finished_at=time.time(), event=reason)
        return self.update(job_id, cancel_requested=True, event=f"Cancel requested: {reason}")

    def retry(self, job_id: str, fn: Callable[[Dict[str, Any]], Dict[str, Any]] | None = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        old = self.get(job_id)
        if not old:
            return None, "job_not_found"
        payload = self.payload_for(job_id)
        if payload is None:
            return None, "retry_payload_not_available"
        return self.create(str(old.get("type") or "job"), payload, None, parent_id=job_id), None

    def cleanup(self, keep: int = 500, terminal_only: bool = True) -> Dict[str, Any]:
        keep = max(10, min(int(keep), 10000))
        rows = sorted(self._jobs().values(), key=lambda j: j.get("updated_at", 0), reverse=True)
        keep_ids = {job["id"] for job in rows[:keep] if job.get("id")}
        removed: List[str] = []
        for job in rows[keep:]:
            if terminal_only and job.get("status") not in TERMINAL_STATUSES:
                continue
            removed.append(str(job.get("id")))
            self.persist(dict(job, status="cleaned", updated_at=time.time(), error="removed_by_cleanup"))
        return {"removed": len(removed), "removed_ids": removed[:50], "remaining": len(keep_ids), "mode": "tombstone"}


def _store_for_worker() -> CeleryBackedJobStore:
    return CeleryBackedJobStore(app_module.DATA_DIR)


if celery_app is not None:
    @celery_app.task(name="claimradar.run_job", bind=True)
    def run_claimradar_job(self, job_id: str, job_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        store = _store_for_worker()
        store.update(job_id, status="running", progress=10, started_at=time.time(), celery_task_id=getattr(self.request, "id", ""), event="Celery worker started job")
        try:
            fn = _task_functions().get(job_type)
            if fn is None:
                raise RuntimeError(f"no_celery_worker_function_for_type:{job_type}")
            result = fn(payload)
            latest = store.get(job_id) or {}
            if latest.get("cancel_requested"):
                store.update(job_id, status="cancelled", progress=100, finished_at=time.time(), error="cancelled_after_processing", event="Celery job cancelled after processing")
                return {"ok": False, "status": "cancelled", "job_id": job_id}
            clean = _trim_result(result)
            store.update(job_id, status="done", progress=100, result=clean, finished_at=time.time(), event="Celery worker finished job")
            return {"ok": True, "status": "done", "job_id": job_id, "result": clean}
        except Exception as exc:
            store.update(job_id, status="failed", progress=100, finished_at=time.time(), error=str(exc)[:1000], event="Celery worker failed job")
            raise


def celery_queue_status(store: Any | None = None) -> Dict[str, Any]:
    is_celery_store = isinstance(store, CeleryBackedJobStore)
    return {"enabled": CELERY_ENABLED, "store_type": type(store).__name__ if store is not None else "none", "celery_store_active": is_celery_store, "config": celery_config(), "stats": store.stats() if is_celery_store else {}}


def maybe_celery_job_store(current_store: Any, data_dir: Path) -> Any:
    if os.getenv("JOB_EXECUTION_MODE", "thread").strip().lower() == "celery":
        return CeleryBackedJobStore(data_dir)
    return current_store


def register_celery_routes(app: FastAPI, job_store: Any) -> None:
    @app.get("/celery/status")
    def public_celery_status():
        return JSONResponse({"ok": True, "celery": celery_queue_status(job_store)})

    @app.get("/api/celery/status")
    def api_celery_status():
        return JSONResponse({"ok": True, "celery": celery_queue_status(job_store)})
