import os
from html import escape
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

import app as app_module
import launch as base_launch
from db_storage import storage
from jobs_api import register_job_routes
from monitoring import MonitoringMiddleware, log_custom_event, monitoring_status, public_metrics, read_events
from persistent_jobs import patch_job_store_persistence
from security_jobs import SecurityAndRateLimitMiddleware

_original_append_jsonl = app_module.append_jsonl
_original_read_jsonl = app_module.read_jsonl
SCHEMA_FILE = Path("supabase/schema.sql")
LEGAL_DOC = Path("LEGAL_METHODOLOGY_BG.md")


def db_aware_append_jsonl(path: Path, obj: dict):
    _original_append_jsonl(path, obj)
    try:
        storage.write_jsonl_mirror(Path(path).name, obj)
    except Exception:
        pass


def db_aware_read_jsonl(path: Path, limit=200):
    try:
        rows = storage.read_jsonl_mirror(Path(path).name, limit)
        if rows is not None:
            return rows
    except Exception:
        pass
    return _original_read_jsonl(path, limit)


app_module.append_jsonl = db_aware_append_jsonl
app_module.read_jsonl = db_aware_read_jsonl
patch_job_store_persistence(base_launch.job_store, storage)

outer_app = FastAPI(title="ClaimRadar BG Persistent Layer", version="3.1-background-jobs-controls")
outer_app.add_middleware(SecurityAndRateLimitMiddleware)
outer_app.add_middleware(MonitoringMiddleware)


def can_admin(admin_key: str = "") -> bool:
    configured = getattr(app_module, "ADMIN_KEY", "") or os.getenv("ADMIN_KEY", "")
    return bool(configured and admin_key and admin_key == configured)


def migrate_jsonl_to_db() -> dict:
    files = {
        app_module.CHECKS_FILE: "checks",
        app_module.FEEDBACK_FILE: "feedback",
        Path("data/abuse_reports.jsonl"): "reports",
        Path("data/visibility.jsonl"): "visibility",
        Path("data/jobs.jsonl"): "jobs",
    }
    counts = {}
    for path, label in files.items():
        rows = _original_read_jsonl(path, limit=10000)
        count = 0
        for row in reversed(rows):
            if storage.write_jsonl_mirror(Path(path).name, row):
                count += 1
        counts[label] = count
    return counts


def legal_style() -> str:
    return """
    :root{--bg:#020617;--cyan:#22d3ee;--purple:#a855f7;--text:#f8fafc;--muted:#94a3b8;--border:rgba(34,211,238,.22)}
    *{box-sizing:border-box} body{margin:0;background:radial-gradient(circle at 12% 10%,rgba(34,211,238,.16),transparent 24%),radial-gradient(circle at 85% 8%,rgba(168,85,247,.20),transparent 26%),linear-gradient(180deg,#020617,#071126);color:var(--text);font-family:Inter,Arial,sans-serif} main{max-width:1080px;margin:0 auto;padding:28px 18px 70px}.hero,.card{border:1px solid var(--border);border-radius:26px;background:linear-gradient(135deg,rgba(2,6,23,.94),rgba(30,27,75,.70));box-shadow:0 0 44px rgba(34,211,238,.13)}.hero{padding:32px}.kicker{color:#67e8f9;letter-spacing:.18em;text-transform:uppercase;font-size:12px;font-weight:900}h1{font-size:clamp(34px,6vw,64px);line-height:.96;margin:12px 0;color:#fff}h2{color:#fff;margin:0 0 12px}h3{color:#e0f2fe;margin:0 0 8px}.lead,p,li{color:#cbd5e1;line-height:1.65}.lead{font-size:18px;max-width:920px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin-top:18px}.card{padding:20px;border-radius:20px;margin-top:18px}.actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}a.button{border:1px solid rgba(34,211,238,.28);background:rgba(15,23,42,.72);color:#e0f2fe;border-radius:14px;padding:11px 14px;text-decoration:none;font-weight:700}a.primary{border:0;background:linear-gradient(90deg,#0891b2,#7c3aed);color:#fff}.pill{display:inline-flex;border:1px solid rgba(34,211,238,.24);background:rgba(8,145,178,.12);color:#cffafe;border-radius:999px;padding:7px 11px;font-size:12px;margin:4px}code,pre{background:rgba(15,23,42,.75);border:1px solid rgba(34,211,238,.18);border-radius:10px;color:#e0f2fe}code{padding:2px 6px}pre{padding:14px;overflow:auto}.warning{border:1px solid rgba(251,191,36,.35);background:rgba(120,53,15,.22);color:#fde68a;border-radius:18px;padding:14px;line-height:1.55;margin-top:18px}.footer{margin-top:28px;color:#94a3b8;font-size:13px}
    """


LEGAL_PAGES = {
    "about": {"title": "За ClaimRadar BG", "description": "Какво е ClaimRadar BG и за кого е предназначен.", "body": """<p class='lead'>ClaimRadar BG е български AI помощник за откриване, транскрибиране и първична проверка на публични твърдения.</p><div class='grid'><div class='card'><h3>За кого е?</h3><p>За журналисти, студенти, анализатори, модератори, създатели на съдържание и граждани.</p></div><div class='card'><h3>Какво обработва?</h3><p>Текст, транскрипти, аудио/видео файлове, YouTube captions/transcripts и realtime tab audio prototype.</p></div><div class='card'><h3>Какво не е?</h3><p>Не е съд, официална институция, медия или окончателна журналистическа присъда.</p></div></div>"""},
    "methodology": {"title": "Методология", "description": "Как ClaimRadar BG извлича твърдения, търси evidence и дава verdict.", "body": """<p class='lead'>ClaimRadar BG следва предпазлив workflow: <code>input → transcription → claim extraction → topic classification → evidence search → verdict → citations → public result</code>.</p><div class='card'><h2>Вход и транскрипция</h2><p>Потребителят може да въведе текст, да качи аудио/видео или да използва browser extension. При медия системата използва Faster Whisper.</p></div><div class='card'><h2>Claim extraction</h2><p>Системата търси изречения с числа, проценти, години, парични стойности, сравнения и публични теми.</p></div><div class='card'><h2>Evidence и verdict</h2><p>Search layer-ът търси в whitelist от надеждни източници. AI verdict engine сравнява твърдението само с намереното evidence.</p></div><div class='warning'><b>Confidence не е „истина в проценти“.</b> Това е технически индикатор за силата на намерените сигнали.</div>"""},
    "privacy": {"title": "Поверителност", "description": "Какви данни може да обработва ClaimRadar BG.", "body": """<p class='lead'>ClaimRadar BG обработва данните, които потребителят предоставя чрез приложението или browser extension-а.</p><div class='card'><h2>Възможно обработвани данни</h2><ul><li>въведен текст;</li><li>качени аудио/видео файлове;</li><li>транскрипти;</li><li>feedback;</li><li>abuse reports;</li><li>extension local history;</li><li>tab audio chunks при ръчно стартиран realtime режим.</li></ul></div><div class='warning'><b>Важно:</b> API ключове, database credentials и admin keys трябва да се пазят като server-side secrets.</div>"""},
    "terms": {"title": "Условия за използване", "description": "Правила и ограничения при използване на ClaimRadar BG.", "body": """<p class='lead'>ClaimRadar BG е тестов/бета инструмент.</p><div class='card'><h2>Потребителят приема, че:</h2><ul><li>резултатите са ориентир, не окончателна присъда;</li><li>системата може да греши;</li><li>важни заключения трябва да се потвърждават от човек;</li><li>не трябва да се качват чувствителни лични данни без основание;</li><li>не трябва да се използва за тормоз, doxxing или автоматизирана злоупотреба.</li></ul></div>"""},
    "sources": {"title": "Източници", "description": "Whitelist и принципи за избор на източници.", "body": """<p class='lead'>Официалните първични източници имат приоритет пред вторични публикации.</p><div class='card'><h2>Основни whitelist източници</h2><div><span class='pill'>nsi.bg</span><span class='pill'>bnb.bg</span><span class='pill'>nssi.bg</span><span class='pill'>nra.bg</span><span class='pill'>cik.bg</span><span class='pill'>parliament.bg</span><span class='pill'>dv.parliament.bg</span><span class='pill'>gov.bg</span><span class='pill'>minfin.bg</span><span class='pill'>ec.europa.eu</span><span class='pill'>factcheck.bg</span><span class='pill'>bta.bg</span><span class='pill'>bnr.bg</span></div></div><div class='actions'><a class='button primary' href='/sources/whitelist'>JSON whitelist</a><a class='button' href='/search/status'>Search status</a></div>"""},
    "contact": {"title": "Контакт и обратна връзка", "description": "Как да подадеш сигнал, feedback или abuse report.", "body": """<p class='lead'>За обратна връзка използвай вградената форма в приложението или Report abuse бутона на публична проверка.</p><div class='card'><h2>Подходящи сигнали</h2><ul><li>грешна категоризация;</li><li>липсващ източник;</li><li>грешен verdict;</li><li>проблем с публична страница;</li><li>лични данни в public check;</li><li>технически проблем.</li></ul></div><div class='actions'><a class='button primary' href='/'>Отвори приложението</a><a class='button' href='/product'>За продукта</a></div>"""},
}


def legal_page_html(slug: str) -> str:
    page = LEGAL_PAGES[slug]
    canonical = f"{app_module.PUBLIC_BASE_URL.rstrip('/')}/{slug}"
    nav = "".join([f"<a class='button' href='/{key}'>{escape(value['title'])}</a>" for key, value in LEGAL_PAGES.items()])
    return f"""<!doctype html><html lang='bg'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>{escape(page['title'])} · ClaimRadar BG</title><meta name='description' content='{escape(page['description'])}'><link rel='canonical' href='{escape(canonical)}'><style>{legal_style()}</style></head><body><main><section class='hero'><div class='kicker'>ClaimRadar BG · legal / methodology</div><h1>{escape(page['title'])}</h1><p class='lead'>{escape(page['description'])}</p><div class='actions'><a class='button primary' href='/product'>Продукт</a>{nav}</div></section>{page['body']}<p class='footer'>ClaimRadar BG е тестов инструмент. Всички резултати трябва да се проверяват по evidence линковете и официалните източници.</p></main></body></html>"""


@outer_app.get("/about", response_class=HTMLResponse)
def about_page():
    return HTMLResponse(legal_page_html("about"))


@outer_app.get("/methodology", response_class=HTMLResponse)
def methodology_page():
    return HTMLResponse(legal_page_html("methodology"))


@outer_app.get("/privacy", response_class=HTMLResponse)
def privacy_page():
    return HTMLResponse(legal_page_html("privacy"))


@outer_app.get("/terms", response_class=HTMLResponse)
def terms_page():
    return HTMLResponse(legal_page_html("terms"))


@outer_app.get("/sources", response_class=HTMLResponse)
def sources_page():
    return HTMLResponse(legal_page_html("sources"))


@outer_app.get("/contact", response_class=HTMLResponse)
def contact_page():
    return HTMLResponse(legal_page_html("contact"))


@outer_app.get("/legal-methodology.md")
def legal_methodology_md():
    if not LEGAL_DOC.exists():
        return JSONResponse({"ok": False, "error": "legal_doc_missing"}, status_code=404)
    return Response(LEGAL_DOC.read_text(encoding="utf-8"), media_type="text/plain; charset=utf-8")


@outer_app.get("/monitoring/status")
def monitoring_status_page():
    return JSONResponse(monitoring_status({"storage": "postgres" if storage.status().get("connected") else "jsonl_fallback"}))


@outer_app.get("/monitoring/metrics")
def monitoring_metrics_page():
    return JSONResponse({"ok": True, "metrics": public_metrics()})


@outer_app.get("/monitoring/logs")
def monitoring_logs_page(admin_key: str = "", limit: int = 100, level: str = ""):
    if not can_admin(admin_key):
        return JSONResponse({"ok": False, "error": "invalid_admin_key"}, status_code=403)
    return JSONResponse({"ok": True, "events": read_events(limit=limit, level=level)})


@outer_app.post("/api/monitoring/event")
async def monitoring_event_page(request: Request):
    payload = await request.json()
    if not can_admin(str(payload.get("admin_key", ""))):
        return JSONResponse({"ok": False, "error": "invalid_admin_key"}, status_code=403)
    event = log_custom_event(
        kind=str(payload.get("kind", "manual_event")),
        level=str(payload.get("level", "info")),
        message=str(payload.get("message", "")),
        data=payload.get("data") if isinstance(payload.get("data"), dict) else {},
    )
    return JSONResponse({"ok": True, "event": event})


@outer_app.get("/db/status")
def db_status():
    status = storage.status()
    return JSONResponse({"ok": True, "storage": "postgres" if status.get("connected") else "jsonl_fallback", **status})


@outer_app.get("/api/db/status")
def db_status_alias():
    return db_status()


@outer_app.get("/api/db/schema")
def db_schema():
    if not SCHEMA_FILE.exists():
        return JSONResponse({"ok": False, "error": "schema_file_missing"}, status_code=404)
    return Response(SCHEMA_FILE.read_text(encoding="utf-8"), media_type="text/plain; charset=utf-8")


@outer_app.post("/api/db/migrate-jsonl")
async def db_migrate_jsonl(request: Request):
    payload = await request.json()
    if not can_admin(str(payload.get("admin_key", ""))):
        return JSONResponse({"ok": False, "error": "invalid_admin_key"}, status_code=403)
    if not storage.configured:
        return JSONResponse({"ok": False, "error": "database_not_configured"}, status_code=400)
    counts = migrate_jsonl_to_db()
    return JSONResponse({"ok": True, "migrated": counts, "db": storage.status()})


register_job_routes(
    outer_app,
    base_launch.job_store,
    can_admin,
    base_launch.run_check_job,
    base_launch.run_ai_verdict_job,
    base_launch.run_real_check_job,
)

outer_app.mount("/", base_launch.app)
app = outer_app


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("APP_PORT", "7860")))
