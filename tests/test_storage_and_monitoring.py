from pathlib import Path

import db_storage
import monitoring


def test_storage_status_shape_without_required_database():
    status = db_storage.storage.status()
    assert "enabled" in status
    assert "configured" in status
    assert "driver_available" in status
    assert "connected" in status
    assert isinstance(status["tables"], dict)


def test_storage_sslmode_helper_adds_require():
    url = "postgresql://user:pass@example.com:5432/postgres"
    assert db_storage._with_sslmode(url).endswith("?sslmode=require")


def test_storage_sslmode_helper_does_not_duplicate():
    url = "postgresql://user:pass@example.com:5432/postgres?sslmode=require"
    assert db_storage._with_sslmode(url) == url


def test_monitoring_metrics_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(monitoring, "MONITORING_LOG_FILE", str(tmp_path / "events.jsonl"))
    event = monitoring.log_custom_event("test_event", "info", "automated test", {"ok": True})
    assert event["kind"] == "test_event"

    events = monitoring.read_events(limit=10)
    assert events
    assert events[0]["kind"] == "test_event"

    metrics = monitoring.public_metrics()
    assert "uptime_seconds" in metrics
    assert "requests_total" in metrics
    assert "status_counts" in metrics


def test_monitoring_log_file_path_is_jsonl():
    assert Path(monitoring.MONITORING_LOG_FILE).suffix == ".jsonl"
