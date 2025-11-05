#!/bin/bash

set -euo pipefail

# Usage: ./authenticate.sh <camera-ip> [port]

CAMERA_IP="${1:-169.254.50.183}"
NEXUS_PORT="${2:-80}"
NEXUS_CGI_PATH="/Nexus.cgi"
BASE_URL="http://${CAMERA_IP}:${NEXUS_PORT}${NEXUS_CGI_PATH}"
AUTH_URL="${BASE_URL}?action=SERVERWhoAmI"

response="$(curl --silent --show-error "$AUTH_URL")"
if [[ -z "$response" ]]; then
  echo "Authentication Error: Empty response from camera at ${CAMERA_IP}" >&2
  exit 1
fi

if ! session_id="$(printf '%s' "$response" | jq -e -r '.SERVERWhoAmI.Id // empty')"; then
  echo "Authentication Error: Failed to parse session ID from response." >&2
  exit 1
fi

if [[ -z "$session_id" ]]; then
  echo "Authentication Error: Session ID received from API was empty." >&2
  exit 1
fi

printf '%s\n' "$session_id"
