#!/usr/bin/env python3
"""Small production-safe HTTP load test for ClaimRadar BG.

Uses only the Python standard library so it can run in GitHub Actions without
extra dependencies. The default profile is intentionally gentle and is meant to
verify live Hugging Face availability, latency and endpoint stability, not to
stress or attack the service.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List

DEFAULT_ENDPOINTS = [
    "/health",
    "/product",
    "/auth/status",
    "/db/status",
    "/rate-limit/status",
    "/monitoring/status",
    "/api/jobs/stats",
]


@dataclass
class Sample:
    endpoint: str
    url: str
    ok: bool
    status: int
    latency_ms: float
    bytes_read: int
    error: str = ""


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 2)
    k = (len(ordered) - 1) * pct
    floor = math.floor(k)
    ceil = math.ceil(k)
    if floor == ceil:
        return round(ordered[int(k)], 2)
    return round(ordered[floor] * (ceil - k) + ordered[ceil] * (k - floor), 2)


def fetch_once(base_url: str, endpoint: str, timeout: float, auth_header: str = "") -> Sample:
    url = base_url.rstrip("/") + endpoint
    headers = {
        "User-Agent": "ClaimRadarBG-load-test/1.0",
        "Accept": "application/json,text/html,text/plain,*/*",
    }
    if auth_header:
        headers["Authorization"] = auth_header
    request = urllib.request.Request(url, headers=headers, method="GET")
    started = time.perf_counter()
    status = 0
    size = 0
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            body = response.read(4096)
            size = len(body)
            ok = 200 <= status < 400
            return Sample(endpoint, url, ok, status, round((time.perf_counter() - started) * 1000, 2), size)
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        try:
            body = exc.read(2048)
            size = len(body)
        except Exception:
            size = 0
        return Sample(endpoint, url, False, status, round((time.perf_counter() - started) * 1000, 2), size, str(exc))
    except Exception as exc:
        return Sample(endpoint, url, False, status, round((time.perf_counter() - started) * 1000, 2), size, f"{type(exc).__name__}: {exc}")


def run_load_test(args: argparse.Namespace) -> Dict:
    endpoints = [item.strip() for item in args.endpoints.split(",") if item.strip()]
    total_requests = max(1, int(args.requests))
    concurrency = max(1, min(int(args.concurrency), total_requests))
    timeout = float(args.timeout)
    auth_header = f"Bearer {args.auth_token}" if args.auth_token else ""

    print(f"Target: {args.base_url}")
    print(f"Endpoints: {', '.join(endpoints)}")
    print(f"Requests: {total_requests} | Concurrency: {concurrency} | Timeout: {timeout}s")

    warmup_samples: List[Sample] = []
    if args.warmup:
        print("Warmup...")
        for endpoint in endpoints:
            sample = fetch_once(args.base_url, endpoint, timeout, auth_header)
            warmup_samples.append(sample)
            print(f"  {endpoint}: status={sample.status} latency={sample.latency_ms}ms ok={sample.ok}")

    samples: List[Sample] = []
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = []
        for idx in range(total_requests):
            endpoint = endpoints[idx % len(endpoints)]
            futures.append(executor.submit(fetch_once, args.base_url, endpoint, timeout, auth_header))
        for future in as_completed(futures):
            sample = future.result()
            samples.append(sample)
            if args.verbose:
                print(f"{sample.endpoint}: {sample.status} {sample.latency_ms}ms ok={sample.ok} {sample.error}")
    duration_seconds = max(0.001, time.perf_counter() - started)

    latencies = [sample.latency_ms for sample in samples]
    ok_samples = [sample for sample in samples if sample.ok]
    failed_samples = [sample for sample in samples if not sample.ok]
    status_counts: Dict[str, int] = {}
    endpoint_counts: Dict[str, Dict[str, int]] = {}
    for sample in samples:
        status_counts[str(sample.status)] = status_counts.get(str(sample.status), 0) + 1
        endpoint_counts.setdefault(sample.endpoint, {"total": 0, "ok": 0, "failed": 0})
        endpoint_counts[sample.endpoint]["total"] += 1
        endpoint_counts[sample.endpoint]["ok" if sample.ok else "failed"] += 1

    summary = {
        "target": args.base_url,
        "endpoints": endpoints,
        "profile": args.profile,
        "requests": total_requests,
        "concurrency": concurrency,
        "timeout_seconds": timeout,
        "duration_seconds": round(duration_seconds, 3),
        "requests_per_second": round(total_requests / duration_seconds, 3),
        "ok": len(ok_samples),
        "failed": len(failed_samples),
        "error_rate": round(len(failed_samples) / total_requests, 4),
        "status_counts": status_counts,
        "endpoint_counts": endpoint_counts,
        "latency_ms": {
            "min": round(min(latencies), 2) if latencies else 0,
            "max": round(max(latencies), 2) if latencies else 0,
            "mean": round(statistics.mean(latencies), 2) if latencies else 0,
            "median": round(statistics.median(latencies), 2) if latencies else 0,
            "p90": percentile(latencies, 0.90),
            "p95": percentile(latencies, 0.95),
            "p99": percentile(latencies, 0.99),
        },
        "thresholds": {
            "max_error_rate": args.max_error_rate,
            "max_p95_ms": args.max_p95_ms,
        },
        "warmup": [asdict(sample) for sample in warmup_samples],
        "samples": [asdict(sample) for sample in samples],
    }

    passed = summary["error_rate"] <= args.max_error_rate and summary["latency_ms"]["p95"] <= args.max_p95_ms
    summary["passed"] = bool(passed)
    return summary


def write_report(summary: Dict, out_json: Path, out_md: Path) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# ClaimRadar BG Load Test Report",
        "",
        f"- Target: `{summary['target']}`",
        f"- Profile: `{summary['profile']}`",
        f"- Requests: `{summary['requests']}`",
        f"- Concurrency: `{summary['concurrency']}`",
        f"- Duration: `{summary['duration_seconds']}s`",
        f"- RPS: `{summary['requests_per_second']}`",
        f"- OK: `{summary['ok']}`",
        f"- Failed: `{summary['failed']}`",
        f"- Error rate: `{summary['error_rate']}`",
        f"- Passed: `{summary['passed']}`",
        "",
        "## Latency",
        "",
    ]
    for key, value in summary["latency_ms"].items():
        lines.append(f"- {key}: `{value} ms`")
    lines += ["", "## Status counts", ""]
    for status, count in sorted(summary["status_counts"].items()):
        lines.append(f"- {status}: `{count}`")
    lines += ["", "## Endpoint counts", ""]
    for endpoint, counts in summary["endpoint_counts"].items():
        lines.append(f"- `{endpoint}`: total `{counts['total']}`, ok `{counts['ok']}`, failed `{counts['failed']}`")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a gentle real HTTP load test against ClaimRadar BG.")
    parser.add_argument("--base-url", default=os.getenv("LOAD_TEST_BASE_URL", "https://dyrakarmy-claimradar-bg.hf.space"))
    parser.add_argument("--endpoints", default=os.getenv("LOAD_TEST_ENDPOINTS", ",".join(DEFAULT_ENDPOINTS)))
    parser.add_argument("--requests", type=int, default=int(os.getenv("LOAD_TEST_REQUESTS", "70")))
    parser.add_argument("--concurrency", type=int, default=int(os.getenv("LOAD_TEST_CONCURRENCY", "5")))
    parser.add_argument("--timeout", type=float, default=float(os.getenv("LOAD_TEST_TIMEOUT", "25")))
    parser.add_argument("--max-error-rate", type=float, default=float(os.getenv("LOAD_TEST_MAX_ERROR_RATE", "0.20")))
    parser.add_argument("--max-p95-ms", type=float, default=float(os.getenv("LOAD_TEST_MAX_P95_MS", "15000")))
    parser.add_argument("--profile", default=os.getenv("LOAD_TEST_PROFILE", "gentle"))
    parser.add_argument("--auth-token", default=os.getenv("LOAD_TEST_AUTH_TOKEN", ""))
    parser.add_argument("--out-json", default=os.getenv("LOAD_TEST_OUT_JSON", "load-test-results/load-test-report.json"))
    parser.add_argument("--out-md", default=os.getenv("LOAD_TEST_OUT_MD", "load-test-results/load-test-report.md"))
    parser.add_argument("--no-warmup", action="store_false", dest="warmup")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run_load_test(args)
    write_report(summary, Path(args.out_json), Path(args.out_md))
    print(json.dumps({k: summary[k] for k in ["target", "requests", "concurrency", "ok", "failed", "error_rate", "latency_ms", "passed"]}, ensure_ascii=False, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
