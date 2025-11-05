#!/bin/bash

set -euo pipefail

# Usage: ./set_speed.sh <camera-ip> <session-id> <azimuth-speed> <elevation-speed>

CAMERA_IP="${1:-169.254.50.183}"
SESSION_ID="${2:-}"
AZ_SPEED="${3:-}"
EL_SPEED="${4:-}"

if [[ -z "$SESSION_ID" || -z "$AZ_SPEED" || -z "$EL_SPEED" ]]; then
  echo "Usage: $0 <camera-ip> <session-id> <azimuth-speed> <elevation-speed>" >&2
  exit 1
fi

while true; do
  if ping -c 1 "$CAMERA_IP" > /dev/null 2>&1; then
    echo "$(date) - IP address ${CAMERA_IP} is reachable"
    curl -g "http://${CAMERA_IP}/Nexus.cgi?session=${SESSION_ID}&action=PTSpeedModeSet&Azimuth_Speed=${AZ_SPEED}&Elevation_Speed=${EL_SPEED}&tokenoverride=1&_=0"
    break
  else
    echo "$(date) - IP address ${CAMERA_IP} is not reachable"
  fi
  sleep 1
done
