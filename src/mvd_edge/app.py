import argparse
from datetime import datetime
from enum import Enum
import platform
import signal
import sys
import time
from types import FrameType
from typing import Any, Callable, Optional

from mvd_edge import __version__
from mvd_edge.adapters.idt85 import ANSWER_MODE, IDT85Reader, format_work_mode
from mvd_edge.config import EdgeConfig
from mvd_edge.discovery.serial import DiscoveryResult, discover_reader_port
from mvd_edge.event_engine.state import DetectedEvent, PresenceState
from mvd_edge.health.state import HealthState
from mvd_edge.storage.queue import EventQueue
from mvd_edge.transport.cloud import CloudTransport, DeliveryResult


class ReaderState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    READY = "READY"
    CONFIG_ERROR = "CONFIG_ERROR"


class ShutdownController:
    def __init__(self) -> None:
        self._requested = False

    def request_shutdown(
        self,
        signum: Optional[int] = None,
        _frame: Optional[FrameType] = None,
    ) -> None:
        self._requested = True
        if signum is not None:
            print()
            print("Shutdown requested:", signal.Signals(signum).name)

    def is_requested(self) -> bool:
        return self._requested


def install_signal_handlers(controller: ShutdownController) -> None:
    signal.signal(signal.SIGINT, controller.request_shutdown)

    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, controller.request_shutdown)


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def format_application_profile(value: str) -> str:
    return value.replace("_", " ").title().replace("Rfid", "RFID")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mvd-edge-agent",
        description="MVD Insights Edge Agent",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print version information and exit.",
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Validate configuration without opening the reader or contacting cloud.",
    )

    return parser


def print_version() -> None:
    print(f"MVD Insights Edge Agent {__version__}")
    print("Platform:", platform.platform())
    print("Python:", platform.python_version())


def check_config() -> int:
    try:
        config = EdgeConfig.from_env()
    except Exception as exc:
        print(f"MVD Insights Edge Agent {__version__}")
        print()
        print("Configuration:")
        print("INVALID")
        print("Error:", exc)
        return 1

    print(f"MVD Insights Edge Agent {__version__}")
    print()
    print("Configuration:")
    print("VALID")
    print()
    print("Application:", format_application_profile(config.application_profile))
    print("Site:", config.site_id)
    print("Location:", config.location_id)
    print("Zone:", config.zone_id)
    print("Device:", config.device_id)
    print("Reader:", config.reader_id)
    print("Serial:", config.serial_port)
    print("Baud:", config.serial_baud)
    print("API:", "configured" if config.rfid_api_url else "missing")
    print("API Key:", "configured" if config.rfid_ingest_api_key else "missing")
    print("Heartbeat:", f"every {config.heartbeat_interval:g}s")
    print("Data Directory:", config.edge_data_dir)

    if config.edge_log_dir:
        print("Log Directory:", config.edge_log_dir)
    else:
        print("Log Directory:", "terminal only")

    if config.target_read_distance_m is not None:
        print("Target Read Distance:", f"{config.target_read_distance_m:g} m")

    return 0


def build_event_payload(event: DetectedEvent, reader_id: str) -> dict[str, Any]:
    return {
        "edge_event_id": event.edge_event_id,
        "event": event.event_type,
        "epc": event.epc,
        "reader_id": reader_id,
        "timestamp": event.edge_event_at,
        "edge_event_at": event.edge_event_at,
        "edge_send_at": timestamp(),
    }


def process_pending_deliveries(
    queue: EventQueue,
    transport: CloudTransport,
    batch_size: int,
    health_state: Optional[HealthState] = None,
) -> int:
    delivered_count = 0

    for queued_event in queue.fetch_pending(limit=batch_size):
        payload = dict(queued_event.payload)
        payload["edge_send_at"] = timestamp()
        queue.update_payload(queued_event.edge_event_id, payload)

        try:
            result = transport.send_payload(payload)
        except Exception as exc:
            result = DeliveryResult(success=False, error=str(exc))

        queue.mark_attempt(
            queued_event.edge_event_id,
            error=None if result.success else result.error,
        )

        if result.success:
            queue.mark_delivered(queued_event.edge_event_id)
            if health_state:
                health_state.mark_cloud_delivery()
            delivered_count += 1
            print("DELIVERED:")
            print("edge_event_id=", queued_event.edge_event_id, sep="")
        else:
            if health_state:
                health_state.mark_error("CLOUD_DELIVERY_FAILED")
            print("CLOUD UNAVAILABLE:")
            print("event retained locally")

    return delivered_count


def attempt_immediate_delivery(
    *,
    queue: EventQueue,
    transport: CloudTransport,
    batch_size: int,
    health_state: HealthState,
) -> float:
    pending = queue.pending_count()

    if pending:
        print("QUEUE:", pending, "pending")

    process_pending_deliveries(
        queue=queue,
        transport=transport,
        batch_size=batch_size,
        health_state=health_state,
    )

    return time.time()


def connect_and_verify_reader(
    reader: IDT85Reader,
    auto_configure_reader: bool,
    target_read_distance_m: Optional[float] = None,
) -> tuple[ReaderState, str]:
    print("READER")
    print("Connecting...")

    try:
        reader.open()

        if not reader.verify_reader():
            reader.close()
            return (
                ReaderState.CONFIG_ERROR,
                "Reader communication failed verification",
            )

        work_mode = reader.get_work_mode()

        if work_mode == ANSWER_MODE:
            print("READER CONNECTED")
            print("Port:", reader.port)
            print("Baud:", reader.baudrate)
            print("Mode:", format_work_mode(work_mode))
            reader.apply_installation_profile(
                target_read_distance_m=target_read_distance_m
            )
            print("Inventory resumed")
            return ReaderState.READY, "Communication verified"

        if not auto_configure_reader:
            reader.close()
            return (
                ReaderState.CONFIG_ERROR,
                (
                    "Reader Work Mode: "
                    f"{format_work_mode(work_mode)}; Required: ANSWER"
                ),
            )

        if not reader.set_answer_mode():
            reader.close()
            return (
                ReaderState.CONFIG_ERROR,
                "Unable to set reader work mode to ANSWER",
            )

        verified_mode = reader.get_work_mode()

        if verified_mode != ANSWER_MODE:
            reader.close()
            return (
                ReaderState.CONFIG_ERROR,
                (
                    "Reader Work Mode after configuration: "
                    f"{format_work_mode(verified_mode)}; Required: ANSWER"
                ),
            )

        print("READER CONNECTED")
        print("Port:", reader.port)
        print("Baud:", reader.baudrate)
        print("Mode:", format_work_mode(verified_mode))
        reader.apply_installation_profile(
            target_read_distance_m=target_read_distance_m
        )
        print("Inventory resumed")
        return ReaderState.READY, "Communication verified"

    except Exception as exc:
        reader.close()
        return ReaderState.DISCONNECTED, str(exc)


def should_auto_discover(serial_port: str) -> bool:
    return serial_port.upper() == "AUTO"


def resolve_reader_port(config: EdgeConfig) -> tuple[Optional[str], str, Optional[DiscoveryResult]]:
    if not should_auto_discover(config.serial_port):
        return config.serial_port, "Using configured serial port", None

    print("Searching for reader...")
    result = discover_reader_port(baudrate=config.serial_baud)

    if result.selected_port:
        print("READER DETECTED")
        print(result.selected_port)
        return result.selected_port, result.message, result

    return None, result.message, result


def report_reader_unavailable(
    message: str,
    port: str,
    reconnect_interval: float,
) -> None:
    print("READER UNAVAILABLE")
    print("Port:", port)
    print(message)
    print(f"Retry in {reconnect_interval:g}s")


def read_inventory_events(
    reader: IDT85Reader,
    state: PresenceState,
    health_state: Optional[HealthState] = None,
) -> tuple[ReaderState, list[DetectedEvent], str]:
    try:
        tags = reader.inventory()
        if health_state:
            health_state.mark_reader_activity()
        return ReaderState.READY, state.update(tags, now=time.time()), ""
    except Exception as exc:
        reader.close()
        if health_state:
            health_state.set_reader_state(ReaderState.DISCONNECTED.value)
            health_state.mark_error("SERIAL_DISCONNECTED")
        return ReaderState.DISCONNECTED, [], str(exc)


def build_heartbeat_payload(
    *,
    config: EdgeConfig,
    queue: EventQueue,
    health_state: HealthState,
) -> dict[str, object]:
    return health_state.payload(
        device_id=config.device_id,
        reader_id=config.reader_id,
        agent_version=__version__,
        serial_port=config.serial_port,
        queue_pending=queue.pending_count(),
    )


def send_heartbeat(
    *,
    config: EdgeConfig,
    queue: EventQueue,
    health_state: HealthState,
    transport: CloudTransport,
) -> DeliveryResult:
    result = transport.send_heartbeat(
        build_heartbeat_payload(
            config=config,
            queue=queue,
            health_state=health_state,
        )
    )

    if not result.success:
        print("HEARTBEAT ERROR:", result.error)

    return result


def interruptible_sleep(
    duration: float,
    shutdown_requested: Callable[[], bool],
    interval: float = 0.2,
) -> None:
    end_at = time.time() + duration

    while not shutdown_requested():
        remaining = end_at - time.time()

        if remaining <= 0:
            return

        time.sleep(min(interval, remaining))


def run_agent(
    config: EdgeConfig,
    shutdown_requested: Optional[Callable[[], bool]] = None,
) -> None:

    if config.device_type != "IDT85":
        raise RuntimeError(f"Unsupported DEVICE_TYPE: {config.device_type}")

    if shutdown_requested is None:
        shutdown_requested = lambda: False

    reader: Optional[IDT85Reader] = None
    state = PresenceState(exit_timeout=config.exit_timeout)
    transport = CloudTransport(
        api_url=config.rfid_api_url,
        api_key=config.rfid_ingest_api_key,
        heartbeat_url=config.heartbeat_api_url,
    )
    queue = EventQueue(config.edge_data_dir / "events.sqlite3")
    health_state = HealthState(reader_state=ReaderState.DISCONNECTED.value)

    print()
    print("EDGE AGENT STARTED")
    print("IDT-85 CONTINUOUS RFID COLLECTOR")
    print("================================")
    print("Application:", format_application_profile(config.application_profile))
    print("Site:", config.site_id)
    print("Location:", config.location_id)
    print("Zone:", config.zone_id)
    print("Reader:", config.reader_id)
    print("Device:", config.device_id)
    print("Serial:", config.serial_port)
    print("Baud:", config.serial_baud)
    print("API:", config.rfid_api_url)
    print("Local Queue:", queue.pending_count(), "pending events")
    print("Heartbeat: every", f"{config.heartbeat_interval:g}s")
    print()
    print("Press Ctrl+C to stop.")
    print()

    print("Cloud:")
    print("retrying queued events...")
    process_pending_deliveries(
        queue=queue,
        transport=transport,
        batch_size=config.queue_batch_size,
        health_state=health_state,
    )
    last_delivery_attempt = time.time()
    last_heartbeat_attempt = 0.0
    reader_state = ReaderState.DISCONNECTED
    next_reader_attempt = 0.0

    try:
        while not shutdown_requested():
            scan_start = time.time()
            now = time.time()

            if now >= next_reader_attempt and reader_state != ReaderState.READY:
                reader_state = ReaderState.CONNECTING
                health_state.set_reader_state(reader_state.value)

                selected_port, reader_message, discovery_result = resolve_reader_port(config)

                if selected_port:
                    reader = IDT85Reader(
                        port=selected_port,
                        baudrate=config.serial_baud,
                    )
                    reader_state, reader_message = connect_and_verify_reader(
                        reader=reader,
                        auto_configure_reader=config.auto_configure_reader,
                        target_read_distance_m=config.target_read_distance_m,
                    )
                else:
                    reader_state = ReaderState.DISCONNECTED

                    if discovery_result and len(discovery_result.supported_readers) > 1:
                        reader_state = ReaderState.CONFIG_ERROR

                health_state.set_reader_state(reader_state.value)

                if reader_state != ReaderState.READY:
                    if reader_state == ReaderState.CONFIG_ERROR:
                        health_state.mark_error(reader_message)
                    else:
                        health_state.mark_error("SERIAL_DISCONNECTED")
                    report_reader_unavailable(
                        message=reader_message,
                        port=config.serial_port,
                        reconnect_interval=config.serial_reconnect_interval,
                    )
                    next_reader_attempt = now + config.serial_reconnect_interval
                else:
                    health_state.clear_error()

            events: list[DetectedEvent] = []

            if reader_state == ReaderState.READY:
                if not reader:
                    reader_state = ReaderState.DISCONNECTED
                    health_state.set_reader_state(reader_state.value)
                    continue

                reader_state, events, reader_message = read_inventory_events(
                    reader=reader,
                    state=state,
                    health_state=health_state,
                )
                health_state.set_reader_state(reader_state.value)

                if reader_state == ReaderState.DISCONNECTED:
                    reader_state = ReaderState.DISCONNECTED
                    next_reader_attempt = time.time() + config.serial_reconnect_interval
                    print("READER DISCONNECTED")
                    print("Port:", reader.port)
                    print(reader_message)
                    print(f"Retrying in {config.serial_reconnect_interval:g}s...")

            for event in events:
                health_state.mark_event()
                payload = build_event_payload(event, reader_id=config.reader_id)
                queue.enqueue(payload)
                print("QUEUED:")
                print(event.event_type)
                print("edge_event_id=", event.edge_event_id, sep="")

            if events:
                last_delivery_attempt = attempt_immediate_delivery(
                    queue=queue,
                    transport=transport,
                    batch_size=config.queue_batch_size,
                    health_state=health_state,
                )

            if time.time() - last_delivery_attempt >= config.queue_retry_interval:
                last_delivery_attempt = attempt_immediate_delivery(
                    queue=queue,
                    transport=transport,
                    batch_size=config.queue_batch_size,
                    health_state=health_state,
                )

            if time.time() - last_heartbeat_attempt >= config.heartbeat_interval:
                send_heartbeat(
                    config=config,
                    queue=queue,
                    health_state=health_state,
                    transport=transport,
                )
                last_heartbeat_attempt = time.time()

            elapsed = time.time() - scan_start
            sleep_time = config.scan_interval - elapsed

            if sleep_time > 0:
                interruptible_sleep(sleep_time, shutdown_requested)

    except KeyboardInterrupt:
        print()
        print("Stopping RFID collector...")

    finally:
        if reader:
            reader.close()
        queue.close()
        print("Serial port closed.")


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.version:
        print_version()
        return 0

    if args.check_config:
        return check_config()

    try:
        config = EdgeConfig.from_env()
    except Exception as exc:
        print("FATAL CONFIGURATION ERROR:", exc)
        return 1

    controller = ShutdownController()
    install_signal_handlers(controller)

    try:
        run_agent(config, shutdown_requested=controller.is_requested)
    except Exception as exc:
        print("FATAL STARTUP ERROR:", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
