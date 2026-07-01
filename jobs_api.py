from __future__ import annotations

import html
from typing import Any, Callable, Dict

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

JobFn = Callable[[Dict[str, Any]], Dict[str, Any]]


def register_job_routes(
    app: FastAPI,
    job_store: Any,
    can_admin: Callable[[str], bool],
    run_check_job: JobFn,
    run_ai_verdict_job: JobFn,
    run_real_check_job: JobFn,
) -> None:
    """Register production-style background job routes on the provided FastAPI app.

    Routes intentionally live outside Gradio so long-running checks can be started,
    monitored, cancelled, retried and cleaned up without blocking the UI.
    """

    job_fns: Dict[str, JobFn] = {
        "check": run_check_job,
        "ai_verdict": run_ai_verdict_job,
        "real_check": run_real_check_job,
    }

    def fn_for_type(job_type: str) -> JobFn | None:
        return job_fns.get(job_type)

    async def parse_payload(request: Request) -> Dict[str, Any]:
        try:
            data = await request.json()
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def require_admin(payload: Dict[str, Any]) -> JSONResponse | None:
        if not can_admin(str(payload.get("admin_key", ""))):
            return JSONResponse({"ok": False, "error": "invalid_admin_key"}, status_code=403)
        return None

    def create_job_response(job: Dict[str, Any]) -> JSONResponse:
        job_id = job["id"]
        return JSONResponse(
            {
                "ok": True,
                "job_id": job_id,
                "job": job,
                "status_url": f"/api/jobs/{job_id}",
                "cancel_url": f"/api/jobs/{job_id}/cancel",
                "retry_url": f"/api/jobs/{job_id}/retry",
            }
        )

    def jobs_page_html() -> str:
        return """<!doctype html>
<html lang="bg">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ClaimRadar BG · Jobs</title>
  <style>
    body{margin:0;background:#020617;color:#e5e7eb;font-family:Arial,sans-serif}main{max-width:1180px;margin:auto;padding:28px 18px}.hero,.card{border:1px solid rgba(34,211,238,.24);border-radius:22px;background:linear-gradient(135deg,rgba(2,6,23,.95),rgba(30,27,75,.75));box-shadow:0 0 32px rgba(34,211,238,.14)}.hero{padding:28px}.kicker{color:#67e8f9;letter-spacing:.16em;text-transform:uppercase;font-size:12px;font-weight:900}h1{font-size:48px;margin:10px 0;color:#fff}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin-top:18px}.card{padding:16px}.muted{color:#94a3b8}.jobs{display:grid;gap:10px;margin-top:18px}.job{border:1px solid rgba(34,211,238,.18);border-radius:16px;background:rgba(15,23,42,.75);padding:13px}.pill{display:inline-flex;margin:3px;padding:5px 9px;border-radius:999px;border:1px solid rgba(34,211,238,.24);color:#cffafe;background:rgba(8,145,178,.14);font-size:12px}button,a{border:1px solid rgba(34,211,238,.28);background:rgba(15,23,42,.8);color:#e0f2fe;border-radius:12px;padding:9px 11px;text-decoration:none;cursor:pointer}.primary{border:0;background:linear-gradient(90deg,#0891b2,#7c3aed);color:#fff}.danger{border-color:rgba(248,113,113,.45);color:#fecaca}.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}pre{white-space:pre-wrap;background:rgba(2,6,23,.55);border-radius:12px;padding:10px;color:#cbd5e1;max-height:220px;overflow:auto}.bar{height:7px;background:rgba(148,163,184,.18);border-radius:99px;overflow:hidden;margin:9px 0}.bar span{display:block;height:100%;background:linear-gradient(90deg,#22d3ee,#a855f7)}
  </style>
</head>
<body>
<main>
<section class="hero"><div class="kicker">ClaimRadar BG · Background jobs</div><h1>Jobs Dashboard</h1><p class="muted">Следи background tasks, retry/cancel с ADMIN_KEY и виж статистика без да блокираш основния интерфейс.</p><div class="actions"><button class="primary" onclick="loadJobs()">Refresh</button><button onclick="createDemoJob()">Demo check job</button><button onclick="loadStats()">Stats</button><a href="/product">Product</a></div></section>
<section class="grid" id="stats"></section><section class="jobs" id="jobs"></section>
</main>
<script>
async function loadStats(){const r=await fetch('/api/jobs/stats');const d=await r.json();document.getElementById('stats').innerHTML=Object.entries(d.stats||{}).slice(0,10).map(([k,v])=>`<div class="card"><b>${k}</b><pre>${JSON.stringify(v,null,2)}</pre></div>`).join('')}
async function loadJobs(){const r=await fetch('/api/jobs?limit=25');const d=await r.json();document.getElementById('jobs').innerHTML=(d.jobs||[]).map(j=>`<div class="job"><span class="pill">${j.id}</span><span class="pill">${j.type}</span><span class="pill">${j.status}</span><span class="pill">${j.progress||0}%</span><div class="bar"><span style="width:${j.progress||0}%"></span></div><div class="muted">attempt ${j.attempt||1} · updated ${new Date((j.updated_at||0)*1000).toLocaleString()}</div><pre>${JSON.stringify(j.payload_preview||{},null,2)}</pre><div class="actions"><button onclick="viewJob('${j.id}')">View</button><button onclick="retryJob('${j.id}')">Retry</button><button class="danger" onclick="cancelJob('${j.id}')">Cancel</button></div></div>`).join('')}
async function viewJob(id){const r=await fetch('/api/jobs/'+id);const d=await r.json();alert(JSON.stringify(d.job||d,null,2).slice(0,4000))}
async function cancelJob(id){const admin_key=prompt('ADMIN_KEY');if(!admin_key)return;const r=await fetch(`/api/jobs/${id}/cancel`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({admin_key})});alert(await r.text());loadJobs();loadStats()}
async function retryJob(id){const admin_key=prompt('ADMIN_KEY');if(!admin_key)return;const r=await fetch(`/api/jobs/${id}/retry`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({admin_key})});alert(await r.text());loadJobs();loadStats()}
async function createDemoJob(){const r=await fetch('/api/jobs/check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:'Инфлацията в България е 10 процента през 2024 година.'})});alert(await r.text());loadJobs();loadStats()}
loadStats();loadJobs();setInterval(loadJobs,5000);
</script>
</body></html>"""

    @app.get("/jobs", response_class=HTMLResponse)
    def jobs_dashboard():
        return HTMLResponse(jobs_page_html())

    @app.get("/api/jobs")
    def api_jobs(limit: int = 30, status: str = "", type: str = ""):
        return JSONResponse({"ok": True, "jobs": job_store.recent(limit=max(1, min(limit, 200)), status=status, job_type=type)})

    @app.get("/api/jobs/stats")
    def api_jobs_stats():
        return JSONResponse({"ok": True, "stats": job_store.stats()})

    @app.get("/api/jobs/{job_id}")
    def api_job(job_id: str):
        job = job_store.get(job_id)
        if not job:
            return JSONResponse({"ok": False, "error": "job_not_found", "id": html.escape(job_id)}, status_code=404)
        return JSONResponse({"ok": True, "job": job})

    @app.post("/api/jobs/check")
    async def api_job_check(request: Request):
        payload = await parse_payload(request)
        if not str(payload.get("text", "")).strip():
            return JSONResponse({"ok": False, "error": "missing_text"}, status_code=400)
        return create_job_response(job_store.create("check", payload, run_check_job))

    @app.post("/api/jobs/ai-verdict")
    async def api_job_ai_verdict(request: Request):
        payload = await parse_payload(request)
        if not str(payload.get("text", "")).strip():
            return JSONResponse({"ok": False, "error": "missing_text"}, status_code=400)
        return create_job_response(job_store.create("ai_verdict", payload, run_ai_verdict_job))

    @app.post("/api/jobs/real-check")
    async def api_job_real_check(request: Request):
        payload = await parse_payload(request)
        if not str(payload.get("text", "")).strip():
            return JSONResponse({"ok": False, "error": "missing_text"}, status_code=400)
        return create_job_response(job_store.create("real_check", payload, run_real_check_job))

    @app.post("/api/jobs/{job_id}/cancel")
    async def api_job_cancel(job_id: str, request: Request):
        payload = await parse_payload(request)
        denied = require_admin(payload)
        if denied:
            return denied
        job = job_store.cancel(job_id, reason=str(payload.get("reason", "cancelled_by_admin"))[:200])
        if not job:
            return JSONResponse({"ok": False, "error": "job_not_found", "id": job_id}, status_code=404)
        return JSONResponse({"ok": True, "job": job})

    @app.post("/api/jobs/{job_id}/retry")
    async def api_job_retry(job_id: str, request: Request):
        payload = await parse_payload(request)
        denied = require_admin(payload)
        if denied:
            return denied
        old = job_store.get(job_id)
        if not old:
            return JSONResponse({"ok": False, "error": "job_not_found", "id": job_id}, status_code=404)
        retry_fn = fn_for_type(str(old.get("type", "")))
        new_job, error = job_store.retry(job_id, retry_fn)
        if error:
            return JSONResponse({"ok": False, "error": error, "id": job_id}, status_code=400)
        return create_job_response(new_job)

    @app.post("/api/jobs/cleanup")
    async def api_jobs_cleanup(request: Request):
        payload = await parse_payload(request)
        denied = require_admin(payload)
        if denied:
            return denied
        keep = int(payload.get("keep", 500) or 500)
        terminal_only = bool(payload.get("terminal_only", True))
        return JSONResponse({"ok": True, "cleanup": job_store.cleanup(keep=keep, terminal_only=terminal_only)})
