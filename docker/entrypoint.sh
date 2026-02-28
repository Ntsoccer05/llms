#!/bin/sh
set -e

if [ "$APP_ENV" = "development" ]; then
    echo "🔄 Starting in DEVELOPMENT mode (with --reload)"
    exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
else
    echo "🚀 Starting in PRODUCTION mode"
    exec uvicorn main:app --host 0.0.0.0 --port 8000
fi