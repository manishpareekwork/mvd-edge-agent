import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from mvd_edge.health.network import collect_network_telemetry, parse_wifi_available


class NetworkTelemetryTests(unittest.TestCase):
    def runner_for(self, *, route="", devices="", radio="", ips=None, fail_nmcli=False):
        ips = ips or {}

        def run(command, **_kwargs):
            if command[:3] == ["ip", "route", "show"]:
                return subprocess.CompletedProcess(command, 0, route, "")

            if fail_nmcli and command[0] == "nmcli":
                raise FileNotFoundError("nmcli")

            if command[:4] == ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION"]:
                return subprocess.CompletedProcess(command, 0, devices, "")

            if command[:4] == ["nmcli", "-t", "-f", "WIFI-HW,WIFI,WWAN-HW,WWAN"]:
                return subprocess.CompletedProcess(command, 0, radio, "")

            if command[:4] == ["nmcli", "-t", "-f", "IP4.ADDRESS"]:
                interface = command[-1]
                value = ips.get(interface, "")
                return subprocess.CompletedProcess(
                    command,
                    0,
                    f"IP4.ADDRESS[1]:{value}/24\n" if value else "",
                    "",
                )

            return subprocess.CompletedProcess(command, 1, "", "unexpected")

        return run

    def test_ethernet_only(self):
        telemetry = collect_network_telemetry(self.runner_for(
            route="default via 10.0.0.1 dev eth1 proto dhcp\n",
            devices="eth1:ethernet:connected:Wired connection 2\n",
            radio="missing:enabled:enabled:enabled\n",
            ips={"eth1": "10.0.0.20"},
        ))

        self.assertTrue(telemetry.network_connected)
        self.assertEqual(telemetry.primary_network_type, "ETHERNET")
        self.assertEqual(telemetry.primary_interface, "eth1")
        self.assertTrue(telemetry.ethernet_connected)
        self.assertFalse(telemetry.lte_connected)

    def test_lte_only(self):
        telemetry = collect_network_telemetry(self.runner_for(
            route="default via 100.64.0.1 dev cdc-wdm0 proto dhcp\n",
            devices="cdc-wdm0:gsm:connected:Jio-LTE\n",
            radio="missing:enabled:enabled:enabled\n",
        ))

        self.assertEqual(telemetry.primary_network_type, "LTE")
        self.assertTrue(telemetry.lte_connected)
        self.assertEqual(telemetry.lte_connection_name, "Jio-LTE")

    def test_ethernet_and_lte_with_ethernet_default(self):
        telemetry = collect_network_telemetry(self.runner_for(
            route="default via 10.0.0.1 dev eth1 proto dhcp\n",
            devices=(
                "eth1:ethernet:connected:Wired connection 2\n"
                "cdc-wdm0:gsm:connected:Jio-LTE\n"
            ),
            radio="missing:enabled:enabled:enabled\n",
        ))

        self.assertEqual(telemetry.primary_network_type, "ETHERNET")
        self.assertTrue(telemetry.ethernet_connected)
        self.assertTrue(telemetry.lte_connected)

    def test_ethernet_and_lte_with_lte_default(self):
        telemetry = collect_network_telemetry(self.runner_for(
            route="default via 100.64.0.1 dev cdc-wdm0 proto dhcp\n",
            devices=(
                "eth1:ethernet:connected:Wired connection 2\n"
                "cdc-wdm0:gsm:connected:Jio-LTE\n"
            ),
            radio="missing:enabled:enabled:enabled\n",
        ))

        self.assertEqual(telemetry.primary_network_type, "LTE")
        self.assertTrue(telemetry.ethernet_connected)
        self.assertTrue(telemetry.lte_connected)

    def test_wifi_hardware_missing(self):
        telemetry = collect_network_telemetry(self.runner_for(
            devices="eth1:ethernet:connected:Wired connection 2\n",
            radio="missing:enabled:enabled:enabled\n",
        ))

        self.assertFalse(telemetry.wifi_available)
        self.assertFalse(telemetry.wifi_connected)

    def test_wifi_connected(self):
        telemetry = collect_network_telemetry(self.runner_for(
            route="default via 192.168.1.1 dev wlan0 proto dhcp\n",
            devices="wlan0:wifi:connected:Depot-WiFi\n",
            radio="enabled:enabled:enabled:enabled\n",
            ips={"wlan0": "192.168.1.40"},
        ))

        self.assertTrue(telemetry.wifi_available)
        self.assertTrue(telemetry.wifi_connected)
        self.assertEqual(telemetry.primary_network_type, "WIFI")

    def test_nmcli_unavailable_falls_back_to_unknown(self):
        telemetry = collect_network_telemetry(self.runner_for(
            route="default via 10.0.0.1 dev eth1 proto dhcp\n",
            fail_nmcli=True,
        ))

        self.assertIsNone(telemetry.network_connected)
        self.assertEqual(telemetry.default_route_interface, "eth1")

    def test_parse_wifi_available_missing_hw(self):
        self.assertFalse(parse_wifi_available("missing:enabled:enabled:enabled\n"))

    def test_parse_wifi_available_enabled_hw(self):
        self.assertTrue(parse_wifi_available("enabled:enabled:enabled:enabled\n"))

    def test_parse_wifi_available_disabled_hw(self):
        self.assertTrue(parse_wifi_available("disabled:disabled:enabled:enabled\n"))

    def test_parse_wifi_available_empty_output(self):
        self.assertIsNone(parse_wifi_available(""))

    def test_parse_wifi_available_malformed_output(self):
        self.assertIsNone(parse_wifi_available("missing:enabled\n"))

    def test_subprocess_timeout_falls_back_to_unknown(self):
        def timeout_runner(_command, **_kwargs):
            raise subprocess.TimeoutExpired("nmcli", timeout=1)

        telemetry = collect_network_telemetry(timeout_runner)

        self.assertIsNone(telemetry.network_connected)


class HeartbeatNetworkTelemetryTests(unittest.TestCase):
    def test_network_detection_failure_does_not_stop_heartbeat(self):
        from mvd_edge.app import ReaderState, build_heartbeat_payload
        from mvd_edge.config import EdgeConfig
        from mvd_edge.health.state import HealthState

        queue = Mock()
        queue.pending_count.return_value = 0
        config = EdgeConfig(
            application_profile="RFID_ASSET_TRACKING",
            customer_id="MVD-INSIGHTS",
            site_id="EXPERIENCE-CENTER",
            location_id="GATE-1",
            zone_id="INBOUND",
            device_id="EXP-CENTER-EDGE-01",
            device_type="IDT85",
            reader_id="LAB-RFID-01",
            reader_address=0x00,
            reader_verify_method="AUTO",
            usb_vendor_id=None,
            usb_product_id=None,
            usb_serial=None,
            serial_port="AUTO",
            serial_baud=57600,
            rfid_api_url="https://api.example.test/api/v1/rfid/events",
            rfid_ingest_api_key="secret",
            scan_interval=0.5,
            exit_timeout=3.0,
            edge_data_dir=Path("/tmp/edge-test"),
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

        with patch("mvd_edge.app.collect_network_telemetry", side_effect=RuntimeError("boom")):
            payload = build_heartbeat_payload(
                config=config,
                queue=queue,
                health_state=HealthState(reader_state=ReaderState.READY.value),
            )

        self.assertEqual(payload["device_id"], "EXP-CENTER-EDGE-01")


if __name__ == "__main__":
    unittest.main()
