# MVD Insights Edge Agent Packaging

## Current Packaging Stage

- Python package: `mvd-insights-edge-agent`
- Python package import: `mvd_edge`
- Console entrypoint: `mvd-edge-agent`
- PyInstaller configuration: `packaging/pyinstaller/mvd-edge-agent.spec`
- Linux systemd template: `packaging/linux/systemd/mvd-edge.service`
- Windows service wrapper template: `packaging/windows/service/MVDInsightsEdgeAgent.xml`
- Linux installer foundation: `packaging/linux/install.sh`
- Linux uninstaller foundation: `packaging/linux/uninstall.sh`
- Linux release bundle assembler: `packaging/linux/assemble-release.sh`
- Windows scripted service foundation: `packaging/windows/scripts/`
- USB distribution template: `packaging/usb/`
- Initial build type: one-folder distribution
- macOS packaging proof: pending unless PyInstaller is installed locally
- Windows/Linux builds and service validation: pending

One-folder output is preferred for initial field validation because bundled
dependencies remain inspectable and troubleshooting is simpler than a one-file
archive.

## Target Artifacts

- Windows x64: `mvd-edge-agent.exe`
- Linux x64: `mvd-edge-agent`
- Linux ARM64: `mvd-edge-agent`

Windows executables must be built and tested on Windows. Linux x64 binaries
must be built and tested on Linux x64. Linux ARM64 binaries must be built and
tested on ARM64. A locally built macOS binary is only a macOS packaging proof.

## Build Command

```bash
python3 -m pip install -e ".[build]"
pyinstaller packaging/pyinstaller/mvd-edge-agent.spec
```

Equivalent helper:

```bash
sh scripts/build_local.sh
```

Expected native output:

```text
dist/mvd-edge-agent/
├── mvd-edge-agent
└── _internal/
```

Generated `build/` and `dist/` directories are ignored by Git.

## Configuration

Configuration remains external to the executable. Do not bake `.env` files or
secrets into build artifacts.

Config discovery order:

1. `MVD_EDGE_CONFIG=/path/to/edge.env`
2. `.env` next to the frozen executable
3. `.env` in the current working directory
4. development project `.env`

Field template:

```text
packaging/config/edge-agent.env.example
```

## Runtime Data

Runtime data remains external. Set `EDGE_DATA_DIR` in deployment config.

Current development fallback is `edge-agent/data/`. Future installers should
set platform paths such as:

- Windows: `ProgramData/MVDInsights/EdgeAgent`
- Linux: `/var/lib/mvd-edge`

## Logging

Current logging is terminal-oriented. `EDGE_LOG_DIR` is reserved for service
packaging and future persistent log redirection.

Linux service output should initially flow to the systemd journal. Windows
service output should be captured by the selected service wrapper with bounded
log retention.

## Service Foundation

Detailed service notes:

```text
docs/LINUX_SERVICE.md
docs/WINDOWS_SERVICE.md
```

Service deployments should provide explicit external paths:

```text
Linux config: /etc/mvd-edge/edge.env
Linux data:   /var/lib/mvd-edge
Linux logs:   /var/log/mvd-edge

Windows config: %ProgramData%\MVD Insights\Edge Agent\edge.env
Windows data:   %ProgramData%\MVD Insights\Edge Agent\data
Windows logs:   %ProgramData%\MVD Insights\Edge Agent\logs
```

Before starting a service, run:

```bash
mvd-edge-agent --check-config
```

Missing required configuration and SQLite initialization failures are fatal.
Reader unavailable and cloud unavailable are recoverable runtime states.

## Linux Installer Foundation

Script path:

```bash
packaging/linux/install.sh
```

The script is designed for an already-built Linux artifact and does not attempt
to build Linux binaries from macOS. It installs the complete PyInstaller onedir
runtime:

```text
/opt/mvd-edge/mvd-edge-agent
/opt/mvd-edge/_internal/
/opt/mvd-edge/docs/LINUX_SERVICE.md
/etc/mvd-edge/edge.env
/var/lib/mvd-edge/
/var/log/mvd-edge/
/etc/systemd/system/mvd-edge.service
```

Upgrade behavior is intentionally conservative: the binary and systemd unit may
be replaced, and stale application runtime files under `/opt/mvd-edge/` may be
removed, but an existing `/etc/mvd-edge/edge.env`, SQLite data under
`/var/lib/mvd-edge/`, and logs under `/var/log/mvd-edge/` are preserved.

Default first install behavior is commissioning-friendly:

- create the service account
- add the service account to `dialout` when present
- install the application runtime
- create `/etc/mvd-edge/edge.env` from the blank template only if absent
- install and enable the systemd service for future boots
- do not run preflight by default
- do not start the service by default

After editing `/etc/mvd-edge/edge.env`, run explicit preflight and start:

```bash
sudo ./preflight.sh
sudo systemctl start mvd-edge
```

Safe staged validation is supported:

```bash
DESTDIR=/tmp/mvd-edge-test AGENT_RUNTIME_DIR=/path/to/dist/mvd-edge-agent sh packaging/linux/install.sh
DESTDIR=/tmp/mvd-edge-test sh packaging/linux/uninstall.sh
```

Staged install does not create users, call systemd, or touch real `/opt`,
`/etc`, or `/var`.

## Linux Preflight

Script path:

```bash
packaging/linux/preflight.sh
```

Preflight checks the executable, config file, writable data/log directories,
serial setting syntax, API URL presence, API key presence without printing the
key, and `mvd-edge-agent --check-config`.

Hardware and cloud connectivity tests remain future optional flags.

## Linux Aarch64 Release Bundle

Build on the Debian 12 aarch64 gateway or an equivalent native aarch64 Linux
environment:

```bash
python3 -m pip install -e ".[build]"
pyinstaller packaging/pyinstaller/mvd-edge-agent.spec
ARCH=aarch64 sh packaging/linux/assemble-release.sh
```

Expected bundle:

```text
release/mvd-edge-agent-<pyproject-version>-linux-aarch64/
├── executable/
│   ├── mvd-edge-agent
│   └── _internal/
├── install.sh
├── uninstall.sh
├── preflight.sh
├── config/edge.env.example
├── systemd/mvd-edge.service
├── docs/LINUX_SERVICE.md
└── INSTALL.md
```

The bundle is self-contained for installation on another Debian 12 aarch64
gateway. It must not include Git metadata, `.env`, API keys, development venvs,
tests, SQLite runtime data, logs, or source code.

## Windows Installation Foundation

Script paths:

```text
packaging/windows/scripts/install-service.ps1
packaging/windows/scripts/uninstall-service.ps1
packaging/windows/scripts/check-install.ps1
```

The scripts are written for a future Windows bundle containing
`mvd-edge-agent.exe`, the reviewed WinSW wrapper executable, and
`MVDInsightsEdgeAgent.xml`. They preserve existing ProgramData configuration,
data, and logs by default.

This repository does not bundle a WinSW executable. See
`packaging/windows/THIRD_PARTY.md`.

## USB Distribution Template

Template path:

```text
packaging/usb/
```

The USB directory documents the future offline bundle layout and includes
driver guidance plus a technician quick start. It intentionally contains no
fake executables, third-party binaries, proprietary drivers, or generated
checksums.

## Security

Never embed `RFID_INGEST_API_KEY`, Supabase keys, production `.env` files, or
other secrets in the executable or build artifacts. Deployment-specific
configuration must be supplied externally.

## Future Installer Layer

Future Windows installer:

```text
MVDInsightsEdgeAgent-Setup.exe
```

Future Linux package:

```text
install package/script
```

USB bundle shape:

```text
MVD-Edge-Agent/
├── WINDOWS/
├── LINUX-X64/
├── LINUX-ARM64/
├── CONFIG/
├── DRIVERS/
├── DOCS/
└── checksums.txt
```

Future technician flow:

```text
connect reader -> insert USB -> run installer -> configure -> validate -> start service
```

## Future Cloud Distribution

Future releases can use GitHub Releases or MVD-hosted signed downloads with
versioned artifacts that match the package version.

Pending release requirements:

- checksums
- signing
- release notes
- rollback
- trusted distribution
- auto-update policy
