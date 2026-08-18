from dataclasses import dataclass
import os
from pathlib import Path
import sys
from typing import Optional

from dotenv import dotenv_values, load_dotenv

from mvd_edge.adapters.idt85 import SUPPORTED_VERIFY_METHODS


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

    parsed = parse_float(name, value)

    if parsed <= 0:
        raise ValueError(f"{name} must be positive")

    return parsed


def required_string(name: str, value: Optional[str]) -> str:
    if value is None or not value.strip():
        raise RuntimeError(f"{name} is required")

    return value.strip()


def parse_int(name: str, value: Optional[str], *, minimum: Optional[int] = None) -> int:
    try:
        parsed = int(required_string(name, value))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc

    if minimum is not None and parsed < minimum:
        raise ValueError(f"{name} must be at least {minimum}")

    return parsed


def parse_float(
    name: str,
    value: Optional[str],
    *,
    minimum: Optional[float] = None,
    exclusive_minimum: bool = False,
) -> float:
    try:
        parsed = float(required_string(name, value))
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc

    if minimum is not None:
        if exclusive_minimum and parsed <= minimum:
            raise ValueError(f"{name} must be greater than {minimum:g}")
        if not exclusive_minimum and parsed < minimum:
            raise ValueError(f"{name} must be at least {minimum:g}")

    return parsed


def parse_bool(name: str, value: Optional[str]) -> bool:
    normalized = required_string(name, value).lower()

    if normalized in ("1", "true", "yes", "on"):
        return True

    if normalized in ("0", "false", "no", "off"):
        return False

    raise ValueError(f"{name} must be true or false")


def parse_reader_address(name: str, value: Optional[str]) -> int:
    raw = required_string(name, value)

    try:
        parsed = int(raw, 0)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer from 0x00 to 0xFF") from exc

    if parsed < 0 or parsed > 0xFF:
        raise ValueError(f"{name} must be between 0x00 and 0xFF")

    return parsed


def parse_verify_method(name: str, value: Optional[str]) -> str:
    parsed = required_string(name, value).upper()

    if parsed not in SUPPORTED_VERIFY_METHODS:
        supported = ", ".join(SUPPORTED_VERIFY_METHODS)
        raise ValueError(f"{name} must be one of: {supported}")

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
    reader_address: int
    reader_verify_method: str
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
    reader_discovery_interval: float
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

        def get_env(
            name: str,
            default: Optional[str] = None,
            *,
            allow_process_env: bool = False,
        ) -> Optional[str]:
            if name in file_values:
                return file_values[name]

            if selected_env_file.exists() and not allow_process_env:
                return default

            return os.getenv(name, default)

        rfid_api_url = required_string("RFID_API_URL", get_env("RFID_API_URL"))

        serial_reconnect_interval = parse_float(
            "SERIAL_RECONNECT_INTERVAL",
            get_env("SERIAL_RECONNECT_INTERVAL", "5"),
            minimum=0,
            exclusive_minimum=True,
        )

        return cls(
            application_profile=required_string(
                "APPLICATION_PROFILE",
                get_env(
                    "APPLICATION_PROFILE",
                    "RFID_ASSET_TRACKING",
                ),
            ),
            site_id=required_string("SITE_ID", get_env("SITE_ID")),
            location_id=required_string("LOCATION_ID", get_env("LOCATION_ID")),
            zone_id=required_string("ZONE_ID", get_env("ZONE_ID")),
            device_id=required_string("DEVICE_ID", get_env("DEVICE_ID")),
            device_type=required_string(
                "DEVICE_TYPE",
                get_env("DEVICE_TYPE", "IDT85"),
            ),
            reader_id=required_string("READER_ID", get_env("READER_ID")),
            reader_address=parse_reader_address(
                "READER_ADDRESS",
                get_env("READER_ADDRESS", "0x00"),
            ),
            reader_verify_method=parse_verify_method(
                "READER_VERIFY_METHOD",
                get_env("READER_VERIFY_METHOD", "AUTO"),
            ),
            serial_port=required_string(
                "SERIAL_PORT",
                get_env("SERIAL_PORT", "AUTO"),
            ),
            serial_baud=parse_int(
                "SERIAL_BAUD",
                get_env("SERIAL_BAUD", "57600"),
                minimum=1,
            ),
            rfid_api_url=rfid_api_url,
            rfid_ingest_api_key=required_string(
                "RFID_INGEST_API_KEY",
                get_env("RFID_INGEST_API_KEY"),
            ),
            scan_interval=parse_float(
                "SCAN_INTERVAL",
                get_env("SCAN_INTERVAL", "0.5"),
                minimum=0,
                exclusive_minimum=True,
            ),
            exit_timeout=parse_float(
                "EXIT_TIMEOUT",
                get_env("EXIT_TIMEOUT", "3.0"),
                minimum=0,
                exclusive_minimum=True,
            ),
            edge_data_dir=Path(
                get_env("EDGE_DATA_DIR", allow_process_env=True)
                or str(EDGE_AGENT_DIR / "data")
            ),
            queue_retry_interval=parse_float(
                "QUEUE_RETRY_INTERVAL",
                get_env("QUEUE_RETRY_INTERVAL", "5"),
                minimum=0,
                exclusive_minimum=True,
            ),
            queue_batch_size=parse_int(
                "QUEUE_BATCH_SIZE",
                get_env("QUEUE_BATCH_SIZE", "20"),
                minimum=1,
            ),
            serial_reconnect_interval=serial_reconnect_interval,
            reader_discovery_interval=parse_float(
                "READER_DISCOVERY_INTERVAL",
                get_env(
                    "READER_DISCOVERY_INTERVAL",
                    str(serial_reconnect_interval),
                ),
                minimum=0,
                exclusive_minimum=True,
            ),
            auto_configure_reader=parse_bool(
                "AUTO_CONFIGURE_READER",
                get_env("AUTO_CONFIGURE_READER", "false"),
            ),
            heartbeat_interval=parse_float(
                "HEARTBEAT_INTERVAL",
                get_env("HEARTBEAT_INTERVAL", "30"),
                minimum=0,
                exclusive_minimum=True,
            ),
            heartbeat_api_url=(
                get_env("HEARTBEAT_API_URL")
                or default_heartbeat_url(rfid_api_url)
            ),
            target_read_distance_m=optional_positive_float(
                "TARGET_READ_DISTANCE_M",
                get_env("TARGET_READ_DISTANCE_M"),
            ),
            edge_log_dir=(
                Path(get_env("EDGE_LOG_DIR", allow_process_env=True))
                if get_env("EDGE_LOG_DIR", allow_process_env=True)
                else None
            ),
        )
