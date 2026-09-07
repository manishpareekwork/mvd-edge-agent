from dataclasses import dataclass
import subprocess
from typing import Callable, Optional


Runner = Callable[..., subprocess.CompletedProcess]

NMCLI_TIMEOUT_SECONDS = 1.5
IP_ROUTE_TIMEOUT_SECONDS = 1.0


@dataclass(frozen=True)
class NetworkTelemetry:
    network_connected: Optional[bool] = None
    primary_network_type: Optional[str] = None
    primary_interface: Optional[str] = None
    primary_connection_name: Optional[str] = None
    primary_ip_address: Optional[str] = None
    ethernet_connected: Optional[bool] = None
    ethernet_interface: Optional[str] = None
    ethernet_connection_name: Optional[str] = None
    ethernet_ip_address: Optional[str] = None
    lte_connected: Optional[bool] = None
    lte_interface: Optional[str] = None
    lte_connection_name: Optional[str] = None
    lte_ip_address: Optional[str] = None
    wifi_available: Optional[bool] = None
    wifi_connected: Optional[bool] = None
    wifi_interface: Optional[str] = None
    wifi_connection_name: Optional[str] = None
    wifi_ip_address: Optional[str] = None
    default_route_interface: Optional[str] = None

    def payload(self) -> dict[str, object]:
        return self.__dict__.copy()


def _run(command: list[str], timeout: float, runner: Runner) -> Optional[str]:
    try:
        result = runner(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None

    return result.stdout


def default_route_interface(runner: Runner = subprocess.run) -> Optional[str]:
    output = _run(
        ["ip", "route", "show", "default"],
        IP_ROUTE_TIMEOUT_SECONDS,
        runner,
    )

    if not output:
        return None

    for line in output.splitlines():
        parts = line.split()
        if parts[:1] == ["default"] and "dev" in parts:
            index = parts.index("dev")
            if index + 1 < len(parts):
                return parts[index + 1]

    return None


def parse_nmcli_devices(output: str) -> list[dict[str, str]]:
    devices = []

    for line in output.splitlines():
        if not line.strip():
            continue

        parts = line.split(":", 3)
        if len(parts) != 4:
            continue

        devices.append({
            "interface": parts[0],
            "type": parts[1],
            "state": parts[2],
            "connection": parts[3] if parts[3] != "--" else "",
        })

    return devices


def parse_wifi_available(output: Optional[str]) -> Optional[bool]:
    if output is None or not output.strip():
        return None

    first_line = output.splitlines()[0].strip()
    parts = first_line.split(":")

    if len(parts) != 4:
        return None

    wifi_hw = parts[0].strip().lower()

    if wifi_hw == "missing":
        return False

    if wifi_hw in ("enabled", "disabled"):
        return True

    return None


def nmcli_ip_address(interface: Optional[str], runner: Runner = subprocess.run) -> Optional[str]:
    if not interface:
        return None

    output = _run(
        ["nmcli", "-t", "-f", "IP4.ADDRESS", "device", "show", interface],
        NMCLI_TIMEOUT_SECONDS,
        runner,
    )

    if not output:
        return None

    for line in output.splitlines():
        if line.startswith("IP4.ADDRESS"):
            value = line.split(":", 1)[1].split("/", 1)[0].strip()
            if value:
                return value

    return None


def _network_type(device_type: Optional[str]) -> Optional[str]:
    if device_type == "ethernet":
        return "ETHERNET"
    if device_type in ("gsm", "wwan"):
        return "LTE"
    if device_type == "wifi":
        return "WIFI"
    return None


def _first_connected(devices: list[dict[str, str]], *types: str) -> Optional[dict[str, str]]:
    for device in devices:
        if device["type"] in types and device["state"] == "connected":
            return device

    return None


def collect_network_telemetry(runner: Runner = subprocess.run) -> NetworkTelemetry:
    default_interface = default_route_interface(runner)
    devices_output = _run(
        ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"],
        NMCLI_TIMEOUT_SECONDS,
        runner,
    )
    radio_output = _run(
        ["nmcli", "-t", "-f", "WIFI-HW,WIFI,WWAN-HW,WWAN", "radio"],
        NMCLI_TIMEOUT_SECONDS,
        runner,
    )

    if devices_output is None:
        return NetworkTelemetry(default_route_interface=default_interface)

    devices = parse_nmcli_devices(devices_output)
    ethernet = _first_connected(devices, "ethernet")
    lte = _first_connected(devices, "gsm", "wwan")
    wifi = _first_connected(devices, "wifi")
    default_device = next(
        (
            device
            for device in devices
            if device["interface"] == default_interface
        ),
        None,
    )
    primary_type = _network_type(default_device["type"] if default_device else None)

    if primary_type is None:
        primary = ethernet or lte or wifi
        primary_type = _network_type(primary["type"] if primary else None)
    else:
        primary = default_device

    return NetworkTelemetry(
        network_connected=bool(ethernet or lte or wifi),
        primary_network_type=primary_type,
        primary_interface=primary["interface"] if primary else default_interface,
        primary_connection_name=primary["connection"] if primary else None,
        primary_ip_address=nmcli_ip_address(primary["interface"], runner) if primary else None,
        ethernet_connected=ethernet is not None,
        ethernet_interface=ethernet["interface"] if ethernet else None,
        ethernet_connection_name=ethernet["connection"] if ethernet else None,
        ethernet_ip_address=nmcli_ip_address(ethernet["interface"], runner) if ethernet else None,
        lte_connected=lte is not None,
        lte_interface=lte["interface"] if lte else None,
        lte_connection_name=lte["connection"] if lte else None,
        lte_ip_address=nmcli_ip_address(lte["interface"], runner) if lte else None,
        wifi_available=parse_wifi_available(radio_output),
        wifi_connected=wifi is not None,
        wifi_interface=wifi["interface"] if wifi else None,
        wifi_connection_name=wifi["connection"] if wifi else None,
        wifi_ip_address=nmcli_ip_address(wifi["interface"], runner) if wifi else None,
        default_route_interface=default_interface,
    )
