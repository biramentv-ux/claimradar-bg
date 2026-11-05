"""The public server / Hugging Face Space must not expose desktop-only features.

Runs in a subprocess so the import-time DESKTOP_FEATURES_ENABLED flag is
evaluated with a clean environment, independent of the rest of the suite.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROBE = r"""
import json, sys
from fastapi.testclient import TestClient
import auth_launch
client = TestClient(auth_launch.app)
paths = {
    "start": client.post("/api/remote-simple/start", json={"provider": "cloudflare"}).status_code,
    "remote_page": client.get("/remote-simple").status_code,
    "mobile": client.get("/api/mobile/status").status_code,
    "health": client.get("/health").status_code,
    "loaded": "easy_remote_access" in sys.modules,
    "flag": auth_launch.DESKTOP_FEATURES_ENABLED,
}
print("RESULT" + json.dumps(paths))
"""


def run_probe(extra_env):
    env = {k: v for k, v in os.environ.items() if k not in {"DESKTOP_FEATURES_ENABLED", "SPACE_ID"}}
    env.update({"DB_ENABLED": "0", "RATE_LIMIT_ENABLED": "0", "WHISPER_MODEL_SIZE": "tiny"})
    env.update(extra_env)
    out = subprocess.run([sys.executable, "-c", PROBE], cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
    line = [l for l in out.stdout.splitlines() if l.startswith("RESULT")]
    assert line, out.stderr[-2000:]
    return json.loads(line[-1][len("RESULT"):])


def test_huggingface_space_hides_desktop_and_tunnel_routes():
    result = run_probe({"SPACE_ID": "DyrakArmy/claimradar-bg"})
    assert result["flag"] is False
    assert result["loaded"] is False
    assert result["health"] == 200
    for key in ("start", "remote_page", "mobile"):
        assert result[key] in {404, 405}, (key, result[key])


def test_explicit_server_mode_hides_tunnel_start():
    result = run_probe({"DESKTOP_FEATURES_ENABLED": "0"})
    assert result["flag"] is False
    assert result["start"] in {404, 405}


def test_dockerfile_and_sync_disable_desktop_features():
    assert "DESKTOP_FEATURES_ENABLED=0" in (ROOT / "Dockerfile").read_text(encoding="utf-8")
    sync = (ROOT / ".github" / "workflows" / "sync-to-hf.yml").read_text(encoding="utf-8")
    assert '--delete "easy_remote_access.py"' in sync
    assert '--exclude "mobile_remote_control.py"' in sync
