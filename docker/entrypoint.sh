#!/bin/sh
set -e

# 待ち受けポート（未指定時 8000）
PORT="${BACKEND_PORT:-8000}"
HOST="${BACKEND_HOST_BIND:-0.0.0.0}"

if [ "$APP_ENV" = "development" ]; then
    echo "🔄 Starting in DEVELOPMENT mode (with --reload) on ${HOST}:${PORT}"
    exec uvicorn main:app --host "$HOST" --port "$PORT" --reload
else
    echo "🚀 Starting in PRODUCTION mode on ${HOST}:${PORT}"
    exec uvicorn main:app --host "$HOST" --port "$PORT"
fi