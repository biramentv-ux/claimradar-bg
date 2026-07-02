import os

os.environ.setdefault("DB_ENABLED", "0")
os.environ.setdefault("RATE_LIMIT_ENABLED", "0")
os.environ.setdefault("MONITORING_ENABLED", "1")
os.environ.setdefault("REQUEST_LOG_ENABLED", "0")
os.environ.setdefault("AUTH_ENABLED", "1")
os.environ.setdefault("ADMIN_KEY", "test-admin-key")
os.environ.setdefault("JOB_EXECUTION_MODE", "celery")
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "0")
os.environ.setdefault("CELERY_QUEUE_NAME", "claimradar-test")
os.environ.setdefault("WHISPER_MODEL_SIZE", "tiny")
os.environ.setdefault("WHISPER_DEVICE", "cpu")
os.environ.setdefault("WHISPER_COMPUTE_TYPE", "int8")

from fastapi.testclient import TestClient

import auth_launch_celery
from celery_queue import CeleryBackedJobStore, celery_config, celery_queue_status, maybe_celery_job_store
from security_jobs import JobStore

client = TestClient(auth_launch_celery.app)


def test_celery_config_detects_memory_broker():
    cfg = celery_config()
    assert cfg["enabled"] is True
    assert cfg["available"] is True
    assert cfg["broker_kind"] == "memory"
    assert cfg["queue_name"] == "claimradar-test"


def test_maybe_celery_job_store_switches_when_mode_enabled(tmp_path):
    base = JobStore(tmp_path)
    store = maybe_celery_job_store(base, tmp_path)
    assert isinstance(store, CeleryBackedJobStore)


def test_celery_store_enqueue_cancel_retry_and_stats(tmp_path):
    store = CeleryBackedJobStore(tmp_path)
    job = store.create("unknown", {"text": "celery queue test"})
    assert job["execution_mode"] == "celery"
    assert job["status"] in {"queued", "failed"}
    assert job["broker_kind"] == "memory"
    assert store.payload_for(job["id"])["text"] == "celery queue test"

    cancelled = store.cancel(job["id"], reason="test_cancel")
    assert cancelled is not None
    assert cancelled["status"] in {"queued", "failed", "cancelled"}

    retry_job, error = store.retry(job["id"])
    assert error is None
    assert retry_job["parent_id"] == job["id"]
    assert retry_job["attempt"] == 2

    stats = store.stats()
    assert stats["execution_mode"] == "celery"
    assert stats["total"] >= 1
    assert stats["celery"]["broker_kind"] == "memory"


def test_celery_status_endpoint_active_in_celery_entrypoint():
    response = client.get("/api/celery/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["celery"]["celery_store_active"] is True
    assert payload["celery"]["config"]["broker_kind"] == "memory"


def test_celery_queue_status_shape(tmp_path):
    store = CeleryBackedJobStore(tmp_path)
    status = celery_queue_status(store)
    assert status["enabled"] is True
    assert status["celery_store_active"] is True
    assert "config" in status
    assert "stats" in status
