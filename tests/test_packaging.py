import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_package_extension_script_builds_zip():
    result = subprocess.run(
        [sys.executable, "scripts/package_extension.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "Built:" in result.stdout

    manifest = json.loads((ROOT / "extension" / "manifest.json").read_text(encoding="utf-8"))
    zip_path = ROOT / "dist" / f"claimradar-bg-extension-v{manifest['version']}.zip"
    assert zip_path.exists()

    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())

    required = {
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
    }
    assert required.issubset(names)


def test_generated_icons_are_png_files():
    for size in [16, 32, 48, 128]:
        path = ROOT / "extension" / "icons" / f"icon{size}.png"
        assert path.exists()
        assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
