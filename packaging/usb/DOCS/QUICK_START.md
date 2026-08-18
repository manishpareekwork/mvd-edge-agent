# Field Quick Start

This foundation has not yet been field-tested on Windows or Linux industrial
PCs. Use it for controlled commissioning only.

1. Connect the IDT-85 reader and RS485/USB converter or native serial link.
2. Install the Edge Agent.
   - Linux: `sudo ./install.sh`
   - Windows: run the future installer or elevated `install-service.ps1`.
3. Create or edit `edge.env`.
4. Set `DEVICE_ID`, `READER_ID`, `SITE_ID`, `LOCATION_ID`, and `ZONE_ID`.
5. Set `APPLICATION_PROFILE`.
6. Set `RFID_API_URL`.
7. Set `RFID_INGEST_API_KEY`.
8. Leave `SERIAL_PORT=AUTO` for initial commissioning unless a specific port
   has already been validated.
9. Set `TARGET_READ_DISTANCE_M` as the requested physical read-zone target.
10. Run `mvd-edge-agent --check-config`.
11. Run the safe reader probe if needed.
12. Start or install the service.
13. Scan a known test tag and confirm ENTER locally, in cloud ingestion, and on
   the dashboard.
14. Remove the tag and confirm EXIT.
15. Record commissioning results in the checklist.

Read distance is environmental. A target such as `3 m` must be physically
validated at the installed location. Record the measured reliable detection
range and mark the read-zone test as PASS or ADJUSTMENT REQUIRED.
