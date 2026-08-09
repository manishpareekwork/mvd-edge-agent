# MVD Insights Edge Agent Windows Service

This is the Windows service foundation for MVD Insights Edge Agent. It defines
the target layout and service wrapper configuration, but it is not a finished
installer and has not been validated on Windows in this step.

## Service Architecture

Use the PyInstaller-built executable with an external Windows service wrapper.
The selected first wrapper strategy is WinSW because it can run an existing
`.exe` as a Windows Service without requiring Python on the customer machine.

This step does not download WinSW binaries. A future installer or release
bundle must provide the wrapper binary and verify its version, checksum, and
signature.

## Target Filesystem

```text
C:\Program Files\MVD Insights\Edge Agent\
    mvd-edge-agent.exe
    MVDInsightsEdgeAgent.exe
    MVDInsightsEdgeAgent.xml

C:\ProgramData\MVD Insights\Edge Agent\
    edge.env
    data\
    logs\
```

Writable configuration, data, and logs use ProgramData rather than Program
Files.

## Service Identity

```text
Service name: MVDInsightsEdgeAgent
Display name: MVD Insights Edge Agent
Description: Connects local devices to the MVD Insights Event & Automation Platform.
```

## Service Template

Template path:

```text
packaging/windows/service/MVDInsightsEdgeAgent.xml
```

The template sets:

```text
MVD_EDGE_CONFIG=%ProgramData%\MVD Insights\Edge Agent\edge.env
EDGE_DATA_DIR=%ProgramData%\MVD Insights\Edge Agent\data
EDGE_LOG_DIR=%ProgramData%\MVD Insights\Edge Agent\logs
```

The wrapper starts automatically and restarts the process on failure. Log output
is directed to ProgramData logs with size-based rotation in the template.

## Commissioning

Before installing or starting the service, validate config from an elevated or
service-equivalent shell:

```powershell
$env:MVD_EDGE_CONFIG = "$env:ProgramData\MVD Insights\Edge Agent\edge.env"
& "C:\Program Files\MVD Insights\Edge Agent\mvd-edge-agent.exe" --check-config
```

This does not open the reader or contact cloud.

## Service Runtime Requirements

The runtime must not depend on an open terminal, desktop login, a user home
directory, or a current working directory. The service wrapper supplies explicit
config, data, and log paths.

The Windows service account must have access to the serial adapter and write
access to ProgramData data/log directories. Automatic permission configuration
is pending installer work.

## Failure Semantics

Missing required configuration is fatal and exits non-zero.

Reader unavailable is recoverable. The process stays alive, reports health when
possible, and retries discovery/reconnect.

Cloud unavailable is recoverable. Events remain in the SQLite queue and retry
later.

SQLite initialization failure is fatal because local persistence is required
before live event processing.

## Current Limitations

Windows service validation, installer creation, service-account setup,
automatic permission configuration, code signing, and upgrade/rollback are
pending future steps.
