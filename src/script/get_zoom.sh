#!/bin/bash
# get_zoom.sh

set -euo pipefail

# Usage: ./get_zoom.sh <camera-ip> <session-id>

CAMERA_IP="${1:-169.254.50.183}"
SESSION_ID="${2:-}"

if [[ -z "$SESSION_ID" ]]; then
  echo "Usage: $0 <camera-ip> <session-id>" >&2
  exit 1
fi

curl -s -g "http://${CAMERA_IP}/Nexus.cgi?session=${SESSION_ID}&action=DLTVFOVMagnificationGet&tokenoverride=1&_=0"
