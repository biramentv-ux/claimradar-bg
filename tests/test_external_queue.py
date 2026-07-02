import os

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

import auth_launch
from external_queue import QueueBackedJobStore, QueueWorker, external_queue_status

client = TestClient(auth_launch.app)


def test_queue_status_endpoint_has_stable_shape():
    response = client.get("/api/queue/status")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "queue" in data
    assert "execution_mode" in data["queue"]
    assert "store_type" in data["queue"]


def test_external_store_enqueues_without_running(tmp_path):
    store = QueueBackedJobStore(tmp_path)
    job = store.create("check", {"text": "Инфлацията през 2024 е 10 процента."})
    assert job["status"] == "queued"
    assert job["execution_mode"] == "external"
    assert store.get(job["id"])["status"] == "queued"
    assert store.payload_for(job["id"])["text"].startswith("Инфлацията")
    stats = store.stats()
    assert stats["queued"] == 1
    assert stats["execution_mode"] == "external"


def test_queue_worker_processes_one_job(tmp_path):
    store = QueueBackedJobStore(tmp_path)
    job = store.create("check", {"text": "abc"})

    def run_check(payload):
        return {"ok": True, "upper": payload["text"].upper()}

    worker = QueueWorker(store, {"check": run_check}, worker_id="test-worker")
    result = worker.process_one()
    assert result["processed"] is True
    assert result["status"] == "done"
    done = store.get(job["id"])
    assert done["status"] == "done"
    assert done["worker_id"] == "test-worker"
    assert done["result"]["upper"] == "ABC"
    assert store.worker_heartbeats(limit=1)[0]["worker_id"] == "test-worker"


def test_queue_worker_marks_missing_function_failed(tmp_path):
    store = QueueBackedJobStore(tmp_path)
    job = store.create("unknown_type", {"x": 1})
    result = QueueWorker(store, {}, worker_id="test-worker").process_one()
    assert result["processed"] is True
    assert result["status"] == "failed"
    assert store.get(job["id"])["status"] == "failed"


def test_queue_cancel_and_retry(tmp_path):
    store = QueueBackedJobStore(tmp_path)
    job = store.create("check", {"text": "retry me"})
    cancelled = store.cancel(job["id"], reason="test_cancel")
    assert cancelled["status"] == "cancelled"
    retry_job, error = store.retry(job["id"])
    assert error is None
    assert retry_job["parent_id"] == job["id"]
    assert retry_job["attempt"] == 2


def test_external_queue_status_for_store(tmp_path):
    store = QueueBackedJobStore(tmp_path)
    store.create("check", {"text": "status"})
    status = external_queue_status(store)
    assert status["external_store_active"] is True
    assert status["stats"]["queued"] == 1
