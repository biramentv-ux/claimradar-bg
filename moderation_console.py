from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Callable, Dict, List

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

import app as app_module
from auth_roles import auth_context_from_request, has_role
from moderation_actions import ABUSE_FILE, ABUSE_STATUS_FILE, MODERATION_ACTIONS_FILE, MODERATOR_NOTES_FILE

JsonRowsReader = Callable[[Path, int], List[Dict[str, Any]]]


def _read_rows(read_jsonl: JsonRowsReader, path: Path, limit: int = 100) -> List[Dict[str, Any]]:
    try:
        rows = read_jsonl(path, limit=limit)
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def _token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return request.query_params.get("admin_key") or request.query_params.get("api_key") or request.headers.get("x-admin-key") or request.headers.get("x-api-key") or ""


def _allowed(request: Request, can_admin: Callable[[str], bool]) -> bool:
    ctx = auth_context_from_request(request)
    return has_role(ctx, "moderator") or bool(_token(request) and can_admin(_token(request)))


def _denied() -> str:
    return """<!doctype html><html lang='bg'><head><meta charset='utf-8'><title>403 · Moderation</title><style>body{background:#020617;color:#e5e7eb;font-family:Arial,sans-serif}main{max-width:760px;margin:10vh auto;padding:24px}.card{border:1px solid #7f1d1d;background:#2b1111;border-radius:20px;padding:20px}code{background:#111827;padding:2px 6px;border-radius:8px}</style></head><body><main><section class='card'><h1>403 · Moderation</h1><p>Нужен е moderator, admin или owner ключ.</p><p>Отвори с <code>/admin/moderation?admin_key=...</code>.</p></section></main></body></html>"""


def _latest_status(rows: List[Dict[str, Any]], report_id: str) -> str:
    for row in rows:
        if row.get("report_id") == report_id:
            return str(row.get("status") or "new")
    return "new"


def _short(value: Any, n: int = 120) -> str:
    text = str(value or "").replace("\n", " ").strip()
    return text[:n] + ("…" if len(text) > n else "")


def moderation_payload(read_jsonl: JsonRowsReader) -> Dict[str, Any]:
    return {
        "checks": _read_rows(read_jsonl, app_module.CHECKS_FILE, 20),
        "reports": _read_rows(read_jsonl, ABUSE_FILE, 20),
        "report_status": _read_rows(read_jsonl, ABUSE_STATUS_FILE, 100),
        "actions": _read_rows(read_jsonl, MODERATION_ACTIONS_FILE, 50),
        "notes": _read_rows(read_jsonl, MODERATOR_NOTES_FILE, 50),
    }


def moderation_html(data: Dict[str, Any], admin_key: str = "") -> str:
    key_js = repr(admin_key or "")
    checks_rows = []
    for row in data.get("checks", [])[:20]:
        check_id = str(row.get("id") or "")
        checks_rows.append(f"<tr><td><a href='/check/{escape(check_id)}' target='_blank'>{escape(_short(row.get('title') or row.get('text_preview')))}</a><div class='mini'>id={escape(check_id)} · visibility={escape(str(row.get('visibility','public')))}</div></td><td><button onclick=\"act('/api/moderation/check/{escape(check_id)}/hide')\">Hide</button><button onclick=\"act('/api/moderation/check/{escape(check_id)}/restore')\">Restore</button><button onclick=\"note('{escape(check_id)}')\">Note</button><a class='button' href='/export/check/{escape(check_id)}.pdf' target='_blank'>PDF</a><a class='button' href='/export/check/{escape(check_id)}.md' target='_blank'>MD</a></td></tr>")
    report_status = data.get("report_status", [])
    report_rows = []
    for row in data.get("reports", [])[:20]:
        report_id = str(row.get("id") or "")
        status = _latest_status(report_status, report_id)
        report_rows.append(f"<tr><td>{escape(_short(row.get('reason') or row.get('details')))}<div class='mini'>id={escape(report_id)} · status={escape(status)} · check={escape(str(row.get('check_id','')))}</div></td><td><button onclick=\"review('{escape(report_id)}','under_review')\">Under review</button><button onclick=\"review('{escape(report_id)}','reviewed')\">Reviewed</button><button onclick=\"review('{escape(report_id)}','dismissed')\">Dismiss</button><button onclick=\"review('{escape(report_id)}','action_taken')\">Action taken</button></td></tr>")
    action_rows = "".join([f"<tr><td>{escape(str(row.get('action','')))}</td><td>{escape(_short(row.get('target_id') or row.get('note') or row.get('reason')))}</td></tr>" for row in data.get("actions", [])[:20]])
    note_rows = "".join([f"<tr><td>{escape(str(row.get('check_id','')))}</td><td>{escape(_short(row.get('note'), 180))}</td></tr>" for row in data.get("notes", [])[:20]])
    return f"""<!doctype html><html lang='bg'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Moderation Console · ClaimRadar BG</title><style>body{{margin:0;background:#020617;color:#e5e7eb;font-family:Arial,sans-serif}}main{{max-width:1180px;margin:auto;padding:28px 18px 70px}}.hero,.panel{{border:1px solid rgba(34,211,238,.24);border-radius:24px;background:linear-gradient(135deg,rgba(2,6,23,.96),rgba(30,27,75,.72));padding:22px;margin:16px 0}}h1{{font-size:44px;margin:8px 0;color:#fff}}h2{{color:#fff}}p,td{{color:#cbd5e1}}table{{width:100%;border-collapse:collapse}}td{{border-top:1px solid rgba(148,163,184,.18);padding:10px;vertical-align:top}}button,a.button{{border:1px solid rgba(34,211,238,.28);background:rgba(15,23,42,.78);color:#e0f2fe;border-radius:10px;padding:8px 10px;text-decoration:none;font-weight:700;margin:3px;cursor:pointer}}.mini{{color:#94a3b8;font-size:12px;margin-top:4px}}.actions{{display:flex;gap:8px;flex-wrap:wrap}}</style></head><body><main><section class='hero'><div class='mini'>ClaimRadar BG · moderation</div><h1>Moderation Console</h1><p>Hide/restore public check, mark reports reviewed, add moderator notes, export PDF/Markdown reports.</p><div class='actions'><a class='button' href='/admin?admin_key={escape(admin_key)}'>Admin</a><a class='button' href='/api/moderation/actions?admin_key={escape(admin_key)}'>Actions JSON</a><a class='button' href='/api/admin/status?admin_key={escape(admin_key)}'>Admin JSON</a></div></section><section class='panel'><h2>Checks</h2><table>{''.join(checks_rows) or '<tr><td>Няма проверки.</td></tr>'}</table></section><section class='panel'><h2>Reports</h2><table>{''.join(report_rows) or '<tr><td>Няма reports.</td></tr>'}</table></section><section class='panel'><h2>Recent moderation actions</h2><table>{action_rows or '<tr><td>Няма actions.</td></tr>'}</table></section><section class='panel'><h2>Moderator notes</h2><table>{note_rows or '<tr><td>Няма notes.</td></tr>'}</table></section></main><script>const ADMIN_KEY={key_js};async function postJson(url,payload){{payload=payload||{{}};if(ADMIN_KEY)payload.admin_key=ADMIN_KEY;const res=await fetch(url,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload)}});const data=await res.json().catch(()=>({{ok:false,error:'bad_json'}}));alert(data.ok?'Готово':'Грешка: '+(data.error||'unknown'));if(data.ok)location.reload();}}function act(url){{const reason=prompt('Причина:')||'';postJson(url,{{reason}})}}function note(checkId){{const note=prompt('Moderator note:');if(note)postJson('/api/moderation/check/'+encodeURIComponent(checkId)+'/note',{{note}})}}function review(reportId,status){{const note=prompt('Бележка:')||'';postJson('/api/moderation/abuse/'+encodeURIComponent(reportId)+'/review',{{status,note}})}}</script></body></html>"""


def register_moderation_console_routes(app: FastAPI, can_admin: Callable[[str], bool], read_jsonl: JsonRowsReader) -> None:
    @app.get("/admin/moderation", response_class=HTMLResponse)
    def admin_moderation_page(request: Request):
        if not _allowed(request, can_admin):
            return HTMLResponse(_denied(), status_code=403)
        return HTMLResponse(moderation_html(moderation_payload(read_jsonl), admin_key=request.query_params.get("admin_key", "")))

    @app.get("/api/admin/moderation")
    def admin_moderation_json(request: Request):
        if not _allowed(request, can_admin):
            return JSONResponse({"ok": False, "error": "moderator_or_admin_required"}, status_code=403)
        return JSONResponse({"ok": True, "moderation": moderation_payload(read_jsonl)})
