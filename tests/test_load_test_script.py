import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_load_test_script_help():
    result = subprocess.run(
        [sys.executable, "scripts/load_test.py", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "Run a gentle real HTTP load test" in result.stdout
    assert "--base-url" in result.stdout
    assert "--requests" in result.stdout
    assert "--concurrency" in result.stdout


def test_load_test_script_contains_safe_default_profile():
    content = (ROOT / "scripts" / "load_test.py").read_text(encoding="utf-8")
    assert "https://dyrakarmy-claimradar-bg.hf.space" in content
    assert "LOAD_TEST_REQUESTS" in content
    assert "LOAD_TEST_CONCURRENCY" in content
    assert "DEFAULT_ENDPOINTS" in content
    assert "/health" in content
    assert "/rate-limit/status" in content


def test_load_test_workflow_uploads_artifact():
    workflow = (ROOT / ".github" / "workflows" / "load-test.yml").read_text(encoding="utf-8")
    assert "Real Load Test" in workflow
    assert "python scripts/load_test.py" in workflow
    assert "claimradar-bg-load-test-report" in workflow
    assert "workflow_dispatch" in workflow
