import time
from typing import Optional

import serial


INVENTORY_COMMAND = 0x01
GET_WORK_MODE_COMMAND = 0x36
SET_WORK_MODE_COMMAND = 0x35


def crc16(data: bytes) -> int:
    crc = 0xFFFF

    for value in data:
        crc ^= value

        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1

    return crc & 0xFFFF


def make_command(address: int, command: int, params: bytes = b"") -> bytes:
    length = 1 + 1 + len(params) + 2
    body = bytes([length, address, command]) + params
    crc = crc16(body)

    return body + bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def build_inventory_command(address: int = 0x00) -> bytes:
    return make_command(address=address, command=INVENTORY_COMMAND)


def parse_inventory_response(response: bytes) -> list[str]:
    if len(response) < 6:
        return []

    if response[2] != INVENTORY_COMMAND:
        return []

    status = response[3]

    if status not in (0x01, 0x02, 0x03, 0x04):
        return []

    tag_count = response[4]
    position = 5
    tags: list[str] = []

    for _ in range(tag_count):
        if position >= len(response) - 2:
            break

        epc_length = response[position]
        position += 1

        if position + epc_length > len(response) - 2:
            break

        epc_bytes = response[position:position + epc_length]
        position += epc_length

        tags.append(epc_bytes.hex().upper())

    return tags


class IDT85Reader:
    def __init__(
        self,
        port: str,
        baudrate: int,
        address: int = 0x00,
        read_delay: float = 0.20,
        read_size: int = 4096,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.address = address
        self.read_delay = read_delay
        self.read_size = read_size
        self._serial: Optional[serial.Serial] = None
        self._inventory_command = build_inventory_command(address=address)

    def open(self) -> None:
        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=1,
        )

    def close(self) -> None:
        if self._serial:
            self._serial.close()

    def inventory(self) -> list[str]:
        if not self._serial:
            raise RuntimeError("Serial port is not open")

        self._serial.reset_input_buffer()
        self._serial.write(self._inventory_command)
        self._serial.flush()

        time.sleep(self.read_delay)

        response = self._serial.read(self.read_size)
        return parse_inventory_response(response)
