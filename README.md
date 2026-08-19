# MVD Insights Edge Agent

Portable runtime for connecting physical devices to the MVD Insights Event &
Automation Platform.

Current supported adapter:

- IDT-85 UHF RFID Reader

Current flow:

```text
IDT-85 -> RS485/USB converter -> Edge Agent -> HTTPS -> MVD Insights Cloud API
```

## Development Status

- macOS: currently validated
- Windows: packaging/validation pending
- Linux: packaging/validation pending
- Industrial PC: planned/validation pending

## Setup

```bash
cd edge-agent
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
```

Edit `edge-agent/.env` with the local serial port and RFID API endpoint. Keep
deployment secrets outside source control.

## Run

```bash
python continuous_reader.py
```

Preferred package command:

```bash
python -m mvd_edge.app
```

Installed console script:

```bash
mvd-edge-agent
```

All commands read configuration from `edge-agent/.env`. The edge agent does not
read `rfid-api/.env`. Packaged or field runs can point at an explicit config
file:

```bash
MVD_EDGE_CONFIG=/path/to/edge.env mvd-edge-agent --check-config
```

Safe CLI checks:

```bash
mvd-edge-agent --version
mvd-edge-agent --check-config
```

Queue configuration:

```text
EDGE_DATA_DIR=
EDGE_LOG_DIR=
QUEUE_RETRY_INTERVAL=5
QUEUE_BATCH_SIZE=20
SERIAL_RECONNECT_INTERVAL=5
AUTO_CONFIGURE_READER=false
HEARTBEAT_INTERVAL=30
APPLICATION_PROFILE=RFID_ASSET_TRACKING
SITE_ID=
LOCATION_ID=
ZONE_ID=
DEVICE_ID=
READER_ID=
TARGET_READ_DISTANCE_M=
```

When `EDGE_DATA_DIR` is blank, runtime data is stored under `edge-agent/data/`.
That directory is ignored by Git.

## Packaging

Packaging foundation lives in `docs/PACKAGING.md`. The current build target is a
PyInstaller one-folder distribution named `mvd-edge-agent`, with external
configuration and runtime data. Linux installation copies the complete onedir
runtime while preserving `/opt/mvd-edge/mvd-edge-agent` as the service
executable. Windows, Linux x64, and Linux ARM64 artifacts must each be built and
tested on their target platform.

Service foundation docs:

```text
docs/LINUX_SERVICE.md
docs/WINDOWS_SERVICE.md
```

## Hardware Defaults

- Device type: IDT-85
- Baud: 57600
- Reader address: 0x00
- Work mode: Answer Mode
- Serial default: `AUTO`

## Protocol

The IDT-85 inventory command, CRC algorithm, serial settings, parser behavior,
ENTER logic, EXIT timeout behavior, and API payload fields are preserved from
the original `continuous_reader.py`.

Each ENTER or EXIT event receives a stable edge-generated UUID in
`edge_event_id`. The transport includes that same ID on every send attempt so
the API can treat retries as one logical event.

## Local Store-and-Forward

Every ENTER or EXIT event is written to a local SQLite queue before cloud
delivery is attempted. If the API or network is unavailable, the event remains
queued as `PENDING` and is retried by the running edge process.

Queued events are delivered oldest first in bounded batches. A cloud response
with `status` equal to `stored` or `already_stored` marks the local event as
`DELIVERED`; delivered records are retained for diagnostics. Future cleanup
policy will define delivered-record pruning.

The stable `edge_event_id` is stored inside each queued payload and reused on
retry, so retry delivery is safe against duplicate cloud records.

Follow-up: cloud/API delivery currently runs in the same process loop as RFID
inventory. Slow cloud calls or a large pending retry batch can stretch the
effective inventory polling cadence. Edge Agent 0.1.4 intentionally does not
change this behavior.

## Reader Connection Recovery

The agent can start when the configured serial reader is unavailable. It still
opens the local SQLite queue, reports pending depth, and attempts cloud
delivery for queued events while retrying the reader connection separately.

On reader connection, the IDT-85 adapter verifies protocol communication, reads
the reader work mode, and only resumes inventory when the reader is in Answer
Mode. If `AUTO_CONFIGURE_READER=false`, a non-Answer mode is reported as a
commissioning error and the agent keeps retrying without changing hardware
configuration. If `AUTO_CONFIGURE_READER=true`, the agent sends the existing
Set Work Mode command for Answer Mode, verifies the mode again, and proceeds
only after verification.

During reader communication loss, the agent closes the stale serial handle and
retries after `SERIAL_RECONNECT_INTERVAL`. Inventory state is not updated while
the reader is unavailable, so a USB unplug or reader power loss does not create
false EXIT events for tags that were last known to be present.

## Heartbeat / Health

The agent sends a lightweight heartbeat to the API every `HEARTBEAT_INTERVAL`
seconds. `DEVICE_ID` identifies the edge machine or controller, while
`READER_ID` identifies the current attached RFID reader.

Heartbeat health separates these conditions:

- Edge Agent alive: the process can report health.
- Reader connected: `reader_state` reports `READY`, `DISCONNECTED`,
  `CONNECTING`, or `CONFIG_ERROR`.
- Cloud queue healthy: `queue_pending` reports local undelivered event depth.

An agent can be alive while the reader is disconnected. In that state,
heartbeats continue and queued RFID events can still synchronize to cloud.
Future dashboard logic can consider a device stale when its last heartbeat is
older than about 2-3 heartbeat intervals.

## Automatic Reader Discovery

Set `SERIAL_PORT=AUTO` to let the agent scan serial interfaces using pyserial
port enumeration. Each candidate is opened at `SERIAL_BAUD` and probed only
with the safe Get Reader Information command. Discovery does not inventory
tags, change Answer Mode, or send RF tuning commands.

If exactly one compatible reader responds, the agent selects that port. If no
reader responds, the agent stays alive and retries discovery on the normal
serial reconnect interval. If multiple readers respond, the agent refuses to
choose one automatically and reports that `SERIAL_PORT` must be configured
explicitly. In AUTO mode, reconnect attempts rerun discovery, so a reader that
reenumerates from `/dev/ttyUSB0` to `/dev/ttyUSB1` can recover automatically.

For diagnostics, run:

```bash
python tools/probe_reader.py
```

The probe tool lists serial candidates, non-sensitive USB metadata when
available, and whether each port returned an IDT-85 compatible response.

## Installation Identity

Commissioning identity is local configuration:

- `APPLICATION_PROFILE`
- `SITE_ID`
- `LOCATION_ID`
- `ZONE_ID`
- `DEVICE_ID`
- `READER_ID`

`DEVICE_ID` identifies the edge machine or controller. `READER_ID` identifies
the current logical RFID reader. Future deployments may attach multiple inputs
to one device, but the current runtime remains single-reader.

## RFID Read Zone

`TARGET_READ_DISTANCE_M` is an optional commissioning target for the intended
read zone. It must be a positive number when provided.

This value does not guarantee an exact RF boundary. The IDT-85 read range is
nominally about 0-8 m, and actual range depends on reader RF settings, antenna,
tag type and orientation, environment, metal/liquid, reflections, and
installation geometry. This step stores and documents the target only; verified
reader-specific RF tuning and physical read-zone validation remain future work.

## Project Layout

```text
continuous_reader.py          Compatibility launcher
src/mvd_edge/app.py           Runtime loop
src/mvd_edge/config.py        Environment configuration
src/mvd_edge/adapters/idt85.py
src/mvd_edge/event_engine/state.py
src/mvd_edge/storage/queue.py
src/mvd_edge/transport/cloud.py
tools/                        Commissioning and diagnostic scripts
legacy/                       Preserved experimental scripts
tests/                        Hardware-independent tests
```
