#!/bin/bash

set -euo pipefail

# Usage: ./get_zoomfov.sh <camera-ip> <session-id>

CAMERA_IP="${1:-169.254.50.183}"
SESSION_ID="${2:-}"

if [[ -z "$SESSION_ID" ]]; then
  echo "Usage: $0 <camera-ip> <session-id>" >&2
  exit 1
fi

curl -s -g "http://${CAMERA_IP}/Nexus.cgi?session=${SESSION_ID}&action=DLTVZoomDegreesGet&tokenoverride=1&_=0"
