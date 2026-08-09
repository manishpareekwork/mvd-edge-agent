import unittest

from mvd_edge.adapters.idt85 import (
    ANSWER_MODE,
    GET_READER_INFO_COMMAND,
    GET_WORK_MODE_COMMAND,
    SET_WORK_MODE_COMMAND,
    build_inventory_command,
    build_get_reader_info_command,
    build_get_work_mode_command,
    build_set_answer_mode_command,
    format_work_mode,
    is_valid_command_response,
    parse_inventory_response,
    parse_work_mode_response,
)


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


if __name__ == "__main__":
    unittest.main()
