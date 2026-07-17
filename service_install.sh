#!/usr/bin/env bash
# service_install.sh — install SmartReader as a systemd service.
# Usage: ./service_install.sh [state-file-path]
#   state-file-path defaults to state.sqlite (relative to project dir)
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="smartreader"
UNIT_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
STATE_ARG="${1:-}"

# Determine the user/group to run as (default: current user).
RUN_USER="${SUDO_USER:-$(id -un)}"
RUN_GROUP="$(id -gn "$RUN_USER")"

echo "[service_install] installing $SERVICE_NAME as $RUN_USER"

cat > "$UNIT_FILE" <<EOF
[Unit]
Description=SmartReader news reader service
After=network.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_GROUP}
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${SCRIPT_DIR}/retry_run.sh ${STATE_ARG}
Restart=no
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo "[service_install] done — run ./service_up.sh to start"
