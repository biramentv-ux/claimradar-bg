import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_check_custom_domain_help():
    result = subprocess.run(
        [sys.executable, "scripts/check_custom_domain.py", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "Check ClaimRadar BG custom domain readiness" in result.stdout
    assert "--domain" in result.stdout
    assert "--hf-url" in result.stdout


def test_custom_domain_files_contain_expected_domain_and_target():
    files = [
        ROOT / "custom_domain.py",
        ROOT / "scripts" / "check_custom_domain.py",
        ROOT / "docs" / "CUSTOM_DOMAIN_BG.md",
        ROOT / ".github" / "workflows" / "custom-domain-check.yml",
    ]
    for path in files:
        content = path.read_text(encoding="utf-8")
        assert "claimradar.dyrakarmy.eu" in content
    assert "hf.space" in (ROOT / "docs" / "CUSTOM_DOMAIN_BG.md").read_text(encoding="utf-8")
