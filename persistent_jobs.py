from __future__ import annotations

from typing import Any


def patch_job_store_persistence(job_store: Any, storage: Any) -> None:
    """Mirror JobStore writes to Postgres when DATABASE_URL is configured.

    JobStore is intentionally usable without a database. This patch keeps the
    JSONL file as a local backup and additionally mirrors each job state into
    the `claimradar_jobs` table when the Postgres adapter is configured.
    """

    if getattr(job_store, "_claimradar_persistent_patch", False):
        return

    original_persist = job_store.persist

    def db_aware_persist(job: dict):
        original_persist(job)
        try:
            storage.upsert_job(job)
        except Exception:
            pass

    job_store.persist = db_aware_persist
    job_store._claimradar_persistent_patch = True

    try:
        for row in storage.list_jobs(limit=500):
            if row.get("id") and row["id"] not in job_store.jobs:
                job_store.jobs[row["id"]] = row
    except Exception:
        pass
