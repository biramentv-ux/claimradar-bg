from __future__ import annotations

import json
import os
import signal
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import FastAPI
from fastapi.responses import JSONResponse

JOB_EXECUTION_MODE = os.getenv("JOB_EXECUTION_MODE", "thread").strip().lower()  # thread | external | hybrid
QUEUE_POLL_SECONDS = float(os.getenv("QUEUE_POLL_SECONDS", "2.0"))
QUEUE_BATCH_SIZE = int(os.getenv("QUEUE_BATCH_SIZE", "1"))
QUEUE_STALE_RUNNING_SECONDS = int(os.getenv("QUEUE_STALE_RUNNING_SECONDS", "1800"))
QUEUE_WORKER_ID = os.getenv("QUEUE_WORKER_ID", f"worker-{os.getpid()}-{uuid.uuid4().hex[:6]}")
JOB_RESULT_MAX_CHARS = int(os.getenv("JOB_RESULT_MAX_CHARS", "50000"))
TERMINAL_STATUSES = {"done", "failed", "cancelled"}

JobFn = Callable[[Dict[str, Any]], Dict[str, Any]]


def now_ts() -> float:
    return time.time()


def append_jsonl(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")


def read_jsonl(path: Path, limit: int = 10000) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            item = json.loads(line)
            if isinstance(item, dict):
                rows.append(item)
        except json.JSONDecodeError:
            continue
    return rows[-limit:]


def latest_by_id(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        job_id = row.get("id") or row.get("job_id")
        if job_id:
            latest[str(job_id)] = row
    return latest


def trim_result(result: Dict[str, Any]) -> Dict[str, Any]:
    def trim(value: Any):
        if isinstance(value, str) and len(value) > JOB_RESULT_MAX_CHARS:
            return value[:JOB_RESULT_MAX_CHARS] + "\n...[trimmed]"
        if isinstance(value, dict):
            return {key: trim(val) for key, val in value.items()}
        if isinstance(value, list):
            return [trim(item) for item in value]
        return value

    return trim(result or {})


class QueueBackedJobStore:
    """Durable job store that can be processed by a separate worker process.

    The API process only enqueues jobs. A separate `python queue_worker.py` process
    can claim and execute them. This keeps heavy checks/transcription out of the
    HTTP process when JOB_EXECUTION_MODE=external.
    """

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_file = self.data_dir / "jobs.jsonl"
        self.payloads_file = self.data_dir / "job_payloads.jsonl"
        self.heartbeats_file = self.data_dir / "queue_worker_heartbeats.jsonl"

    def _jobs(self) -> Dict[str, Dict[str, Any]]:
        return latest_by_id(read_jsonl(self.jobs_file, limit=100000))

    def _payloads(self) -> Dict[str, Dict[str, Any]]:
        return latest_by_id(read_jsonl(self.payloads_file, limit=100000))

    def persist(self, job: Dict[str, Any]) -> None:
        append_jsonl(self.jobs_file, job)

    def preview_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        preview: Dict[str, Any] = {}
        for key, value in (payload or {}).items():
            if isinstance(value, str):
                preview[key] = value[:300]
            elif isinstance(value, (int, float, bool)) or value is None:
                preview[key] = value
            else:
                preview[key] = str(type(value).__name__)
        return preview

    def next_attempt(self, parent_id: str | None) -> int:
        if not parent_id:
            return 1
        parent = self.get(parent_id) or {}
        return int(parent.get("attempt") or 1) + 1

    def create(self, job_type: str, payload: Dict[str, Any], fn: JobFn | None = None, parent_id: str | None = None) -> Dict[str, Any]:
        job_id = uuid.uuid4().hex[:12]
        ts = now_ts()
        job = {
            "id": job_id,
            "type": job_type,
            "status": "queued",
            "progress": 0,
            "created_at": ts,
            "updated_at": ts,
            "started_at": None,
            "finished_at": None,
            "duration_seconds": None,
            "parent_id": parent_id,
            "attempt": self.next_attempt(parent_id),
            "cancel_requested": False,
            "payload_preview": self.preview_payload(payload),
            "result": None,
            "error": None,
            "worker_id": None,
            "execution_mode": "external",
            "events": [{"ts": ts, "status": "queued", "message": "Job queued for external worker"}],
        }
        append_jsonl(self.payloads_file, {"id": job_id, "type": job_type, "payload": payload, "parent_id": parent_id, "created_at": ts})
        self.persist(job)
        return job

    def update(self, job_id: str, **patch: Any) -> Optional[Dict[str, Any]]:
        job = self.get(job_id)
        if not job:
            return None
        event_message = patch.pop("event", None)
        job.update(patch)
        ts = now_ts()
        job["updated_at"] = ts
        if job.get("started_at") and job.get("finished_at"):
            job["duration_seconds"] = round(float(job["finished_at"]) - float(job["started_at"]), 3)
        if event_message:
            job.setdefault("events", []).append({"ts": ts, "status": job.get("status"), "message": event_message})
            job["events"] = job["events"][-25:]
        self.persist(job)
        return job

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._jobs().get(job_id)

    def payload_for(self, job_id: str) -> Optional[Dict[str, Any]]:
        rec = self._payloads().get(job_id)
        if not rec:
            return None
        payload = rec.get("payload")
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
        return {
            "execution_mode": "external",
            "total": len(jobs),
            "status_counts": dict(status_counts),
            "type_counts": dict(type_counts),
            "running": status_counts.get("running", 0),
            "queued": status_counts.get("queued", 0),
            "failed": status_counts.get("failed", 0),
            "cancelled": status_counts.get("cancelled", 0),
            "done": status_counts.get("done", 0),
            "avg_duration_seconds": round(sum(durations) / len(durations), 3) if durations else 0,
            "max_duration_seconds": round(max(durations), 3) if durations else 0,
            "payloads_file": str(self.payloads_file),
            "jobs_file": str(self.jobs_file),
        }

    def cancel(self, job_id: str, reason: str = "cancelled_by_admin") -> Optional[Dict[str, Any]]:
        job = self.get(job_id)
        if not job:
            return None
        if job.get("status") in TERMINAL_STATUSES:
            return job
        if job.get("status") == "queued":
            return self.update(job_id, status="cancelled", progress=100, cancel_requested=True, error=reason, finished_at=now_ts(), event=reason)
        return self.update(job_id, cancel_requested=True, event=f"Cancel requested: {reason}")

    def retry(self, job_id: str, fn: JobFn | None = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        old = self.get(job_id)
        if not old:
            return None, "job_not_found"
        payload = self.payload_for(job_id)
        if payload is None:
            return None, "retry_payload_not_available"
        return self.create(str(old.get("type") or "job"), payload, None, parent_id=job_id), None

    def cleanup(self, keep: int = 500, terminal_only: bool = True) -> Dict[str, Any]:
        keep = max(10, min(int(keep), 10_000))
        rows = sorted(self._jobs().values(), key=lambda j: j.get("updated_at", 0), reverse=True)
        keep_ids = {job["id"] for job in rows[:keep] if job.get("id")}
        removed: List[str] = []
        for job in rows[keep:]:
            if terminal_only and job.get("status") not in TERMINAL_STATUSES:
                continue
            job_id = str(job.get("id"))
            removed.append(job_id)
            tombstone = dict(job, status="cleaned", updated_at=now_ts(), error="removed_by_cleanup")
            self.persist(tombstone)
        return {"removed": len(removed), "removed_ids": removed[:50], "remaining": len(keep_ids), "mode": "tombstone"}

    def claim_next(self, worker_id: str = QUEUE_WORKER_ID) -> Optional[Dict[str, Any]]:
        jobs = sorted(self._jobs().values(), key=lambda j: j.get("created_at", 0))
        ts = now_ts()
        for job in jobs:
            status = job.get("status")
            if status == "queued":
                if job.get("cancel_requested"):
                    self.update(job["id"], status="cancelled", progress=100, finished_at=ts, error="cancelled_before_worker_claim", event="Cancelled before worker claim")
                    continue
                return self.update(job["id"], status="running", progress=10, started_at=ts, worker_id=worker_id, event=f"Claimed by {worker_id}")
            if status == "running" and QUEUE_STALE_RUNNING_SECONDS > 0:
                updated_at = float(job.get("updated_at") or 0)
                if updated_at and ts - updated_at > QUEUE_STALE_RUNNING_SECONDS:
                    self.update(job["id"], status="queued", progress=0, worker_id=None, error="stale_running_requeued", event="Stale running job requeued")
        return None

    def heartbeat(self, worker_id: str = QUEUE_WORKER_ID) -> Dict[str, Any]:
        row = {"id": worker_id, "worker_id": worker_id, "ts": now_ts(), "pid": os.getpid(), "mode": JOB_EXECUTION_MODE}
        append_jsonl(self.heartbeats_file, row)
        return row

    def worker_heartbeats(self, limit: int = 20) -> List[Dict[str, Any]]:
        return read_jsonl(self.heartbeats_file, limit=limit)


class QueueWorker:
    def __init__(self, store: QueueBackedJobStore, job_fns: Dict[str, JobFn], worker_id: str = QUEUE_WORKER_ID):
        self.store = store
        self.job_fns = job_fns
        self.worker_id = worker_id
        self.stop_requested = False

    def request_stop(self, *_args: Any) -> None:
        self.stop_requested = True

    def process_one(self) -> Dict[str, Any]:
        self.store.heartbeat(self.worker_id)
        job = self.store.claim_next(self.worker_id)
        if not job:
            return {"processed": False, "reason": "no_queued_jobs"}
        job_id = str(job["id"])
        job_type = str(job.get("type") or "")
        fn = self.job_fns.get(job_type)
        payload = self.store.payload_for(job_id)
        if fn is None:
            self.store.update(job_id, status="failed", progress=100, finished_at=now_ts(), error=f"no_worker_function_for_type:{job_type}", event="Worker function missing")
            return {"processed": True, "job_id": job_id, "status": "failed", "error": "missing_function"}
        if payload is None:
            self.store.update(job_id, status="failed", progress=100, finished_at=now_ts(), error="payload_not_found", event="Payload missing")
            return {"processed": True, "job_id": job_id, "status": "failed", "error": "payload_not_found"}
        try:
            result = fn(payload)
            latest = self.store.get(job_id) or {}
            if latest.get("cancel_requested"):
                self.store.update(job_id, status="cancelled", progress=100, finished_at=now_ts(), error="cancelled_after_processing", event="Cancelled after processing")
                return {"processed": True, "job_id": job_id, "status": "cancelled"}
            self.store.update(job_id, status="done", progress=100, result=trim_result(result), finished_at=now_ts(), event="Worker finished job")
            return {"processed": True, "job_id": job_id, "status": "done"}
        except Exception as exc:
            self.store.update(job_id, status="failed", progress=100, finished_at=now_ts(), error=str(exc)[:1000], event="Worker failed job")
            return {"processed": True, "job_id": job_id, "status": "failed", "error": str(exc)[:300]}

    def loop(self, poll_seconds: float = QUEUE_POLL_SECONDS, batch_size: int = QUEUE_BATCH_SIZE) -> None:
        signal.signal(signal.SIGTERM, self.request_stop)
        signal.signal(signal.SIGINT, self.request_stop)
        while not self.stop_requested:
            processed = 0
            for _ in range(max(1, batch_size)):
                result = self.process_one()
                if result.get("processed"):
                    processed += 1
                else:
                    break
            if processed == 0:
                time.sleep(max(0.2, poll_seconds))


def external_queue_status(store: QueueBackedJobStore | Any) -> Dict[str, Any]:
    is_external = isinstance(store, QueueBackedJobStore)
    status = {
        "enabled": JOB_EXECUTION_MODE in {"external", "hybrid"},
        "execution_mode": JOB_EXECUTION_MODE,
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


def maybe_external_job_store(current_store: Any, data_dir: Path) -> Any:
    if JOB_EXECUTION_MODE in {"external", "hybrid"}:
        return QueueBackedJobStore(data_dir)
    return current_store


def register_external_queue_routes(app: FastAPI, job_store: Any) -> None:
    @app.get("/queue/status")
    def queue_status():
        return JSONResponse({"ok": True, "queue": external_queue_status(job_store)})

    @app.get("/api/queue/status")
    def api_queue_status():
        return JSONResponse({"ok": True, "queue": external_queue_status(job_store)})
