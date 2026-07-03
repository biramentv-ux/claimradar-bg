#!/bin/sh
set -eu

APP_PORT="${APP_PORT:-7860}"
APP_ROLE="${APP_ROLE:-web}"
WORKER_ONLY_MODE="${WORKER_ONLY_MODE:-0}"
QUEUE_WORKER_AUTOSTART="${QUEUE_WORKER_AUTOSTART:-0}"
CELERY_WORKER_AUTOSTART="${CELERY_WORKER_AUTOSTART:-0}"
JOB_EXECUTION_MODE="${JOB_EXECUTION_MODE:-thread}"
QUEUE_BACKEND="${QUEUE_BACKEND:-jsonl}"
CELERY_QUEUE_NAME="${CELERY_QUEUE_NAME:-claimradar}"
CELERY_WORKER_LOGLEVEL="${CELERY_WORKER_LOGLEVEL:-INFO}"
CELERY_WORKER_CONCURRENCY="${CELERY_WORKER_CONCURRENCY:-1}"

WORKER_PID=""
CELERY_PID=""

if [ "$WORKER_ONLY_MODE" = "1" ] || [ "$APP_ROLE" = "worker" ]; then
  echo "Starting ClaimRadar BG worker-only process with backend=$QUEUE_BACKEND..."
  exec python queue_worker.py --poll "${QUEUE_POLL_SECONDS:-2.0}" --batch "${QUEUE_BATCH_SIZE:-1}"
fi

if [ "$APP_ROLE" = "celery-worker" ]; then
  echo "Starting ClaimRadar BG Celery worker-only process..."
  exec celery -A celery_queue.celery_app worker -Q "$CELERY_QUEUE_NAME" --loglevel="$CELERY_WORKER_LOGLEVEL" --concurrency="$CELERY_WORKER_CONCURRENCY"
fi

if [ "$QUEUE_WORKER_AUTOSTART" = "1" ]; then
  echo "Starting ClaimRadar BG external queue worker sidecar in same container..."
  python queue_worker.py --poll "${QUEUE_POLL_SECONDS:-2.0}" --batch "${QUEUE_BATCH_SIZE:-1}" &
  WORKER_PID=$!
fi

if [ "$CELERY_WORKER_AUTOSTART" = "1" ] || [ "$JOB_EXECUTION_MODE" = "celery" ]; then
  echo "Starting ClaimRadar BG Celery worker sidecar..."
  celery -A celery_queue.celery_app worker -Q "$CELERY_QUEUE_NAME" --loglevel="$CELERY_WORKER_LOGLEVEL" --concurrency="$CELERY_WORKER_CONCURRENCY" &
  CELERY_PID=$!
fi

cleanup() {
  if [ -n "${WORKER_PID:-}" ]; then
    echo "Stopping queue worker $WORKER_PID"
    kill "$WORKER_PID" 2>/dev/null || true
  fi
  if [ -n "${CELERY_PID:-}" ]; then
    echo "Stopping Celery worker $CELERY_PID"
    kill "$CELERY_PID" 2>/dev/null || true
  fi
}
trap cleanup INT TERM EXIT

echo "Starting ClaimRadar BG runtime-safe web app on port $APP_PORT with queue backend=$QUEUE_BACKEND..."
python runtime_safe_launch.py
