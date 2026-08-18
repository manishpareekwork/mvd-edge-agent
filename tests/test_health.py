import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from mvd_edge.app import (
    ReaderState,
    build_heartbeat_payload,
    read_inventory_events,
    send_heartbeat,
)
from mvd_edge.config import EdgeConfig
from mvd_edge.event_engine.state import PresenceState
from mvd_edge.health.state import HealthState
from mvd_edge.storage.queue import EventQueue
from mvd_edge.transport.cloud import CloudTransport


class FakeReader:
    port = "/dev/test-reader"
    baudrate = 57600

    def __init__(self, inventory_result):
        self.inventory_result = inventory_result

    def inventory(self):
        if isinstance(self.inventory_result, Exception):
            raise self.inventory_result

        return self.inventory_result

    def close(self):
        pass


class HealthTests(unittest.TestCase):
    def test_device_id_loads_from_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "\n".join([
                    "DEVICE_ID=EXP-CENTER-EDGE-99",
                    "READER_ID=LAB-RFID-01",
                    "SITE_ID=EXPERIENCE-CENTER",
                    "LOCATION_ID=GATE-1",
                    "ZONE_ID=INBOUND",
                    "RFID_API_URL=https://api.example.test/api/v1/rfid/events",
                    "RFID_INGEST_API_KEY=test-key",
                ])
            )

            config = EdgeConfig.from_env(env_file=env_file)

        self.assertEqual(config.device_id, "EXP-CENTER-EDGE-99")
        self.assertEqual(
            config.heartbeat_api_url,
            "https://api.example.test/api/v1/edge/heartbeat",
        )

    def test_heartbeat_payload_contains_device_reader_state_and_queue_depth(self):
        with tempfile.TemporaryDirectory() as directory:
            config = EdgeConfig(
                application_profile="RFID_ASSET_TRACKING",
                site_id="EXPERIENCE-CENTER",
                location_id="GATE-1",
                zone_id="INBOUND",
                device_id="EXP-CENTER-EDGE-01",
                device_type="IDT85",
                reader_id="LAB-RFID-01",
                reader_address=0x00,
                reader_verify_method="AUTO",
                serial_port="/dev/test-reader",
                serial_baud=57600,
                rfid_api_url="https://api.example.test/api/v1/rfid/events",
                rfid_ingest_api_key="secret",
                scan_interval=0.5,
                exit_timeout=3.0,
                edge_data_dir=Path(directory),
                queue_retry_interval=5,
                queue_batch_size=20,
                serial_reconnect_interval=5,
                reader_discovery_interval=5,
                auto_configure_reader=False,
                heartbeat_interval=30,
                heartbeat_api_url="https://api.example.test/api/v1/edge/heartbeat",
                target_read_distance_m=None,
                edge_log_dir=None,
            )
            queue = EventQueue(Path(directory) / "events.sqlite3")
            health = HealthState(reader_state=ReaderState.DISCONNECTED.value)

            payload = build_heartbeat_payload(
                config=config,
                queue=queue,
                health_state=health,
            )

            self.assertEqual(payload["device_id"], "EXP-CENTER-EDGE-01")
            self.assertEqual(payload["reader_state"], "DISCONNECTED")
            self.assertEqual(payload["queue_pending"], 0)
            self.assertIsNotNone(payload["reported_at"])
            queue.close()

    def test_reader_activity_updates_last_reader_activity(self) -> None:
        health = HealthState()
        state = PresenceState(exit_timeout=3.0)
        reader = FakeReader(["EPC1"])

        reader_state, events, _ = read_inventory_events(reader, state, health)

        self.assertEqual(reader_state, ReaderState.READY)
        self.assertEqual(len(events), 1)
        self.assertIsNotNone(health.last_reader_activity_at)

    def test_event_updates_last_event(self) -> None:
        health = HealthState()

        health.mark_event()

        self.assertIsNotNone(health.last_event_at)

    def test_reader_failure_updates_sanitized_error(self) -> None:
        health = HealthState()
        state = PresenceState(exit_timeout=3.0)
        reader = FakeReader(OSError("serial failed\nsecret detail"))

        reader_state, events, _ = read_inventory_events(reader, state, health)

        self.assertEqual(reader_state, ReaderState.DISCONNECTED)
        self.assertEqual(events, [])
        self.assertEqual(health.last_error, "SERIAL_DISCONNECTED")

    def test_heartbeat_attempted_without_reader(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = EdgeConfig(
                application_profile="RFID_ASSET_TRACKING",
                site_id="EXPERIENCE-CENTER",
                location_id="GATE-1",
                zone_id="INBOUND",
                device_id="EXP-CENTER-EDGE-01",
                device_type="IDT85",
                reader_id="LAB-RFID-01",
                reader_address=0x00,
                reader_verify_method="AUTO",
                serial_port="/dev/test-reader",
                serial_baud=57600,
                rfid_api_url="https://api.example.test/api/v1/rfid/events",
                rfid_ingest_api_key="secret",
                scan_interval=0.5,
                exit_timeout=3.0,
                edge_data_dir=Path(directory),
                queue_retry_interval=5,
                queue_batch_size=20,
                serial_reconnect_interval=5,
                reader_discovery_interval=5,
                auto_configure_reader=False,
                heartbeat_interval=30,
                heartbeat_api_url="https://api.example.test/api/v1/edge/heartbeat",
                target_read_distance_m=None,
                edge_log_dir=None,
            )
            queue = EventQueue(Path(directory) / "events.sqlite3")
            health = HealthState(reader_state=ReaderState.DISCONNECTED.value)
            response = Mock()
            response.status_code = 200
            response.json.return_value = {"status": "ok"}
            transport = CloudTransport(
                api_url=config.rfid_api_url,
                api_key="secret",
                heartbeat_url=config.heartbeat_api_url,
            )

            with patch("mvd_edge.transport.cloud.requests.post", return_value=response) as post:
                result = send_heartbeat(
                    config=config,
                    queue=queue,
                    health_state=health,
                    transport=transport,
                )

            self.assertTrue(result.success)
            self.assertEqual(post.call_args.kwargs["json"]["reader_state"], "DISCONNECTED")
            queue.close()


if __name__ == "__main__":
    unittest.main()
