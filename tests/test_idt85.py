import unittest

from mvd_edge.adapters.idt85 import (
    build_inventory_command,
    parse_inventory_response,
)


class IDT85ParserTests(unittest.TestCase):
    def test_build_inventory_command_preserves_known_wire_format(self) -> None:
        self.assertEqual(
            build_inventory_command(address=0x00).hex(" ").upper(),
            "04 00 01 DB 4B",
        )

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
