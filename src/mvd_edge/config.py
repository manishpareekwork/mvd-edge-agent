from dataclasses import dataclass
import os
from pathlib import Path
import sys
from typing import Optional

from dotenv import dotenv_values, load_dotenv


EDGE_AGENT_DIR = Path(__file__).resolve().parents[2]
CONFIG_ENV_VAR = "MVD_EDGE_CONFIG"
LEGACY_CONFIG_ENV_VAR = "MVD_EDGE_ENV_FILE"


def default_heartbeat_url(rfid_api_url: str) -> str:
    event_path = "/api/v1/rfid/events"

    if rfid_api_url.endswith(event_path):
        return rfid_api_url[: -len(event_path)] + "/api/v1/edge/heartbeat"

    return rfid_api_url.rstrip("/") + "/api/v1/edge/heartbeat"


def optional_positive_float(name: str, value: Optional[str]) -> Optional[float]:
    if not value:
        return None

    parsed = float(value)

    if parsed <= 0:
        raise ValueError(f"{name} must be positive")

    return parsed


def runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path.cwd()


def discover_config_file(env_file: Optional[Path] = None) -> Path:
    if env_file:
        return Path(env_file)

    configured_env_file = os.getenv(CONFIG_ENV_VAR) or os.getenv(LEGACY_CONFIG_ENV_VAR)

    if configured_env_file:
        return Path(configured_env_file)

    runtime_env_file = runtime_dir() / ".env"

    if runtime_env_file.exists():
        return runtime_env_file

    return EDGE_AGENT_DIR / ".env"


@dataclass(frozen=True)
class EdgeConfig:
    application_profile: str
    site_id: str
    location_id: str
    zone_id: str
    device_id: str
    device_type: str
    reader_id: str
    serial_port: str
    serial_baud: int
    rfid_api_url: str
    rfid_ingest_api_key: Optional[str]
    scan_interval: float
    exit_timeout: float
    edge_data_dir: Path
    queue_retry_interval: float
    queue_batch_size: int
    serial_reconnect_interval: float
    auto_configure_reader: bool
    heartbeat_interval: float
    heartbeat_api_url: str
    target_read_distance_m: Optional[float]
    edge_log_dir: Optional[Path]

    @classmethod
    def from_env(cls, env_file: Optional[Path] = None) -> "EdgeConfig":
        selected_env_file = discover_config_file(env_file)

        load_dotenv(selected_env_file, override=True)
        file_values = dotenv_values(selected_env_file)

        def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
            if name in file_values:
                return file_values[name]

            if selected_env_file.exists():
                return default

            return os.getenv(name, default)

        rfid_api_url = get_env("RFID_API_URL")

        if not rfid_api_url:
            raise RuntimeError(
                f"RFID_API_URL missing from {selected_env_file}"
            )

        return cls(
            application_profile=get_env(
                "APPLICATION_PROFILE",
                "RFID_ASSET_TRACKING",
            ),
            site_id=get_env("SITE_ID", "EXPERIENCE-CENTER"),
            location_id=get_env("LOCATION_ID", "GATE-1"),
            zone_id=get_env("ZONE_ID", "INBOUND"),
            device_id=get_env("DEVICE_ID", "EXP-CENTER-EDGE-01"),
            device_type=get_env("DEVICE_TYPE", "IDT85"),
            reader_id=get_env("READER_ID", "LAB-RFID-01"),
            serial_port=get_env("SERIAL_PORT", "AUTO"),
            serial_baud=int(get_env("SERIAL_BAUD", "57600")),
            rfid_api_url=rfid_api_url,
            rfid_ingest_api_key=get_env("RFID_INGEST_API_KEY") or None,
            scan_interval=float(get_env("SCAN_INTERVAL", "0.5")),
            exit_timeout=float(get_env("EXIT_TIMEOUT", "3.0")),
            edge_data_dir=Path(
                get_env("EDGE_DATA_DIR") or str(EDGE_AGENT_DIR / "data")
            ),
            queue_retry_interval=float(get_env("QUEUE_RETRY_INTERVAL") or "5"),
            queue_batch_size=int(get_env("QUEUE_BATCH_SIZE") or "20"),
            serial_reconnect_interval=float(
                get_env("SERIAL_RECONNECT_INTERVAL") or "5"
            ),
            auto_configure_reader=(
                get_env("AUTO_CONFIGURE_READER", "false").lower()
                in ("1", "true", "yes", "on")
            ),
            heartbeat_interval=float(get_env("HEARTBEAT_INTERVAL") or "30"),
            heartbeat_api_url=(
                get_env("HEARTBEAT_API_URL")
                or default_heartbeat_url(rfid_api_url)
            ),
            target_read_distance_m=optional_positive_float(
                "TARGET_READ_DISTANCE_M",
                get_env("TARGET_READ_DISTANCE_M"),
            ),
            edge_log_dir=(
                Path(get_env("EDGE_LOG_DIR"))
                if get_env("EDGE_LOG_DIR")
                else None
            ),
        )
