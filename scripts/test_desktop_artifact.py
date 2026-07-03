from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List

SUPPORTED_ARCHIVES = {".zip", ".7z"}
UNSUPPORTED_ARCHIVES = {".rar", ".tar", ".gz", ".xz"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def list_tree(root: Path, limit: int = 5000) -> List[str]:
    rows: List[str] = []
    for path in root.rglob("*"):
        if len(rows) >= limit:
            break
        if path.is_file():
            rows.append(str(path.relative_to(root)).replace("\\", "/"))
    return sorted(rows)


def _safe_destination(root: Path, member_name: str) -> bool:
    destination = (root / member_name).resolve()
    try:
        destination.relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _validate_zip_members(archive: Path, target: Path) -> None:
    with zipfile.ZipFile(archive) as zf:
        bad = [name for name in zf.namelist() if not _safe_destination(target, name)]
        if bad:
            raise SystemExit(f"Unsafe archive paths detected: {bad[:5]}")


def _extract_zip(archive: Path, target: Path) -> None:
    _validate_zip_members(archive, target)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(target)


def _extract_7z(archive: Path, target: Path) -> None:
    try:
        import py7zr
    except Exception as exc:
        raise SystemExit("7z artifact support requires py7zr. Install with: pip install py7zr") from exc
    with py7zr.SevenZipFile(archive, mode="r") as zf:
        names = zf.getnames()
        bad = [name for name in names if not _safe_destination(target, name)]
        if bad:
            raise SystemExit(f"Unsafe archive paths detected: {bad[:5]}")
        zf.extractall(path=target)


def extract_if_supported(artifact: Path, workdir: Path) -> Path:
    suffix = artifact.suffix.lower()
    if artifact.is_dir():
        return artifact
    if suffix in UNSUPPORTED_ARCHIVES:
        raise SystemExit(f"Unsupported archive {suffix}. Expected .zip, .7z, or extracted folder.")
    if suffix not in SUPPORTED_ARCHIVES:
        raise SystemExit(f"Unsupported artifact type {suffix}. Expected .zip, .7z, or extracted folder.")
    target = workdir / "artifact"
    target.mkdir(parents=True, exist_ok=True)
    if suffix == ".7z":
        _extract_7z(artifact, target)
    else:
        _extract_zip(artifact, target)
    return target


def find_files(root: Path) -> Dict[str, List[str]]:
    files = list_tree(root)
    return {
        "all_sample": files[:300],
        "desktop_exes": [p for p in files if p.lower().endswith(".exe") and "claimradar" in p.lower()],
        "backend_exes": [p for p in files if p.lower().endswith("claimradar_backend.exe")],
        "electron_main": [p for p in files if p.replace("\\", "/").endswith("resources/app.asar.unpacked/main.js") or p.endswith("main.js")],
        "backend_dirs": [p for p in files if "backend" in p.lower()][:200],
    }


def layout_checks(root: Path) -> Dict[str, Any]:
    found = find_files(root)
    errors: List[str] = []
    warnings: List[str] = []
    if not found["desktop_exes"]:
        errors.append("No ClaimRadar desktop .exe found.")
    if not found["backend_exes"]:
        errors.append("No claimradar_backend.exe found. Electron will show fetch failed if backend is missing.")
    if found["desktop_exes"] and found["backend_exes"]:
        warnings.append("Layout contains both desktop exe and backend exe. Runtime smoke test is still required on Windows.")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "found": found}


def windows_runtime_smoke(root: Path, seconds: int = 20) -> Dict[str, Any]:
    if platform.system().lower() != "windows":
        return {"skipped": True, "reason": "runtime smoke test requires Windows"}
    candidates = find_files(root)["backend_exes"]
    if not candidates:
        return {"ok": False, "error": "backend_exe_not_found"}
    exe = root / candidates[0]
    env = os.environ.copy()
    env.setdefault("APP_PORT", "8765")
    env.setdefault("LOCAL_AI_ENABLED", "1")
    proc = subprocess.Popen([str(exe)], cwd=str(exe.parent), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        import urllib.request

        deadline = __import__("time").time() + seconds
        last_error = ""
        while __import__("time").time() < deadline:
            try:
                with urllib.request.urlopen("http://127.0.0.1:8765/api/local-ai/status", timeout=2) as res:
                    body = res.read().decode("utf-8", errors="ignore")
                    return {"ok": True, "status_code": res.status, "body_sample": body[:1000]}
            except Exception as exc:
                last_error = str(exc)
                __import__("time").sleep(1)
        return {"ok": False, "error": last_error, "logs": (proc.stdout.read(4000) if proc.stdout else "")}
    finally:
        proc.terminate()


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test ClaimRadar BG desktop artifact layout")
    parser.add_argument("artifact", help="Path to GitHub artifact .zip/.7z or extracted folder")
    parser.add_argument("--runtime", action="store_true", help="Run backend runtime smoke test when executed on Windows")
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    args = parser.parse_args()

    artifact = Path(args.artifact).expanduser().resolve()
    if not artifact.exists():
        raise SystemExit(f"Artifact not found: {artifact}")
    report: Dict[str, Any] = {"artifact": str(artifact), "size_bytes": artifact.stat().st_size if artifact.is_file() else None, "sha256": sha256(artifact) if artifact.is_file() else None}
    with tempfile.TemporaryDirectory() as tmp:
        root = extract_if_supported(artifact, Path(tmp))
        report["root"] = str(root)
        report["layout"] = layout_checks(root)
        if args.runtime:
            report["runtime"] = windows_runtime_smoke(root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("layout", {}).get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
