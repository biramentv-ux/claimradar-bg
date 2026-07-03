from pathlib import Path


def test_desktop_artifact_testing_doc_exists():
    doc = Path("docs/DESKTOP_ARTIFACT_TESTING_BG.md").read_text(encoding="utf-8")
    assert "не се изпраща `.exe`" in doc
    assert "test_desktop_artifact.py" in doc
    assert "ClaimRadarBG-Windows-Desktop.zip" in doc
