from __future__ import annotations

import os
from typing import Any, Dict, List

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from local_archive import search_archive
from search_providers import active_search_config, enhanced_search_web

EVIDENCE_MODE = os.getenv("EVIDENCE_MODE", os.getenv("LOCAL_AI_MODE", "offline")).strip().lower()
EVIDENCE_WEB_LIMIT = int(os.getenv("EVIDENCE_WEB_LIMIT", "5"))
EVIDENCE_LOCAL_LIMIT = int(os.getenv("EVIDENCE_LOCAL_LIMIT", "8"))
VALID_EVIDENCE_MODES = {"offline", "online_evidence", "hybrid"}


def normalized_evidence_mode(mode: str | None = None) -> str:
    selected = (mode or EVIDENCE_MODE or "offline").strip().lower().replace("-", "_")
    if selected in {"online", "web"}:
        return "online_evidence"
    if selected not in VALID_EVIDENCE_MODES:
        return "offline"
    return selected


def _local_results(query: str, limit: int) -> List[Dict[str, Any]]:
    local = search_archive(query, limit=limit)
    out = []
    for item in local.get("evidence", []):
        out.append({"kind": "local_archive", "title": item.get("source_title"), "url": "local://" + str(item.get("chunk_id")), "snippet": item.get("text"), "raw": item})
    return out


def _web_results(query: str, limit: int) -> List[Dict[str, Any]]:
    return [{"kind": "web", **item} for item in enhanced_search_web(query, limit=limit)]


def evidence_search(query: str, mode: str | None = None, local_limit: int = EVIDENCE_LOCAL_LIMIT, web_limit: int = EVIDENCE_WEB_LIMIT) -> Dict[str, Any]:
    selected = normalized_evidence_mode(mode)
    query = str(query or "").strip()
    local_results: List[Dict[str, Any]] = []
    web_results: List[Dict[str, Any]] = []
    if not query:
        return {"mode": selected, "query": query, "results": [], "local": [], "web": [], "search_config": active_search_config()}
    if selected in {"offline", "hybrid", "online_evidence"}:
        local_results = _local_results(query, limit=local_limit)
    if selected in {"online_evidence", "hybrid"}:
        web_results = _web_results(query, limit=web_limit)
    if selected == "offline":
        merged = local_results
    elif selected == "online_evidence":
        merged = [*web_results, *local_results]
    else:
        merged = [*local_results, *web_results]
    return {"mode": selected, "query": query, "results": merged, "local": local_results, "web": web_results, "search_config": active_search_config()}


def register_local_evidence_routes(app: FastAPI) -> None:
    @app.get("/api/local-ai/evidence/status")
    def api_evidence_status():
        return JSONResponse({"ok": True, "evidence": {"mode": normalized_evidence_mode(), "search_config": active_search_config()}})

    @app.get("/api/local-ai/evidence/search")
    def api_evidence_search_get(q: str = "", mode: str = ""):
        return JSONResponse({"ok": True, "evidence": evidence_search(q, mode=mode or None)})

    @app.post("/api/local-ai/evidence/search")
    async def api_evidence_search_post(request: Request):
        payload = await request.json()
        if not isinstance(payload, dict):
            return JSONResponse({"ok": False, "error": "invalid_payload"}, status_code=400)
        return JSONResponse({"ok": True, "evidence": evidence_search(str(payload.get("query", "")), mode=payload.get("mode"))})
