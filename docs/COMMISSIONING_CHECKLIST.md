# MVD Insights Edge Agent Commissioning Checklist

## Site Information

- Site ID:
- Location ID:
- Zone ID:
- Application Profile:

## Edge Device

- Device ID:
- OS:
- Edge Agent Version:

## Reader

- Reader ID:
- Reader Type:
- Serial Port:
- Baud:
- Reader Work Mode:

## RFID Read Zone

- Target Read Distance:
- Physical Test Distance:
- Requested Distance:
- Measured Reliable Detection:
- Status: PASS / ADJUSTMENT REQUIRED
- Tag Type:
- Notes:

`TARGET_READ_DISTANCE_M` is a commissioning target, not RF calibration. Validate
the real read zone physically because RFID range depends on environment,
mounting, antenna orientation, tag type, and nearby materials.

Example:

```text
Requested: 3 m
Measured reliable detection: 2.7-3.2 m
Status: PASS
```

## Cloud

- API connectivity:
- Authentication:
- Heartbeat:

## Functional Test

- ENTER:
- EXIT:
- Offline queue:
- Reconnect:

## Dashboard

- Event visible:
- Current state correct:

## Sign-Off

- Technician:
- Customer representative:
- Date:
- Notes:
