import importlib
import os
from pathlib import Path


def test_queue_backend_selector_uses_postgres_when_requested(monkeypatch):
    monkeypatch.setenv("JOB_EXECUTION_MODE", "external")
    monkeypatch.setenv("QUEUE_BACKEND", "postgres")
    import external_queue
    import queue_backends
    import postgres_queue
    importlib.reload(external_queue)
    qb = importlib.reload(queue_backends)
    store = qb.build_external_job_store(Path("/tmp/claimradar-test"))
    assert isinstance(store, postgres_queue.PostgresQueueBackedJobStore)
    status = qb.queue_backend_status(store)
    assert status["queue_backend"] == "postgres"
    assert status["store_type"] == "PostgresQueueBackedJobStore"


def test_queue_backend_selector_defaults_to_jsonl(monkeypatch, tmp_path):
    monkeypatch.setenv("JOB_EXECUTION_MODE", "external")
    monkeypatch.setenv("QUEUE_BACKEND", "jsonl")
    import external_queue
    import queue_backends
    importlib.reload(external_queue)
    qb = importlib.reload(queue_backends)
    store = qb.build_external_job_store(tmp_path)
    assert type(store).__name__ == "QueueBackedJobStore"
    job = store.create("check", {"text": "тест"})
    assert job["status"] == "queued"
    assert store.payload_for(job["id"]) == {"text": "тест"}


def test_start_script_supports_worker_only_mode():
    script = Path("scripts/start_production.sh").read_text(encoding="utf-8")
    assert "WORKER_ONLY_MODE" in script
    assert "APP_ROLE" in script
    assert "exec python queue_worker.py" in script
    assert "QUEUE_WORKER_AUTOSTART" in script
    assert "queue backend" in script.lower()


def test_queue_worker_uses_backend_selector():
    worker = Path("queue_worker.py").read_text(encoding="utf-8")
    assert "build_external_job_store" in worker
    assert "QUEUE_BACKEND" in worker
    assert "QueueWorker" in worker


def test_postgres_queue_contract_contains_skip_locked_claim():
    source = Path("postgres_queue.py").read_text(encoding="utf-8")
    assert "PostgresQueueBackedJobStore" in source
    assert "for update skip locked" in source.lower()
    assert "external-postgres" in source
    assert "claimradar_jobs" in source
