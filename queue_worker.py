from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import app as app_module
from hardware_inference import configure_app_module

configure_app_module(app_module)

import launch as base_launch
from external_queue import QueueBackedJobStore, QueueWorker


def job_functions():
    return {
        "check": base_launch.run_check_job,
        "ai_verdict": base_launch.run_ai_verdict_job,
        "real_check": base_launch.run_real_check_job,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="ClaimRadar BG external queue worker")
    parser.add_argument("--once", action="store_true", help="Process one available job and exit")
    parser.add_argument("--poll", type=float, default=float(os.getenv("QUEUE_POLL_SECONDS", "2.0")), help="Polling interval in seconds")
    parser.add_argument("--batch", type=int, default=int(os.getenv("QUEUE_BATCH_SIZE", "1")), help="Max jobs per polling cycle")
    parser.add_argument("--data-dir", default=str(app_module.DATA_DIR), help="Data directory containing queue JSONL files")
    parser.add_argument("--worker-id", default=os.getenv("QUEUE_WORKER_ID", ""), help="Stable worker id")
    args = parser.parse_args()

    store = QueueBackedJobStore(Path(args.data_dir))
    worker = QueueWorker(store, job_functions(), worker_id=args.worker_id or None or "queue-worker")
    if args.once:
        print(worker.process_one())
        return 0
    print({"ok": True, "message": "ClaimRadar BG queue worker started", "poll": args.poll, "batch": args.batch, "data_dir": args.data_dir})
    worker.loop(poll_seconds=args.poll, batch_size=args.batch)
    print({"ok": True, "message": "ClaimRadar BG queue worker stopped"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
