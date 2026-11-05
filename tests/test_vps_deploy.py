import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VPS = ROOT / "deploy" / "vps"


def test_install_script_is_valid_bash():
    result = subprocess.run(["bash", "-n", str(VPS / "install.sh")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_install_script_has_no_hardcoded_secrets_and_generates_keys():
    text = (VPS / "install.sh").read_text(encoding="utf-8")
    assert not re.search(r"sk-[A-Za-z0-9]{20,}", text)
    assert not re.search(r"hf_[A-Za-z0-9]{20,}", text)
    for key in ("OWNER_KEY", "ADMIN_KEY", "AUTH_TOKEN_SALT", "RATE_LIMIT_HASH_SALT"):
        assert f"{key}=" in text
    assert "chmod 600 .env" in text
    assert 'OWASP_FRAME_ANCESTORS="\'self\'"' in text


def test_compose_only_publishes_caddy_ports():
    text = (VPS / "docker-compose.yml").read_text(encoding="utf-8")
    published = re.findall(r'-\s*"(\d+):\d+(?:/udp)?"', text)
    assert sorted(set(published)) == ["443", "80"]
    assert "7860:7860" not in text
    assert 'DESKTOP_FEATURES_ENABLED: "0"' in text
    assert "claimradar_data:/app/data" in text


def test_caddyfile_proxies_to_app():
    text = (VPS / "Caddyfile").read_text(encoding="utf-8")
    assert "{$DOMAIN}" in text
    assert "reverse_proxy app:7860" in text


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker CLI not installed")
def test_compose_config_renders(tmp_path):
    env = tmp_path / ".env"
    env.write_text("DOMAIN=claimradar.dyrakarmy.eu\nOWASP_FRAME_ANCESTORS=\"'self'\"\n", encoding="utf-8")
    result = subprocess.run(
        ["docker", "compose", "-f", str(VPS / "docker-compose.yml"), "--env-file", str(env), "config"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "claimradar.dyrakarmy.eu" in result.stdout
