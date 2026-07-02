#!/bin/sh
set -eu

APP_PORT="${APP_PORT:-7860}"
QUEUE_WORKER_AUTOSTART="${QUEUE_WORKER_AUTOSTART:-0}"
JOB_EXECUTION_MODE="${JOB_EXECUTION_MODE:-thread}"

if [ "$QUEUE_WORKER_AUTOSTART" = "1" ] || [ "$JOB_EXECUTION_MODE" = "external" ]; then
  echo "Starting ClaimRadar BG external queue worker..."
  python queue_worker.py --poll "${QUEUE_POLL_SECONDS:-2.0}" --batch "${QUEUE_BATCH_SIZE:-1}" &
  WORKER_PID=$!
else
  WORKER_PID=""
fi

cleanup() {
  if [ -n "${WORKER_PID:-}" ]; then
    echo "Stopping queue worker $WORKER_PID"
    kill "$WORKER_PID" 2>/dev/null || true
  fi
}
trap cleanup INT TERM EXIT

echo "Starting ClaimRadar BG web app on port $APP_PORT..."
python auth_launch.py
