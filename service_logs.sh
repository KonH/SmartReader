#!/usr/bin/env bash
# service_logs.sh — tail the SmartReader systemd journal.
# Usage: ./service_logs.sh [journalctl-options...]
#   Defaults to -f (follow). Pass e.g. --since today or -n 100 to override.
set -eo pipefail

SERVICE_NAME="smartreader"

if [[ $# -eq 0 ]]; then
    exec journalctl -u "$SERVICE_NAME" -f
else
    exec journalctl -u "$SERVICE_NAME" "$@"
fi
