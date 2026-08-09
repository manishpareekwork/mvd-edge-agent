from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


EDGE_AGENT_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class EdgeConfig:
    device_type: str
    reader_id: str
    serial_port: str
    serial_baud: int
    rfid_api_url: str
    rfid_ingest_api_key: Optional[str]
    scan_interval: float
    exit_timeout: float

    @classmethod
    def from_env(cls, env_file: Optional[Path] = None) -> "EdgeConfig":
        configured_env_file = os.getenv("MVD_EDGE_ENV_FILE")
        selected_env_file = (
            Path(configured_env_file)
            if configured_env_file
            else env_file or EDGE_AGENT_DIR / ".env"
        )

        load_dotenv(selected_env_file)

        rfid_api_url = os.getenv("RFID_API_URL")

        if not rfid_api_url:
            raise RuntimeError(
                f"RFID_API_URL missing from {selected_env_file}"
            )

        return cls(
            device_type=os.getenv("DEVICE_TYPE", "IDT85"),
            reader_id=os.getenv("READER_ID", "LAB-RFID-01"),
            serial_port=os.getenv("SERIAL_PORT", "/dev/cu.usbserial-2120"),
            serial_baud=int(os.getenv("SERIAL_BAUD", "57600")),
            rfid_api_url=rfid_api_url,
            rfid_ingest_api_key=os.getenv("RFID_INGEST_API_KEY") or None,
            scan_interval=float(os.getenv("SCAN_INTERVAL", "0.5")),
            exit_timeout=float(os.getenv("EXIT_TIMEOUT", "3.0")),
        )
