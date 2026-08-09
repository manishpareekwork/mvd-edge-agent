import time

from mvd_edge.adapters.idt85 import IDT85Reader
from mvd_edge.config import EdgeConfig
from mvd_edge.event_engine.state import PresenceState
from mvd_edge.transport.cloud import CloudTransport


def main() -> None:
    config = EdgeConfig.from_env()

    if config.device_type != "IDT85":
        raise RuntimeError(f"Unsupported DEVICE_TYPE: {config.device_type}")

    reader = IDT85Reader(
        port=config.serial_port,
        baudrate=config.serial_baud,
    )
    state = PresenceState(exit_timeout=config.exit_timeout)
    transport = CloudTransport(
        api_url=config.rfid_api_url,
        api_key=config.rfid_ingest_api_key,
    )

    print()
    print("IDT-85 CONTINUOUS RFID COLLECTOR")
    print("================================")
    print("Reader:", config.reader_id)
    print("Port:", config.serial_port)
    print("Baud:", config.serial_baud)
    print("API:", config.rfid_api_url)
    print()
    print("Press Ctrl+C to stop.")
    print()

    reader.open()

    try:
        while True:
            scan_start = time.time()
            tags = reader.inventory()
            events = state.update(tags, now=time.time())

            for event in events:
                transport.send_event(
                    event_type=event.event_type,
                    epc=event.epc,
                    reader_id=config.reader_id,
                    edge_event_at=event.edge_event_at,
                )

            elapsed = time.time() - scan_start
            sleep_time = config.scan_interval - elapsed

            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print()
        print("Stopping RFID collector...")

    finally:
        reader.close()
        print("Serial port closed.")


if __name__ == "__main__":
    main()
