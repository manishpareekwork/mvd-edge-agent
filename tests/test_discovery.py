import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mvd_edge.app import resolve_reader_port
from mvd_edge.config import EdgeConfig
from mvd_edge.discovery.serial import discover_reader_port, probe_reader_port


class FakePort:
    def __init__(
        self,
        device,
        description=None,
        manufacturer=None,
        vid=None,
        pid=None,
        serial_number=None,
    ):
        self.device = device
        self.description = description
        self.manufacturer = manufacturer
        self.vid = vid
        self.pid = pid
        self.serial_number = serial_number


class FakeReader:
    verified_ports = set()
    calls = []

    def __init__(self, port, baudrate):
        self.port = port
        self.baudrate = baudrate
        self.closed = False

    def open(self):
        FakeReader.calls.append(("open", self.port, self.baudrate))

    def verify_reader(self):
        FakeReader.calls.append(("verify_reader", self.port))
        return self.port in FakeReader.verified_ports

    def close(self):
        FakeReader.calls.append(("close", self.port))
        self.closed = True

    def inventory(self):
        FakeReader.calls.append(("inventory", self.port))
        return []

    def get_work_mode(self):
        FakeReader.calls.append(("get_work_mode", self.port))
        return None

    def set_answer_mode(self):
        FakeReader.calls.append(("set_answer_mode", self.port))
        return False


def config(serial_port="AUTO", target_read_distance_m=None):
    return EdgeConfig(
        application_profile="RFID_ASSET_TRACKING",
        site_id="EXPERIENCE-CENTER",
        location_id="GATE-1",
        zone_id="INBOUND",
        device_id="EXP-CENTER-EDGE-01",
        device_type="IDT85",
        reader_id="LAB-RFID-01",
        serial_port=serial_port,
        serial_baud=57600,
        rfid_api_url="https://api.example.test/api/v1/rfid/events",
        rfid_ingest_api_key="secret",
        scan_interval=0.5,
        exit_timeout=3.0,
        edge_data_dir=Path("/tmp/edge-test"),
        queue_retry_interval=5,
        queue_batch_size=20,
        serial_reconnect_interval=5,
        auto_configure_reader=False,
        heartbeat_interval=30,
        heartbeat_api_url="https://api.example.test/api/v1/edge/heartbeat",
        target_read_distance_m=target_read_distance_m,
        edge_log_dir=None,
    )


class SerialDiscoveryTests(unittest.TestCase):
    def setUp(self):
        FakeReader.verified_ports = set()
        FakeReader.calls = []

    def test_explicit_serial_port_bypasses_discovery(self):
        selected_port, message, result = resolve_reader_port(config(serial_port="COM4"))

        self.assertEqual(selected_port, "COM4")
        self.assertEqual(message, "Using configured serial port")
        self.assertIsNone(result)

    def test_auto_with_one_supported_reader_selects_it(self):
        FakeReader.verified_ports = {"/dev/ttyUSB0"}

        result = discover_reader_port(
            baudrate=57600,
            port_infos=[
                FakePort("/dev/ttyACM0", description="Other device"),
                FakePort("/dev/ttyUSB0", description="USB Serial"),
            ],
            reader_factory=FakeReader,
        )

        self.assertEqual(result.selected_port, "/dev/ttyUSB0")
        self.assertEqual(len(result.supported_readers), 1)

    def test_auto_with_zero_readers_returns_no_match(self):
        result = discover_reader_port(
            baudrate=57600,
            port_infos=[FakePort("/dev/ttyACM0")],
            reader_factory=FakeReader,
        )

        self.assertIsNone(result.selected_port)
        self.assertEqual(result.message, "No supported reader found")

    def test_auto_with_multiple_readers_refuses_selection(self):
        FakeReader.verified_ports = {"COM4", "COM7"}

        result = discover_reader_port(
            baudrate=57600,
            port_infos=[FakePort("COM4"), FakePort("COM7")],
            reader_factory=FakeReader,
        )

        self.assertIsNone(result.selected_port)
        self.assertEqual(len(result.supported_readers), 2)
        self.assertIn("Multiple", result.message)

    def test_unsupported_serial_devices_are_ignored(self):
        FakeReader.verified_ports = {"/dev/cu.usbserial-1"}

        result = discover_reader_port(
            baudrate=57600,
            port_infos=[
                FakePort("/dev/cu.Bluetooth-Incoming-Port"),
                FakePort("/dev/cu.usbserial-1"),
            ],
            reader_factory=FakeReader,
        )

        self.assertEqual(result.selected_port, "/dev/cu.usbserial-1")

    def test_safe_probe_uses_reader_info_verification_only(self):
        FakeReader.verified_ports = {"COM4"}

        verified, error = probe_reader_port(
            port="COM4",
            baudrate=57600,
            reader_factory=FakeReader,
        )

        self.assertTrue(verified)
        self.assertIsNone(error)
        self.assertIn(("verify_reader", "COM4"), FakeReader.calls)
        self.assertNotIn(("inventory", "COM4"), FakeReader.calls)
        self.assertNotIn(("set_answer_mode", "COM4"), FakeReader.calls)

    def test_auto_reconnect_reruns_discovery_and_can_select_changed_path(self):
        first = discover_reader_port(
            baudrate=57600,
            port_infos=[FakePort("/dev/ttyUSB0")],
            reader_factory=FakeReader,
        )
        self.assertIsNone(first.selected_port)

        FakeReader.verified_ports = {"/dev/ttyUSB1"}
        second = discover_reader_port(
            baudrate=57600,
            port_infos=[FakePort("/dev/ttyUSB1")],
            reader_factory=FakeReader,
        )

        self.assertEqual(second.selected_port, "/dev/ttyUSB1")

    def test_missing_usb_metadata_does_not_break_discovery(self):
        FakeReader.verified_ports = {"COM4"}

        result = discover_reader_port(
            baudrate=57600,
            port_infos=[FakePort("COM4")],
            reader_factory=FakeReader,
        )

        self.assertEqual(result.selected_port, "COM4")
        self.assertIsNone(result.devices[0].manufacturer)

    def test_resolve_auto_uses_discovery_each_call(self):
        with patch("mvd_edge.app.discover_reader_port") as discover:
            discover.return_value.selected_port = "COM4"
            discover.return_value.message = "Reader selected"
            discover.return_value.supported_readers = []

            first = resolve_reader_port(config(serial_port="AUTO"))
            second = resolve_reader_port(config(serial_port="AUTO"))

        self.assertEqual(first[0], "COM4")
        self.assertEqual(second[0], "COM4")
        self.assertEqual(discover.call_count, 2)


class ConfigCommissioningTests(unittest.TestCase):
    def test_commissioning_config_loads(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "\n".join([
                    "RFID_API_URL=https://api.example.test/api/v1/rfid/events",
                    "APPLICATION_PROFILE=RFID_ASSET_TRACKING",
                    "SITE_ID=EXPERIENCE-CENTER",
                    "LOCATION_ID=GATE-1",
                    "ZONE_ID=INBOUND",
                    "DEVICE_ID=EXP-CENTER-EDGE-01",
                    "READER_ID=LAB-RFID-01",
                    "SERIAL_PORT=AUTO",
                    "TARGET_READ_DISTANCE_M=3",
                ])
            )

            loaded = EdgeConfig.from_env(env_file=env_file)

        self.assertEqual(loaded.application_profile, "RFID_ASSET_TRACKING")
        self.assertEqual(loaded.site_id, "EXPERIENCE-CENTER")
        self.assertEqual(loaded.location_id, "GATE-1")
        self.assertEqual(loaded.zone_id, "INBOUND")
        self.assertEqual(loaded.serial_port, "AUTO")
        self.assertEqual(loaded.target_read_distance_m, 3)

    def test_target_read_distance_m_must_be_positive(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "\n".join([
                    "RFID_API_URL=https://api.example.test/api/v1/rfid/events",
                    "TARGET_READ_DISTANCE_M=0",
                ])
            )

            with self.assertRaises(ValueError):
                EdgeConfig.from_env(env_file=env_file)


if __name__ == "__main__":
    unittest.main()
