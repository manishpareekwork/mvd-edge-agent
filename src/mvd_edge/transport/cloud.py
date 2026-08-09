import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import requests


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def format_ms(value: Any) -> str:
    if value is None:
        return "n/a"

    if isinstance(value, (int, float)):
        return f"{value:.0f} ms"

    return "n/a"


@dataclass(frozen=True)
class DeliveryResult:
    success: bool
    duplicate: bool = False
    status: Optional[str] = None
    event_id: Optional[str] = None
    error: Optional[str] = None


class CloudTransport:
    def __init__(
        self,
        api_url: str,
        api_key: Optional[str] = None,
        heartbeat_url: Optional[str] = None,
        timeout_seconds: float = 5,
    ) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.heartbeat_url = heartbeat_url
        self.timeout_seconds = timeout_seconds

    def send_payload(self, event: dict[str, Any]) -> DeliveryResult:
        headers = {}
        if self.api_key:
            headers["x-rfid-ingest-api-key"] = self.api_key

        print()

        try:
            print(json.dumps(event))

            response = requests.post(
                self.api_url,
                json=event,
                headers=headers,
                timeout=self.timeout_seconds,
            )

            if response.status_code != 201:
                error = f"HTTP {response.status_code}: {response.text}"
                print("CLOUD ERROR:", error)
                return DeliveryResult(success=False, error=error)

            result = response.json()
            status = result.get("status")
            success = status in ("stored", "already_stored")
            duplicate = bool(result.get("duplicate")) or status == "already_stored"

            if success:
                self._print_success(result, event["epc"])
                return DeliveryResult(
                    success=True,
                    duplicate=duplicate,
                    status=status,
                    event_id=result.get("event_id"),
                )

            error = f"Unexpected API status: {status}"
            print("CLOUD ERROR:", error)
            return DeliveryResult(success=False, status=status, error=error)

        except requests.RequestException as error:
            print("CLOUD CONNECTION ERROR:", error)
            return DeliveryResult(success=False, error=str(error))

    def send_heartbeat(self, heartbeat: dict[str, Any]) -> DeliveryResult:
        if not self.heartbeat_url:
            return DeliveryResult(success=False, error="Heartbeat URL is not configured")

        headers = {}
        if self.api_key:
            headers["x-rfid-ingest-api-key"] = self.api_key

        try:
            response = requests.post(
                self.heartbeat_url,
                json=heartbeat,
                headers=headers,
                timeout=self.timeout_seconds,
            )

            if response.status_code != 200:
                return DeliveryResult(
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text}",
                )

            result = response.json()
            return DeliveryResult(
                success=result.get("status") == "ok",
                status=result.get("status"),
                error=None if result.get("status") == "ok" else "Heartbeat failed",
            )

        except requests.RequestException as error:
            return DeliveryResult(success=False, error=str(error))

    def _print_success(self, result: dict[str, Any], epc: str) -> None:
        print("CLOUD OK:", result.get("event_id"))

        asset = result.get("asset")

        if isinstance(asset, dict):
            print("ASSET:", asset.get("asset_code"), "-", asset.get("asset_name"))
            print("TYPE:", asset.get("asset_type"))
            print("STATUS:", asset.get("status"))
        else:
            print("ASSET: UNKNOWN EPC", epc)

        timing = result.get("timing") or {}

        if not isinstance(timing, dict):
            timing = {}

        print("EDGE -> API:", format_ms(timing.get("edge_to_api_ms")))
        print("API PROCESSING:", format_ms(timing.get("api_processing_ms")))
        print("EDGE -> DB:", format_ms(timing.get("edge_to_db_ms")))
