from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

REMOTE_SIMPLE_ENABLED = os.getenv("REMOTE_SIMPLE_ENABLED", "1").lower() not in {"0", "false", "no"}
REMOTE_SIMPLE_PORT = int(os.getenv("APP_PORT", "8765"))
REMOTE_SIMPLE_TARGET = os.getenv("REMOTE_SIMPLE_TARGET", f"http://127.0.0.1:{REMOTE_SIMPLE_PORT}")
REMOTE_SIMPLE_DEFAULT_PROVIDER = os.getenv("REMOTE_SIMPLE_DEFAULT_PROVIDER", "cloudflare").strip().lower()
URL_RE = re.compile(r"https://[A-Za-z0-9.-]+(?:trycloudflare\.com|ngrok-free\.app|ngrok\.app|ngrok\.io)")

REMOTE_STATE: Dict[str, Any] = {
    "running": False,
    "provider": "",
    "public_url": "",
    "mobile_url": "",
    "message": "not_started",
    "logs": [],
    "started_at": None,
    "process_pid": None,
}
REMOTE_PROCESS: Optional[subprocess.Popen] = None
REMOTE_LOCK = threading.Lock()


def _append_log(line: str) -> None:
    line = str(line or "").strip()
    if not line:
        return
    with REMOTE_LOCK:
        logs = REMOTE_STATE.setdefault("logs", [])
        logs.append(line[-500:])
        REMOTE_STATE["logs"] = logs[-80:]
        match = URL_RE.search(line)
        if match:
            url = match.group(0).rstrip("/")
            REMOTE_STATE["public_url"] = url
            REMOTE_STATE["mobile_url"] = f"{url}/mobile"
            REMOTE_STATE["message"] = "ready"


def _reader(pipe: Any) -> None:
    try:
        for raw in iter(pipe.readline, ""):
            _append_log(raw)
    except Exception as exc:
        _append_log(f"reader_error: {exc}")


def _which_cloudflared() -> str:
    candidates = [
        os.getenv("REMOTE_CLOUDFLARED_PATH", ""),
        shutil.which("cloudflared") or "",
        str(Path.cwd() / "tools" / "cloudflared.exe"),
        str(Path.cwd() / "cloudflared.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return ""


def _which_ngrok() -> str:
    candidates = [
        os.getenv("REMOTE_NGROK_PATH", ""),
        shutil.which("ngrok") or "",
        str(Path.cwd() / "tools" / "ngrok.exe"),
        str(Path.cwd() / "ngrok.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return ""


def remote_install_help() -> Dict[str, Any]:
    return {
        "cloudflare": {
            "name": "Cloudflare Quick Tunnel",
            "install": "Install cloudflared, then press Start. No domain is required for Quick Tunnel.",
            "command": f"cloudflared tunnel --url {REMOTE_SIMPLE_TARGET}",
            "download_url": "https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/",
        },
        "ngrok": {
            "name": "ngrok",
            "install": "Install ngrok, add your authtoken, then press Start with ngrok.",
            "command": f"ngrok http {REMOTE_SIMPLE_PORT}",
            "download_url": "https://ngrok.com/download",
        },
    }


def _command_for(provider: str) -> tuple[List[str], str]:
    selected = (provider or REMOTE_SIMPLE_DEFAULT_PROVIDER or "cloudflare").strip().lower()
    if selected in {"ngrok", "ng"}:
        exe = _which_ngrok()
        if not exe:
            return [], "ngrok_not_found"
        return [exe, "http", str(REMOTE_SIMPLE_PORT), "--log=stdout"], "ngrok"
    exe = _which_cloudflared()
    if not exe:
        return [], "cloudflared_not_found"
    return [exe, "tunnel", "--url", REMOTE_SIMPLE_TARGET], "cloudflare"


def start_remote_tunnel(provider: str = "") -> Dict[str, Any]:
    global REMOTE_PROCESS
    if not REMOTE_SIMPLE_ENABLED:
        return {"ok": False, "error": "remote_simple_disabled"}
    with REMOTE_LOCK:
        if REMOTE_PROCESS and REMOTE_PROCESS.poll() is None:
            return {"ok": True, "remote": dict(REMOTE_STATE)}
    command, resolved_provider = _command_for(provider)
    if not command:
        with REMOTE_LOCK:
            REMOTE_STATE.update({"running": False, "provider": resolved_provider, "message": resolved_provider, "public_url": "", "mobile_url": ""})
        return {"ok": False, "error": resolved_provider, "help": remote_install_help(), "remote": dict(REMOTE_STATE)}
    with REMOTE_LOCK:
        REMOTE_STATE.update({
            "running": True,
            "provider": resolved_provider,
            "public_url": "",
            "mobile_url": "",
            "message": "starting",
            "logs": [],
            "started_at": time.time(),
            "command_preview": " ".join(command[:1] + command[1:]),
        })
    try:
        REMOTE_PROCESS = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        with REMOTE_LOCK:
            REMOTE_STATE["process_pid"] = REMOTE_PROCESS.pid
        if REMOTE_PROCESS.stdout:
            threading.Thread(target=_reader, args=(REMOTE_PROCESS.stdout,), daemon=True).start()
        if REMOTE_PROCESS.stderr:
            threading.Thread(target=_reader, args=(REMOTE_PROCESS.stderr,), daemon=True).start()
        return {"ok": True, "remote": dict(REMOTE_STATE)}
    except Exception as exc:
        with REMOTE_LOCK:
            REMOTE_STATE.update({"running": False, "message": "failed", "error": str(exc)})
        return {"ok": False, "error": str(exc), "remote": dict(REMOTE_STATE)}


def stop_remote_tunnel() -> Dict[str, Any]:
    global REMOTE_PROCESS
    with REMOTE_LOCK:
        proc = REMOTE_PROCESS
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception as exc:
            _append_log(f"stop_error: {exc}")
    with REMOTE_LOCK:
        REMOTE_PROCESS = None
        REMOTE_STATE.update({"running": False, "message": "stopped", "process_pid": None})
        return {"ok": True, "remote": dict(REMOTE_STATE)}


def remote_status() -> Dict[str, Any]:
    with REMOTE_LOCK:
        if REMOTE_PROCESS and REMOTE_PROCESS.poll() is not None and REMOTE_STATE.get("running"):
            REMOTE_STATE["running"] = False
            REMOTE_STATE["message"] = "process_exited"
        return dict(REMOTE_STATE)


def _page() -> str:
    return """<!doctype html><html lang='bg'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>ClaimRadar Easy Remote</title><style>body{margin:0;font-family:Arial,sans-serif;background:#020617;color:#e5e7eb}.wrap{max-width:920px;margin:auto;padding:22px}.hero{border:1px solid #164e63;border-radius:28px;padding:24px;background:#0f172a}.big{font-size:28px}.step{background:#111827;border:1px solid #164e63;border-radius:22px;padding:18px;margin:14px 0}.btn{font-size:22px;padding:18px 22px;border:0;border-radius:18px;margin:8px 8px 8px 0;font-weight:900;color:#fff;background:#0891b2}.stop{background:#dc2626}.copy{background:#7c3aed}.muted{color:#94a3b8}.link{font-size:20px;word-break:break-all;color:#67e8f9}pre{white-space:pre-wrap;background:#020617;border-radius:14px;padding:12px;max-height:260px;overflow:auto}</style></head><body><main class='wrap'><section class='hero'><h1 class='big'>🌍 Лесен достъп извън Wi‑Fi</h1><p class='muted'>Натискаш един бутон. Получаваш линк. Отваряш го на телефона. Компютърът трябва да остане включен.</p><div class='step'><h2>1) Пусни линк</h2><button class='btn' onclick='start("cloudflare")'>🟢 Старт — най-лесно</button><button class='btn' onclick='start("ngrok")'>🟣 Старт с ngrok</button><button class='btn stop' onclick='stopIt()'>🔴 Стоп</button></div><div class='step'><h2>2) Отвори на телефона</h2><div id='mobile' class='link'>Още няма линк.</div><button class='btn copy' onclick='copyLink()'>📋 Копирай линка</button><p class='muted'>След това въведи PIN от <a href='/mobile/pair' style='color:#67e8f9'>Pair Phone</a>.</p></div><div class='step'><h2>3) Статус</h2><pre id='out'>Зареждам...</pre></div></section></main><script>let current='';async function api(u,o={}){const r=await fetch(u,{headers:{'content-type':'application/json'},...o});return r.json()}async function refresh(){const d=await api('/api/remote-simple/status');current=(d.remote&&d.remote.mobile_url)||'';mobile.textContent=current||'Още няма линк.';out.textContent=JSON.stringify(d,null,2)}async function start(provider){out.textContent='Стартирам...';const d=await api('/api/remote-simple/start',{method:'POST',body:JSON.stringify({provider})});await refresh();if(!d.ok&&d.help){out.textContent=JSON.stringify(d,null,2)+'\n\nНужно е да се инсталира cloudflared или ngrok.'}}async function stopIt(){await api('/api/remote-simple/stop',{method:'POST'});refresh()}async function copyLink(){if(current){await navigator.clipboard.writeText(current);alert('Копирано!')}}setInterval(refresh,2500);refresh()</script></body></html>"""


def register_easy_remote_access_routes(app: FastAPI) -> None:
    @app.get("/remote-simple")
    def remote_simple_page():
        if not REMOTE_SIMPLE_ENABLED:
            return JSONResponse({"ok": False, "error": "remote_simple_disabled"}, status_code=404)
        return HTMLResponse(_page())

    @app.get("/api/remote-simple/status")
    def api_remote_status():
        return JSONResponse({"ok": True, "remote": remote_status(), "help": remote_install_help()})

    @app.post("/api/remote-simple/start")
    async def api_remote_start(request: Request):
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        result = start_remote_tunnel(str((payload or {}).get("provider", REMOTE_SIMPLE_DEFAULT_PROVIDER)))
        return JSONResponse(result, status_code=200 if result.get("ok") else 400)

    @app.post("/api/remote-simple/stop")
    def api_remote_stop():
        return JSONResponse(stop_remote_tunnel())

    @app.get("/api/remote-simple/help")
    def api_remote_help():
        return JSONResponse({"ok": True, "help": remote_install_help()})
