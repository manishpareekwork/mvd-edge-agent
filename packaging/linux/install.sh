#!/usr/bin/env sh
set -eu

SERVICE_NAME=mvd-edge
SERVICE_USER=${SERVICE_USER:-mvd-edge}
SERVICE_GROUP=${SERVICE_GROUP:-mvd-edge}
START_SERVICE=${START_SERVICE:-0}
RUN_PREFLIGHT=${RUN_PREFLIGHT:-0}
DESTDIR=${DESTDIR:-}

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SOURCE_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)

root_path() {
  printf '%s%s\n' "$DESTDIR" "$1"
}

require_root_or_staging() {
  if [ -z "$DESTDIR" ] && [ "$(id -u)" -ne 0 ]; then
    printf 'ERROR: run as root, or set DESTDIR for a staged install test.\n' >&2
    exit 1
  fi
}

copy_file() {
  src=$1
  dst=$2
  mode=$3
  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
  chmod "$mode" "$dst"
}

detect_runtime_dir() {
  if [ -n "${AGENT_RUNTIME_DIR:-}" ]; then
    printf '%s\n' "$AGENT_RUNTIME_DIR"
    return
  fi

  if [ -d "$SCRIPT_DIR/executable" ]; then
    printf '%s\n' "$SCRIPT_DIR/executable"
    return
  fi

  if [ -d "$SOURCE_ROOT/dist/mvd-edge-agent" ]; then
    printf '%s\n' "$SOURCE_ROOT/dist/mvd-edge-agent"
    return
  fi

  if [ -n "${AGENT_SOURCE:-}" ] && [ -d "$AGENT_SOURCE" ]; then
    printf '%s\n' "$AGENT_SOURCE"
    return
  fi

  printf 'ERROR: Linux PyInstaller onedir runtime not found.\n' >&2
  printf 'Expected AGENT_RUNTIME_DIR, ./executable, or dist/mvd-edge-agent.\n' >&2
  exit 1
}

replace_runtime() {
  runtime_dir=$1

  [ -f "$runtime_dir/mvd-edge-agent" ] || {
    printf 'ERROR: runtime directory missing mvd-edge-agent: %s\n' "$runtime_dir" >&2
    exit 1
  }

  mkdir -p "$APP_DIR"
  find "$APP_DIR" -mindepth 1 -maxdepth 1 ! -name docs -exec rm -rf {} +
  cp -R "$runtime_dir"/. "$APP_DIR"/
  chmod 0755 "$APP_DIR/mvd-edge-agent"
}

install_docs() {
  docs_source=

  if [ -f "$SCRIPT_DIR/docs/LINUX_SERVICE.md" ]; then
    docs_source="$SCRIPT_DIR/docs/LINUX_SERVICE.md"
  elif [ -f "$SOURCE_ROOT/docs/LINUX_SERVICE.md" ]; then
    docs_source="$SOURCE_ROOT/docs/LINUX_SERVICE.md"
  fi

  if [ -n "$docs_source" ]; then
    copy_file "$docs_source" "$APP_DIR/docs/LINUX_SERVICE.md" 0644
  fi
}

create_service_account() {
  if [ -n "$DESTDIR" ]; then
    printf 'Staged install: skipping service account creation.\n'
    return
  fi

  if ! getent group "$SERVICE_GROUP" >/dev/null 2>&1; then
    groupadd --system "$SERVICE_GROUP"
  fi

  if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    useradd \
      --system \
      --gid "$SERVICE_GROUP" \
      --home-dir /var/lib/mvd-edge \
      --no-create-home \
      --shell /usr/sbin/nologin \
      "$SERVICE_USER"
  fi
}

configure_serial_group() {
  if [ -n "$DESTDIR" ]; then
    return
  fi

  if getent group dialout >/dev/null 2>&1; then
    usermod -a -G dialout "$SERVICE_USER"
    printf 'Added %s to serial access group: dialout\n' "$SERVICE_USER"
  else
    printf 'WARNING: dialout group not found. Grant %s serial-device access using this distribution'\''s serial group policy.\n' "$SERVICE_USER" >&2
  fi
}

require_root_or_staging

APP_DIR=$(root_path /opt/mvd-edge)
CONFIG_DIR=$(root_path /etc/mvd-edge)
DATA_DIR=$(root_path /var/lib/mvd-edge)
LOG_DIR=$(root_path /var/log/mvd-edge)
SYSTEMD_DIR=$(root_path /etc/systemd/system)

RUNTIME_SOURCE=$(detect_runtime_dir)

create_service_account

mkdir -p "$APP_DIR" "$CONFIG_DIR" "$DATA_DIR" "$LOG_DIR" "$SYSTEMD_DIR"
replace_runtime "$RUNTIME_SOURCE"
install_docs
copy_file "$SCRIPT_DIR/systemd/mvd-edge.service" "$SYSTEMD_DIR/mvd-edge.service" 0644

if [ ! -f "$CONFIG_DIR/edge.env" ]; then
  copy_file "$SCRIPT_DIR/config/edge.env.example" "$CONFIG_DIR/edge.env" 0640
  printf 'Created config template: %s\n' "$CONFIG_DIR/edge.env"
else
  printf 'Preserved existing config: %s\n' "$CONFIG_DIR/edge.env"
fi

if [ -z "$DESTDIR" ]; then
  chown -R root:root "$APP_DIR"
  chown root:root "$SYSTEMD_DIR/mvd-edge.service"
  chown root:"$SERVICE_GROUP" "$CONFIG_DIR/edge.env"
  chown "$SERVICE_USER":"$SERVICE_GROUP" "$DATA_DIR" "$LOG_DIR"
  chmod 0755 "$APP_DIR"
  chmod 0750 "$DATA_DIR" "$LOG_DIR"
  configure_serial_group
else
  chmod 0755 "$APP_DIR"
  chmod 0750 "$DATA_DIR" "$LOG_DIR"
fi

if [ "$RUN_PREFLIGHT" = "1" ]; then
  if [ -z "$DESTDIR" ]; then
    MVD_EDGE_CONFIG=/etc/mvd-edge/edge.env \
      EDGE_DATA_DIR=/var/lib/mvd-edge \
      EDGE_LOG_DIR=/var/log/mvd-edge \
      AGENT_BIN=/opt/mvd-edge/mvd-edge-agent \
      "$SCRIPT_DIR/preflight.sh"
  else
    printf 'Staged install: skipping preflight by default because the service paths are rooted under DESTDIR.\n'
  fi
fi

if [ -z "$DESTDIR" ]; then
  systemctl daemon-reload
  systemctl enable "$SERVICE_NAME"

  if [ "$START_SERVICE" = "1" ]; then
    systemctl start "$SERVICE_NAME"
  else
    printf 'Service installed and enabled for boot.\n'
    printf 'Configuration/commissioning is required before starting the service.\n'
    printf 'Edit: /etc/mvd-edge/edge.env\n'
    printf 'Validate: RUN_PREFLIGHT=1 %s/preflight.sh\n' "$SCRIPT_DIR"
    printf 'Start after validation: systemctl start %s\n' "$SERVICE_NAME"
  fi
else
  printf 'Staged install complete under: %s\n' "$DESTDIR"
fi
