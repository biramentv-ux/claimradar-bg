import json
import os
import time
import uuid
from collections import Counter, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "1").lower() not in {"0", "false", "no"}
SECURITY_HEADERS_ENABLED = os.getenv("SECURITY_HEADERS_ENABLED", "1").lower() not in {"0", "false", "no"}
MAX_REQUEST_BYTES = int(os.getenv("MAX_REQUEST_BYTES", str(25 * 1024 * 1024)))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_DEFAULT = int(os.getenv("RATE_LIMIT_DEFAULT", "120"))
RATE_LIMIT_API = int(os.getenv("RATE_LIMIT_API", "60"))
RATE_LIMIT_HEAVY = int(os.getenv("RATE_LIMIT_HEAVY", "12"))
RATE_LIMIT_ABUSE = int(os.getenv("RATE_LIMIT_ABUSE", "6"))
JOB_WORKERS = int(os.getenv("JOB_WORKERS", "2"))
JOB_RETENTION = int(os.getenv("JOB_RETENTION", "500"))
JOB_RESULT_MAX_CHARS = int(os.getenv("JOB_RESULT_MAX_CHARS", "50000"))

HEAVY_PREFIXES = (
    "/api/jobs",
    "/api/report-abuse",
    "/api/check/",
    "/ws/",
)
PUBLIC_PREFIXES = (
    "/check/",
    "/product",
    "/social-preview.svg",
    "/sources/whitelist",
    "/search/status",
    "/health",
)
TERMINAL_STATUSES = {"done", "failed", "cancelled"}
RUNNING_STATUSES = {"queued", "running"}


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip", "")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


class InMemoryRateLimiter:
    def __init__(self):
        self.hits: Dict[str, deque] = defaultdict(deque)

    def limit_for_path(self, path: str) -> int:
        if path.startswith("/api/report-abuse"):
            return RATE_LIMIT_ABUSE
        if path.startswith("/api/"):
            return RATE_LIMIT_API
        if any(path.startswith(prefix) for prefix in HEAVY_PREFIXES):
            return RATE_LIMIT_HEAVY
        return RATE_LIMIT_DEFAULT

    def check(self, key: str, path: str) -> tuple[bool, int, int]:
        now = time.time()
        limit = self.limit_for_path(path)
        bucket = self.hits[key]
        while bucket and bucket[0] <= now - RATE_LIMIT_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= limit:
            reset = int(RATE_LIMIT_WINDOW_SECONDS - (now - bucket[0])) if bucket else RATE_LIMIT_WINDOW_SECONDS
            return False, max(0, reset), limit
        bucket.append(now)
        return True, 0, limit


rate_limiter = InMemoryRateLimiter()


class SecurityAndRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        content_length = int(request.headers.get("content-length") or 0)
        if MAX_REQUEST_BYTES > 0 and content_length > MAX_REQUEST_BYTES:
            return JSONResponse(
                {"ok": False, "error": "request_too_large", "max_bytes": MAX_REQUEST_BYTES},
                status_code=413,
            )

        if RATE_LIMIT_ENABLED:
            ip = client_ip(request)
            key = f"{ip}:{path.split('/')[1] if len(path.split('/')) > 1 else 'root'}"
            allowed, retry_after, limit = rate_limiter.check(key, path)
            if not allowed:
                return JSONResponse(
                    {"ok": False, "error": "rate_limited", "retry_after_seconds": retry_after, "limit_per_window": limit},
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                )

        response = await call_next(request)

        if SECURITY_HEADERS_ENABLED:
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
            response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
            response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin-allow-popups")
            response.headers.setdefault("X-ClaimRadar-Security", "enabled")
        return response


class JobStore:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.jobs_file = self.data_dir / "jobs.jsonl"
        self.executor = ThreadPoolExecutor(max_workers=max(1, JOB_WORKERS))
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.payloads: Dict[str, Dict[str, Any]] = {}
        self.functions: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}
        self.load_recent()

    def load_recent(self):
        if not self.jobs_file.exists():
            return
        rows = []
        for line in self.jobs_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        for row in rows[-JOB_RETENTION:]:
            if row.get("id"):
                self.jobs[row["id"]] = row

    def persist(self, job: Dict[str, Any]):
        with self.jobs_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(job, ensure_ascii=False, default=str) + "\n")

    def create(
        self,
        job_type: str,
        payload: Dict[str, Any],
        fn: Callable[[Dict[str, Any]], Dict[str, Any]],
        parent_id: str | None = None,
    ) -> Dict[str, Any]:
        job_id = uuid.uuid4().hex[:12]
        now = time.time()
        job = {
            "id": job_id,
            "type": job_type,
            "status": "queued",
            "progress": 0,
            "created_at": now,
            "updated_at": now,
            "started_at": None,
            "finished_at": None,
            "duration_seconds": None,
            "parent_id": parent_id,
            "attempt": self.next_attempt(parent_id),
            "cancel_requested": False,
            "payload_preview": self.preview_payload(payload),
            "result": None,
            "error": None,
            "events": [{"ts": now, "status": "queued", "message": "Job queued"}],
        }
        self.jobs[job_id] = job
        self.payloads[job_id] = payload
        self.functions[job_id] = fn
        self.persist(job)
        self.executor.submit(self._run, job_id, payload, fn)
        return job

    def next_attempt(self, parent_id: str | None) -> int:
        if not parent_id:
            return 1
        parent = self.jobs.get(parent_id) or {}
        return int(parent.get("attempt") or 1) + 1

    def _run(self, job_id: str, payload: Dict[str, Any], fn: Callable[[Dict[str, Any]], Dict[str, Any]]):
        job = self.jobs.get(job_id)
        if not job:
            return
        if job.get("cancel_requested"):
            self.update(job_id, status="cancelled", progress=100, finished_at=time.time(), error="cancelled_before_start")
            return
        started = time.time()
        try:
            self.update(job_id, status="running", progress=10, started_at=started, event="Job started")
            result = fn(payload)
            if self.jobs.get(job_id, {}).get("cancel_requested"):
                self.update(job_id, status="cancelled", progress=100, finished_at=time.time(), error="cancelled_after_processing")
                return
            self.update(job_id, status="done", progress=100, result=self.trim_result(result), finished_at=time.time(), event="Job finished")
        except Exception as exc:
            self.update(job_id, status="failed", error=str(exc), progress=100, finished_at=time.time(), event="Job failed")

    def update(self, job_id: str, **patch):
        job = self.jobs.get(job_id)
        if not job:
            return
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

    def cancel(self, job_id: str, reason: str = "cancelled_by_admin") -> Optional[Dict[str, Any]]:
        job = self.jobs.get(job_id)
        if not job:
            return None
        if job.get("status") in TERMINAL_STATUSES:
            return job
        if job.get("status") == "queued":
            self.update(job_id, status="cancelled", progress=100, cancel_requested=True, error=reason, finished_at=time.time(), event=reason)
        else:
            self.update(job_id, cancel_requested=True, event=f"Cancel requested: {reason}")
        return self.jobs.get(job_id)

    def retry(self, job_id: str, fn: Callable[[Dict[str, Any]], Dict[str, Any]] | None = None) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        old = self.jobs.get(job_id)
        if not old:
            return None, "job_not_found"
        payload = self.payloads.get(job_id)
        if payload is None:
            return None, "retry_payload_not_available_after_restart"
        retry_fn = fn or self.functions.get(job_id)
        if retry_fn is None:
            return None, "retry_function_not_available"
        return self.create(str(old.get("type") or "job"), payload, retry_fn, parent_id=job_id), None

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self.jobs.get(job_id)

    def recent(self, limit: int = 50, status: str = "", job_type: str = ""):
        rows = sorted(self.jobs.values(), key=lambda j: j.get("updated_at", 0), reverse=True)
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if job_type:
            rows = [row for row in rows if row.get("type") == job_type]
        return rows[:limit]

    def stats(self) -> Dict[str, Any]:
        status_counts = Counter(str(job.get("status", "unknown")) for job in self.jobs.values())
        type_counts = Counter(str(job.get("type", "unknown")) for job in self.jobs.values())
        durations = [float(job.get("duration_seconds") or 0) for job in self.jobs.values() if job.get("duration_seconds")]
        return {
            "total": len(self.jobs),
            "status_counts": dict(status_counts),
            "type_counts": dict(type_counts),
            "running": status_counts.get("running", 0),
            "queued": status_counts.get("queued", 0),
            "failed": status_counts.get("failed", 0),
            "cancelled": status_counts.get("cancelled", 0),
            "done": status_counts.get("done", 0),
            "workers": JOB_WORKERS,
            "retention": JOB_RETENTION,
            "avg_duration_seconds": round(sum(durations) / len(durations), 3) if durations else 0,
            "max_duration_seconds": round(max(durations), 3) if durations else 0,
        }

    def cleanup(self, keep: int = JOB_RETENTION, terminal_only: bool = True) -> Dict[str, Any]:
        keep = max(10, min(int(keep), max(JOB_RETENTION, 10_000)))
        rows = sorted(self.jobs.values(), key=lambda j: j.get("updated_at", 0), reverse=True)
        keep_ids = {job["id"] for job in rows[:keep] if job.get("id")}
        removed = []
        for job_id, job in list(self.jobs.items()):
            if job_id in keep_ids:
                continue
            if terminal_only and job.get("status") not in TERMINAL_STATUSES:
                continue
            removed.append(job_id)
            self.jobs.pop(job_id, None)
            self.payloads.pop(job_id, None)
            self.functions.pop(job_id, None)
        return {"removed": len(removed), "removed_ids": removed[:50], "remaining": len(self.jobs)}

    @staticmethod
    def preview_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        preview = {}
        for key, value in (payload or {}).items():
            if isinstance(value, str):
                preview[key] = value[:300]
            elif isinstance(value, (int, float, bool)) or value is None:
                preview[key] = value
            else:
                preview[key] = str(type(value).__name__)
        return preview

    @staticmethod
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


def security_status() -> Dict[str, Any]:
    return {
        "rate_limit_enabled": RATE_LIMIT_ENABLED,
        "security_headers_enabled": SECURITY_HEADERS_ENABLED,
        "max_request_bytes": MAX_REQUEST_BYTES,
        "rate_limit_window_seconds": RATE_LIMIT_WINDOW_SECONDS,
        "rate_limit_default": RATE_LIMIT_DEFAULT,
        "rate_limit_api": RATE_LIMIT_API,
        "rate_limit_heavy": RATE_LIMIT_HEAVY,
        "rate_limit_abuse": RATE_LIMIT_ABUSE,
        "job_workers": JOB_WORKERS,
        "job_retention": JOB_RETENTION,
        "job_result_max_chars": JOB_RESULT_MAX_CHARS,
    }
