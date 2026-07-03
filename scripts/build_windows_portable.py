from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ELECTRON_DIR = ROOT / "desktop" / "electron"
PORTABLE_DIR = ROOT / "dist" / "ClaimRadarBG_Portable"


def run(cmd: list[str], cwd: Path = ROOT) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=cwd)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ClaimRadar BG portable Windows desktop package")
    parser.add_argument("--skip-backend", action="store_true", help="Do not run the PyInstaller backend build")
    parser.add_argument("--skip-electron", action="store_true", help="Do not run npm/electron-builder")
    parser.add_argument("--clean", action="store_true", help="Remove previous portable output")
    args = parser.parse_args()

    if args.clean and PORTABLE_DIR.exists():
        shutil.rmtree(PORTABLE_DIR)

    if not args.skip_backend:
        run([sys.executable, "scripts/build_desktop_backend.py", "--clean"])

    if not args.skip_electron:
        if not shutil.which("npm"):
            print("npm is required for Electron build.")
            return 2
        if not (ELECTRON_DIR / "node_modules").exists():
            run(["npm", "install"], cwd=ELECTRON_DIR)
        run(["npm", "run", "dist"], cwd=ELECTRON_DIR)

    PORTABLE_DIR.mkdir(parents=True, exist_ok=True)
    manifest = PORTABLE_DIR / "README_PORTABLE.txt"
    manifest.write_text(
        "ClaimRadar BG Portable Desktop\n"
        "1) Build backend: python scripts/build_desktop_backend.py\n"
        "2) Build Electron: cd desktop/electron && npm install && npm run dist\n"
        "3) Run portable EXE from dist/desktop when produced by electron-builder.\n",
        encoding="utf-8",
    )
    print({"ok": True, "portable_dir": str(PORTABLE_DIR)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
