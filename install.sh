#!/usr/bin/env bash
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

VENV="$SCRIPT_DIR/.venv"
if [[ ! -f "$VENV/bin/activate" ]]; then
    echo "virtualenv not found, creating..."
    python -m venv "$VENV"
fi

source "$VENV/bin/activate"

pip install -r "$SCRIPT_DIR/requirements.txt"
