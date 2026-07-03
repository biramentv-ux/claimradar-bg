from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist" / "desktop-backend"
ENTRYPOINT = ROOT / "local_desktop_launch.py"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ClaimRadar BG local backend executable with PyInstaller")
    parser.add_argument("--clean", action="store_true", help="Remove previous desktop backend build")
    parser.add_argument("--name", default="claimradar_backend", help="Output executable name")
    args = parser.parse_args()

    if args.clean and DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)

    try:
        import PyInstaller.__main__  # noqa: F401
    except Exception:
        print("PyInstaller is missing. Install it with: pip install pyinstaller")
        return 2

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--name",
        args.name,
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(ROOT / "build" / "desktop-backend"),
        str(ENTRYPOINT),
    ]
    run(cmd)
    print({"ok": True, "backend_dist": str(DIST_DIR / args.name)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
