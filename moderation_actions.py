from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import app as app_module
from auth_roles import auth_context_from_request, has_role

JsonRowsReader = Callable[[Path, int], List[Dict[str, Any]]]

MODERATION_ACTIONS_FILE = app_module.DATA_DIR / "moderation_actions.jsonl"
MODERATOR_NOTES_FILE = app_module.DATA_DIR / "moderator_notes.jsonl"
ABUSE_STATUS_FILE = app_module.DATA_DIR / "abuse_status.jsonl"
VISIBILITY_FILE = app_module.DATA_DIR / "visibility.jsonl"
ABUSE_FILE = app_module.DATA_DIR / "abuse_reports.jsonl"

VALID_ABUSE_STATUSES = {"new", "under_review", "reviewed", "dismissed", "action_taken"}


def _read_rows(read_jsonl: JsonRowsReader, path: Path, limit: int = 500) -> List[Dict[str, Any]]:
    try:
        rows = read_jsonl(path, limit=limit)
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def _extract_token(request: Request, payload: Optional[Dict[str, Any]] = None) -> str:
    payload = payload or {}
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return (
        str(payload.get("admin_key") or payload.get("api_key") or payload.get("auth_token") or "")
        or request.query_params.get("admin_key")
        or request.query_params.get("api_key")
        or request.query_params.get("auth_token")
        or request.headers.get("x-admin-key")
        or request.headers.get("x-api-key")
        or request.headers.get("x-claimradar-admin-key")
        or ""
    )


def _moderator_context(request: Request, payload: Optional[Dict[str, Any]], can_admin: Callable[[str], bool]) -> Dict[str, Any]:
    ctx = auth_context_from_request(request)
    if has_role(ctx, "moderator"):
        return {"allowed": True, "role": ctx.role, "subject": ctx.subject, "token_hash": ctx.token_hash, "source": ctx.source}
    token = _extract_token(request, payload)
    if token and can_admin(token):
        return {"allowed": True, "role": "admin", "subject": "legacy-admin-key", "token_hash": "legacy", "source": "admin_key"}
    return {"allowed": False, "role": ctx.role, "subject": ctx.subject, "token_hash": "", "source": ctx.source}


def _find_check(read_jsonl: JsonRowsReader, check_id: str) -> Optional[Dict[str, Any]]:
    for rec in _read_rows(read_jsonl, app_module.CHECKS_FILE, 5000):
        if rec.get("id") == check_id:
            return rec
    return None


def _find_abuse_report(read_jsonl: JsonRowsReader, report_id: str) -> Optional[Dict[str, Any]]:
    for rec in _read_rows(read_jsonl, ABUSE_FILE, 5000):
        if rec.get("id") == report_id:
            return rec
    return None


def _latest_abuse_status(read_jsonl: JsonRowsReader, report_id: str) -> str:
    for row in _read_rows(read_jsonl, ABUSE_STATUS_FILE, 5000):
        if row.get("report_id") == report_id:
            return str(row.get("status") or "new")
    return "new"


def _notes_for_check(read_jsonl: JsonRowsReader, check_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    return [row for row in _read_rows(read_jsonl, MODERATOR_NOTES_FILE, limit=1000) if row.get("check_id") == check_id][:limit]


def _actions_for_target(read_jsonl: JsonRowsReader, target_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    return [row for row in _read_rows(read_jsonl, MODERATION_ACTIONS_FILE, limit=1000) if row.get("target_id") == target_id][:limit]


def _append_action(action: str, target_type: str, target_id: str, payload: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    row = {
        "id": uuid.uuid4().hex[:12],
        "created_at": app_module.now_iso(),
        "type": "moderation_action",
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "actor_role": actor.get("role"),
        "actor_subject": actor.get("subject"),
        "actor_source": actor.get("source"),
        "reason": str(payload.get("reason") or "")[:500],
        "note": str(payload.get("note") or "")[:2000],
    }
    app_module.append_jsonl(MODERATION_ACTIONS_FILE, row)
    return row


def public_moderation_status(read_jsonl: JsonRowsReader, check_id: str) -> Dict[str, Any]:
    return {
        "check_id": check_id,
        "notes": _notes_for_check(read_jsonl, check_id, limit=50),
        "actions": _actions_for_target(read_jsonl, check_id, limit=50),
    }


def register_moderation_routes(app: FastAPI, can_admin: Callable[[str], bool], read_jsonl: JsonRowsReader) -> None:
    async def payload_and_actor(request: Request):
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        actor = _moderator_context(request, payload, can_admin)
        if not actor.get("allowed"):
            return payload, actor, JSONResponse({"ok": False, "error": "moderator_or_admin_required"}, status_code=403)
        return payload, actor, None

    @app.get("/api/moderation/actions")
    def api_moderation_actions(request: Request, limit: int = 100):
        actor = _moderator_context(request, None, can_admin)
        if not actor.get("allowed"):
            return JSONResponse({"ok": False, "error": "moderator_or_admin_required"}, status_code=403)
        rows = _read_rows(read_jsonl, MODERATION_ACTIONS_FILE, limit=max(1, min(limit, 500)))
        return JSONResponse({"ok": True, "actions": rows})

    @app.get("/api/moderation/check/{check_id}/notes")
    def api_check_notes(check_id: str, request: Request):
        actor = _moderator_context(request, None, can_admin)
        if not actor.get("allowed"):
            return JSONResponse({"ok": False, "error": "moderator_or_admin_required"}, status_code=403)
        return JSONResponse({"ok": True, "check_id": check_id, "notes": _notes_for_check(read_jsonl, check_id)})

    @app.get("/api/moderation/check/{check_id}/status")
    def api_check_moderation_status(check_id: str, request: Request):
        actor = _moderator_context(request, None, can_admin)
        if not actor.get("allowed"):
            return JSONResponse({"ok": False, "error": "moderator_or_admin_required"}, status_code=403)
        return JSONResponse({"ok": True, "moderation": public_moderation_status(read_jsonl, check_id)})

    @app.post("/api/moderation/check/{check_id}/hide")
    async def api_hide_check(check_id: str, request: Request):
        payload, actor, denied = await payload_and_actor(request)
        if denied:
            return denied
        if not _find_check(read_jsonl, check_id):
            return JSONResponse({"ok": False, "error": "check_not_found", "id": check_id}, status_code=404)
        visibility_event = {"id": check_id, "visibility": "private", "updated_at": app_module.now_iso(), "reason": str(payload.get("reason") or "moderation_hide")[:300]}
        app_module.append_jsonl(VISIBILITY_FILE, visibility_event)
        action = _append_action("hide_check", "check", check_id, payload, actor)
        return JSONResponse({"ok": True, "id": check_id, "visibility": "private", "action": action})

    @app.post("/api/moderation/check/{check_id}/restore")
    async def api_restore_check(check_id: str, request: Request):
        payload, actor, denied = await payload_and_actor(request)
        if denied:
            return denied
        if not _find_check(read_jsonl, check_id):
            return JSONResponse({"ok": False, "error": "check_not_found", "id": check_id}, status_code=404)
        visibility_event = {"id": check_id, "visibility": "public", "updated_at": app_module.now_iso(), "reason": str(payload.get("reason") or "moderation_restore")[:300]}
        app_module.append_jsonl(VISIBILITY_FILE, visibility_event)
        action = _append_action("restore_check", "check", check_id, payload, actor)
        return JSONResponse({"ok": True, "id": check_id, "visibility": "public", "action": action})

    @app.post("/api/moderation/check/{check_id}/note")
    async def api_add_check_note(check_id: str, request: Request):
        payload, actor, denied = await payload_and_actor(request)
        if denied:
            return denied
        if not _find_check(read_jsonl, check_id):
            return JSONResponse({"ok": False, "error": "check_not_found", "id": check_id}, status_code=404)
        note_text = str(payload.get("note") or "").strip()
        if not note_text:
            return JSONResponse({"ok": False, "error": "missing_note"}, status_code=400)
        note = {
            "id": uuid.uuid4().hex[:12],
            "created_at": app_module.now_iso(),
            "type": "moderator_note",
            "check_id": check_id,
            "note": note_text[:2000],
            "actor_role": actor.get("role"),
            "actor_subject": actor.get("subject"),
        }
        app_module.append_jsonl(MODERATOR_NOTES_FILE, note)
        action = _append_action("add_note", "check", check_id, payload, actor)
        return JSONResponse({"ok": True, "note": note, "action": action})

    @app.post("/api/moderation/abuse/{report_id}/review")
    async def api_review_abuse_report(report_id: str, request: Request):
        payload, actor, denied = await payload_and_actor(request)
        if denied:
            return denied
        report = _find_abuse_report(read_jsonl, report_id)
        if not report:
            return JSONResponse({"ok": False, "error": "report_not_found", "id": report_id}, status_code=404)
        status = str(payload.get("status") or "reviewed").lower().strip()
        if status not in VALID_ABUSE_STATUSES:
            return JSONResponse({"ok": False, "error": "invalid_status", "valid": sorted(VALID_ABUSE_STATUSES)}, status_code=400)
        row = {
            "id": uuid.uuid4().hex[:12],
            "created_at": app_module.now_iso(),
            "type": "abuse_status",
            "report_id": report_id,
            "check_id": report.get("check_id"),
            "status": status,
            "note": str(payload.get("note") or "")[:2000],
            "actor_role": actor.get("role"),
            "actor_subject": actor.get("subject"),
        }
        app_module.append_jsonl(ABUSE_STATUS_FILE, row)
        action = _append_action("review_abuse_report", "abuse_report", report_id, {**payload, "reason": status}, actor)
        return JSONResponse({"ok": True, "report_id": report_id, "status": status, "review": row, "action": action})

    @app.get("/api/moderation/abuse/{report_id}/status")
    def api_abuse_report_status(report_id: str, request: Request):
        actor = _moderator_context(request, None, can_admin)
        if not actor.get("allowed"):
            return JSONResponse({"ok": False, "error": "moderator_or_admin_required"}, status_code=403)
        return JSONResponse({"ok": True, "report_id": report_id, "status": _latest_abuse_status(read_jsonl, report_id)})
