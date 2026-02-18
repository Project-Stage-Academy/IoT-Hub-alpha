#!/usr/bin/env bash
# =============================================================================
# Generate the Mosquitto password file for development.
#
# Usage (run from the repo root):
#   bash devops/mosquitto/generate_passwords.sh
#
# The script uses the mosquitto Docker image to hash passwords, so Docker
# must be running.  The generated file is written to:
#   devops/mosquitto/passwords
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PASSWORD_FILE="${SCRIPT_DIR}/passwords"

# Default credentials — override via env vars if needed.
MQTT_ADAPTER_USER="${MQTT_ADAPTER_USER:-mqtt_adapter}"
MQTT_ADAPTER_PASS="${MQTT_ADAPTER_PASS:-mqtt_adapter_secret}"

# Demo device credentials (matching seed_data serial numbers)
DEVICE_USERS=(
    "TEMP-SN-001:device_pass_001"
    "TEMP-SN-002:device_pass_002"
    "TEMP-SN-003:device_pass_003"
    "HUM-SN-001:device_pass_004"
)

echo "Generating Mosquitto password file at: ${PASSWORD_FILE}"

# Start with an empty file
> "${PASSWORD_FILE}"

# Helper: add a user:password entry via the mosquitto_passwd tool in Docker
add_user() {
    local user="$1"
    local pass="$2"
    docker run --rm -v "${PASSWORD_FILE}:/tmp/passwords" \
        eclipse-mosquitto:2 \
        mosquitto_passwd -b /tmp/passwords "${user}" "${pass}"
    echo "  + ${user}"
}

# Adapter service account
add_user "${MQTT_ADAPTER_USER}" "${MQTT_ADAPTER_PASS}"

# Device accounts
for entry in "${DEVICE_USERS[@]}"; do
    IFS=":" read -r user pass <<< "${entry}"
    add_user "${user}" "${pass}"
done

echo ""
echo "Done. ${PASSWORD_FILE} contains $(wc -l < "${PASSWORD_FILE}" | tr -d ' ') entries."
echo "Mount it into Mosquitto at /mosquitto/config/passwords"
