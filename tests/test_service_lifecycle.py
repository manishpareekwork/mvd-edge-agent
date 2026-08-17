import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from mvd_edge.app import ReaderState, ShutdownController, main, run_agent
from mvd_edge.config import EdgeConfig
from mvd_edge.event_engine.state import PresenceState
from mvd_edge.transport.cloud import DeliveryResult


def make_config(directory: Path, **overrides) -> EdgeConfig:
    values = {
        "application_profile": "RFID_ASSET_TRACKING",
        "site_id": "EXPERIENCE-CENTER",
        "location_id": "GATE-1",
        "zone_id": "INBOUND",
        "device_id": "EXP-CENTER-EDGE-01",
        "device_type": "IDT85",
        "reader_id": "LAB-RFID-01",
        "serial_port": "AUTO",
        "serial_baud": 57600,
        "rfid_api_url": "https://api.example.test/api/v1/rfid/events",
        "rfid_ingest_api_key": "secret",
        "scan_interval": 0,
        "exit_timeout": 3.0,
        "edge_data_dir": directory,
        "queue_retry_interval": 60,
        "queue_batch_size": 20,
        "serial_reconnect_interval": 60,
        "auto_configure_reader": False,
        "heartbeat_interval": 0,
        "heartbeat_api_url": "https://api.example.test/api/v1/edge/heartbeat",
        "target_read_distance_m": None,
        "edge_log_dir": None,
    }
    values.update(overrides)
    return EdgeConfig(**values)


class FakeQueue:
    def __init__(self, _db_path: Path) -> None:
        self.closed = False
        self.enqueued = []

    def pending_count(self) -> int:
        return 0

    def fetch_pending(self, limit: int):
        return []

    def enqueue(self, payload):
        self.enqueued.append(dict(payload))

    def close(self) -> None:
        self.closed = True


class FakeReader:
    def __init__(self, port: str, baudrate: int) -> None:
        self.port = port
        self.baudrate = baudrate
        self.close_count = 0

    def close(self) -> None:
        self.close_count += 1


class ServiceLifecycleTests(unittest.TestCase):
    def test_shutdown_request_stops_loop_and_closes_owned_resources(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch("builtins.print"):
            controller = ShutdownController()
            fake_queue = FakeQueue(Path(directory) / "events.sqlite3")
            fake_reader = FakeReader("/dev/test-reader", 57600)

            def stop_after_heartbeat(**_kwargs):
                controller.request_shutdown()
                return DeliveryResult(success=True, status="ok")

            with (
                patch("mvd_edge.app.EventQueue", return_value=fake_queue),
                patch("mvd_edge.app.CloudTransport"),
                patch(
                    "mvd_edge.app.resolve_reader_port",
                    return_value=("/dev/test-reader", "ok", None),
                ),
                patch("mvd_edge.app.IDT85Reader", return_value=fake_reader),
                patch(
                    "mvd_edge.app.connect_and_verify_reader",
                    return_value=(ReaderState.READY, "ok"),
                ),
                patch(
                    "mvd_edge.app.read_inventory_events",
                    return_value=(ReaderState.READY, [], ""),
                ),
                patch("mvd_edge.app.process_pending_deliveries", return_value=0),
                patch("mvd_edge.app.send_heartbeat", side_effect=stop_after_heartbeat),
            ):
                run_agent(
                    make_config(Path(directory)),
                    shutdown_requested=controller.is_requested,
                )

        self.assertTrue(fake_queue.closed)
        self.assertEqual(fake_reader.close_count, 1)
        self.assertEqual(fake_queue.enqueued, [])

    def test_reader_absent_is_recoverable_until_shutdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch("builtins.print"):
            controller = ShutdownController()
            fake_queue = FakeQueue(Path(directory) / "events.sqlite3")

            def stop_after_heartbeat(**_kwargs):
                controller.request_shutdown()
                return DeliveryResult(success=True, status="ok")

            with (
                patch("mvd_edge.app.EventQueue", return_value=fake_queue),
                patch("mvd_edge.app.CloudTransport"),
                patch(
                    "mvd_edge.app.resolve_reader_port",
                    return_value=(None, "reader not found", Mock(supported_readers=[])),
                ),
                patch("mvd_edge.app.process_pending_deliveries", return_value=0),
                patch("mvd_edge.app.send_heartbeat", side_effect=stop_after_heartbeat),
            ):
                run_agent(
                    make_config(Path(directory)),
                    shutdown_requested=controller.is_requested,
                )

        self.assertTrue(fake_queue.closed)

    def test_cloud_unavailable_is_recoverable_until_shutdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch("builtins.print"):
            controller = ShutdownController()
            fake_queue = FakeQueue(Path(directory) / "events.sqlite3")

            def stop_after_failed_heartbeat(**_kwargs):
                controller.request_shutdown()
                return DeliveryResult(success=False, error="network down")

            with (
                patch("mvd_edge.app.EventQueue", return_value=fake_queue),
                patch("mvd_edge.app.CloudTransport"),
                patch(
                    "mvd_edge.app.resolve_reader_port",
                    return_value=(None, "reader not found", Mock(supported_readers=[])),
                ),
                patch("mvd_edge.app.process_pending_deliveries", return_value=0),
                patch(
                    "mvd_edge.app.send_heartbeat",
                    side_effect=stop_after_failed_heartbeat,
                ),
            ):
                run_agent(
                    make_config(Path(directory)),
                    shutdown_requested=controller.is_requested,
                )

        self.assertTrue(fake_queue.closed)

    def test_new_event_triggers_immediate_queue_delivery_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch("builtins.print"):
            controller = ShutdownController()
            fake_queue = FakeQueue(Path(directory) / "events.sqlite3")
            fake_reader = FakeReader("/dev/test-reader", 57600)
            state = PresenceState(exit_timeout=3.0)
            event = state.update(["EPC1"], now=100.0)[0]

            def stop_after_heartbeat(**_kwargs):
                controller.request_shutdown()
                return DeliveryResult(success=True, status="ok")

            with (
                patch("mvd_edge.app.EventQueue", return_value=fake_queue),
                patch("mvd_edge.app.CloudTransport"),
                patch(
                    "mvd_edge.app.resolve_reader_port",
                    return_value=("/dev/test-reader", "ok", None),
                ),
                patch("mvd_edge.app.IDT85Reader", return_value=fake_reader),
                patch(
                    "mvd_edge.app.connect_and_verify_reader",
                    return_value=(ReaderState.READY, "ok"),
                ),
                patch(
                    "mvd_edge.app.read_inventory_events",
                    return_value=(ReaderState.READY, [event], ""),
                ),
                patch("mvd_edge.app.process_pending_deliveries", return_value=0) as deliver,
                patch("mvd_edge.app.send_heartbeat", side_effect=stop_after_heartbeat),
            ):
                run_agent(
                    make_config(Path(directory), queue_retry_interval=60),
                    shutdown_requested=controller.is_requested,
                )

        self.assertTrue(fake_queue.closed)
        self.assertEqual(len(fake_queue.enqueued), 1)
        self.assertEqual(deliver.call_count, 2)

    def test_sqlite_initialization_failure_is_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / "edge.env"
            env_file.write_text(
                "\n".join([
                    "RFID_API_URL=https://api.example.test/api/v1/rfid/events",
                    f"EDGE_DATA_DIR={Path(directory) / 'data'}",
                ])
            )
            output = io.StringIO()

            with (
                patch.dict(os.environ, {"MVD_EDGE_CONFIG": str(env_file)}, clear=True),
                patch("mvd_edge.app.install_signal_handlers"),
                patch("mvd_edge.app.EventQueue", side_effect=OSError("sqlite failed")),
                contextlib.redirect_stdout(output),
            ):
                code = main([])

        self.assertEqual(code, 1)
        self.assertIn("FATAL STARTUP ERROR", output.getvalue())

    def test_missing_required_config_is_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / "edge.env"
            env_file.write_text("RFID_API_URL=\n")
            output = io.StringIO()

            with (
                patch.dict(os.environ, {"MVD_EDGE_CONFIG": str(env_file)}, clear=True),
                patch("mvd_edge.app.install_signal_handlers"),
                contextlib.redirect_stdout(output),
            ):
                code = main([])

        self.assertEqual(code, 1)
        self.assertIn("FATAL CONFIGURATION ERROR", output.getvalue())


class ServiceTemplateTests(unittest.TestCase):
    def test_systemd_template_uses_expected_paths_and_restart_policy(self) -> None:
        service = Path("packaging/linux/systemd/mvd-edge.service").read_text()

        self.assertIn("ExecStart=/opt/mvd-edge/mvd-edge-agent", service)
        self.assertIn("MVD_EDGE_CONFIG=/etc/mvd-edge/edge.env", service)
        self.assertIn("EDGE_DATA_DIR=/var/lib/mvd-edge", service)
        self.assertIn("EDGE_LOG_DIR=/var/log/mvd-edge", service)
        self.assertIn("Restart=on-failure", service)
        self.assertIn("User=mvd-edge", service)

    def test_windows_service_template_has_no_secrets_or_developer_paths(self) -> None:
        template = Path(
            "packaging/windows/service/MVDInsightsEdgeAgent.xml"
        ).read_text()

        self.assertIn("MVDInsightsEdgeAgent", template)
        self.assertIn("mvd-edge-agent.exe", template)
        self.assertIn("MVD_EDGE_CONFIG", template)
        self.assertIn("%ProgramData%\\MVD Insights\\Edge Agent\\edge.env", template)
        self.assertNotIn("RFID_INGEST_API_KEY=", template)
        self.assertNotIn("/Users/manishpareek", template)


if __name__ == "__main__":
    unittest.main()
