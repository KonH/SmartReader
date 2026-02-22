#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse --yes / -y flag (skip confirmation prompt)
YES=0
ARGS=()
for arg in "$@"; do
    case "$arg" in
        --yes|-y) YES=1 ;;
        *) ARGS+=("$arg") ;;
    esac
done

VENV="$SCRIPT_DIR/.venv"
if [[ ! -f "$VENV/bin/activate" ]]; then
    echo "error: virtualenv not found. Run:" >&2
    echo "  python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
    exit 1
fi
source "$VENV/bin/activate"

CMD="python -m smartreader${ARGS[*]:+ ${ARGS[*]}}"
echo "$ $CMD"

if [[ "$YES" -eq 0 ]]; then
    read -r -p "Run? [Y/n] " reply
    reply="${reply:-Y}"
    if [[ ! "$reply" =~ ^[Yy]$ ]]; then
        echo "aborted"
        exit 0
    fi
fi

PYTHONPATH="$SCRIPT_DIR/src" exec python -m smartreader "${ARGS[@]}"
