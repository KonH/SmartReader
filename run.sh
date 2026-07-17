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

# Load secrets from .env if present (copy .env.example → .env and fill in values).
# Variables already set in the shell environment take precedence.
ENV_FILE="$SCRIPT_DIR/.env"
if [[ -f "$ENV_FILE" ]]; then
    # shellcheck source=/dev/null
    set -a
    source "$ENV_FILE"
    set +a
fi

PYTHONPATH="$SCRIPT_DIR/src" exec python -m smartreader "$@"
