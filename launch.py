import json
import os
from html import escape
from pathlib import Path
from urllib.parse import quote

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

import app as app_module
from search_providers import SOURCE_WHITELIST, active_search_config, enhanced_search_web

# Patch the lightweight DuckDuckGo search in app.py with the provider layer:
# Brave / Bing / Tavily / SerpAPI / Google CSE / DuckDuckGo fallback.
app_module.search_web = enhanced_search_web

public_app = FastAPI(title="ClaimRadar BG Public Layer", version="2.5-privacy-metadata-abuse")

DATA_DIR: Path = app_module.DATA_DIR
VISIBILITY_FILE = DATA_DIR / "visibility.jsonl"
ABUSE_FILE = DATA_DIR / "abuse_reports.jsonl"


def public_base() -> str:
    return app_module.PUBLIC_BASE_URL.rstrip("/")


def base_style() -> str:
    return """
    :root{--bg:#020617;--cyan:#22d3ee;--purple:#a855f7;--text:#f8fafc;--muted:#94a3b8;--border:rgba(34,211,238,.22)}
    *{box-sizing:border-box} body{margin:0;background:radial-gradient(circle at 12% 10%,rgba(34,211,238,.16),transparent 24%),radial-gradient(circle at 85% 8%,rgba(168,85,247,.20),transparent 26%),linear-gradient(180deg,#020617,#071126);color:var(--text);font-family:Inter,Arial,sans-serif} main{max-width:1180px;margin:0 auto;padding:28px 18px 60px}.hero,.card{border:1px solid var(--border);border-radius:28px;background:linear-gradient(135deg,rgba(2,6,23,.92),rgba(30,27,75,.70));box-shadow:0 0 44px rgba(34,211,238,.13)}.hero{padding:34px}.kicker{color:#67e8f9;letter-spacing:.18em;text-transform:uppercase;font-size:12px;font-weight:900}h1{font-size:clamp(34px,6vw,68px);line-height:.95;margin:12px 0;color:#fff}h2{color:#fff;margin:0 0 12px}h3{color:#e0f2fe;margin:0 0 8px}.lead{max-width:950px;color:#cbd5e1;line-height:1.65;font-size:18px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px;margin-top:20px}.card{padding:20px;border-radius:22px}.pill{display:inline-flex;border:1px solid rgba(34,211,238,.24);background:rgba(8,145,178,.12);color:#cffafe;border-radius:999px;padding:7px 11px;font-size:12px;margin:4px}.pill.private{border-color:rgba(251,113,133,.35);background:rgba(127,29,29,.28);color:#fecdd3}.actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}button,a.button{border:1px solid rgba(34,211,238,.28);background:rgba(15,23,42,.72);color:#e0f2fe;border-radius:14px;padding:11px 14px;cursor:pointer;text-decoration:none;font-weight:700}button.danger,a.button.danger{border-color:rgba(251,113,133,.42);color:#fecdd3;background:rgba(127,29,29,.22)}a.button.primary,button.primary{border:0;background:linear-gradient(90deg,#0891b2,#7c3aed);color:#fff}.muted{color:#94a3b8;line-height:1.55}.section{margin-top:24px}.list{display:grid;gap:10px;margin:0;padding:0;list-style:none}.list li{border:1px solid rgba(34,211,238,.16);background:rgba(15,23,42,.45);border-radius:16px;padding:12px;color:#cbd5e1}.flow{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}.flow div{border:1px solid rgba(168,85,247,.26);background:rgba(88,28,135,.20);border-radius:16px;padding:13px;text-align:center;color:#f5d0fe;font-weight:800}.warning{border:1px solid rgba(251,191,36,.35);background:rgba(120,53,15,.22);color:#fde68a;border-radius:18px;padding:14px;line-height:1.55}.footer{margin-top:28px;color:#94a3b8;font-size:13px;line-height:1.6}
    .claim-card,.history-card,.admin-card,.section-frame,.archive-head{border:1px solid var(--border);background:linear-gradient(135deg,rgba(15,23,42,.80),rgba(30,41,59,.58));border-radius:22px;box-shadow:0 0 28px rgba(34,211,238,.13);padding:18px;margin:14px 0}.claim-top{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}.claim-index{color:#67e8f9;font-family:monospace;font-weight:900}.topic-pill,.label-pill,.source-chip,.status-pill{display:inline-flex;align-items:center;gap:8px;border-radius:999px;padding:7px 11px;font-size:12px;text-decoration:none}.topic-pill{background:rgba(37,99,235,.18);color:#bfdbfe;border:1px solid rgba(59,130,246,.25)}.label-pill{background:rgba(168,85,247,.18);color:#e9d5ff;border:1px solid rgba(168,85,247,.28)}.status-pill{border:1px solid rgba(34,211,238,.24);background:rgba(8,145,178,.12);color:#cffafe}.claim-text{font-size:16px;color:#f8fafc;line-height:1.55}.meter{height:8px;border-radius:999px;background:rgba(148,163,184,.17);overflow:hidden;margin:14px 0 8px}.meter span{display:block;height:100%;background:linear-gradient(90deg,#22d3ee,#a855f7);border-radius:999px}.meta-line{color:#cbd5e1;font-size:13px;margin-bottom:12px}.source-chip,.evidence-link{color:#cffafe!important;border:1px solid rgba(34,211,238,.24);background:rgba(8,145,178,.12)}.evidence-list{display:grid;gap:10px;margin-top:12px}.evidence-link{display:grid;gap:4px;text-decoration:none!important;border-radius:16px;padding:12px}.evidence-link span{color:#fff}.evidence-link small{color:#94a3b8;line-height:1.35}.caution{margin-top:12px;color:#fbbf24;font-size:12px}.disclaimer{margin-top:24px;color:#fbbf24;font-size:13px;line-height:1.5}.preview{color:#cbd5e1;line-height:1.55}.content{margin-top:22px}.empty{border:1px solid var(--border);border-radius:20px;padding:20px;color:#cbd5e1;background:rgba(15,23,42,.60)}
    """


def find_check(check_id: str):
    check_id = (check_id or "").strip()
    for rec in app_module.read_jsonl(app_module.CHECKS_FILE, limit=2000):
        if rec.get("id") == check_id:
            return rec
    return None


def visibility_for(check_id: str) -> str:
    rec = find_check(check_id)
    default_visibility = (rec or {}).get("visibility", "public")
    for row in app_module.read_jsonl(VISIBILITY_FILE, limit=2000):
        if row.get("id") == check_id:
            return row.get("visibility", default_visibility)
    return default_visibility


def can_admin(admin_key: str = "") -> bool:
    configured = getattr(app_module, "ADMIN_KEY", "") or os.getenv("ADMIN_KEY", "")
    return bool(configured and admin_key and admin_key == configured)


def private_html(check_id: str) -> str:
    return f"""<!doctype html><html lang="bg"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Private check · ClaimRadar BG</title><style>{base_style()}</style></head><body><main><section class="hero"><div class="kicker">ClaimRadar BG</div><h1>Тази проверка е private</h1><p class="lead">Share ID <code>{escape(check_id)}</code> съществува, но публичният достъп е изключен.</p><div class="actions"><a class="button primary" href="/product">Информация за продукта</a><a class="button" href="/">Отвори приложението</a></div></section></main></body></html>"""


def social_image_url(title: str = "ClaimRadar BG") -> str:
    return f"{public_base()}/social-preview.svg?title={quote(title[:100])}"


def product_page_html() -> str:
    canonical = f"{public_base()}/product"
    image = social_image_url("ClaimRadar BG · Информация за продукта")
    return f"""<!doctype html>
<html lang="bg">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ClaimRadar BG · Информация за продукта</title>
  <meta name="description" content="ClaimRadar BG е български инструмент за откриване, транскрибиране и проверка на публични твърдения с evidence, AI verdict и цитати." />
  <link rel="canonical" href="{escape(canonical)}" />
  <meta property="og:type" content="website" />
  <meta property="og:title" content="ClaimRadar BG · Информация за продукта" />
  <meta property="og:description" content="Български AI помощник за проверка на публични твърдения с evidence, verdict и цитати." />
  <meta property="og:url" content="{escape(canonical)}" />
  <meta property="og:image" content="{escape(image)}" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="ClaimRadar BG · Информация за продукта" />
  <meta name="twitter:description" content="Български AI помощник за проверка на публични твърдения." />
  <meta name="twitter:image" content="{escape(image)}" />
  <style>{base_style()}</style>
</head>
<body>
<main>
  <section class="hero">
    <div class="kicker">ClaimRadar BG · продуктова информация</div>
    <h1>Български AI помощник за проверка на публични твърдения</h1>
    <p class="lead">ClaimRadar BG помага да се откриват проверими твърдения в текст, аудио, видео, YouTube/live съдържание и публични изказвания. Системата извлича claims, търси надеждни източници, показва evidence links, дава предпазлива оценка и позволява споделяне чрез публична страница.</p>
    <div class="actions"><a class="button primary" href="/" target="_blank">Отвори приложението</a><a class="button" href="/search/status" target="_blank">Search status</a><a class="button" href="/sources/whitelist" target="_blank">Източници</a><a class="button" href="https://github.com/biramentv-ux/claimradar-bg" target="_blank">GitHub</a></div>
  </section>
  <section class="section grid"><div class="card"><h3>За кого е?</h3><p class="muted">За журналисти, студенти, анализатори, модератори, създатели на съдържание и хора, които искат бързо да проверят публични твърдения в български контекст.</p></div><div class="card"><h3>Какво проверява?</h3><p class="muted">Твърдения с числа, проценти, години, бюджет, инфлация, избори, закони, енергетика, образование, здравеопазване, ЕС и други публични теми.</p></div><div class="card"><h3>Какво не е?</h3><p class="muted">Не е съд, не е окончателна журналистическа присъда и не трябва да се използва като единствен източник. Резултатите са ориентир за проверка.</p></div></section>
  <section class="section card"><h2>Как работи</h2><div class="flow"><div>1. Вход</div><div>2. Транскрипция</div><div>3. Claims</div><div>4. Evidence</div><div>5. Verdict</div><div>6. Share</div></div><p class="muted">Потребителят подава текст или медия. При аудио/видео системата прави транскрипция с Faster Whisper. След това открива проверими claims, избира тема, търси evidence в whitelist/API източници и показва резултат с confidence, цитати и публичен Share ID.</p></section>
  <section class="section grid"><div class="card"><h3>Текстова проверка</h3><p class="muted">Поставяш текст от дебат, интервю, новина или стенограма. Системата извлича проверими твърдения и предлага източници.</p></div><div class="card"><h3>AI verdict</h3><p class="muted">Сравнява твърдението с намереното evidence и връща verdict: вярно, частично вярно, подвеждащо, невярно, непроверимо или нужен контекст.</p></div><div class="card"><h3>Аудио/видео</h3><p class="muted">Качваш кратък файл, получаваш транскрипция, проверка, AI verdict и SRT export.</p></div><div class="card"><h3>Realtime/Extension</h3><p class="muted">Chrome/Edge extension overlay може да анализира YouTube captions, селекция от страница или tab audio realtime stream.</p></div></section>
  <section class="section card"><h2>Verdict значения</h2><ul class="list"><li><b>Вярно</b> — наличното evidence подкрепя твърдението.</li><li><b>По-скоро вярно</b> — твърдението е основно подкрепено, но може да има малки уточнения.</li><li><b>Частично вярно</b> — има вярна част, но контекстът или формулировката са непълни.</li><li><b>Подвеждащо</b> — има данни, но твърдението може да внушава грешен извод.</li><li><b>Невярно</b> — наличното evidence противоречи на твърдението.</li><li><b>Непроверимо</b> — липсват достатъчно надеждни данни.</li><li><b>Нужен контекст</b> — има evidence, но е нужна допълнителна проверка или уточнение.</li></ul></section>
  <section class="section card"><h2>Източници и търсене</h2><p class="muted">ClaimRadar BG използва whitelist от официални и надеждни източници. Search API слойът поддържа Brave, Bing, Tavily, SerpAPI, Google CSE и DuckDuckGo fallback.</p><div>{''.join([f'<span class="pill">{escape(domain)}</span>' for domain in SOURCE_WHITELIST])}</div></section>
  <section class="section warning"><b>Важно:</b> ClaimRadar BG е тестов инструмент. Той помага за ориентация, но не заменя човешка проверка, редакторска преценка или официално становище.</section>
  <p class="footer">Версия на app слоя: {escape(getattr(app_module, 'APP_VERSION', 'unknown'))}. Public layer: 2.5-privacy-metadata-abuse.</p>
</main>
</body>
</html>"""


def public_page_html(rec: dict, admin_view: bool = False) -> str:
    check_id = rec.get("id", "")
    title = rec.get("title", "ClaimRadar BG check")
    created_at = rec.get("created_at", "")
    mode = rec.get("mode", "")
    visibility = visibility_for(check_id)
    text_preview = rec.get("text_preview", "")
    body_html = rec.get("html", "") or "<div class='empty'>Няма запазени резултати.</div>"
    copy_text = rec.get("copy_text", "")
    canonical = f"{public_base()}/check/{check_id}"
    image = social_image_url(title)
    safe_copy_json = json.dumps(copy_text, ensure_ascii=False)
    safe_share_json = json.dumps(canonical, ensure_ascii=False)
    noindex = '<meta name="robots" content="noindex,nofollow" />' if visibility != "public" else ""
    return f"""<!doctype html>
<html lang="bg">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)} · ClaimRadar BG</title>
  <meta name="description" content="ClaimRadar BG public result page with verdict, evidence links and confidence." />
  {noindex}
  <link rel="canonical" href="{escape(canonical)}" />
  <meta property="og:type" content="article" />
  <meta property="og:title" content="{escape(title)} · ClaimRadar BG" />
  <meta property="og:description" content="{escape(text_preview[:180] or 'Публична проверка с evidence и AI verdict.')}" />
  <meta property="og:url" content="{escape(canonical)}" />
  <meta property="og:image" content="{escape(image)}" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{escape(title)} · ClaimRadar BG" />
  <meta name="twitter:description" content="{escape(text_preview[:180] or 'Публична проверка с evidence и AI verdict.')}" />
  <meta name="twitter:image" content="{escape(image)}" />
  <style>{base_style()}</style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="kicker">ClaimRadar BG · public result page</div>
      <h1>{escape(title)}</h1>
      <div><span class="pill">ID: {escape(check_id)}</span><span class="pill">Mode: {escape(mode)}</span><span class="pill {'private' if visibility != 'public' else ''}">Visibility: {escape(visibility)}</span><span class="pill">Date: {escape(created_at)}</span></div>
      <p class="preview">{escape(text_preview)}</p>
      <div class="actions"><button class="primary" onclick="copyResult()">Копирай резултата</button><button onclick="shareResult()">Сподели</button><button class="danger" onclick="reportAbuse()">Report abuse</button><button onclick="toggleVisibility()">Public/private</button><a class="button" href="{escape(public_base())}" target="_blank">Отвори приложението</a><a class="button" href="/product" target="_blank">За продукта</a><a class="button" href="/api/check/{escape(check_id)}" target="_blank">JSON</a></div>
    </section>
    <section class="content">{body_html}</section>
    <p class="disclaimer">{escape(app_module.DISCLAIMER)} Всички резултати трябва да се проверяват по посочените източници.</p>
  </main>
  <script>
    const CHECK_ID = {json.dumps(check_id)};
    const COPY_TEXT = {safe_copy_json};
    const SHARE_URL = {safe_share_json};
    async function copyResult() {{ try {{ await navigator.clipboard.writeText(COPY_TEXT || SHARE_URL); alert('Копирано.'); }} catch(e) {{ prompt('Копирай:', COPY_TEXT || SHARE_URL); }} }}
    async function shareResult() {{ if (navigator.share) {{ await navigator.share({{title: document.title, url: SHARE_URL}}); }} else {{ try {{ await navigator.clipboard.writeText(SHARE_URL); alert('Линкът е копиран.'); }} catch(e) {{ prompt('Share URL:', SHARE_URL); }} }} }}
    async function reportAbuse() {{
      const reason = prompt('Причина за доклада: spam, грешна информация, лични данни, вредно съдържание или друго.');
      if (!reason) return;
      const details = prompt('Допълнителни детайли по избор:') || '';
      const res = await fetch('/api/report-abuse', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{check_id: CHECK_ID, reason, details, page: location.href}})}});
      alert(res.ok ? 'Докладът е записан. Благодаря.' : 'Неуспешно изпращане на доклада.');
    }}
    async function toggleVisibility() {{
      const admin_key = prompt('Admin key:');
      if (!admin_key) return;
      const visibility = prompt('Нова видимост: public или private', '{visibility}') || '{visibility}';
      const res = await fetch('/api/check/' + encodeURIComponent(CHECK_ID) + '/visibility', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{admin_key, visibility}})}});
      const data = await res.json().catch(() => ({{ok:false}}));
      alert(data.ok ? ('Записано: ' + data.visibility) : ('Грешка: ' + (data.error || 'unknown')));
      if (data.ok) location.reload();
    }}
  </script>
</body>
</html>"""


@public_app.get("/social-preview.svg")
def social_preview(title: str = "ClaimRadar BG"):
    safe_title = escape((title or "ClaimRadar BG")[:120])
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#020617"/><stop offset="0.55" stop-color="#1e1b4b"/><stop offset="1" stop-color="#0e7490"/></linearGradient><filter id="glow"><feGaussianBlur stdDeviation="8" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
<rect width="1200" height="630" fill="url(#g)"/><circle cx="160" cy="100" r="220" fill="#22d3ee" opacity="0.18"/><circle cx="980" cy="80" r="240" fill="#a855f7" opacity="0.20"/><path d="M0 520 C260 440 420 590 680 500 S1020 430 1200 520" fill="none" stroke="#22d3ee" stroke-width="3" opacity="0.35"/>
<text x="72" y="115" font-family="Arial, sans-serif" font-size="28" fill="#67e8f9" letter-spacing="6" font-weight="700">CLAIMRADAR BG</text>
<text x="72" y="235" font-family="Arial, sans-serif" font-size="66" fill="#ffffff" font-weight="900" filter="url(#glow)">Проверка на твърдения</text>
<foreignObject x="72" y="275" width="920" height="170"><div xmlns="http://www.w3.org/1999/xhtml" style="font-family:Arial,sans-serif;font-size:38px;line-height:1.18;color:#e0f2fe;font-weight:800;">{safe_title}</div></foreignObject>
<text x="72" y="560" font-family="Arial, sans-serif" font-size="30" fill="#cbd5e1">Evidence · AI verdict · Citations · Български контекст</text>
</svg>"""
    return Response(svg, media_type="image/svg+xml")


@public_app.get("/product", response_class=HTMLResponse)
def product_page():
    return HTMLResponse(product_page_html())


@public_app.get("/search/status")
def search_status():
    return JSONResponse(active_search_config())


@public_app.post("/api/report-abuse")
async def api_report_abuse(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    check_id = str(payload.get("check_id", "")).strip()
    report = {
        "id": __import__("uuid").uuid4().hex[:10],
        "created_at": app_module.now_iso(),
        "type": "abuse_report",
        "check_id": check_id,
        "reason": str(payload.get("reason", ""))[:300],
        "details": str(payload.get("details", ""))[:1500],
        "page": str(payload.get("page", ""))[:500],
    }
    app_module.append_jsonl(ABUSE_FILE, report)
    app_module.append_jsonl(app_module.FEEDBACK_FILE, {**report, "kind": "abuse_report", "comment": f"{report['reason']} — {report['details']}"})
    return JSONResponse({"ok": True, "report_id": report["id"]})


@public_app.post("/api/check/{check_id}/visibility")
async def api_set_visibility(check_id: str, request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    admin_key = str(payload.get("admin_key", ""))
    visibility = str(payload.get("visibility", "public")).lower().strip()
    if visibility not in {"public", "private"}:
        return JSONResponse({"ok": False, "error": "visibility must be public or private"}, status_code=400)
    if not can_admin(admin_key):
        return JSONResponse({"ok": False, "error": "invalid_admin_key"}, status_code=403)
    if not find_check(check_id):
        return JSONResponse({"ok": False, "error": "check_not_found"}, status_code=404)
    app_module.append_jsonl(VISIBILITY_FILE, {"id": check_id, "visibility": visibility, "updated_at": app_module.now_iso()})
    return JSONResponse({"ok": True, "id": check_id, "visibility": visibility})


@public_app.get("/api/check/{check_id}")
def api_check(check_id: str, admin_key: str = ""):
    rec = find_check(check_id)
    if not rec:
        return JSONResponse({"ok": False, "error": "check_not_found", "id": check_id}, status_code=404)
    visibility = visibility_for(check_id)
    if visibility != "public" and not can_admin(admin_key):
        return JSONResponse({"ok": False, "error": "private_check", "id": check_id}, status_code=403)
    return JSONResponse({"ok": True, "visibility": visibility, "check": rec})


@public_app.get("/check/{check_id}", response_class=HTMLResponse)
def public_check(check_id: str, admin_key: str = ""):
    rec = find_check(check_id)
    if not rec:
        return HTMLResponse("<h1>ClaimRadar BG</h1><p>Не е намерена публична проверка с този Share ID.</p><p><a href='/product'>Информация за продукта</a></p>", status_code=404)
    visibility = visibility_for(check_id)
    if visibility != "public" and not can_admin(admin_key):
        return HTMLResponse(private_html(check_id), status_code=403)
    return HTMLResponse(public_page_html(rec, admin_view=can_admin(admin_key)))


@public_app.get("/sources/whitelist")
def sources_whitelist():
    return JSONResponse({"ok": True, "whitelist": SOURCE_WHITELIST})


# Mount the original FastAPI + Gradio app after the public routes.
public_app.mount("/", app_module.app)
app = public_app


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("APP_PORT", "7860")))
