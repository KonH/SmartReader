#!/usr/bin/env bash
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

VENV="$SCRIPT_DIR/.venv"
if [[ ! -f "$VENV/bin/activate" ]]; then
    echo "virtualenv not found."
    read -r -p "Run 'python -m venv .venv && pip install -r requirements.txt'? [Y/n] " reply
    reply="${reply:-Y}"
    if [[ ! "$reply" =~ ^[Yy]$ ]]; then
        echo "aborted"
        exit 0
    fi
    python -m venv "$VENV"
    "$VENV/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
fi

source "$VENV/bin/activate"

PYTHONPATH="$SCRIPT_DIR/src" exec python -m smartreader "$@"
