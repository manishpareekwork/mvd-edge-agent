# Reader Tools

One-off diagnostics and reader configuration helpers live here. These scripts
are useful during hardware commissioning but are not the production edge agent.

Review serial port constants before running a tool on a new machine.

`probe_reader.py` is safe to run during commissioning. It scans serial ports
with pyserial, sends only the Get Reader Information command, and reports
compatible reader responses without changing reader configuration.
