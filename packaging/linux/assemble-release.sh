#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
VERSION=$(
  sed -n 's/^version[[:space:]]*=[[:space:]]*"\([^"]*\)"/\1/p' "$ROOT/pyproject.toml" |
    head -n 1
)
ARCH=${ARCH:-$(uname -m)}
RUNTIME_DIR=${RUNTIME_DIR:-"$ROOT/dist/mvd-edge-agent"}
OUTPUT_DIR=${OUTPUT_DIR:-"$ROOT/release"}
BUNDLE_NAME=${BUNDLE_NAME:-"mvd-edge-agent-$VERSION-linux-$ARCH"}
BUNDLE_DIR="$OUTPUT_DIR/$BUNDLE_NAME"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

[ -n "$VERSION" ] || fail "Could not determine package version from pyproject.toml"
[ -d "$RUNTIME_DIR" ] || fail "PyInstaller onedir runtime not found: $RUNTIME_DIR"
[ -f "$RUNTIME_DIR/mvd-edge-agent" ] || fail "Runtime missing executable: $RUNTIME_DIR/mvd-edge-agent"

case "$ARCH" in
  aarch64 | arm64)
    ;;
  *)
    printf 'WARNING: assembling Linux bundle for non-aarch64 architecture: %s\n' "$ARCH" >&2
    ;;
esac

rm -rf "$BUNDLE_DIR"
mkdir -p \
  "$BUNDLE_DIR/executable" \
  "$BUNDLE_DIR/config" \
  "$BUNDLE_DIR/systemd" \
  "$BUNDLE_DIR/docs"

cp -R "$RUNTIME_DIR"/. "$BUNDLE_DIR/executable"/
cp "$SCRIPT_DIR/install.sh" "$BUNDLE_DIR/install.sh"
cp "$SCRIPT_DIR/uninstall.sh" "$BUNDLE_DIR/uninstall.sh"
cp "$SCRIPT_DIR/preflight.sh" "$BUNDLE_DIR/preflight.sh"
cp "$SCRIPT_DIR/config/edge.env.example" "$BUNDLE_DIR/config/edge.env.example"
cp "$SCRIPT_DIR/systemd/mvd-edge.service" "$BUNDLE_DIR/systemd/mvd-edge.service"
cp "$ROOT/docs/LINUX_SERVICE.md" "$BUNDLE_DIR/docs/LINUX_SERVICE.md"

chmod 0755 \
  "$BUNDLE_DIR/install.sh" \
  "$BUNDLE_DIR/uninstall.sh" \
  "$BUNDLE_DIR/preflight.sh" \
  "$BUNDLE_DIR/executable/mvd-edge-agent"

cat > "$BUNDLE_DIR/INSTALL.md" <<EOF
# MVD Insights Edge Agent $VERSION Linux $ARCH Installer

This bundle installs the PyInstaller onedir runtime to /opt/mvd-edge and keeps
configuration, queue data, and logs external to the application.

## Install

\`\`\`bash
sudo ./install.sh
\`\`\`

The installer creates /etc/mvd-edge/edge.env from config/edge.env.example only
when the config file does not already exist. Existing config, /var/lib/mvd-edge,
and /var/log/mvd-edge are preserved on upgrades.

## Configure

Edit /etc/mvd-edge/edge.env and set the deployment-specific values, including
RFID_API_URL and RFID_INGEST_API_KEY. Do not place real secrets in this bundle.

## Validate

\`\`\`bash
sudo ./preflight.sh
\`\`\`

## Start

\`\`\`bash
sudo systemctl start mvd-edge
\`\`\`

The service is enabled during install and will start automatically on later
boots after commissioning.
EOF

forbidden=$(
  find "$BUNDLE_DIR" \( \
  -name .git -o \
  -name .env -o \
  -name .venv -o \
  -name __pycache__ -o \
  -name '*.sqlite3' -o \
  -name '*.sqlite3-shm' -o \
  -name '*.sqlite3-wal' -o \
  -name '*.log' \
  \) -print
)

if [ -n "$forbidden" ]; then
  printf '%s\n' "$forbidden" >&2
  fail "Forbidden development/runtime artifact found in bundle"
fi

printf 'Created release bundle: %s\n' "$BUNDLE_DIR"
