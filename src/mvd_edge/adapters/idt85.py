import time
from typing import Optional

import serial


INVENTORY_COMMAND = 0x01
GET_READER_INFO_COMMAND = 0x21
GET_WORK_MODE_COMMAND = 0x36
SET_WORK_MODE_COMMAND = 0x35
ANSWER_MODE = 0x00
SCAN_MODE = 0x01
ANSWER_MODE_PARAMS = bytes([
    0x00,
    0x00,
    0x05,
    0x00,
    0x01,
    0x00,
])


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


def build_get_reader_info_command(address: int = 0xFF) -> bytes:
    return make_command(address=address, command=GET_READER_INFO_COMMAND)


def build_get_work_mode_command(address: int = 0x00) -> bytes:
    return make_command(address=address, command=GET_WORK_MODE_COMMAND)


def build_set_answer_mode_command(address: int = 0x00) -> bytes:
    return make_command(
        address=address,
        command=SET_WORK_MODE_COMMAND,
        params=ANSWER_MODE_PARAMS,
    )


def is_valid_command_response(response: bytes, command: int) -> bool:
    if len(response) < 5:
        return False

    return response[2] == command


def parse_work_mode_response(response: bytes) -> Optional[int]:
    if not is_valid_command_response(response, GET_WORK_MODE_COMMAND):
        return None

    if len(response) < 5:
        return None

    return response[4]


def format_work_mode(mode: Optional[int]) -> str:
    if mode == ANSWER_MODE:
        return "ANSWER"

    if mode == SCAN_MODE:
        return "SCAN"

    if mode is None:
        return "UNKNOWN"

    return f"UNKNOWN({mode:#04x})"


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
        self._reader_info_command = build_get_reader_info_command()
        self._get_work_mode_command = build_get_work_mode_command(address=address)
        self._set_answer_mode_command = build_set_answer_mode_command(address=address)

    def apply_installation_profile(
        self,
        target_read_distance_m: Optional[float] = None,
    ) -> None:
        # Placeholder for future verified RF tuning. Intentionally sends no
        # reader commands until hardware-specific calibration is validated.
        _ = target_read_distance_m

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
            self._serial = None

    def _send_command(self, command: bytes, read_delay: Optional[float] = None) -> bytes:
        if not self._serial:
            raise RuntimeError("Serial port is not open")

        self._serial.reset_input_buffer()
        self._serial.write(command)
        self._serial.flush()

        time.sleep(self.read_delay if read_delay is None else read_delay)

        return self._serial.read(self.read_size)

    def get_reader_info(self) -> bytes:
        return self._send_command(self._reader_info_command)

    def verify_reader(self) -> bool:
        return is_valid_command_response(
            self.get_reader_info(),
            GET_READER_INFO_COMMAND,
        )

    def get_work_mode(self) -> Optional[int]:
        return parse_work_mode_response(
            self._send_command(self._get_work_mode_command)
        )

    def set_answer_mode(self) -> bool:
        response = self._send_command(self._set_answer_mode_command)
        return is_valid_command_response(response, SET_WORK_MODE_COMMAND)

    def inventory(self) -> list[str]:
        response = self._send_command(self._inventory_command)
        return parse_inventory_response(response)
