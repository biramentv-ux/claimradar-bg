#!/usr/bin/env python3
"""Build a Chrome/Edge-ready ZIP for the ClaimRadar BG extension.

This script uses only the Python standard library. It generates PNG icons,
validates required files, and creates dist/claimradar-bg-extension-v<version>.zip.
"""

from __future__ import annotations

import json
import os
import struct
import zlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "extension"
DIST = ROOT / "dist"
ICONS = EXT / "icons"

REQUIRED_FILES = [
    "manifest.json",
    "popup.html",
    "popup.js",
    "content.js",
    "audio_controls.js",
    "service_worker.js",
    "offscreen.html",
    "offscreen.js",
    "PRIVACY_POLICY.md",
]

PACKAGE_FILES = [
    "manifest.json",
    "popup.html",
    "popup.js",
    "content.js",
    "audio_controls.js",
    "service_worker.js",
    "offscreen.html",
    "offscreen.js",
    "PRIVACY_POLICY.md",
    "icons/icon16.png",
    "icons/icon32.png",
    "icons/icon48.png",
    "icons/icon128.png",
]


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def write_png(path: Path, size: int) -> None:
    """Generate a simple neon radar PNG icon without external dependencies."""
    rows = []
    cx = cy = (size - 1) / 2
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            dx = x - cx
            dy = y - cy
            d = (dx * dx + dy * dy) ** 0.5
            ring = abs(d - size * 0.34) < max(1.0, size * 0.025)
            inner = d < size * 0.20
            sweep = abs(dy - dx * 0.35) < max(1.0, size * 0.035) and d < size * 0.42
            glow = max(0, 1 - d / (size * 0.70))
            if ring or sweep:
                r, g, b, a = 34, 211, 238, 255
            elif inner:
                r, g, b, a = 168, 85, 247, 255
            else:
                r = int(2 + 18 * glow)
                g = int(6 + 60 * glow)
                b = int(23 + 90 * glow)
                a = 255
            row.extend([r, g, b, a])
        rows.append(bytes(row))
    raw = b"".join(rows)
    data = b"\x89PNG\r\n\x1a\n"
    data += png_chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    data += png_chunk(b"IDAT", zlib.compress(raw, 9))
    data += png_chunk(b"IEND", b"")
    path.write_bytes(data)


def generate_icons() -> None:
    ICONS.mkdir(parents=True, exist_ok=True)
    for size in (16, 32, 48, 128):
        write_png(ICONS / f"icon{size}.png", size)


def read_manifest() -> dict:
    return json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))


def validate() -> dict:
    manifest = read_manifest()
    missing = [name for name in REQUIRED_FILES if not (EXT / name).exists()]
    if missing:
        raise SystemExit(f"Missing extension files: {', '.join(missing)}")
    for icon in ("16", "32", "48", "128"):
        path = manifest.get("icons", {}).get(icon)
        if not path or not (EXT / path).exists():
            raise SystemExit(f"Missing manifest icon {icon}: {path}")
    return manifest


def build_zip(manifest: dict) -> Path:
    DIST.mkdir(exist_ok=True)
    version = manifest.get("version", "dev")
    out = DIST / f"claimradar-bg-extension-v{version}.zip"
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in PACKAGE_FILES:
            path = EXT / rel
            if path.exists():
                zf.write(path, arcname=rel)
    return out


def main() -> None:
    os.chdir(ROOT)
    generate_icons()
    manifest = validate()
    out = build_zip(manifest)
    print(f"Built: {out}")
    print("Upload this ZIP to Chrome Web Store or Edge Add-ons after final manual review.")


if __name__ == "__main__":
    main()
