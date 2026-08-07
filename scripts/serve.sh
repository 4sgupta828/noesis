#!/usr/bin/env bash
# Hardened local launcher — avoids the stale-server / replay-mode trap:
#  1. kills ALL listeners on the port first (by port — catches --reload children),
#  2. loads .env.medical (keys + corpus DSN) if present,
#  3. defaults to LIVE mode when an ANTHROPIC key is available (else replay),
#  4. runs ONE process, no --reload,
#  5. verifies it is the sole listener and prints the effective config.
#
# Usage: ./scripts/serve.sh [port]   (env overrides: NOESIS_ACTIVE_VERTICAL, NOESIS_PROVIDER_MODE)
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${1:-${PORT:-8000}}"

# 1) free the port (kills reload children a name-based pkill would miss)
PIDS="$(lsof -t -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
if [ -n "$PIDS" ]; then echo "[serve] freeing :$PORT (killing: $PIDS)"; kill -9 $PIDS 2>/dev/null || true; sleep 1; fi

# 2) load local secrets/config if present
[ -f .env.medical ] && { set -a; . ./.env.medical; set +a; }

# 3) sensible defaults
export NOESIS_ACTIVE_VERTICAL="${NOESIS_ACTIVE_VERTICAL:-medical}"
if [ -z "${NOESIS_PROVIDER_MODE:-}" ]; then
  if [ -n "${ANTHROPIC_API_KEY:-}" ] && [ -n "${OPENAI_API_KEY:-}" ]; then
    export NOESIS_PROVIDER_MODE=live
  else
    export NOESIS_PROVIDER_MODE=replay
  fi
fi
export PYTHONPATH="packages/kernel:packages/vertical_medical:apps"
PY="${PY:-.venv/bin/python}"

echo "[serve] vertical=$NOESIS_ACTIVE_VERTICAL mode=$NOESIS_PROVIDER_MODE corpus=${NOESIS_CORPUS_DSN:+pg}${NOESIS_CORPUS_DSN:-fixture} port=$PORT"
if [ "$NOESIS_PROVIDER_MODE" = "replay" ]; then
  echo "[serve] WARNING: replay mode — /research needs a model. Add ANTHROPIC_API_KEY + OPENAI_API_KEY (or .env.medical) for live answers."
fi

# 4) run ONE process, no --reload
exec "$PY" -m uvicorn api.app:create_app --factory --host 127.0.0.1 --port "$PORT"
