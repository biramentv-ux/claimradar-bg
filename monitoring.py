import json
import os
import platform
import time
import traceback
import uuid
from collections import Counter, deque
from pathlib import Path
from typing import Any, Dict, List

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

MONITORING_ENABLED = os.getenv("MONITORING_ENABLED", "1").lower() not in {"0", "false", "no"}
REQUEST_LOG_ENABLED = os.getenv("REQUEST_LOG_ENABLED", "1").lower() not in {"0", "false", "no"}
REQUEST_LOG_BODY = os.getenv("REQUEST_LOG_BODY", "0").lower() in {"1", "true", "yes"}
MONITORING_RECENT_LIMIT = int(os.getenv("MONITORING_RECENT_LIMIT", "200"))
MONITORING_SLOW_MS = int(os.getenv("MONITORING_SLOW_MS", "2500"))
MONITORING_LOG_FILE = os.getenv("MONITORING_LOG_FILE", "data/system_events.jsonl")

START_TIME = time.time()
RECENT_REQUESTS: deque = deque(maxlen=MONITORING_RECENT_LIMIT)
RECENT_ERRORS: deque = deque(maxlen=MONITORING_RECENT_LIMIT)
STATUS_COUNTERS: Counter = Counter()
PATH_COUNTERS: Counter = Counter()
METHOD_COUNTERS: Counter = Counter()
LATENCY_TOTAL_MS = 0.0
LATENCY_COUNT = 0
LATENCY_MAX_MS = 0.0


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def event_file() -> Path:
    path = Path(MONITORING_LOG_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def safe_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip", "")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


def write_event(event: Dict[str, Any]) -> None:
    if not MONITORING_ENABLED:
        return
    event = {"ts": now_iso(), **event}
    try:
        with event_file().open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def read_events(limit: int = 100, level: str = "") -> List[Dict[str, Any]]:
    path = event_file()
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[-max(1, min(limit * 3, 2000)):]:
        try:
            item = json.loads(line)
        except Exception:
            continue
        if level and item.get("level") != level:
            continue
        rows.append(item)
    return rows[-max(1, min(limit, 500)):][::-1]


def public_metrics() -> Dict[str, Any]:
    uptime_seconds = int(time.time() - START_TIME)
    avg_latency = (LATENCY_TOTAL_MS / LATENCY_COUNT) if LATENCY_COUNT else 0.0
    error_count = sum(count for status, count in STATUS_COUNTERS.items() if str(status).startswith(("4", "5")))
    return {
        "enabled": MONITORING_ENABLED,
        "request_log_enabled": REQUEST_LOG_ENABLED,
        "uptime_seconds": uptime_seconds,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(START_TIME)),
        "requests_total": LATENCY_COUNT,
        "errors_total": error_count,
        "avg_latency_ms": round(avg_latency, 2),
        "max_latency_ms": round(LATENCY_MAX_MS, 2),
        "slow_threshold_ms": MONITORING_SLOW_MS,
        "status_counts": dict(STATUS_COUNTERS),
        "method_counts": dict(METHOD_COUNTERS),
        "top_paths": PATH_COUNTERS.most_common(20),
        "recent_errors_count": len(RECENT_ERRORS),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "pid": os.getpid(),
    }


def monitoring_status(extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {
        "ok": True,
        "monitoring": public_metrics(),
        **(extra or {}),
    }


def log_custom_event(kind: str, level: str = "info", message: str = "", data: Dict[str, Any] | None = None) -> Dict[str, Any]:
    event = {
        "id": uuid.uuid4().hex[:12],
        "kind": kind[:80],
        "level": level[:20],
        "message": message[:1000],
        "data": data or {},
    }
    write_event(event)
    if level in {"error", "critical", "warning"}:
        RECENT_ERRORS.appendleft(event)
    return event


class MonitoringMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not MONITORING_ENABLED:
            return await call_next(request)

        global LATENCY_TOTAL_MS, LATENCY_COUNT, LATENCY_MAX_MS
        started = time.perf_counter()
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        path = request.url.path
        method = request.method
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            error_event = {
                "id": request_id,
                "kind": "unhandled_exception",
                "level": "error",
                "method": method,
                "path": path,
                "client_ip": safe_client_ip(request),
                "latency_ms": elapsed_ms,
                "error": str(exc),
                "traceback": traceback.format_exc()[-5000:],
            }
            RECENT_ERRORS.appendleft(error_event)
            write_event(error_event)
            return JSONResponse({"ok": False, "error": "internal_server_error", "request_id": request_id}, status_code=500)

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        LATENCY_COUNT += 1
        LATENCY_TOTAL_MS += elapsed_ms
        LATENCY_MAX_MS = max(LATENCY_MAX_MS, elapsed_ms)
        STATUS_COUNTERS[str(status_code)] += 1
        PATH_COUNTERS[path] += 1
        METHOD_COUNTERS[method] += 1

        record = {
            "id": request_id,
            "kind": "request",
            "level": "warning" if elapsed_ms >= MONITORING_SLOW_MS or status_code >= 400 else "info",
            "method": method,
            "path": path,
            "status_code": status_code,
            "latency_ms": elapsed_ms,
            "client_ip": safe_client_ip(request),
            "user_agent": request.headers.get("user-agent", "")[:300],
        }
        RECENT_REQUESTS.appendleft(record)

        if REQUEST_LOG_ENABLED and (status_code >= 400 or elapsed_ms >= MONITORING_SLOW_MS or path.startswith("/api/")):
            write_event(record)
        if status_code >= 500:
            RECENT_ERRORS.appendleft(record)

        response.headers.setdefault("X-Request-ID", request_id)
        response.headers.setdefault("X-ClaimRadar-Monitoring", "enabled")
        return response
