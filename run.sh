#!/usr/bin/env bash
# One-command local start for the ET617 prototype.
# Backend on :8000 (SQLite), frontend on :3000.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo "Created backend/.env — add your GEMINI_API_KEY there for live models."
fi

if [ ! -d backend/.venv ]; then
  echo "Setting up the Python environment…"
  (cd backend && uv venv --python 3.13 -q && uv pip install -q \
     "fastapi>=0.115" "uvicorn[standard]>=0.32" "sqlalchemy>=2.0" \
     "pydantic>=2.9" "pydantic-settings>=2.6" "httpx>=0.27" "python-multipart>=0.0.12")
fi

[ -d frontend/node_modules ] || (echo "Installing frontend packages…" && cd frontend && npm install --silent)

cleanup() { echo; echo "Shutting down…"; kill 0 2>/dev/null || true; }
trap cleanup EXIT INT TERM

(cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000) &
(cd frontend && npm run dev) &

sleep 4
echo
echo "  Story Studio is running"
echo "  ─────────────────────────────────────────"
echo "  Student workspace   http://localhost:3000"
echo "  Researcher panel    http://localhost:3000/research"
echo "  API docs            http://localhost:8000/docs"
echo
echo "  Ctrl-C to stop."
wait
