import argparse

from mvd_edge.discovery.serial import discover_reader_port


def format_hex(value):
    if value is None:
        return "n/a"

    return f"0x{value:04X}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Safely scan serial ports for an IDT-85 compatible reader."
    )
    parser.add_argument("--baud", default=57600, type=int)
    args = parser.parse_args()

    print("Scanning serial ports...")
    print("Baud:", args.baud)
    print()

    result = discover_reader_port(baudrate=args.baud)

    if not result.devices:
        print("No serial ports reported by pyserial.")
        return

    for device in result.devices:
        print(device.port)
        print("Description:", device.description or "n/a")
        print("Manufacturer:", device.manufacturer or "n/a")
        print("VID:", format_hex(device.vid))
        print("PID:", format_hex(device.pid))
        print("Serial Number:", device.serial_number or "n/a")

        if device.reader_verified:
            print("IDT-85 compatible reader detected")
        else:
            print("No supported reader response")

            if device.error:
                print("Error:", device.error)

        print()

    if result.selected_port:
        print("Selected:", result.selected_port)
    else:
        print(result.message)


if __name__ == "__main__":
    main()
