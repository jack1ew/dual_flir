#!/bin/bash

set -euo pipefail

# Usage: ./center.sh <camera-ip> <session-id> <screen-x> <screen-y>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CAMERA_IP="${1:-169.254.50.183}"
SESSION_ID="${2:-}"
SCREEN_X="${3:-0}"
SCREEN_Y="${4:-0}"

if [[ -z "$SESSION_ID" ]]; then
  echo "Usage: $0 <camera-ip> <session-id> <screen-x> <screen-y>" >&2
  exit 1
fi

BASE_URL="http://${CAMERA_IP}/Nexus.cgi"
TOKEN_SUFFIX="tokenoverride=1&_=0"
MOVE_URL="${BASE_URL}?action=PTAzimuthElevationOnScreenSet&ScreenX=${SCREEN_X}&ScreenY=${SCREEN_Y}&Active_cam=0&Cam_type=4&Cam_id=0&session=${SESSION_ID}&${TOKEN_SUFFIX}"

json_response="$(curl --silent --show-error "$MOVE_URL" | jq -r '.error."Return Code" // empty')"
if [[ "$json_response" == "21" ]]; then
  new_session="$("${SCRIPT_DIR}/authenticate.sh" "${CAMERA_IP}")"
  printf '%s\n' "$new_session"
else
  echo "Success"
fi
