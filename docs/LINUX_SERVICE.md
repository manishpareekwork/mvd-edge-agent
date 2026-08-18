# MVD Insights Edge Agent Linux Service

This is the Linux service foundation for MVD Insights Edge Agent. It defines the
target layout, systemd template, and scripted installer foundation. Linux
industrial PC field validation is still pending.

## Target Filesystem

```text
/opt/mvd-edge/                 PyInstaller onedir runtime and mvd-edge-agent
/opt/mvd-edge/docs/            installed service documentation
/etc/mvd-edge/edge.env         external deployment configuration
/var/lib/mvd-edge/             persistent SQLite queue and runtime data
/var/log/mvd-edge/             future persistent service logs
/etc/systemd/system/mvd-edge.service
```

Do not store secrets in `/opt/mvd-edge/` or inside the executable. Deployment
configuration belongs in `/etc/mvd-edge/edge.env`.

## Service Account

The service template uses a dedicated non-root account:

```text
User=mvd-edge
Group=mvd-edge
```

`packaging/linux/install.sh` creates this account during a real Linux install
when it does not already exist. The account is system-only and uses
`/usr/sbin/nologin`. Staged installs with `DESTDIR` skip user creation.

## Serial Permissions

The `mvd-edge` user must be allowed to open the RS485/USB serial device. Many
Linux distributions use a serial access group such as `dialout`, but the exact
group is distro-dependent.

Example only:

```bash
sudo usermod -a -G dialout mvd-edge
```

`SERIAL_PORT=AUTO` still requires permission to open discovered serial devices.
The installer adds `mvd-edge` to `dialout` only when that group exists. If the
distribution uses a different group or udev policy, grant serial access
manually. Do not use broad device permissions such as `chmod 777`.

## Service Template

Template path:

```text
packaging/linux/systemd/mvd-edge.service
```

The template sets:

```text
MVD_EDGE_CONFIG=/etc/mvd-edge/edge.env
EDGE_DATA_DIR=/var/lib/mvd-edge
EDGE_LOG_DIR=/var/log/mvd-edge
PYTHONUNBUFFERED=1
```

The service starts after `network-online.target`, restarts on unexpected
failure with a 10 second delay, and uses `SIGTERM` for clean shutdown.

## Hardening

The initial hardening is intentionally conservative:

```text
NoNewPrivileges=true
PrivateTmp=true
```

More aggressive sandboxing is deferred until it can be validated with serial
devices, network access, `/etc/mvd-edge/`, `/var/lib/mvd-edge/`, and
`/var/log/mvd-edge/`.

## Commissioning

The installer enables the service for future boots but does not start it by
default. Edit the external config first:

```bash
sudo editor /etc/mvd-edge/edge.env
```

Then validate the external config:

```bash
sudo ./preflight.sh
```

This does not open the reader or contact cloud.

## Operator Commands

Future installer or operator commands:

```bash
sudo systemctl daemon-reload
sudo systemctl enable mvd-edge
sudo systemctl start mvd-edge
sudo systemctl status mvd-edge
sudo systemctl restart mvd-edge
sudo systemctl stop mvd-edge
journalctl -u mvd-edge
```

Do not run these on the macOS development machine.

## Failure Semantics

Missing required configuration is fatal and exits non-zero.

Reader unavailable is recoverable. The process remains alive, sends heartbeat
when possible, and retries discovery/reconnect.

Cloud unavailable is recoverable. Events remain in the SQLite queue and retry
later.

SQLite initialization failure is fatal because local persistence is required
before live event processing.

## Logging

Linux service logging uses stdout/stderr through the systemd journal.
`PYTHONUNBUFFERED=1` is set in the service so application output is visible
promptly in `journalctl`. `EDGE_LOG_DIR=/var/log/mvd-edge` is reserved for
future file logging or service packaging needs.

## Installer, Upgrades, And Uninstall

Installer paths:

```bash
packaging/linux/install.sh
packaging/linux/uninstall.sh
packaging/linux/preflight.sh
```

Upgrade behavior replaces the application runtime and service template while
preserving:

```text
/etc/mvd-edge/edge.env
/var/lib/mvd-edge/
/var/log/mvd-edge/
```

Default uninstall stops/disables the service and removes executable/service
files, but preserves config, runtime data, and logs. Full purge is an explicit
operator action, not the default.

Staged install test:

```bash
DESTDIR=/tmp/mvd-edge-test AGENT_RUNTIME_DIR=/path/to/dist/mvd-edge-agent sh packaging/linux/install.sh
```
