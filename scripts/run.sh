#!/usr/bin/env bash
set -e

USER_ID="${1:-00000000-0000-0000-0000-000000000001}"
PORT=8888
SERVER_PID=""

cleanup() {
  [[ -n "$SERVER_PID" ]] && kill "$SERVER_PID" 2>/dev/null
}
trap cleanup EXIT

cd "$(dirname "$0")/../backend"

echo "▶ Starting server..."
python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT 2>&1 &
SERVER_PID=$!

until curl -sf "http://localhost:$PORT/health" > /dev/null; do sleep 0.5; done
echo "✓ Server ready"

echo "▶ Triggering run for user $USER_ID..."
curl -s -X POST "http://localhost:$PORT/api/test-run?user_id=$USER_ID" | python3 -m json.tool

echo ""
echo "✓ Done — call should be incoming"
