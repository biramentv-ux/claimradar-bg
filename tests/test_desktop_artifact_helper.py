from pathlib import Path


def test_desktop_artifact_helper_supports_zip_and_7z_layout_checks():
    helper = Path("scripts/test_desktop_artifact.py").read_text(encoding="utf-8")
    assert 'SUPPORTED_ARCHIVES = {".zip", ".7z"}' in helper
    assert "py7zr" in helper
    assert "7z artifact support requires py7zr" in helper
    assert "claimradar_backend.exe" in helper
    assert "api/local-ai/status" in helper
    assert "runtime smoke test requires Windows" in helper
    assert "Unsafe archive paths detected" in helper
