#!/bin/bash
# Detects dockerd restarts by diffing systemd's ActiveEnterTimestamp against the
# last-seen value. Logs a heartbeat on every run so the monitor's own liveness
# can be confirmed, plus a distinct line when a restart is detected.
set -euo pipefail

LOG_FILE="/var/log/docker-restart-monitor.log"
STATE_FILE="/var/lib/docker-restart-monitor.state"

current_start=$(systemctl show docker --property=ActiveEnterTimestamp --value 2>/dev/null || echo "unknown")
current_pid=$(systemctl show docker --property=MainPID --value 2>/dev/null || echo "unknown")
now=$(date '+%Y-%m-%d %H:%M:%S %Z')

prev_start=""
if [ -f "$STATE_FILE" ]; then
  prev_start=$(cat "$STATE_FILE")
fi

if [ -n "$prev_start" ] && [ "$prev_start" != "$current_start" ]; then
  echo "$now RESTART_DETECTED prev_start=\"$prev_start\" new_start=\"$current_start\" new_pid=$current_pid" >> "$LOG_FILE"
else
  echo "$now check_ok start=\"$current_start\" pid=$current_pid" >> "$LOG_FILE"
fi

echo "$current_start" > "$STATE_FILE"
