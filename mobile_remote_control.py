from __future__ import annotations

import os
import secrets
import socket
import time
from typing import Any, Dict, List

from fastapi import FastAPI, Header, Request
from fastapi.responses import HTMLResponse, JSONResponse

from local_archive import import_text_to_archive
from local_evidence_router import evidence_search, normalized_evidence_mode
from local_llm_engine import extract_claims, local_verdict
from local_storage_sqlite import local_sqlite_store

MOBILE_REMOTE_ENABLED = os.getenv("MOBILE_REMOTE_ENABLED", "1").lower() not in {"0", "false", "no"}
MOBILE_REMOTE_REQUIRE_PIN = os.getenv("MOBILE_REMOTE_REQUIRE_PIN", "1").lower() not in {"0", "false", "no"}
MOBILE_REMOTE_SESSION_TTL_SECONDS = int(os.getenv("MOBILE_REMOTE_SESSION_TTL_SECONDS", "86400"))
MOBILE_REMOTE_MAX_TEXT_CHARS = int(os.getenv("MOBILE_REMOTE_MAX_TEXT_CHARS", "16000"))
MOBILE_REMOTE_APP_PORT = int(os.getenv("APP_PORT", "8765"))
MOBILE_REMOTE_PIN = os.getenv("MOBILE_REMOTE_PIN", "").strip() or f"{secrets.randbelow(900000) + 100000}"
MOBILE_REMOTE_TOKEN = os.getenv("MOBILE_REMOTE_TOKEN", "").strip() or secrets.token_urlsafe(24)
MOBILE_REMOTE_CREATED_AT = time.time()
MOBILE_SESSIONS: Dict[str, Dict[str, Any]] = {}


def _local_ips() -> List[str]:
    ips = {"127.0.0.1"}
    try:
        hostname = socket.gethostname()
        for item in socket.getaddrinfo(hostname, None):
            ip = item[4][0]
            if ":" not in ip and not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ips.add(sock.getsockname()[0])
        sock.close()
    except Exception:
        pass
    return sorted(ips)


def mobile_urls() -> List[str]:
    return [f"http://{ip}:{MOBILE_REMOTE_APP_PORT}/mobile" for ip in _local_ips()]


def _session_valid(token: str) -> bool:
    if token == MOBILE_REMOTE_TOKEN and not MOBILE_REMOTE_REQUIRE_PIN:
        return True
    session = MOBILE_SESSIONS.get(token)
    return bool(session and time.time() - float(session.get("created_at", 0)) <= MOBILE_REMOTE_SESSION_TTL_SECONDS)


def _require_mobile_token(token: str | None) -> tuple[bool, JSONResponse | None]:
    if not MOBILE_REMOTE_ENABLED:
        return False, JSONResponse({"ok": False, "error": "mobile_remote_disabled"}, status_code=404)
    if not MOBILE_REMOTE_REQUIRE_PIN:
        return True, None
    if token and _session_valid(token):
        return True, None
    return False, JSONResponse({"ok": False, "error": "mobile_pairing_required"}, status_code=401)


def _mobile_page() -> str:
    return """<!doctype html><html lang='bg'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>ClaimRadar Mobile Remote</title><style>body{margin:0;font-family:Arial,sans-serif;background:#020617;color:#e5e7eb}.wrap{max-width:760px;margin:auto;padding:20px}.card{background:#0f172a;border:1px solid #164e63;border-radius:18px;padding:16px;margin:12px 0}input,textarea,select{box-sizing:border-box;width:100%;padding:12px;border-radius:12px;border:1px solid #164e63;background:#020617;color:white;margin-top:8px}textarea{min-height:150px}button{padding:12px 14px;border:0;border-radius:12px;background:#0891b2;color:#fff;font-weight:800;margin-top:10px}.muted{color:#94a3b8}pre{white-space:pre-wrap;background:#020617;border-radius:12px;padding:12px;overflow:auto}</style></head><body><main class='wrap'><h1>ClaimRadar BG Remote</h1><p class='muted'>Телефонът е дистанционно. Компютърът трябва да е включен и приложението да работи.</p><section class='card'><h2>Pair</h2><input id='pin' placeholder='PIN от компютъра'><button onclick='pair()'>Свържи телефона</button><p class='muted' id='pairStatus'>Не е свързан.</p></section><section class='card'><h2>Analyze</h2><select id='mode'><option>offline</option><option>hybrid</option><option>online_evidence</option></select><textarea id='text' placeholder='Постави текст за проверка...'></textarea><button onclick='analyze()'>Analyze on PC</button><pre id='out'>—</pre></section><section class='card'><h2>Import to local archive</h2><input id='title' placeholder='Заглавие'><textarea id='archiveText' placeholder='Текст за локалния архив...'></textarea><button onclick='importArchive()'>Import</button></section></main><script>let token=localStorage.getItem('claimradar_mobile_token')||'';pairStatus.textContent=token?'Свързан token в браузъра.':'Не е свързан.';async function api(u,o={}){const r=await fetch(u,{headers:{'content-type':'application/json','x-mobile-token':token},...o});const j=await r.json();if(!r.ok)throw j;return j}async function pair(){const r=await fetch('/api/mobile/pair',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({pin:pin.value})});const j=await r.json();if(j.ok){token=j.token;localStorage.setItem('claimradar_mobile_token',token);pairStatus.textContent='Свързан.'}else{pairStatus.textContent='Грешка: '+j.error}}async function analyze(){out.textContent='Работи на компютъра...';try{out.textContent=JSON.stringify(await api('/api/mobile/analyze',{method:'POST',body:JSON.stringify({text:text.value,mode:mode.value})}),null,2)}catch(e){out.textContent=JSON.stringify(e,null,2)}}async function importArchive(){try{out.textContent=JSON.stringify(await api('/api/mobile/archive/import-text',{method:'POST',body:JSON.stringify({title:title.value,text:archiveText.value})}),null,2)}catch(e){out.textContent=JSON.stringify(e,null,2)}}</script></body></html>"""


def _pair_page() -> str:
    urls = "".join(f"<li><code>{url}</code></li>" for url in mobile_urls())
    return f"""<!doctype html><html lang='bg'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>ClaimRadar Pair Phone</title><style>body{{font-family:Arial;background:#020617;color:#e5e7eb;margin:0}}.wrap{{max-width:820px;margin:auto;padding:24px}}.card{{background:#0f172a;border:1px solid #164e63;border-radius:18px;padding:18px}}code{{color:#67e8f9}}.pin{{font-size:42px;letter-spacing:.18em;font-weight:900;color:#fff}}</style></head><body><main class='wrap'><section class='card'><h1>Свързване на телефон</h1><p>Отвори един от адресите на телефона, когато телефонът и компютърът са в една Wi‑Fi/LAN мрежа.</p><ul>{urls}</ul><p>PIN за телефона:</p><div class='pin'>{MOBILE_REMOTE_PIN}</div><p>Компютърът трябва да остане включен и приложението да работи. За достъп извън домашната мрежа използвай Cloudflare Tunnel/ngrok и пак запази PIN pairing.</p></section></main></body></html>"""


def mobile_status() -> Dict[str, Any]:
    return {
        "enabled": MOBILE_REMOTE_ENABLED,
        "require_pin": MOBILE_REMOTE_REQUIRE_PIN,
        "port": MOBILE_REMOTE_APP_PORT,
        "urls": mobile_urls(),
        "pin_created_at": MOBILE_REMOTE_CREATED_AT,
        "session_count": len(MOBILE_SESSIONS),
        "lan_bind_required": "set MOBILE_REMOTE_BIND_LAN=1 or LOCAL_DESKTOP_HOST=0.0.0.0 for phone access from another device",
    }


def register_mobile_remote_routes(app: FastAPI) -> None:
    @app.get("/mobile")
    def mobile_page():
        if not MOBILE_REMOTE_ENABLED:
            return JSONResponse({"ok": False, "error": "mobile_remote_disabled"}, status_code=404)
        return HTMLResponse(_mobile_page())

    @app.get("/mobile/pair")
    def mobile_pair_page():
        if not MOBILE_REMOTE_ENABLED:
            return JSONResponse({"ok": False, "error": "mobile_remote_disabled"}, status_code=404)
        return HTMLResponse(_pair_page())

    @app.get("/api/mobile/status")
    def api_mobile_status():
        return JSONResponse({"ok": True, "mobile": mobile_status()})

    @app.post("/api/mobile/pair")
    async def api_mobile_pair(request: Request):
        payload = await request.json()
        pin = str((payload or {}).get("pin", "")).strip()
        if MOBILE_REMOTE_REQUIRE_PIN and pin != MOBILE_REMOTE_PIN:
            return JSONResponse({"ok": False, "error": "invalid_pin"}, status_code=403)
        token = secrets.token_urlsafe(24)
        MOBILE_SESSIONS[token] = {"created_at": time.time(), "user_agent": request.headers.get("user-agent", "")[:300]}
        return JSONResponse({"ok": True, "token": token, "ttl_seconds": MOBILE_REMOTE_SESSION_TTL_SECONDS})

    @app.post("/api/mobile/analyze")
    async def api_mobile_analyze(request: Request, x_mobile_token: str | None = Header(default=None)):
        ok, error = _require_mobile_token(x_mobile_token)
        if not ok:
            return error
        payload = await request.json()
        text = str((payload or {}).get("text", ""))[:MOBILE_REMOTE_MAX_TEXT_CHARS]
        mode = normalized_evidence_mode(str((payload or {}).get("mode", "offline")))
        claims = extract_claims(text)
        evidence = evidence_search(text[:800], mode=mode)
        verdict = local_verdict(text, evidence=evidence.get("results", [])[:8])
        saved = local_sqlite_store.save_check(text, {"claims": claims, "evidence": evidence, "verdict": verdict}, title="Mobile remote check")
        return JSONResponse({"ok": True, "mode": mode, "check_id": saved.get("id"), "claims": claims, "evidence": evidence, "verdict": verdict})

    @app.post("/api/mobile/archive/import-text")
    async def api_mobile_archive_import(request: Request, x_mobile_token: str | None = Header(default=None)):
        ok, error = _require_mobile_token(x_mobile_token)
        if not ok:
            return error
        payload = await request.json()
        imported = import_text_to_archive(str((payload or {}).get("title", "Mobile source")), str((payload or {}).get("text", "")), source_type="mobile_text")
        return JSONResponse({"ok": True, "imported": imported})
