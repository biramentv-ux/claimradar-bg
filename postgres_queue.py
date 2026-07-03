from __future__ import annotations

import os
import time
import uuid
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Tuple

from db_storage import Jsonb, storage

QUEUE_STALE_RUNNING_SECONDS = int(os.getenv("QUEUE_STALE_RUNNING_SECONDS", "1800"))
QUEUE_WORKER_ID = os.getenv("QUEUE_WORKER_ID", f"pg-worker-{os.getpid()}-{uuid.uuid4().hex[:6]}")
JOB_RESULT_MAX_CHARS = int(os.getenv("JOB_RESULT_MAX_CHARS", "50000"))
TERMINAL_STATUSES = {"done", "failed", "cancelled", "cleaned"}
JobFn = Callable[[Dict[str, Any]], Dict[str, Any]]


def now_ts() -> float:
    return time.time()


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


def preview_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    preview: Dict[str, Any] = {}
    for key, value in (payload or {}).items():
        if isinstance(value, str):
            preview[key] = value[:300]
        elif isinstance(value, (int, float, bool)) or value is None:
            preview[key] = value
        else:
            preview[key] = str(type(value).__name__)
    return preview


class PostgresQueueBackedJobStore:
    """Supabase/Postgres queue store for worker processes outside the web app."""

    backend = "postgres"

    def __init__(self, db_storage: Any = storage):
        self.storage = db_storage
        self.last_heartbeat: Dict[str, Any] = {}

    @property
    def configured(self) -> bool:
        return bool(getattr(self.storage, "configured", False))

    def _connect(self):
        if not self.configured:
            raise RuntimeError("Postgres queue requires configured storage.")
        return self.storage.connect()

    def _coerce_job(self, row: Dict[str, Any] | None) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        job = dict(row.get("content") or {}) if isinstance(row.get("content"), dict) else {}
        for key in ["id", "type", "status", "progress", "error", "result"]:
            if row.get(key) is not None:
                job[key] = row.get(key)
        return job if job.get("id") else None

    def _write_job(self, cur: Any, job: Dict[str, Any]) -> None:
        cur.execute(
            """
            insert into public.claimradar_jobs
              (id, type, status, progress, payload_preview, result, error, content, created_at, updated_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s,
              to_timestamp(coalesce(%s, extract(epoch from now()))),
              to_timestamp(coalesce(%s, extract(epoch from now()))))
            on conflict (id) do update set
              type = excluded.type, status = excluded.status, progress = excluded.progress,
              payload_preview = excluded.payload_preview, result = excluded.result,
              error = excluded.error, content = excluded.content, updated_at = excluded.updated_at
            """,
            (
                job["id"], job.get("type"), job.get("status"), int(job.get("progress") or 0),
                Jsonb(job.get("payload_preview") or {}),
                Jsonb(job.get("result")) if job.get("result") is not None else None,
                job.get("error"), Jsonb(job), job.get("created_at"), job.get("updated_at"),
            ),
        )

    def create(self, job_type: str, payload: Dict[str, Any], fn: JobFn | None = None, parent_id: str | None = None) -> Dict[str, Any]:
        ts = now_ts()
        job = {
            "id": uuid.uuid4().hex[:12], "type": job_type, "status": "queued", "progress": 0,
            "created_at": ts, "updated_at": ts, "started_at": None, "finished_at": None,
            "duration_seconds": None, "parent_id": parent_id, "attempt": self.next_attempt(parent_id),
            "cancel_requested": False, "payload_preview": preview_payload(payload), "payload": payload,
            "result": None, "error": None, "worker_id": None, "execution_mode": "external-postgres",
            "events": [{"ts": ts, "status": "queued", "message": "Queued for external Postgres worker"}],
        }
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._write_job(cur, job)
        return job

    def next_attempt(self, parent_id: str | None) -> int:
        if not parent_id:
            return 1
        parent = self.get(parent_id) or {}
        return int(parent.get("attempt") or 1) + 1

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("select id, type, status, progress, result, error, content from public.claimradar_jobs where id = %s", (job_id,))
                return self._coerce_job(cur.fetchone())

    def payload_for(self, job_id: str) -> Optional[Dict[str, Any]]:
        payload = (self.get(job_id) or {}).get("payload")
        return payload if isinstance(payload, dict) else None

    def update(self, job_id: str, **patch: Any) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("select id, type, status, progress, result, error, content from public.claimradar_jobs where id = %s for update", (job_id,))
                job = self._coerce_job(cur.fetchone())
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
                self._write_job(cur, job)
                return job

    def recent(self, limit: int = 50, status: str = "", job_type: str = "") -> List[Dict[str, Any]]:
        query = "select id, type, status, progress, result, error, content from public.claimradar_jobs"
        clauses: List[str] = []
        params: List[Any] = []
        if status:
            clauses.append("status = %s")
            params.append(status)
        if job_type:
            clauses.append("type = %s")
            params.append(job_type)
        if clauses:
            query += " where " + " and ".join(clauses)
        query += " order by updated_at desc limit %s"
        params.append(max(1, min(int(limit), 500)))
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple(params))
                return [job for job in (self._coerce_job(row) for row in cur.fetchall()) if job]

    def stats(self) -> Dict[str, Any]:
        jobs = self.recent(limit=5000)
        status_counts = Counter(str(job.get("status", "unknown")) for job in jobs)
        type_counts = Counter(str(job.get("type", "unknown")) for job in jobs)
        return {"execution_mode": "external-postgres", "backend": self.backend, "configured": self.configured, "total_sampled": len(jobs), "status_counts": dict(status_counts), "type_counts": dict(type_counts), "queued": status_counts.get("queued", 0), "running": status_counts.get("running", 0), "done": status_counts.get("done", 0), "failed": status_counts.get("failed", 0)}

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
        payload = old.get("payload")
        if not isinstance(payload, dict):
            return None, "retry_payload_not_available"
        return self.create(str(old.get("type") or "job"), payload, None, parent_id=job_id), None

    def cleanup(self, keep: int = 500, terminal_only: bool = True) -> Dict[str, Any]:
        rows = self.recent(limit=max(int(keep) + 1000, 1000))
        removed: List[str] = []
        for job in rows[max(10, int(keep)) :]:
            if terminal_only and job.get("status") not in TERMINAL_STATUSES:
                continue
            self.update(str(job.get("id")), status="cleaned", error="removed_by_cleanup", event="Cleanup tombstone")
            removed.append(str(job.get("id")))
        return {"removed": len(removed), "removed_ids": removed[:50], "mode": "postgres_tombstone"}

    def claim_next(self, worker_id: str = QUEUE_WORKER_ID) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    select id, type, status, progress, result, error, content
                    from public.claimradar_jobs
                    where status = 'queued'
                    order by created_at asc
                    limit 1
                    for update skip locked
                """)
                job = self._coerce_job(cur.fetchone())
                if not job:
                    return None
                ts = now_ts()
                if job.get("cancel_requested"):
                    job.update({"status": "cancelled", "progress": 100, "finished_at": ts, "updated_at": ts, "error": "cancelled_before_worker_claim"})
                    self._write_job(cur, job)
                    return None
                job.update({"status": "running", "progress": 10, "started_at": job.get("started_at") or ts, "updated_at": ts, "worker_id": worker_id})
                job.setdefault("events", []).append({"ts": ts, "status": "running", "message": f"Claimed by {worker_id}"})
                job["events"] = job["events"][-25:]
                self._write_job(cur, job)
                return job

    def heartbeat(self, worker_id: str = QUEUE_WORKER_ID) -> Dict[str, Any]:
        self.last_heartbeat = {"id": worker_id, "worker_id": worker_id, "ts": now_ts(), "pid": os.getpid(), "mode": os.getenv("JOB_EXECUTION_MODE", "external"), "queue_backend": self.backend}
        return self.last_heartbeat

    def worker_heartbeats(self, limit: int = 20) -> List[Dict[str, Any]]:
        return [self.last_heartbeat] if self.last_heartbeat else []
