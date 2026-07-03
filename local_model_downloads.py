from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from typing import Any, Dict

import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from local_ai_runtime import OLLAMA_BASE_URL

MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9_.:/@+-]{1,120}$")
DOWNLOADS: Dict[str, Dict[str, Any]] = {}
DOWNLOAD_LOCK = threading.Lock()


def _ollama_url(path: str) -> str:
    return f"{OLLAMA_BASE_URL.rstrip('/')}{path}"


def _update(download_id: str, **patch: Any) -> None:
    with DOWNLOAD_LOCK:
        item = DOWNLOADS.setdefault(download_id, {"id": download_id})
        item.update(patch)
        item["updated_at"] = time.time()


def _download_worker(download_id: str, model: str) -> None:
    _update(download_id, status="running", progress=1, model=model, events=[])
    try:
        response = requests.post(_ollama_url("/api/pull"), json={"model": model, "stream": True}, stream=True, timeout=1800)
        _update(download_id, http_status=response.status_code)
        if not response.ok:
            _update(download_id, status="failed", error=response.text[-1000:], progress=100)
            return
        last_status = ""
        completed = 0
        total = 0
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            last_status = str(payload.get("status") or last_status)
            completed = int(payload.get("completed") or completed or 0)
            total = int(payload.get("total") or total or 0)
            progress = min(99, max(1, int(completed * 100 / total))) if total else (75 if "success" in last_status.lower() else 10)
            _update(download_id, status="running", progress=progress, message=last_status, completed=completed, total=total, last_payload=payload)
        _update(download_id, status="done", progress=100, message=last_status or "download_complete", finished_at=time.time())
    except Exception as exc:
        _update(download_id, status="failed", progress=100, error=str(exc), finished_at=time.time())


def start_model_download(model: str) -> Dict[str, Any]:
    model = str(model or "").strip()
    if not MODEL_NAME_RE.match(model):
        return {"ok": False, "error": "invalid_model_name"}
    download_id = uuid.uuid4().hex[:12]
    with DOWNLOAD_LOCK:
        DOWNLOADS[download_id] = {"id": download_id, "model": model, "status": "queued", "progress": 0, "created_at": time.time(), "updated_at": time.time()}
    thread = threading.Thread(target=_download_worker, args=(download_id, model), daemon=True)
    thread.start()
    return {"ok": True, "download": DOWNLOADS[download_id]}


def get_model_download(download_id: str) -> Dict[str, Any] | None:
    with DOWNLOAD_LOCK:
        item = DOWNLOADS.get(download_id)
        return dict(item) if item else None


def list_model_downloads() -> Dict[str, Any]:
    with DOWNLOAD_LOCK:
        items = sorted((dict(v) for v in DOWNLOADS.values()), key=lambda x: x.get("updated_at", 0), reverse=True)
    return {"downloads": items[:100], "count": len(items)}


def register_model_download_routes(app: FastAPI) -> None:
    @app.post("/api/local-ai/ollama/download/start")
    async def api_start_model_download(request: Request):
        payload = await request.json()
        result = start_model_download(str((payload or {}).get("model", "")))
        return JSONResponse(result, status_code=200 if result.get("ok") else 400)

    @app.get("/api/local-ai/ollama/downloads")
    def api_model_downloads():
        return JSONResponse({"ok": True, **list_model_downloads()})

    @app.get("/api/local-ai/ollama/downloads/{download_id}")
    def api_model_download(download_id: str):
        item = get_model_download(download_id)
        if not item:
            return JSONResponse({"ok": False, "error": "download_not_found"}, status_code=404)
        return JSONResponse({"ok": True, "download": item})
