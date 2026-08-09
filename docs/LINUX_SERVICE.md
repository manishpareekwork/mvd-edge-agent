# MVD Insights Edge Agent Linux Service

This is the Linux service foundation for MVD Insights Edge Agent. It defines the
target layout and systemd template, but it is not a finished installer.

## Target Filesystem

```text
/opt/mvd-edge/                 application files and mvd-edge-agent
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

This step does not create the account. A future installer should create it,
own `/var/lib/mvd-edge/` and `/var/log/mvd-edge/`, and grant read access to
`/etc/mvd-edge/edge.env`.

## Serial Permissions

The `mvd-edge` user must be allowed to open the RS485/USB serial device. Many
Linux distributions use a serial access group such as `dialout`, but the exact
group is distro-dependent.

Example only:

```bash
sudo usermod -a -G dialout mvd-edge
```

`SERIAL_PORT=AUTO` still requires permission to open discovered serial devices.

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

Before enabling the service, validate the external config:

```bash
MVD_EDGE_CONFIG=/etc/mvd-edge/edge.env /opt/mvd-edge/mvd-edge-agent --check-config
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

Linux service logging initially uses stdout/stderr through the systemd journal.
`EDGE_LOG_DIR=/var/log/mvd-edge` is reserved for future file logging or service
packaging needs.

## Upgrades And Uninstall

Upgrade and uninstall behavior is pending installer work. Future installers
should stop the service, replace application files under `/opt/mvd-edge/`,
preserve `/etc/mvd-edge/edge.env` and `/var/lib/mvd-edge/`, then restart the
service.
