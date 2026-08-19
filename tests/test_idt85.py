import unittest
from unittest.mock import patch

from mvd_edge.adapters.idt85 import (
    ANSWER_MODE,
    GET_READER_INFO_COMMAND,
    GET_WORK_MODE_COMMAND,
    IDT85Reader,
    INVENTORY_COMMAND,
    InventoryStatus,
    SET_WORK_MODE_COMMAND,
    build_inventory_command,
    build_get_reader_info_command,
    build_get_work_mode_command,
    build_set_answer_mode_command,
    classify_inventory_response,
    format_work_mode,
    is_valid_command_response,
    parse_inventory_response,
    parse_work_mode_response,
)


class ScriptedSerial:
    responses_by_port = {}
    writes_by_port = {}
    read_sizes_by_port = {}

    def __init__(
        self,
        *,
        port,
        baudrate,
        bytesize,
        parity,
        stopbits,
        timeout,
    ):
        self.port = port
        self.responses = list(self.responses_by_port.get(port, []))
        self.closed = False
        self.writes_by_port.setdefault(port, [])
        self.read_sizes_by_port.setdefault(port, [])

    def reset_input_buffer(self):
        pass

    def write(self, command):
        self.writes_by_port[self.port].append(command)

    def flush(self):
        pass

    def read(self, size):
        self.read_sizes_by_port[self.port].append(size)

        if not self.responses:
            return b""

        current = self.responses[0]
        response = current[:size]
        current = current[size:]

        if current:
            self.responses[0] = current
        else:
            self.responses.pop(0)

        return response

    def close(self):
        self.closed = True


def response_for(command: int) -> bytes:
    return bytes([0x05, 0x00, command, 0x00, 0x00])


def inventory_frame(tags=None, status=0x01) -> bytes:
    body = bytearray([0x00, INVENTORY_COMMAND, status, 0x00])

    for epc in tags or []:
        epc_bytes = bytes.fromhex(epc)
        body[3] += 1
        body.append(len(epc_bytes))
        body.extend(epc_bytes)

    body.extend([0x00, 0x00])
    return bytes([len(body)]) + bytes(body)


class IDT85ParserTests(unittest.TestCase):
    def test_build_inventory_command_preserves_known_wire_format(self) -> None:
        self.assertEqual(
            build_inventory_command(address=0x00).hex(" ").upper(),
            "04 00 01 DB 4B",
        )

    def test_build_reader_info_and_work_mode_commands(self) -> None:
        self.assertEqual(build_get_reader_info_command()[2], GET_READER_INFO_COMMAND)
        self.assertEqual(build_get_work_mode_command()[2], GET_WORK_MODE_COMMAND)
        self.assertEqual(build_set_answer_mode_command()[2], SET_WORK_MODE_COMMAND)

    def test_validates_reader_info_response_by_command(self) -> None:
        response = bytes([0x05, 0xFF, GET_READER_INFO_COMMAND, 0x00, 0x00])

        self.assertTrue(is_valid_command_response(response, GET_READER_INFO_COMMAND))

    def test_parse_answer_work_mode_response(self) -> None:
        response = bytes([0x06, 0x00, GET_WORK_MODE_COMMAND, 0x00, ANSWER_MODE, 0x00])

        self.assertEqual(parse_work_mode_response(response), ANSWER_MODE)
        self.assertEqual(format_work_mode(ANSWER_MODE), "ANSWER")

    def test_parse_single_tag_inventory_frame(self) -> None:
        frame = bytes([
            0x00,
            0x00,
            0x01,
            0x01,
            0x01,
            0x03,
            0xAA,
            0xBB,
            0xCC,
            0x00,
            0x00,
        ])

        self.assertEqual(parse_inventory_response(frame), ["AABBCC"])

    def test_parse_multiple_tag_inventory_frame(self) -> None:
        epc_one = bytes.fromhex("E28069150000503242419E26")
        epc_two = bytes.fromhex("E2806915000050324241CCED")
        frame = bytes([
            0x00,
            0x00,
            0x01,
            0x01,
            0x02,
            len(epc_one),
        ]) + epc_one + bytes([len(epc_two)]) + epc_two + bytes([0x00, 0x00])

        self.assertEqual(
            parse_inventory_response(frame),
            [
                "E28069150000503242419E26",
                "E2806915000050324241CCED",
            ],
        )

    def test_parse_known_single_tag_inventory_frame(self) -> None:
        epc = bytes.fromhex("E28069150000503242419E26")
        frame = bytes([
            0x00,
            0x00,
            0x01,
            0x01,
            0x01,
            len(epc),
        ]) + epc + bytes([0x00, 0x00])

        self.assertEqual(
            parse_inventory_response(frame),
            ["E28069150000503242419E26"],
        )

    def test_ignores_non_inventory_frame(self) -> None:
        frame = bytes([0x00, 0x00, 0x36, 0x01, 0x00, 0x00])

        self.assertEqual(parse_inventory_response(frame), [])

    def test_classifies_valid_zero_tag_frame(self) -> None:
        result = classify_inventory_response(inventory_frame())

        self.assertEqual(result.status, InventoryStatus.VALID)
        self.assertEqual(result.tags, [])

    def test_classifies_valid_tagged_frame(self) -> None:
        result = classify_inventory_response(
            inventory_frame(["E28069150000503242419E26"])
        )

        self.assertEqual(result.status, InventoryStatus.VALID)
        self.assertEqual(result.tags, ["E28069150000503242419E26"])

    def test_classifies_no_response(self) -> None:
        result = classify_inventory_response(b"")

        self.assertEqual(result.status, InventoryStatus.NO_RESPONSE)
        self.assertEqual(result.tags, [])

    def test_classifies_malformed_truncated_frame(self) -> None:
        result = classify_inventory_response(inventory_frame(["AABBCC"])[:-1])

        self.assertEqual(result.status, InventoryStatus.MALFORMED)
        self.assertEqual(result.tags, [])

    def test_classifies_malformed_invalid_command(self) -> None:
        result = classify_inventory_response(bytes([0x06, 0x00, 0x36, 0x01, 0x00, 0x00, 0x00]))

        self.assertEqual(result.status, InventoryStatus.MALFORMED)


class IDT85VerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        ScriptedSerial.responses_by_port = {}
        ScriptedSerial.writes_by_port = {}
        ScriptedSerial.read_sizes_by_port = {}

    def verify_with_responses(self, responses):
        port = "/dev/test-reader"
        ScriptedSerial.responses_by_port = {port: responses}
        reader = IDT85Reader(port=port, baudrate=57600, read_delay=0)

        with patch("mvd_edge.adapters.idt85.serial.Serial", ScriptedSerial):
            reader.open()
            try:
                verified = reader.verify_reader()
            finally:
                reader.close()

        return verified, ScriptedSerial.writes_by_port[port]

    def test_valid_reader_info_response_verifies_without_fallback(self) -> None:
        verified, writes = self.verify_with_responses([
            response_for(GET_READER_INFO_COMMAND),
        ])

        self.assertTrue(verified)
        self.assertEqual(writes, [build_get_reader_info_command()])

    def test_invalid_reader_info_valid_work_mode_response_verifies(self) -> None:
        verified, writes = self.verify_with_responses([
            response_for(INVENTORY_COMMAND),
            response_for(GET_WORK_MODE_COMMAND),
        ])

        self.assertTrue(verified)
        self.assertEqual(
            writes,
            [
                build_get_reader_info_command(),
                build_get_work_mode_command(address=0x00),
            ],
        )

    def test_invalid_reader_info_invalid_work_mode_response_does_not_verify(self) -> None:
        verified, writes = self.verify_with_responses([
            response_for(INVENTORY_COMMAND),
            b"",
        ])

        self.assertFalse(verified)
        self.assertEqual(
            writes,
            [
                build_get_reader_info_command(),
                build_get_work_mode_command(address=0x00),
            ],
        )

    def test_verification_does_not_require_tag_inventory(self) -> None:
        verified, writes = self.verify_with_responses([
            b"",
            response_for(GET_WORK_MODE_COMMAND),
        ])

        self.assertTrue(verified)
        self.assertNotIn(build_inventory_command(), writes)
        self.assertNotIn(build_set_answer_mode_command(), writes)

    def test_send_command_reads_length_byte_then_remaining_frame(self) -> None:
        port = "/dev/test-reader"
        frame = bytes.fromhex(
            "13 00 01 01 01 0C E2 80 69 15 00 00 50 32 42 41 CC ED 57 78"
        )
        ScriptedSerial.responses_by_port = {port: [frame]}
        reader = IDT85Reader(port=port, baudrate=57600, read_delay=0)

        with patch("mvd_edge.adapters.idt85.serial.Serial", ScriptedSerial):
            reader.open()
            try:
                response = reader._send_command(build_inventory_command())
            finally:
                reader.close()

        self.assertEqual(ScriptedSerial.read_sizes_by_port[port], [1, 0x13])
        self.assertEqual(response, frame)

    def test_send_command_empty_first_byte_returns_empty_response(self) -> None:
        port = "/dev/test-reader"
        ScriptedSerial.responses_by_port = {port: [b""]}
        reader = IDT85Reader(port=port, baudrate=57600, read_delay=0)

        with patch("mvd_edge.adapters.idt85.serial.Serial", ScriptedSerial):
            reader.open()
            try:
                response = reader._send_command(build_inventory_command())
            finally:
                reader.close()

        self.assertEqual(ScriptedSerial.read_sizes_by_port[port], [1])
        self.assertEqual(response, b"")

    def test_inventory_returns_classified_result(self) -> None:
        port = "/dev/test-reader"
        ScriptedSerial.responses_by_port = {port: [inventory_frame()]}
        reader = IDT85Reader(port=port, baudrate=57600, read_delay=0)

        with patch("mvd_edge.adapters.idt85.serial.Serial", ScriptedSerial):
            reader.open()
            try:
                result = reader.inventory()
            finally:
                reader.close()

        self.assertEqual(result.status, InventoryStatus.VALID)
        self.assertEqual(result.tags, [])


if __name__ == "__main__":
    unittest.main()
