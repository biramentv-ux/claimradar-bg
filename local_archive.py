from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from local_storage_sqlite import local_sqlite_store

LOCAL_ARCHIVE_ENABLED = os.getenv("LOCAL_ARCHIVE_ENABLED", "1").lower() not in {"0", "false", "no"}
LOCAL_ARCHIVE_CHUNK_CHARS = int(os.getenv("LOCAL_ARCHIVE_CHUNK_CHARS", "1200"))
LOCAL_ARCHIVE_CHUNK_OVERLAP = int(os.getenv("LOCAL_ARCHIVE_CHUNK_OVERLAP", "160"))
LOCAL_ARCHIVE_MAX_TEXT_CHARS = int(os.getenv("LOCAL_ARCHIVE_MAX_TEXT_CHARS", "1000000"))


def chunk_text(text: str, size: int = LOCAL_ARCHIVE_CHUNK_CHARS, overlap: int = LOCAL_ARCHIVE_CHUNK_OVERLAP) -> List[str]:
    text = " ".join(str(text or "").split())[:LOCAL_ARCHIVE_MAX_TEXT_CHARS]
    if not text:
        return []
    chunks: List[str] = []
    step = max(200, size - max(0, overlap))
    for start in range(0, len(text), step):
        piece = text[start : start + size].strip()
        if piece:
            chunks.append(piece)
        if start + size >= len(text):
            break
    return chunks


def import_text_to_archive(title: str, text: str, source_type: str = "text", path: str = "", metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
    source = local_sqlite_store.save_source(title=title or "Untitled local source", content_text=text[:LOCAL_ARCHIVE_MAX_TEXT_CHARS], source_type=source_type, path=path, metadata=metadata or {})
    chunks = chunk_text(text)
    saved = [local_sqlite_store.save_chunk(source["id"], idx, chunk, metadata={"title": title, "source_type": source_type}) for idx, chunk in enumerate(chunks)]
    return {"source": source, "chunks_created": len(saved)}


def search_archive(query: str, limit: int = 20) -> Dict[str, Any]:
    rows = local_sqlite_store.search_chunks(query, limit=limit)
    evidence = []
    for row in rows:
        evidence.append({
            "source_id": row.get("source_id"),
            "source_title": row.get("source_title"),
            "source_type": row.get("source_type"),
            "chunk_id": row.get("id"),
            "chunk_index": row.get("chunk_index"),
            "text": row.get("text"),
            "metadata": row.get("metadata", {}),
        })
    return {"query": query, "count": len(evidence), "evidence": evidence}


async def _import_upload(request: Request) -> Dict[str, Any]:
    form = await request.form()
    upload = form.get("file")
    title = str(form.get("title") or getattr(upload, "filename", "uploaded-source") or "uploaded-source")
    if upload is None or not hasattr(upload, "read"):
        return {"ok": False, "error": "missing_file"}
    data = await upload.read()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("cp1251", errors="ignore")
    imported = import_text_to_archive(title=title, text=text, source_type="file", path=getattr(upload, "filename", ""), metadata={"size_bytes": len(data)})
    return {"ok": True, "imported": imported}


def register_local_archive_routes(app: FastAPI) -> None:
    @app.get("/api/local-ai/archive/status")
    def api_archive_status():
        return JSONResponse({"ok": True, "archive": {"enabled": LOCAL_ARCHIVE_ENABLED, "db": local_sqlite_store.status()}})

    @app.get("/api/local-ai/archive/sources")
    def api_archive_sources(limit: int = 100):
        return JSONResponse({"ok": True, "sources": local_sqlite_store.list_sources(limit=limit)})

    @app.post("/api/local-ai/archive/import-text")
    async def api_archive_import_text(request: Request):
        payload = await request.json()
        if not isinstance(payload, dict):
            return JSONResponse({"ok": False, "error": "invalid_payload"}, status_code=400)
        imported = import_text_to_archive(str(payload.get("title") or "Untitled"), str(payload.get("text") or ""), source_type=str(payload.get("source_type") or "text"), metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {})
        return JSONResponse({"ok": True, "imported": imported})

    @app.post("/api/local-ai/archive/import-file")
    async def api_archive_import_file(request: Request):
        result = await _import_upload(request)
        return JSONResponse(result, status_code=200 if result.get("ok") else 400)

    @app.post("/api/local-ai/archive/search")
    async def api_archive_search_post(request: Request):
        payload = await request.json()
        result = search_archive(str((payload or {}).get("query", "")), limit=int((payload or {}).get("limit", 20)))
        return JSONResponse({"ok": True, "archive": result})

    @app.get("/api/local-ai/archive/search")
    def api_archive_search_get(q: str = "", limit: int = 20):
        return JSONResponse({"ok": True, "archive": search_archive(q, limit=limit)})
