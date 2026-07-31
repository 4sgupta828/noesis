#!/usr/bin/env bash
# Launch Noesis locally (API + console at http://localhost:8000).
#   NOESIS_PROVIDER_MODE=replay (default) → shell works; /research needs a model.
#   NOESIS_PROVIDER_MODE=live + ANTHROPIC_API_KEY + OPENAI_API_KEY → real answers.
set -euo pipefail
cd "$(dirname "$0")/.."
export NOESIS_ACTIVE_VERTICAL="${NOESIS_ACTIVE_VERTICAL:-regulatory}"
export NOESIS_PROVIDER_MODE="${NOESIS_PROVIDER_MODE:-replay}"
export PYTHONPATH="packages/kernel:packages/vertical_regulatory:apps"
PY="${PY:-.venv/bin/python}"
exec "$PY" -m uvicorn api.app:create_app --factory --reload --port "${PORT:-8000}"
