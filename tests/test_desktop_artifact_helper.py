from pathlib import Path


def test_desktop_artifact_helper_rejects_7z_and_checks_backend_layout():
    helper = Path("scripts/test_desktop_artifact.py").read_text(encoding="utf-8")
    assert "Unsupported archive" in helper
    assert ".7z" in helper
    assert "claimradar_backend.exe" in helper
    assert "api/local-ai/status" in helper
    assert "runtime smoke test requires Windows" in helper
