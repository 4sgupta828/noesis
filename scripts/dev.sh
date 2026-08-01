#!/usr/bin/env bash
# Deprecated shim → use the hardened launcher (frees the port, loads .env.medical,
# defaults to LIVE when keys are present, single process, no --reload).
exec "$(dirname "$0")/serve.sh" "$@"
