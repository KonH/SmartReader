#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

VENV="$SCRIPT_DIR/.venv"
if [[ ! -f "$VENV/bin/activate" ]]; then
    echo "error: virtualenv not found. Run:" >&2
    echo "  python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
    exit 1
fi
source "$VENV/bin/activate"

PYTHONPATH="$SCRIPT_DIR/src" exec python -m smartreader "$@"
