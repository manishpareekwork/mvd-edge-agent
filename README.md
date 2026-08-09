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

Edit `edge-agent/.env` with the local serial port and RFID API endpoint.

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
read `rfid-api/.env`.

## Hardware Defaults

- Device type: IDT-85
- Baud: 57600
- Reader address: 0x00
- Work mode: Answer Mode
- Serial default: `/dev/cu.usbserial-2120`

## Protocol

The IDT-85 inventory command, CRC algorithm, serial settings, parser behavior,
ENTER logic, EXIT timeout behavior, and API payload fields are preserved from
the original `continuous_reader.py`.

## Project Layout

```text
continuous_reader.py          Compatibility launcher
src/mvd_edge/app.py           Runtime loop
src/mvd_edge/config.py        Environment configuration
src/mvd_edge/adapters/idt85.py
src/mvd_edge/event_engine/state.py
src/mvd_edge/transport/cloud.py
tools/                        Commissioning and diagnostic scripts
legacy/                       Preserved experimental scripts
tests/                        Hardware-independent tests
```
