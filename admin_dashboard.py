from __future__ import annotations

import os
import platform
import time
from html import escape
from pathlib import Path
from typing import Any, Callable, Dict, List

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

import app as app_module
from auth_roles import auth_context_from_request, has_role
from custom_domain import custom_domain_config
from monitoring import public_metrics, read_events
from rate_limit_api import rate_limit_status
from security_jobs import security_status

JsonRowsReader = Callable[[Path, int], List[Dict[str, Any]]]


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_rows(read_jsonl: JsonRowsReader, path: Path, limit: int) -> List[Dict[str, Any]]:
    try:
        rows = read_jsonl(path, limit=limit)
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def _safe_storage_status(storage: Any) -> Dict[str, Any]:
    try:
        return storage.status()
    except Exception as exc:
        return {"enabled": False, "configured": False, "connected": False, "error": str(exc), "tables": {}}


def _safe_list_from_storage(storage: Any, method_name: str, limit: int) -> List[Dict[str, Any]] | None:
    if not getattr(storage, "configured", False):
        return None
    try:
        method = getattr(storage, method_name)
        rows = method(limit=limit)
        return rows if isinstance(rows, list) else []
    except Exception:
        return None


def _mask_text(value: Any, max_chars: int = 220) -> str:
    text = str(value or "").strip().replace("\n", " ")
    return text[:max_chars] + ("…" if len(text) > max_chars else "")


def _check_title(row: Dict[str, Any]) -> str:
    return _mask_text(row.get("title") or row.get("claim") or row.get("text_preview") or row.get("text") or row.get("id"), 140)


def _admin_allowed(request: Request, can_admin: Callable[[str], bool]) -> bool:
    ctx = auth_context_from_request(request)
    if has_role(ctx, "admin"):
        return True
    token = (
        request.query_params.get("admin_key")
        or request.query_params.get("api_key")
        or request.query_params.get("auth_token")
        or request.headers.get("x-admin-key")
        or request.headers.get("x-api-key")
        or ""
    )
    return bool(token and can_admin(str(token)))


def _admin_denied_html() -> str:
    return """<!doctype html><html lang="bg"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Admin required · ClaimRadar BG</title><style>body{margin:0;background:#020617;color:#e5e7eb;font-family:Arial,sans-serif}main{max-width:780px;margin:8vh auto;padding:24px}.card{border:1px solid rgba(248,113,113,.35);border-radius:24px;background:rgba(127,29,29,.18);padding:24px}code{background:rgba(15,23,42,.85);padding:2px 6px;border-radius:8px;color:#fecaca}</style></head><body><main><section class="card"><h1>403 · Admin достъп</h1><p>Тази страница изисква валиден <code>admin</code> или <code>owner</code> ключ.</p><p>Отвори с <code>/admin?admin_key=...</code> или използвай <code>Authorization: Bearer ...</code> към JSON endpoint-ите.</p></section></main></body></html>"""


def collect_admin_status(storage: Any, job_store: Any, read_jsonl: JsonRowsReader) -> Dict[str, Any]:
    db = _safe_storage_status(storage)
    checks_rows = _safe_list_from_storage(storage, "list_checks", 10)
    if checks_rows is None:
        checks_rows = _read_rows(read_jsonl, app_module.CHECKS_FILE, 10)
    abuse_rows = _safe_list_from_storage(storage, "list_abuse", 10)
    if abuse_rows is None:
        abuse_rows = _read_rows(read_jsonl, Path("data/abuse_reports.jsonl"), 10)
    feedback_rows = _safe_list_from_storage(storage, "list_feedback", 10)
    if feedback_rows is None:
        feedback_rows = _read_rows(read_jsonl, app_module.FEEDBACK_FILE, 10)

    jobs_stats = {}
    recent_jobs = []
    try:
        jobs_stats = job_store.stats()
        recent_jobs = job_store.recent(limit=10)
    except Exception as exc:
        jobs_stats = {"error": str(exc)}

    metrics = public_metrics()
    return {
        "generated_at": _now_iso(),
        "app": {
            "name": "ClaimRadar BG",
            "public_base_url": getattr(app_module, "PUBLIC_BASE_URL", os.getenv("PUBLIC_BASE_URL", "")),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "pid": os.getpid(),
        },
        "storage": "postgres" if db.get("connected") else "jsonl_fallback",
        "db": db,
        "auth": {
            "enabled": os.getenv("AUTH_ENABLED", "1"),
            "admin_roles": ["admin", "owner"],
        },
        "security": security_status(),
        "rate_limit": rate_limit_status(),
        "monitoring": metrics,
        "jobs": jobs_stats,
        "custom_domain": custom_domain_config(),
        "counts": {
            "recent_checks_returned": len(checks_rows),
            "recent_abuse_reports_returned": len(abuse_rows),
            "recent_feedback_returned": len(feedback_rows),
            "recent_jobs_returned": len(recent_jobs),
        },
        "recent": {
            "checks": checks_rows,
            "abuse_reports": abuse_rows,
            "feedback": feedback_rows,
            "jobs": recent_jobs,
        },
        "links": {
            "product": "/product",
            "jobs": "/jobs",
            "auth_status": "/auth/status",
            "db_status": "/db/status",
            "monitoring_status": "/monitoring/status",
            "monitoring_metrics": "/monitoring/metrics",
            "rate_limit_status": "/rate-limit/status",
            "custom_domain": "/custom-domain",
            "search_status": "/search/status",
            "health": "/health",
        },
    }


def admin_html(status: Dict[str, Any], admin_key: str = "") -> str:
    db = status.get("db", {})
    monitoring = status.get("monitoring", {})
    jobs = status.get("jobs", {})
    rate = status.get("rate_limit", {})
    recent = status.get("recent", {})
    q = f"?admin_key={escape(admin_key)}" if admin_key else ""

    def stat_card(title: str, value: Any, hint: str = "") -> str:
        return f"<div class='card'><div class='muted'>{escape(title)}</div><div class='big'>{escape(str(value))}</div><div class='hint'>{escape(hint)}</div></div>"

    def rows_table(items: List[Dict[str, Any]], kind: str) -> str:
        if not items:
            return "<p class='muted'>Няма записи за показване.</p>"
        rows = []
        for item in items[:12]:
            if kind == "checks":
                title = _check_title(item)
                meta = f"id={item.get('id','')} · visibility={item.get('visibility','public')}"
                link = f"/check/{escape(str(item.get('id','')))}" if item.get("id") else "#"
                rows.append(f"<tr><td><a href='{link}'>{escape(title)}</a></td><td>{escape(meta)}</td></tr>")
            elif kind == "jobs":
                title = str(item.get("type", "job"))
                meta = f"{item.get('status','')} · {item.get('progress',0)}% · {item.get('id','')}"
                rows.append(f"<tr><td>{escape(title)}</td><td>{escape(meta)}</td></tr>")
            else:
                title = _mask_text(item.get("reason") or item.get("kind") or item.get("comment") or item.get("details") or item.get("id"), 120)
                meta = _mask_text(item.get("check_id") or item.get("page") or item.get("email") or item.get("created_at"), 160)
                rows.append(f"<tr><td>{escape(title)}</td><td>{escape(meta)}</td></tr>")
        return "<table><tbody>" + "".join(rows) + "</tbody></table>"

    cards = "".join([
        stat_card("Storage", status.get("storage"), "Postgres ако DATABASE_URL е активен"),
        stat_card("DB connected", db.get("connected"), f"tables: {len(db.get('tables', {}) or {})}"),
        stat_card("Requests", monitoring.get("requests_total", 0), f"errors: {monitoring.get('errors_total', 0)}"),
        stat_card("Latency p/avg", f"{monitoring.get('avg_latency_ms', 0)} ms", f"max: {monitoring.get('max_latency_ms', 0)} ms"),
        stat_card("Jobs", jobs.get("total", 0), f"running: {jobs.get('running', 0)} · failed: {jobs.get('failed', 0)}"),
        stat_card("Rate limit", "enabled" if rate.get("enabled") else "disabled", f"rejected: {rate.get('rejected_total', 0)}"),
    ])

    links = status.get("links", {})
    link_buttons = "".join([f"<a class='button' href='{escape(url)}{q}'>{escape(name.replace('_',' ').title())}</a>" for name, url in links.items()])

    return f"""<!doctype html>
<html lang="bg">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Admin Dashboard · ClaimRadar BG</title>
  <style>
    body{{margin:0;background:#020617;color:#e5e7eb;font-family:Arial,sans-serif}}main{{max-width:1220px;margin:auto;padding:28px 18px 70px}}.hero,.card,.panel{{border:1px solid rgba(34,211,238,.24);border-radius:24px;background:linear-gradient(135deg,rgba(2,6,23,.96),rgba(30,27,75,.72));box-shadow:0 0 34px rgba(34,211,238,.14)}}.hero{{padding:30px}}.kicker{{color:#67e8f9;text-transform:uppercase;letter-spacing:.16em;font-weight:900;font-size:12px}}h1{{font-size:48px;margin:10px 0;color:#fff}}h2{{color:#fff;margin:0 0 12px}}p,td{{color:#cbd5e1;line-height:1.55}}.muted{{color:#94a3b8;font-size:13px;text-transform:uppercase;letter-spacing:.07em}}.hint{{color:#94a3b8;font-size:13px;margin-top:6px}}.big{{font-size:28px;font-weight:900;color:#fff;margin-top:8px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-top:18px}}.card{{padding:18px}}.panel{{padding:18px;margin-top:18px}}.actions{{display:flex;flex-wrap:wrap;gap:9px;margin-top:18px}}a{{color:#67e8f9}}a.button{{border:1px solid rgba(34,211,238,.28);background:rgba(15,23,42,.78);color:#e0f2fe;border-radius:13px;padding:10px 12px;text-decoration:none;font-weight:700}}a.primary{{border:0;background:linear-gradient(90deg,#0891b2,#7c3aed);color:#fff}}table{{width:100%;border-collapse:collapse}}td{{border-top:1px solid rgba(148,163,184,.18);padding:10px 8px;vertical-align:top}}code,pre{{background:rgba(15,23,42,.78);border:1px solid rgba(34,211,238,.18);border-radius:12px;color:#e0f2fe}}code{{padding:2px 6px}}pre{{padding:14px;overflow:auto;max-height:360px}}.two{{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:16px}}
  </style>
</head>
<body><main>
  <section class="hero"><div class="kicker">ClaimRadar BG · admin</div><h1>Admin Dashboard</h1><p>Централен панел за статус, jobs, reports, checks, monitoring, rate limits, auth и database. Генерирано: <code>{escape(str(status.get('generated_at')))}</code></p><div class="actions"><a class="button primary" href="/api/admin/status{q}">JSON status</a>{link_buttons}</div></section>
  <section class="grid">{cards}</section>
  <section class="two"><div class="panel"><h2>Последни проверки</h2>{rows_table(recent.get('checks', []), 'checks')}</div><div class="panel"><h2>Последни jobs</h2>{rows_table(recent.get('jobs', []), 'jobs')}</div></section>
  <section class="two"><div class="panel"><h2>Abuse reports</h2>{rows_table(recent.get('abuse_reports', []), 'abuse')}</div><div class="panel"><h2>Feedback</h2>{rows_table(recent.get('feedback', []), 'feedback')}</div></section>
  <section class="panel"><h2>System summary</h2><pre>{escape(str({'storage': status.get('storage'), 'db': db, 'jobs': jobs, 'rate_limit': {k: rate.get(k) for k in ['enabled','active_bucket_count','banned_count','rejected_total']}}))}</pre></section>
</main></body></html>"""


def register_admin_dashboard_routes(
    app: FastAPI,
    can_admin: Callable[[str], bool],
    storage: Any,
    job_store: Any,
    read_jsonl: JsonRowsReader,
) -> None:
    def build_status() -> Dict[str, Any]:
        return collect_admin_status(storage, job_store, read_jsonl)

    @app.get("/admin", response_class=HTMLResponse)
    def admin_page(request: Request):
        if not _admin_allowed(request, can_admin):
            return HTMLResponse(_admin_denied_html(), status_code=403)
        status = build_status()
        return HTMLResponse(admin_html(status, admin_key=request.query_params.get("admin_key", "")))

    @app.get("/api/admin/status")
    def api_admin_status(request: Request):
        if not _admin_allowed(request, can_admin):
            return JSONResponse({"ok": False, "error": "invalid_admin_key"}, status_code=403)
        return JSONResponse({"ok": True, "admin": build_status()})

    @app.get("/api/admin/system")
    def api_admin_system(request: Request):
        if not _admin_allowed(request, can_admin):
            return JSONResponse({"ok": False, "error": "invalid_admin_key"}, status_code=403)
        status = build_status()
        return JSONResponse({
            "ok": True,
            "system": {
                "generated_at": status["generated_at"],
                "app": status["app"],
                "storage": status["storage"],
                "db": status["db"],
                "security": status["security"],
                "rate_limit": status["rate_limit"],
                "monitoring": status["monitoring"],
                "custom_domain": status["custom_domain"],
            },
        })

    @app.get("/api/admin/abuse-reports")
    def api_admin_abuse_reports(request: Request, limit: int = 50):
        if not _admin_allowed(request, can_admin):
            return JSONResponse({"ok": False, "error": "invalid_admin_key"}, status_code=403)
        rows = _safe_list_from_storage(storage, "list_abuse", limit)
        if rows is None:
            rows = _read_rows(read_jsonl, Path("data/abuse_reports.jsonl"), limit)
        return JSONResponse({"ok": True, "abuse_reports": rows[: max(1, min(limit, 200))]})

    @app.get("/api/admin/recent-checks")
    def api_admin_recent_checks(request: Request, limit: int = 50):
        if not _admin_allowed(request, can_admin):
            return JSONResponse({"ok": False, "error": "invalid_admin_key"}, status_code=403)
        rows = _safe_list_from_storage(storage, "list_checks", limit)
        if rows is None:
            rows = _read_rows(read_jsonl, app_module.CHECKS_FILE, limit)
        return JSONResponse({"ok": True, "checks": rows[: max(1, min(limit, 200))]})

    @app.get("/api/admin/logs")
    def api_admin_logs(request: Request, limit: int = 100, level: str = ""):
        if not _admin_allowed(request, can_admin):
            return JSONResponse({"ok": False, "error": "invalid_admin_key"}, status_code=403)
        return JSONResponse({"ok": True, "events": read_events(limit=max(1, min(limit, 500)), level=level)})
