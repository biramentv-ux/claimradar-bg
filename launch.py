import json
import os
from html import escape

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

import app as app_module
from search_providers import SOURCE_WHITELIST, active_search_config, enhanced_search_web

# Patch the lightweight DuckDuckGo search in app.py with the provider layer:
# Brave / Bing / Tavily / SerpAPI / Google CSE / DuckDuckGo fallback.
app_module.search_web = enhanced_search_web

public_app = FastAPI(title="ClaimRadar BG Public Layer", version="2.3-search-public-pages")


def find_check(check_id: str):
    check_id = (check_id or "").strip()
    for rec in app_module.read_jsonl(app_module.CHECKS_FILE, limit=2000):
        if rec.get("id") == check_id:
            return rec
    return None


def public_page_html(rec: dict) -> str:
    check_id = rec.get("id", "")
    title = rec.get("title", "ClaimRadar BG check")
    created_at = rec.get("created_at", "")
    mode = rec.get("mode", "")
    text_preview = rec.get("text_preview", "")
    body_html = rec.get("html", "") or "<div class='empty'>Няма запазени резултати.</div>"
    copy_text = rec.get("copy_text", "")
    share_url = f"{app_module.PUBLIC_BASE_URL}/check/{check_id}"
    safe_copy_json = json.dumps(copy_text, ensure_ascii=False)
    safe_share_json = json.dumps(share_url, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="bg">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)} · ClaimRadar BG</title>
  <meta name="description" content="Public ClaimRadar BG result page with verdict, evidence links and confidence." />
  <style>
    :root{{--bg:#020617;--cyan:#22d3ee;--purple:#a855f7;--text:#f8fafc;--muted:#94a3b8;--border:rgba(34,211,238,.22)}}
    *{{box-sizing:border-box}} body{{margin:0;background:radial-gradient(circle at 12% 10%,rgba(34,211,238,.16),transparent 24%),radial-gradient(circle at 85% 8%,rgba(168,85,247,.20),transparent 26%),linear-gradient(180deg,#020617,#071126);color:var(--text);font-family:Inter,Arial,sans-serif}}
    main{{max-width:1120px;margin:0 auto;padding:28px 18px 60px}} .hero{{border:1px solid var(--border);border-radius:28px;padding:28px;background:linear-gradient(135deg,rgba(2,6,23,.92),rgba(30,27,75,.70));box-shadow:0 0 44px rgba(34,211,238,.13)}}
    .kicker{{color:#67e8f9;letter-spacing:.18em;text-transform:uppercase;font-size:12px;font-weight:900}} h1{{font-size:clamp(30px,5vw,56px);line-height:1;margin:12px 0;color:#fff}} .meta{{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}}
    .pill{{display:inline-flex;border:1px solid rgba(34,211,238,.24);background:rgba(8,145,178,.12);color:#cffafe;border-radius:999px;padding:7px 11px;font-size:12px}} .preview{{color:#cbd5e1;line-height:1.55}}
    .actions{{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}} button,a.button{{border:1px solid rgba(34,211,238,.28);background:rgba(15,23,42,.72);color:#e0f2fe;border-radius:14px;padding:11px 14px;cursor:pointer;text-decoration:none;font-weight:700}} button.primary,a.button.primary{{border:0;background:linear-gradient(90deg,#0891b2,#7c3aed);color:#fff}}
    .content{{margin-top:22px}} .empty{{border:1px solid var(--border);border-radius:20px;padding:20px;color:#cbd5e1;background:rgba(15,23,42,.60)}} .disclaimer{{margin-top:24px;color:#fbbf24;font-size:13px;line-height:1.5}}
    .claim-card,.history-card,.admin-card,.section-frame,.archive-head{{border:1px solid var(--border);background:linear-gradient(135deg,rgba(15,23,42,.80),rgba(30,41,59,.58));border-radius:22px;box-shadow:0 0 28px rgba(34,211,238,.13);padding:18px;margin:14px 0}} .claim-top{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}} .claim-index{{color:#67e8f9;font-family:monospace;font-weight:900}} .topic-pill,.label-pill,.source-chip,.status-pill{{display:inline-flex;align-items:center;gap:8px;border-radius:999px;padding:7px 11px;font-size:12px;text-decoration:none}} .topic-pill{{background:rgba(37,99,235,.18);color:#bfdbfe;border:1px solid rgba(59,130,246,.25)}} .label-pill{{background:rgba(168,85,247,.18);color:#e9d5ff;border:1px solid rgba(168,85,247,.28)}} .status-pill{{border:1px solid rgba(34,211,238,.24);background:rgba(8,145,178,.12);color:#cffafe}} .claim-text{{font-size:16px;color:#f8fafc;line-height:1.55}} .meter{{height:8px;border-radius:999px;background:rgba(148,163,184,.17);overflow:hidden;margin:14px 0 8px}} .meter span{{display:block;height:100%;background:linear-gradient(90deg,#22d3ee,#a855f7);border-radius:999px}} .meta-line{{color:#cbd5e1;font-size:13px;margin-bottom:12px}} .source-chip,.evidence-link{{color:#cffafe!important;border:1px solid rgba(34,211,238,.24);background:rgba(8,145,178,.12)}} .evidence-list{{display:grid;gap:10px;margin-top:12px}} .evidence-link{{display:grid;gap:4px;text-decoration:none!important;border-radius:16px;padding:12px}} .evidence-link span{{color:#fff}} .evidence-link small{{color:#94a3b8;line-height:1.35}} .caution{{margin-top:12px;color:#fbbf24;font-size:12px}}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="kicker">ClaimRadar BG · public result page</div>
      <h1>{escape(title)}</h1>
      <div class="meta">
        <span class="pill">ID: {escape(check_id)}</span>
        <span class="pill">Mode: {escape(mode)}</span>
        <span class="pill">Date: {escape(created_at)}</span>
      </div>
      <p class="preview">{escape(text_preview)}</p>
      <div class="actions">
        <button class="primary" onclick="copyResult()">Копирай резултата</button>
        <button onclick="shareResult()">Сподели</button>
        <a class="button" href="{escape(app_module.PUBLIC_BASE_URL)}" target="_blank">Отвори приложението</a>
        <a class="button" href="/api/check/{escape(check_id)}" target="_blank">JSON</a>
      </div>
    </section>
    <section class="content">{body_html}</section>
    <p class="disclaimer">{escape(app_module.DISCLAIMER)} Всички резултати трябва да се проверяват по посочените източници.</p>
  </main>
  <script>
    const COPY_TEXT = {safe_copy_json};
    const SHARE_URL = {safe_share_json};
    async function copyResult() {{ try {{ await navigator.clipboard.writeText(COPY_TEXT || SHARE_URL); alert('Копирано.'); }} catch(e) {{ prompt('Копирай:', COPY_TEXT || SHARE_URL); }} }}
    async function shareResult() {{ if (navigator.share) {{ await navigator.share({{title: document.title, url: SHARE_URL}}); }} else {{ try {{ await navigator.clipboard.writeText(SHARE_URL); alert('Линкът е копиран.'); }} catch(e) {{ prompt('Share URL:', SHARE_URL); }} }} }}
  </script>
</body>
</html>"""


@public_app.get("/search/status")
def search_status():
    return JSONResponse(active_search_config())


@public_app.get("/api/check/{check_id}")
def api_check(check_id: str):
    rec = find_check(check_id)
    if not rec:
        return JSONResponse({"ok": False, "error": "check_not_found", "id": check_id}, status_code=404)
    return JSONResponse({"ok": True, "check": rec})


@public_app.get("/check/{check_id}", response_class=HTMLResponse)
def public_check(check_id: str):
    rec = find_check(check_id)
    if not rec:
        return HTMLResponse(
            "<h1>ClaimRadar BG</h1><p>Не е намерена публична проверка с този Share ID.</p>",
            status_code=404,
        )
    return HTMLResponse(public_page_html(rec))


@public_app.get("/sources/whitelist")
def sources_whitelist():
    return JSONResponse({"ok": True, "whitelist": SOURCE_WHITELIST})


# Mount the original FastAPI + Gradio app after the public routes.
public_app.mount("/", app_module.app)
app = public_app


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("APP_PORT", "7860")))
