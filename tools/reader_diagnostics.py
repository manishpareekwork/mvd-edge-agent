import argparse
import time

import serial

from mvd_edge.adapters.idt85 import build_inventory_command, parse_inventory_response


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a single IDT-85 inventory scan.")
    parser.add_argument("--port", default="/dev/cu.usbserial-2120")
    parser.add_argument("--baud", default=57600, type=int)
    args = parser.parse_args()

    reader = serial.Serial(
        port=args.port,
        baudrate=args.baud,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=3,
    )

    try:
        command = build_inventory_command(address=0x00)
        print("TX HEX:", command.hex(" ").upper())

        reader.reset_input_buffer()
        reader.write(command)
        reader.flush()

        time.sleep(1.2)

        response = reader.read(4096)
        print("RX HEX:", response.hex(" ").upper() if response else "NO RESPONSE")
        print("TAGS:", parse_inventory_response(response))

    finally:
        reader.close()


if __name__ == "__main__":
    main()
