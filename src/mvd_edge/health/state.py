from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def sanitize_error(error: str, max_length: int = 200) -> str:
    return error.replace("\n", " ").replace("\r", " ").strip()[:max_length]


@dataclass
class HealthState:
    reader_state: str = "DISCONNECTED"
    last_reader_activity_at: Optional[str] = None
    last_event_at: Optional[str] = None
    last_cloud_delivery_at: Optional[str] = None
    last_error: Optional[str] = None
    last_error_at: Optional[str] = None

    def set_reader_state(self, reader_state: str) -> None:
        self.reader_state = reader_state

    def mark_reader_activity(self) -> None:
        self.last_reader_activity_at = utc_timestamp()

    def mark_event(self) -> None:
        self.last_event_at = utc_timestamp()

    def mark_cloud_delivery(self) -> None:
        self.last_cloud_delivery_at = utc_timestamp()

    def mark_error(self, error: str) -> None:
        self.last_error = sanitize_error(error)
        self.last_error_at = utc_timestamp()

    def clear_error(self) -> None:
        self.last_error = None
        self.last_error_at = None

    def payload(
        self,
        *,
        device_id: str,
        reader_id: str,
        agent_version: str,
        serial_port: str,
        queue_pending: int,
    ) -> dict[str, object]:
        return {
            "device_id": device_id,
            "reader_id": reader_id,
            "agent_version": agent_version,
            "reader_state": self.reader_state,
            "serial_port": serial_port,
            "queue_pending": queue_pending,
            "last_reader_activity_at": self.last_reader_activity_at,
            "last_event_at": self.last_event_at,
            "last_cloud_delivery_at": self.last_cloud_delivery_at,
            "reported_at": utc_timestamp(),
            "last_error": self.last_error,
            "last_error_at": self.last_error_at,
        }
