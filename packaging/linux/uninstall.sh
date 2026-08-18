#!/usr/bin/env sh
set -eu

SERVICE_NAME=mvd-edge
PURGE=${PURGE:-0}
DESTDIR=${DESTDIR:-}

root_path() {
  printf '%s%s\n' "$DESTDIR" "$1"
}

if [ -z "$DESTDIR" ] && [ "$(id -u)" -ne 0 ]; then
  printf 'ERROR: run as root, or set DESTDIR for a staged uninstall test.\n' >&2
  exit 1
fi

APP_DIR=$(root_path /opt/mvd-edge)
CONFIG_DIR=$(root_path /etc/mvd-edge)
DATA_DIR=$(root_path /var/lib/mvd-edge)
LOG_DIR=$(root_path /var/log/mvd-edge)
SERVICE_FILE=$(root_path /etc/systemd/system/mvd-edge.service)

if [ -z "$DESTDIR" ]; then
  systemctl stop "$SERVICE_NAME" >/dev/null 2>&1 || true
  systemctl disable "$SERVICE_NAME" >/dev/null 2>&1 || true
fi

if [ -d "$APP_DIR" ]; then
  find "$APP_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
fi
rmdir "$APP_DIR" >/dev/null 2>&1 || true
rm -f "$SERVICE_FILE"

if [ "$PURGE" = "1" ]; then
  rm -f "$CONFIG_DIR/edge.env"
  rmdir "$CONFIG_DIR" >/dev/null 2>&1 || true
  rm -f "$DATA_DIR/events.sqlite3" "$DATA_DIR/events.sqlite3-shm" "$DATA_DIR/events.sqlite3-wal"
  rmdir "$DATA_DIR" >/dev/null 2>&1 || true
  rmdir "$LOG_DIR" >/dev/null 2>&1 || true
else
  printf 'Preserved config/data/logs by default:\n'
  printf '  %s\n' "$CONFIG_DIR/edge.env"
  printf '  %s\n' "$DATA_DIR"
  printf '  %s\n' "$LOG_DIR"
fi

if [ -z "$DESTDIR" ]; then
  systemctl daemon-reload
fi

printf 'Uninstall complete.\n'
