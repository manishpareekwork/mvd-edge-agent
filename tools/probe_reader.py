import argparse

from mvd_edge.config import optional_usb_id
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
    parser.add_argument("--usb-vendor-id")
    parser.add_argument("--usb-product-id")
    parser.add_argument("--usb-serial")
    args = parser.parse_args()
    usb_vendor_id = optional_usb_id("USB_VENDOR_ID", args.usb_vendor_id)
    usb_product_id = optional_usb_id("USB_PRODUCT_ID", args.usb_product_id)

    if (usb_vendor_id is None) != (usb_product_id is None):
        parser.error("--usb-vendor-id and --usb-product-id must be provided together")

    print("Scanning serial ports...")
    print("Baud:", args.baud)
    if usb_vendor_id is not None and usb_product_id is not None:
        print("USB VID/PID:", f"{usb_vendor_id:04x}:{usb_product_id:04x}")
    if args.usb_serial:
        print("USB Serial:", args.usb_serial)
    print()

    result = discover_reader_port(
        baudrate=args.baud,
        usb_vendor_id=usb_vendor_id,
        usb_product_id=usb_product_id,
        usb_serial=args.usb_serial,
    )

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
        print("Stable Path:", device.stable_path or "n/a")

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
