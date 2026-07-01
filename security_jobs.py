import json
import os
import time
import uuid
from collections import defaultdict, deque
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
            f.write(json.dumps(job, ensure_ascii=False) + "\n")

    def create(self, job_type: str, payload: Dict[str, Any], fn: Callable[[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
        job_id = uuid.uuid4().hex[:12]
        job = {
            "id": job_id,
            "type": job_type,
            "status": "queued",
            "progress": 0,
            "created_at": time.time(),
            "updated_at": time.time(),
            "payload_preview": self.preview_payload(payload),
            "result": None,
            "error": None,
        }
        self.jobs[job_id] = job
        self.persist(job)
        self.executor.submit(self._run, job_id, payload, fn)
        return job

    def _run(self, job_id: str, payload: Dict[str, Any], fn: Callable[[Dict[str, Any]], Dict[str, Any]]):
        job = self.jobs[job_id]
        try:
            self.update(job_id, status="running", progress=10)
            result = fn(payload)
            self.update(job_id, status="done", progress=100, result=result)
        except Exception as exc:
            self.update(job_id, status="failed", error=str(exc), progress=100)

    def update(self, job_id: str, **patch):
        job = self.jobs.get(job_id)
        if not job:
            return
        job.update(patch)
        job["updated_at"] = time.time()
        self.persist(job)

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self.jobs.get(job_id)

    def recent(self, limit: int = 50):
        rows = sorted(self.jobs.values(), key=lambda j: j.get("updated_at", 0), reverse=True)
        return rows[:limit]

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
    }
