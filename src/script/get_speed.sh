#!/bin/bash

set -euo pipefail

# Usage: ./get_speed.sh <camera-ip> <session-id>

CAMERA_IP="${1:-169.254.50.183}"
SESSION_ID="${2:-}"

if [[ -z "$SESSION_ID" ]]; then
  echo "Usage: $0 <camera-ip> <session-id>" >&2
  exit 1
fi

while true; do
  if ping -c 1 "$CAMERA_IP" > /dev/null 2>&1; then
    echo "$(date) - IP address ${CAMERA_IP} is reachable"
    curl -g "http://${CAMERA_IP}/Nexus.cgi?session=${SESSION_ID}&action=PTSpeedGet&tokenoverride=1&_=0"
    break
  else
    echo "$(date) - IP address ${CAMERA_IP} is not reachable"
  fi
  sleep 1
done
