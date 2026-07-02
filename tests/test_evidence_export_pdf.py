import os

os.environ.setdefault("DB_ENABLED", "0")
os.environ.setdefault("RATE_LIMIT_ENABLED", "0")
os.environ.setdefault("MONITORING_ENABLED", "1")
os.environ.setdefault("REQUEST_LOG_ENABLED", "0")
os.environ.setdefault("AUTH_ENABLED", "1")
os.environ.setdefault("WHISPER_MODEL_SIZE", "tiny")
os.environ.setdefault("WHISPER_DEVICE", "cpu")
os.environ.setdefault("WHISPER_COMPUTE_TYPE", "int8")

from evidence_export import check_to_markdown, enrich_check_record, markdown_to_pdf_bytes


def test_markdown_to_pdf_bytes_handles_evidence_table():
    markdown = """# ClaimRadar BG report

## Claims and evidence

| # | Source | Quality | Title | URL |
|---:|---|---:|---|---|
| 1 | НСИ | 95 | Индекс на потребителските цени | https://nsi.bg |

Кратко обяснение.
"""
    pdf = markdown_to_pdf_bytes(markdown, title="Smoke PDF")
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 100


def test_check_to_markdown_and_pdf_export_bundle_smoke():
    record = {
        "id": "smoke123",
        "title": "Smoke report",
        "mode": "text",
        "created_at": "2026-07-02T13:26:11Z",
        "visibility": "public",
        "text_preview": "Тестова проверка.",
        "items": [
            {
                "claim": "Инфлацията през 2024 година е 10 процента.",
                "topic": "икономика",
                "label": "за проверка",
                "confidence": 70,
                "evidence": [
                    {"source": "НСИ", "title": "Инфлация 2024", "snippet": "2024 инфлация", "url": "https://www.nsi.bg/bg"}
                ],
            }
        ],
    }
    bundle = enrich_check_record(record)
    md = check_to_markdown(bundle)
    assert "Smoke report" in md
    assert "| # | Source | Quality | Title | URL |" in md
    pdf = markdown_to_pdf_bytes(md, title="Smoke report")
    assert pdf.startswith(b"%PDF")
