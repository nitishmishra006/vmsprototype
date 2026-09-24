#!/usr/bin/env bash
# Start the backend (:8000) and frontend (:3000) together.
# Usage: ./scripts/dev.sh     (Ctrl-C stops both)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -d backend/.venv ]; then
  echo "backend/.venv not found. Create it first:" >&2
  echo "  cd backend && python3.11 -m venv .venv && source .venv/bin/activate" >&2
  echo "  pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu" >&2
  echo "  pip install -r requirements.txt" >&2
  exit 1
fi

if [ ! -d frontend/node_modules ]; then
  echo "frontend/node_modules not found. Run: (cd frontend && npm install)" >&2
  exit 1
fi

pids=()
cleanup() {
  echo
  echo "stopping…"
  for pid in "${pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(
  cd backend
  # shellcheck disable=SC1091
  source .venv/bin/activate
  exec uvicorn app.main:app --reload --port 8000 --log-config log_config.json
) &
pids+=($!)

(
  cd frontend
  exec npm run dev -- --port 3000
) &
pids+=($!)

echo "backend  http://localhost:8000  (docs at /docs)"
echo "frontend http://localhost:3000"
wait
