#!/usr/bin/env bash
# service_down.sh — stop the SmartReader systemd service.
set -eo pipefail

SERVICE_NAME="smartreader"
systemctl stop "$SERVICE_NAME"
echo "[service_down] $SERVICE_NAME stopped"
