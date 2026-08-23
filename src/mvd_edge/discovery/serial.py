from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from serial.tools import list_ports

from mvd_edge.adapters.idt85 import IDT85Reader


@dataclass(frozen=True)
class DiscoveredSerialDevice:
    port: str
    stable_path: Optional[str]
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


def enumerate_by_id_paths(base: Path = Path("/dev/serial/by-id")) -> list[Path]:
    try:
        return sorted(
            path
            for path in base.iterdir()
            if path.exists()
        )
    except OSError:
        return []


def _resolved(path: Path) -> Optional[str]:
    try:
        return str(path.resolve())
    except OSError:
        return None


def _normalize_usb_id(value: object) -> Optional[int]:
    if value is None:
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        raw = value.strip()

        if not raw:
            return None

        try:
            return int(raw, 16)
        except ValueError:
            return None

    return None


def _normalize_usb_serial(value: object) -> Optional[str]:
    if value is None:
        return None

    serial = str(value).strip()
    return serial or None


def _metadata(port_info: object) -> dict[str, object]:
    return {
        "port": getattr(port_info, "device", str(port_info)),
        "stable_path": getattr(port_info, "stable_path", None),
        "description": getattr(port_info, "description", None),
        "manufacturer": getattr(port_info, "manufacturer", None),
        "vid": _normalize_usb_id(getattr(port_info, "vid", None)),
        "pid": _normalize_usb_id(getattr(port_info, "pid", None)),
        "serial_number": _normalize_usb_serial(
            getattr(port_info, "serial_number", None)
        ),
    }


def _metadata_with_stable_path(
    port_info: object,
    stable_paths_by_target: dict[str, str],
) -> dict[str, object]:
    metadata = _metadata(port_info)
    port = str(metadata["port"])

    if not metadata["stable_path"]:
        metadata["stable_path"] = (
            stable_paths_by_target.get(port)
            or stable_paths_by_target.get(_resolved(Path(port)) or "")
        )

    return metadata


def _rank_key(metadata: dict[str, object]) -> tuple[int, str]:
    device = str(metadata.get("stable_path") or metadata.get("port") or "")
    description = str(metadata.get("description") or "")
    manufacturer = str(metadata.get("manufacturer") or "")
    haystack = " ".join([device, description, manufacturer]).lower()

    if device.startswith("/dev/serial/by-id/"):
        return (0, device)

    if any(value in haystack for value in ("usbserial", "usb-to-serial", "usb serial")):
        return (1, device)

    if any(value in haystack for value in ("ttyusb", "ttyacm", "slab_usbtouart")):
        return (2, device)

    if device.upper().startswith("COM"):
        return (3, device)

    return (4, device)


def _matches_usb_filter(
    metadata: dict[str, object],
    usb_vendor_id: Optional[int],
    usb_product_id: Optional[int],
    usb_serial: Optional[str],
) -> bool:
    if usb_vendor_id is not None and metadata.get("vid") != usb_vendor_id:
        return False

    if usb_product_id is not None and metadata.get("pid") != usb_product_id:
        return False

    if usb_serial and metadata.get("serial_number") != usb_serial:
        return False

    return True


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
    usb_vendor_id: Optional[int] = None,
    usb_product_id: Optional[int] = None,
    usb_serial: Optional[str] = None,
    port_infos: Optional[list[object]] = None,
    by_id_paths: Optional[list[Path]] = None,
    reader_factory: Callable[..., IDT85Reader] = IDT85Reader,
) -> DiscoveryResult:
    by_id_candidates = (
        by_id_paths
        if by_id_paths is not None
        else ([] if port_infos is not None else enumerate_by_id_paths())
    )
    stable_paths_by_target = {
        resolved: str(path)
        for path in by_id_candidates
        if (resolved := _resolved(path))
    }
    all_metadata = [
        _metadata_with_stable_path(port_info, stable_paths_by_target)
        for port_info in (port_infos if port_infos is not None else enumerate_serial_ports())
    ]
    filtered_metadata = [
        metadata
        for metadata in all_metadata
        if _matches_usb_filter(
            metadata=metadata,
            usb_vendor_id=usb_vendor_id,
            usb_product_id=usb_product_id,
            usb_serial=usb_serial,
        )
    ]
    candidates = sorted(
        filtered_metadata,
        key=_rank_key,
    )
    devices: list[DiscoveredSerialDevice] = []

    for metadata in candidates:
        candidate_port = str(metadata.get("stable_path") or metadata["port"])
        verified, error = probe_reader_port(
            port=candidate_port,
            baudrate=baudrate,
            reader_address=reader_address,
            reader_verify_method=reader_verify_method,
            reader_factory=reader_factory,
        )
        devices.append(
            DiscoveredSerialDevice(
                port=candidate_port,
                stable_path=metadata["stable_path"],
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
        if len(all_metadata) != len(filtered_metadata):
            return DiscoveryResult(
                selected_port=None,
                devices=devices,
                message="No supported reader found for configured USB filters",
            )

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
