from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

PAGE = """
<!doctype html><html lang='bg'><head><meta charset='utf-8'><title>ClaimRadar BG Desktop</title>
<style>body{font-family:Arial;background:#020617;color:#e5e7eb;margin:0}.wrap{max-width:960px;margin:auto;padding:28px}.card{background:#0f172a;border:1px solid #164e63;border-radius:18px;padding:18px;margin:12px 0}a{color:#67e8f9;font-weight:bold}</style></head>
<body><main class='wrap'><h1>ClaimRadar BG Desktop</h1><p>Локален навигационен център.</p>
<div class='card'><a href='/remote-simple'>Easy Remote — извън Wi‑Fi</a><p>Големи бутони: Старт, Копирай линк, Стоп.</p></div>
<div class='card'><a href='/'>Analyze Text</a></div>
<div class='card'><a href='/mobile/pair'>Pair Phone Remote</a><p>Телефонът е дистанционно, а компютърът изпълнява локалните AI задачи.</p></div>
<div class='card'><a href='/mobile'>Mobile Remote UI</a></div>
<div class='card'><a href='/local-ai/models'>Local Model Manager</a></div>
<div class='card'><a href='/api/local-ai/evidence/status'>Evidence Mode Status</a></div>
<div class='card'><a href='/api/local-ai/archive/status'>Local Archive Status</a></div>
<div class='card'><a href='/api/local-ai/transcribe/status'>Transcription Status</a></div>
<div class='card'><a href='/api/local-ai/benchmark/status'>Hardware Benchmark Status</a></div>
</main></body></html>
"""


def register_desktop_ui_routes(app: FastAPI) -> None:
    @app.get('/desktop')
    def desktop_page():
        return HTMLResponse(PAGE)

    @app.get('/local-ai')
    def local_ai_page():
        return HTMLResponse(PAGE)
