import os
import uuid

os.environ.setdefault("DB_ENABLED", "0")
os.environ.setdefault("RATE_LIMIT_ENABLED", "0")
os.environ.setdefault("MONITORING_ENABLED", "1")
os.environ.setdefault("REQUEST_LOG_ENABLED", "0")
os.environ.setdefault("AUTH_ENABLED", "1")
os.environ.setdefault("ADMIN_KEY", "test-admin-key")
os.environ.setdefault("WHISPER_MODEL_SIZE", "tiny")
os.environ.setdefault("WHISPER_DEVICE", "cpu")
os.environ.setdefault("WHISPER_COMPUTE_TYPE", "int8")

from fastapi.testclient import TestClient

import app as app_module
import auth_launch
from evidence_export import enrich_check_record, score_evidence_item

client = TestClient(auth_launch.app)


def make_record(check_id: str):
    record = {
        "id": check_id,
        "title": "Export Test",
        "mode": "AI verdict",
        "created_at": app_module.now_iso(),
        "visibility": "public",
        "text_preview": "Инфлацията през 2024 година е 10 процента.",
        "copy_text": "Export test copy",
        "items": [
            {
                "claim": "Инфлацията през 2024 година е 10 процента.",
                "topic": "инфлация",
                "verdict": "Нужен контекст",
                "confidence": 65,
                "citations": [1],
                "short_reason": "Тестов evidence export.",
                "evidence": [
                    {
                        "source": "НСИ",
                        "title": "Индекс на потребителските цени 2024",
                        "url": "https://www.nsi.bg/bg/content/test",
                        "snippet": "Инфлация и данни за 2024 година 10 процента.",
                        "manual": False,
                    }
                ],
            }
        ],
    }
    app_module.append_jsonl(app_module.CHECKS_FILE, record)
    return record


def test_evidence_quality_scoring_prefers_official_sources():
    quality = score_evidence_item(
        "Инфлацията през 2024 година е 10 процента.",
        {
            "source": "НСИ",
            "title": "Инфлация 2024",
            "url": "https://www.nsi.bg/bg/content/test",
            "snippet": "Инфлация 2024 10 процента",
        },
        cited=True,
    )
    assert quality["score"] >= 85
    assert quality["label"] in {"силно evidence", "добро evidence"}
    assert quality["domain"] == "nsi.bg"


def test_enrich_check_record_adds_quality_and_export_links():
    bundle = enrich_check_record(make_record("exportbundle" + uuid.uuid4().hex[:6]))
    assert bundle["evidence_quality_summary"]["items_scored"] == 1
    assert bundle["items"][0]["evidence_quality"]["score"] >= 70
    assert bundle["export_links"]["markdown"].endswith(".md")
    assert bundle["export_links"]["pdf"].endswith(".pdf")


def test_export_endpoints_return_json_markdown_and_pdf():
    check_id = "export" + uuid.uuid4().hex[:8]
    make_record(check_id)

    data = client.get(f"/api/export/check/{check_id}")
    assert data.status_code == 200
    payload = data.json()
    assert payload["ok"] is True
    assert payload["export"]["id"] == check_id
    assert payload["export"]["items"][0]["evidence"][0]["quality"]["score"] >= 70

    md = client.get(f"/export/check/{check_id}.md")
    assert md.status_code == 200
    assert "text/markdown" in md.headers["content-type"]
    assert "Evidence quality" in md.text
    assert "НСИ" in md.text

    pdf = client.get(f"/export/check/{check_id}.pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")


def test_private_export_requires_admin_key():
    check_id = "exportprivate" + uuid.uuid4().hex[:6]
    record = make_record(check_id)
    record["visibility"] = "private"
    app_module.append_jsonl(app_module.CHECKS_FILE, record)
    app_module.append_jsonl(app_module.DATA_DIR / "visibility.jsonl", {"id": check_id, "visibility": "private", "updated_at": app_module.now_iso()})

    denied = client.get(f"/api/export/check/{check_id}")
    assert denied.status_code == 403

    allowed = client.get(f"/api/export/check/{check_id}?admin_key=test-admin-key")
    assert allowed.status_code == 200
    assert allowed.json()["ok"] is True
