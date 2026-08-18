from dataclasses import dataclass
from typing import Callable, Optional

from serial.tools import list_ports

from mvd_edge.adapters.idt85 import IDT85Reader


@dataclass(frozen=True)
class DiscoveredSerialDevice:
    port: str
    description: Optional[str]
    manufacturer: Optional[str]
    vid: Optional[int]
    pid: Optional[int]
    serial_number: Optional[str]
    reader_verified: bool
    error: Optional[str] = None


@dataclass(frozen=True)
class DiscoveryResult:
    selected_port: Optional[str]
    devices: list[DiscoveredSerialDevice]
    message: str

    @property
    def supported_readers(self) -> list[DiscoveredSerialDevice]:
        return [
            device
            for device in self.devices
            if device.reader_verified
        ]


def enumerate_serial_ports() -> list[object]:
    return list(list_ports.comports())


def _metadata(port_info: object) -> dict[str, object]:
    return {
        "port": getattr(port_info, "device", str(port_info)),
        "description": getattr(port_info, "description", None),
        "manufacturer": getattr(port_info, "manufacturer", None),
        "vid": getattr(port_info, "vid", None),
        "pid": getattr(port_info, "pid", None),
        "serial_number": getattr(port_info, "serial_number", None),
    }


def _rank_key(port_info: object) -> tuple[int, str]:
    device = str(getattr(port_info, "device", "") or "")
    description = str(getattr(port_info, "description", "") or "")
    manufacturer = str(getattr(port_info, "manufacturer", "") or "")
    haystack = " ".join([device, description, manufacturer]).lower()

    if any(value in haystack for value in ("usbserial", "usb-to-serial", "usb serial")):
        return (0, device)

    if any(value in haystack for value in ("ttyusb", "ttyacm", "slab_usbtouart")):
        return (1, device)

    if device.upper().startswith("COM"):
        return (2, device)

    return (3, device)


def probe_reader_port(
    port: str,
    baudrate: int,
    reader_address: int = 0x00,
    reader_verify_method: str = "AUTO",
    reader_factory: Callable[..., IDT85Reader] = IDT85Reader,
) -> tuple[bool, Optional[str]]:
    reader = reader_factory(
        port=port,
        baudrate=baudrate,
        address=reader_address,
        verify_method=reader_verify_method,
    )

    try:
        reader.open()
        return reader.verify_reader(), None
    except Exception as exc:
        return False, str(exc)
    finally:
        reader.close()


def discover_reader_port(
    baudrate: int,
    reader_address: int = 0x00,
    reader_verify_method: str = "AUTO",
    port_infos: Optional[list[object]] = None,
    reader_factory: Callable[..., IDT85Reader] = IDT85Reader,
) -> DiscoveryResult:
    candidates = sorted(
        port_infos if port_infos is not None else enumerate_serial_ports(),
        key=_rank_key,
    )
    devices: list[DiscoveredSerialDevice] = []

    for port_info in candidates:
        metadata = _metadata(port_info)
        verified, error = probe_reader_port(
            port=str(metadata["port"]),
            baudrate=baudrate,
            reader_address=reader_address,
            reader_verify_method=reader_verify_method,
            reader_factory=reader_factory,
        )
        devices.append(
            DiscoveredSerialDevice(
                port=str(metadata["port"]),
                description=metadata["description"],
                manufacturer=metadata["manufacturer"],
                vid=metadata["vid"],
                pid=metadata["pid"],
                serial_number=metadata["serial_number"],
                reader_verified=verified,
                error=error,
            )
        )

    supported = [
        device
        for device in devices
        if device.reader_verified
    ]

    if len(supported) == 1:
        return DiscoveryResult(
            selected_port=supported[0].port,
            devices=devices,
            message="Reader selected",
        )

    if not supported:
        return DiscoveryResult(
            selected_port=None,
            devices=devices,
            message="No supported reader found",
        )

    return DiscoveryResult(
        selected_port=None,
        devices=devices,
        message="Multiple supported readers found; configure SERIAL_PORT explicitly",
    )
