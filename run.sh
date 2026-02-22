#!/usr/bin/env bash
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

VENV="$SCRIPT_DIR/.venv"
if [[ ! -f "$VENV/bin/activate" ]]; then
    echo "virtualenv not found."
    read -r -p "Run install.sh to set up? [Y/n] " reply
    reply="${reply:-Y}"
    if [[ ! "$reply" =~ ^[Yy]$ ]]; then
        echo "aborted"
        exit 0
    fi
    bash "$SCRIPT_DIR/install.sh"
fi

source "$VENV/bin/activate"

PYTHONPATH="$SCRIPT_DIR/src" exec python -m smartreader "$@"
