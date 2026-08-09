# MVD Insights Edge Agent Packaging

## Current Packaging Stage

- Python package: `mvd-insights-edge-agent`
- Python package import: `mvd_edge`
- Console entrypoint: `mvd-edge-agent`
- PyInstaller configuration: `packaging/pyinstaller/mvd-edge-agent.spec`
- Linux systemd template: `packaging/linux/systemd/mvd-edge.service`
- Windows service wrapper template: `packaging/windows/service/MVDInsightsEdgeAgent.xml`
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

Expected local output:

```text
dist/mvd-edge-agent/
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

Before enabling a service, run:

```bash
mvd-edge-agent --check-config
```

Missing required configuration and SQLite initialization failures are fatal.
Reader unavailable and cloud unavailable are recoverable runtime states.

## Security

Never embed `RFID_INGEST_API_KEY`, Supabase keys, production `.env` files, or
other secrets in the executable or build artifacts. Deployment-specific
configuration must be supplied externally.

## Future Installer Layer

Future Windows installer:

```text
MVDInsightsEdgeAgent-Setup.exe
```

Future Linux installer/package:

```text
install package/script
```

Future USB bundle shape:

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
versioned artifacts such as `v0.1.0`.

Pending release requirements:

- checksums
- signing
- release notes
- rollback
- trusted distribution
- auto-update policy
