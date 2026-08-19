from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def sanitize_error(error: str, max_length: int = 200) -> str:
    return error.replace("\n", " ").replace("\r", " ").strip()[:max_length]


class ReaderHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    RECONNECTING = "RECONNECTING"


@dataclass
class HealthState:
    reader_state: str = "DISCONNECTED"
    last_reader_activity_at: Optional[str] = None
    last_event_at: Optional[str] = None
    last_cloud_delivery_at: Optional[str] = None
    last_error: Optional[str] = None
    last_error_at: Optional[str] = None
    reader_connected: bool = False
    inventory_responding: bool = False
    last_successful_inventory_at: Optional[str] = None
    last_tag_seen_at: Optional[str] = None
    last_epc_seen: Optional[str] = None
    consecutive_no_response_count: int = 0
    malformed_response_count: int = 0
    reconnect_count: int = 0
    last_reader_error: Optional[str] = None
    health_status: str = ReaderHealthStatus.OFFLINE.value
    offline_failure_threshold: int = 3

    def set_reader_state(self, reader_state: str) -> None:
        self.reader_state = reader_state

    def mark_reader_activity(self) -> None:
        self.last_reader_activity_at = utc_timestamp()

    def mark_reader_connecting(self) -> None:
        self.reader_connected = False
        self.inventory_responding = False
        self.health_status = ReaderHealthStatus.RECONNECTING.value

    def mark_reader_ready(self) -> None:
        self.reader_connected = True
        if self.health_status in (
            ReaderHealthStatus.OFFLINE.value,
            ReaderHealthStatus.RECONNECTING.value,
        ):
            self.health_status = ReaderHealthStatus.DEGRADED.value

    def mark_reconnect_attempt(self) -> None:
        self.reconnect_count += 1
        self.mark_reader_connecting()

    def mark_inventory_success(self, tags: list[str]) -> None:
        now = utc_timestamp()
        self.reader_connected = True
        self.inventory_responding = True
        self.last_reader_activity_at = now
        self.last_successful_inventory_at = now
        self.consecutive_no_response_count = 0
        self.last_reader_error = None
        self.health_status = ReaderHealthStatus.HEALTHY.value

        if tags:
            self.last_tag_seen_at = now
            self.last_epc_seen = tags[-1]

    def mark_inventory_no_response(self) -> None:
        self.reader_connected = True
        self.inventory_responding = False
        self.consecutive_no_response_count += 1
        self.last_reader_error = "NO_RESPONSE"
        self.health_status = (
            ReaderHealthStatus.OFFLINE.value
            if self.consecutive_no_response_count >= self.offline_failure_threshold
            else ReaderHealthStatus.DEGRADED.value
        )

    def mark_inventory_malformed(self) -> None:
        self.reader_connected = True
        self.inventory_responding = False
        self.malformed_response_count += 1
        self.last_reader_error = "MALFORMED"
        self.health_status = ReaderHealthStatus.DEGRADED.value

    def mark_reader_offline(self, error: str) -> None:
        self.reader_connected = False
        self.inventory_responding = False
        self.last_reader_error = sanitize_error(error)
        self.health_status = ReaderHealthStatus.OFFLINE.value

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
            "reader_connected": self.reader_connected,
            "inventory_responding": self.inventory_responding,
            "last_successful_inventory_at": self.last_successful_inventory_at,
            "last_tag_seen_at": self.last_tag_seen_at,
            "last_epc_seen": self.last_epc_seen,
            "consecutive_no_response_count": self.consecutive_no_response_count,
            "malformed_response_count": self.malformed_response_count,
            "reconnect_count": self.reconnect_count,
            "last_reader_error": self.last_reader_error,
            "health_status": self.health_status,
            "rfid_health_status": self.health_status,
            "reader_error_summary": self.last_reader_error,
        }
