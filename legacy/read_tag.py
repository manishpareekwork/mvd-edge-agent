from chafon_rfid.base import ReaderCommand
from chafon_rfid.command import G2_TAG_INVENTORY
from chafon_rfid.response import G2_TAG_INVENTORY_STATUS_MORE_FRAMES
from chafon_rfid.transport_serial import SerialTransport
from chafon_rfid.uhfreader18 import G2InventoryResponseFrame

PORT = "/dev/cu.usbserial-2120"
BAUD = 57600

print("Opening reader:", PORT)
print("Baud:", BAUD)
print("Place ONE RFID tag near the reader...")

transport = SerialTransport(
    device=PORT,
    baud_rate=BAUD
)

inventory_command = ReaderCommand(G2_TAG_INVENTORY)

transport.write(inventory_command.serialize())

inventory_status = None

while inventory_status is None or inventory_status == G2_TAG_INVENTORY_STATUS_MORE_FRAMES:

    raw = transport.read_frame()

    print("RAW HEX:", bytes(raw).hex(" ").upper())

    response = G2InventoryResponseFrame(raw)

    inventory_status = response.result_status

    print("Status:", hex(inventory_status))
    print("Tags in frame:", response.num_tags)

    for tag in response.get_tag():
        print()
        print("TAG FOUND")
        print("EPC:", tag.epc.hex().upper())
        print("Antenna:", tag.antenna_num)
        print("RSSI:", tag.rssi)

transport.close()
