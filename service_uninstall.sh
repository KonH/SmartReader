#!/usr/bin/env bash
# service_uninstall.sh — stop, disable, and remove the SmartReader systemd service.
set -eo pipefail

SERVICE_NAME="smartreader"
UNIT_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "[service_uninstall] stopping $SERVICE_NAME"
    systemctl stop "$SERVICE_NAME"
fi

if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
    echo "[service_uninstall] disabling $SERVICE_NAME"
    systemctl disable "$SERVICE_NAME"
fi

if [[ -f "$UNIT_FILE" ]]; then
    echo "[service_uninstall] removing $UNIT_FILE"
    rm "$UNIT_FILE"
    systemctl daemon-reload
fi

echo "[service_uninstall] done"
