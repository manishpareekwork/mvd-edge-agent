import serial
import time

PORT = "/dev/cu.usbserial-2120"
BAUD = 57600


def crc16(data):
    crc = 0xFFFF

    for b in data:
        crc ^= b

        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1

    return crc & 0xFFFF


def make_command(address, command):
    body = bytes([
        0x04,
        address,
        command
    ])

    crc = crc16(body)

    return body + bytes([
        crc & 0xFF,
        (crc >> 8) & 0xFF
    ])


ser = serial.Serial(
    port=PORT,
    baudrate=BAUD,
    bytesize=8,
    parity="N",
    stopbits=1,
    timeout=3
)


cmd = make_command(0x00, 0x01)

print()
print("IDT-85 RFID READER")
print("==================")
print("Place tag near reader...")
print()

ser.reset_input_buffer()

ser.write(cmd)
ser.flush()

time.sleep(1.2)

response = ser.read(4096)

if not response:
    print("No response from reader.")
    ser.close()
    exit()


print("RAW HEX:")
print(response.hex(" ").upper())
print()


# Minimum inventory response
if len(response) < 8:
    print("Unexpected response.")
    ser.close()
    exit()


command = response[2]
status = response[3]

if command != 0x01:
    print("Unexpected command response:", hex(command))
    ser.close()
    exit()


if status not in (0x01, 0x02, 0x03, 0x04):
    print("Inventory status:", hex(status))
    ser.close()
    exit()


tag_count = response[4]

print("Tags detected:", tag_count)
print()


position = 5


for i in range(tag_count):

    epc_length = response[position]
    position += 1

    epc_bytes = response[
        position:position + epc_length
    ]

    position += epc_length

    epc = epc_bytes.hex().upper()

    print("TAG", i + 1)
    print("EPC:", epc)
    print("EPC bytes:", epc_length)
    print()


ser.close()
