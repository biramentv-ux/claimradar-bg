#!/usr/bin/env python3
"""Check ClaimRadar BG custom domain readiness.

This script performs practical HTTP checks against the custom domain and the
fallback Hugging Face Space URL. DNS CNAME validation should still be checked in
Hugging Face Space settings or through the domain provider panel.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List

DEFAULT_DOMAIN = "claimradar.dyrakarmy.eu"
DEFAULT_HF_URL = "https://dyrakarmy-claimradar-bg.hf.space"
DEFAULT_ENDPOINTS = ["/health", "/custom-domain/status", "/auth/status", "/product"]


@dataclass
class CheckResult:
    target: str
    ok: bool
    status: int = 0
    latency_ms: float = 0.0
    error: str = ""
    resolved_ips: List[str] | None = None


def resolve_host(host: str) -> List[str]:
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except Exception:
        return []
    return sorted({item[4][0] for item in infos})


def fetch_url(url: str, timeout: float) -> CheckResult:
    started = time.perf_counter()
    request = urllib.request.Request(url, headers={"User-Agent": "ClaimRadarBG-domain-check/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
            response.read(2048)
            return CheckResult(url, 200 <= int(response.status) < 400, int(response.status), round((time.perf_counter() - started) * 1000, 2))
    except urllib.error.HTTPError as exc:
        return CheckResult(url, False, int(exc.code), round((time.perf_counter() - started) * 1000, 2), str(exc))
    except Exception as exc:
        return CheckResult(url, False, 0, round((time.perf_counter() - started) * 1000, 2), f"{type(exc).__name__}: {exc}")


def run_check(domain: str, hf_url: str, endpoints: List[str], timeout: float) -> Dict:
    custom_base = f"https://{domain.strip().strip('/')}"
    host = domain.strip().strip("/")
    resolved_ips = resolve_host(host)
    hf_host = hf_url.replace("https://", "").replace("http://", "").split("/", 1)[0]
    hf_ips = resolve_host(hf_host)

    custom_results = []
    fallback_results = []
    for endpoint in endpoints:
        custom_results.append(fetch_url(custom_base.rstrip("/") + endpoint, timeout))
        fallback_results.append(fetch_url(hf_url.rstrip("/") + endpoint, timeout))

    custom_ok = all(item.ok for item in custom_results)
    fallback_ok = all(item.ok for item in fallback_results)
    return {
        "domain": domain,
        "recommended_dns": {"type": "CNAME", "name": domain, "value": "hf.space"},
        "custom_base_url": custom_base,
        "hf_fallback_url": hf_url,
        "resolved_ips": resolved_ips,
        "hf_resolved_ips": hf_ips,
        "custom_ok": custom_ok,
        "fallback_ok": fallback_ok,
        "passed": bool(custom_ok and fallback_ok),
        "custom_results": [asdict(item) for item in custom_results],
        "fallback_results": [asdict(item) for item in fallback_results],
    }


def write_outputs(report: Dict, out_json: Path, out_md: Path) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# ClaimRadar BG Custom Domain Check",
        "",
        f"- Domain: `{report['domain']}`",
        f"- Custom URL: `{report['custom_base_url']}`",
        f"- HF fallback: `{report['hf_fallback_url']}`",
        f"- Recommended DNS: `CNAME {report['domain']} -> hf.space`",
        f"- Custom OK: `{report['custom_ok']}`",
        f"- Fallback OK: `{report['fallback_ok']}`",
        f"- Passed: `{report['passed']}`",
        "",
        "## Custom domain results",
        "",
    ]
    for item in report["custom_results"]:
        lines.append(f"- `{item['target']}`: status `{item['status']}`, ok `{item['ok']}`, latency `{item['latency_ms']}ms`, error `{item['error']}`")
    lines += ["", "## Hugging Face fallback results", ""]
    for item in report["fallback_results"]:
        lines.append(f"- `{item['target']}`: status `{item['status']}`, ok `{item['ok']}`, latency `{item['latency_ms']}ms`, error `{item['error']}`")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check ClaimRadar BG custom domain readiness.")
    parser.add_argument("--domain", default=os.getenv("CUSTOM_DOMAIN", DEFAULT_DOMAIN))
    parser.add_argument("--hf-url", default=os.getenv("HF_SPACE_URL", DEFAULT_HF_URL))
    parser.add_argument("--endpoints", default=os.getenv("CUSTOM_DOMAIN_CHECK_ENDPOINTS", ",".join(DEFAULT_ENDPOINTS)))
    parser.add_argument("--timeout", type=float, default=float(os.getenv("CUSTOM_DOMAIN_CHECK_TIMEOUT", "20")))
    parser.add_argument("--out-json", default=os.getenv("CUSTOM_DOMAIN_CHECK_OUT_JSON", "custom-domain-results/custom-domain-report.json"))
    parser.add_argument("--out-md", default=os.getenv("CUSTOM_DOMAIN_CHECK_OUT_MD", "custom-domain-results/custom-domain-report.md"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    endpoints = [item.strip() for item in args.endpoints.split(",") if item.strip()]
    report = run_check(args.domain, args.hf_url, endpoints, args.timeout)
    write_outputs(report, Path(args.out_json), Path(args.out_md))
    print(json.dumps({k: report[k] for k in ["domain", "custom_ok", "fallback_ok", "passed", "recommended_dns"]}, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
