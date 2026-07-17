#!/usr/bin/env bash
# retry_run.sh — restart run.sh automatically, capped at MAX_RETRIES starts per WINDOW seconds.
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAX_RETRIES=30
WINDOW=300  # 5 minutes in seconds

declare -a starts=()

while true; do
    now=$(date +%s)
    fresh=()
    for ts in "${starts[@]+"${starts[@]}"}"; do
        (( now - ts < WINDOW )) && fresh+=("$ts")
    done
    starts=("${fresh[@]+"${fresh[@]}"}")

    if (( ${#starts[@]} >= MAX_RETRIES )); then
        echo "[retry_run] reached $MAX_RETRIES starts in $((WINDOW / 60)) minutes — stopping" >&2
        exit 1
    fi

    starts+=("$now")
    echo "[retry_run] launching run.sh (start ${#starts[@]}/$MAX_RETRIES in window)" >&2
    "$SCRIPT_DIR/run.sh" "$@" || true
    echo "[retry_run] exited; retrying in 2s…" >&2
    sleep 2
done
