import json
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


class CloudTransport:
    def __init__(
        self,
        api_url: str,
        api_key: Optional[str] = None,
        timeout_seconds: float = 5,
    ) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def send_event(
        self,
        event_type: str,
        epc: str,
        reader_id: str,
        edge_event_at: str,
    ) -> None:
        event = {
            "event": event_type,
            "epc": epc,
            "reader_id": reader_id,
            "timestamp": edge_event_at,
            "edge_event_at": edge_event_at,
            "edge_send_at": timestamp(),
        }

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

            if response.status_code == 201:
                self._print_success(response.json(), epc)
            else:
                print("CLOUD ERROR:", response.status_code, response.text)

        except requests.RequestException as error:
            print("CLOUD CONNECTION ERROR:", error)

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
