#!/bin/bash
set -e

echo "🟢 Starting Uvicorn server with Background Tasks..."
echo "🟢 Starting Uvicorn server on port ${PORT:-9000} with Background Tasks..."
exec uvicorn main:app \
  --host 0.0.0.0 \
  --port ${PORT:-9000} \
  --workers 2 \
  --timeout-keep-alive 120