#!/usr/bin/env bash
# One command: virtualenv, backend deps, UI build, tests, run. Needs Python 3.10+ and Node 18+. Usage: scripts/setup_and_run.sh [--no-tests]
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv && . .venv/bin/activate
pip install -q -r backend/requirements.txt pytest
(cd frontend-react && npm ci --no-audit --no-fund && npx vite build)
[ "${1:-}" = "--no-tests" ] || (cd backend && python -m pytest -q)
: "${SS_SECRET:=$(python -c 'import secrets;print(secrets.token_hex(32))')}"
export SS_SECRET SS_ADMIN_EMAIL="${SS_ADMIN_EMAIL:-admin@example.org}" SS_ADMIN_PASSWORD="${SS_ADMIN_PASSWORD:-change-me-please-123}"
echo "Open http://localhost:5000  (login: $SS_ADMIN_EMAIL / $SS_ADMIN_PASSWORD)"
cd backend && python -m flask --app wsgi run -p 5000
