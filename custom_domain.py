from __future__ import annotations

import os
from html import escape
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

DEFAULT_CUSTOM_DOMAIN = "claimradar.dyrakarmy.eu"
DEFAULT_ROOT_DOMAIN = "dyrakarmy.eu"
DEFAULT_HF_SPACE_URL = "https://dyrakarmy-claimradar-bg.hf.space"
HF_CNAME_TARGET = "hf.space"


def custom_domain_config() -> Dict[str, Any]:
    custom_domain = os.getenv("CUSTOM_DOMAIN", DEFAULT_CUSTOM_DOMAIN).strip() or DEFAULT_CUSTOM_DOMAIN
    root_domain = os.getenv("ROOT_DOMAIN", DEFAULT_ROOT_DOMAIN).strip() or DEFAULT_ROOT_DOMAIN
    public_base_url = os.getenv("PUBLIC_BASE_URL", f"https://{custom_domain}").strip() or f"https://{custom_domain}"
    hf_space_url = os.getenv("HF_SPACE_URL", DEFAULT_HF_SPACE_URL).strip() or DEFAULT_HF_SPACE_URL
    canonical_host = public_base_url.replace("https://", "").replace("http://", "").split("/", 1)[0]
    return {
        "custom_domain": custom_domain,
        "root_domain": root_domain,
        "public_base_url": public_base_url,
        "canonical_host": canonical_host,
        "hf_space_url": hf_space_url,
        "hf_cname_target": HF_CNAME_TARGET,
        "recommended_dns_record": {
            "type": "CNAME",
            "host": custom_domain.replace(f".{root_domain}", ""),
            "name": custom_domain,
            "value": HF_CNAME_TARGET,
            "ttl": 3600,
        },
        "root_domain_note": "For Hugging Face Spaces, the safest setup is a subdomain CNAME such as claimradar.dyrakarmy.eu -> hf.space. Apex/root domains may require ALIAS/ANAME support from the DNS provider.",
        "required_huggingface_setting": {
            "space_settings": "Custom Domain",
            "value": custom_domain,
        },
        "recommended_hf_variables": {
            "PUBLIC_BASE_URL": public_base_url,
            "CUSTOM_DOMAIN": custom_domain,
            "ROOT_DOMAIN": root_domain,
            "HF_SPACE_URL": hf_space_url,
        },
    }


def custom_domain_html() -> str:
    cfg = custom_domain_config()
    record = cfg["recommended_dns_record"]
    return f"""<!doctype html>
<html lang="bg">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Custom Domain · ClaimRadar BG</title>
  <style>
    body{{margin:0;background:#020617;color:#e5e7eb;font-family:Arial,sans-serif}}main{{max-width:980px;margin:auto;padding:28px 18px 70px}}.hero,.card{{border:1px solid rgba(34,211,238,.25);border-radius:24px;background:linear-gradient(135deg,rgba(2,6,23,.96),rgba(30,27,75,.74));box-shadow:0 0 34px rgba(34,211,238,.14)}}.hero{{padding:30px}}.kicker{{color:#67e8f9;text-transform:uppercase;letter-spacing:.16em;font-weight:900;font-size:12px}}h1{{font-size:46px;margin:10px 0;color:#fff}}h2{{color:#fff}}p,li{{color:#cbd5e1;line-height:1.65}}code,pre{{background:rgba(15,23,42,.78);border:1px solid rgba(34,211,238,.18);border-radius:12px;color:#e0f2fe}}code{{padding:2px 6px}}pre{{padding:14px;overflow:auto}}.card{{padding:18px;margin-top:16px}}.ok{{color:#86efac}}.warn{{color:#fde68a}}a{{color:#67e8f9}}
  </style>
</head>
<body><main>
  <section class="hero">
    <div class="kicker">ClaimRadar BG · custom domain</div>
    <h1>{escape(cfg['custom_domain'])}</h1>
    <p>Препоръчителният custom domain за проекта е <code>{escape(cfg['public_base_url'])}</code>. Старият Hugging Face URL остава fallback: <code>{escape(cfg['hf_space_url'])}</code>.</p>
  </section>
  <section class="card"><h2>DNS запис в SuperHosting</h2><pre>Type:  {escape(record['type'])}
Host:  {escape(record['host'])}
Name:  {escape(record['name'])}
Value: {escape(record['value'])}
TTL:   {record['ttl']}</pre><p class="warn">Не насочвай към IP адрес. Hugging Face Spaces изисква CNAME към <code>hf.space</code>.</p></section>
  <section class="card"><h2>Hugging Face Space settings</h2><p>В Space Settings → Custom Domain добави:</p><pre>{escape(cfg['custom_domain'])}</pre></section>
  <section class="card"><h2>Hugging Face Variables</h2><pre>PUBLIC_BASE_URL={escape(cfg['public_base_url'])}
CUSTOM_DOMAIN={escape(cfg['custom_domain'])}
ROOT_DOMAIN={escape(cfg['root_domain'])}
HF_SPACE_URL={escape(cfg['hf_space_url'])}</pre></section>
  <section class="card"><h2>Проверки</h2><ul><li><a href="/custom-domain/status">/custom-domain/status</a></li><li><a href="/api/custom-domain/status">/api/custom-domain/status</a></li><li><a href="/health">/health</a></li></ul></section>
</main></body></html>"""


def register_custom_domain_routes(app: FastAPI) -> None:
    @app.get("/custom-domain", response_class=HTMLResponse)
    def custom_domain_page():
        return HTMLResponse(custom_domain_html())

    @app.get("/domain", response_class=HTMLResponse)
    def domain_page_alias():
        return HTMLResponse(custom_domain_html())

    @app.get("/custom-domain/status")
    def custom_domain_status():
        return JSONResponse({"ok": True, "custom_domain": custom_domain_config()})

    @app.get("/domain/status")
    def domain_status_alias():
        return JSONResponse({"ok": True, "custom_domain": custom_domain_config()})

    @app.get("/api/custom-domain/status")
    def api_custom_domain_status():
        return JSONResponse({"ok": True, "custom_domain": custom_domain_config()})
