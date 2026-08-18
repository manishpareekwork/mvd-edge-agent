#!/usr/bin/env sh
set -eu

APP_DIR=${APP_DIR:-/opt/mvd-edge}
CONFIG_FILE=${MVD_EDGE_CONFIG:-/etc/mvd-edge/edge.env}
DATA_DIR=${EDGE_DATA_DIR:-/var/lib/mvd-edge}
LOG_DIR=${EDGE_LOG_DIR:-/var/log/mvd-edge}
AGENT_BIN=${AGENT_BIN:-"$APP_DIR/mvd-edge-agent"}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

info() {
  printf '%s\n' "$*"
}

[ -x "$AGENT_BIN" ] || fail "Executable not found or not executable: $AGENT_BIN"
[ -f "$CONFIG_FILE" ] || fail "Config file not found: $CONFIG_FILE"

[ -d "$DATA_DIR" ] || fail "Data directory not found: $DATA_DIR"
[ -w "$DATA_DIR" ] || fail "Data directory is not writable by current user: $DATA_DIR"

if [ -d "$LOG_DIR" ]; then
  [ -w "$LOG_DIR" ] || fail "Log directory is not writable by current user: $LOG_DIR"
fi

serial_port=$(
  sed -n 's/^[[:space:]]*SERIAL_PORT[[:space:]]*=[[:space:]]*//p' "$CONFIG_FILE" |
    tail -n 1
)

case "${serial_port:-AUTO}" in
  AUTO | /* | COM[0-9]* | "")
    ;;
  *)
    fail "SERIAL_PORT should be AUTO, an absolute Linux path, or a Windows COM port template value"
    ;;
esac

rfid_api_url=$(
  sed -n 's/^[[:space:]]*RFID_API_URL[[:space:]]*=[[:space:]]*//p' "$CONFIG_FILE" |
    tail -n 1
)

api_key=$(
  sed -n 's/^[[:space:]]*RFID_INGEST_API_KEY[[:space:]]*=[[:space:]]*//p' "$CONFIG_FILE" |
    tail -n 1
)

[ -n "${rfid_api_url:-}" ] || fail "RFID_API_URL is missing in $CONFIG_FILE"
[ -n "${api_key:-}" ] || fail "RFID_INGEST_API_KEY is missing in $CONFIG_FILE"

info "Running Edge Agent config validation..."
MVD_EDGE_CONFIG="$CONFIG_FILE" EDGE_DATA_DIR="$DATA_DIR" EDGE_LOG_DIR="$LOG_DIR" \
  "$AGENT_BIN" --check-config

info "Preflight passed."
