#!/usr/bin/env bash
# service_up.sh — start the SmartReader systemd service.
set -eo pipefail

SERVICE_NAME="smartreader"
systemctl start "$SERVICE_NAME"
echo "[service_up] $SERVICE_NAME started"
systemctl status "$SERVICE_NAME" --no-pager --lines=5
