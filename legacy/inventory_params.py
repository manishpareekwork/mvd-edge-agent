import serial
import time

PORT = "/dev/cu.usbserial-2120"
BAUD = 57600


def crc16_mcrf4xx(data):
    crc = 0xFFFF

    for b in data:
        crc ^= b

        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1

    return crc & 0xFFFF


def make_command(address, command, params=b""):
    # length counts bytes AFTER the length byte,
    # including address + command + params + 2-byte CRC
    length = 1 + 1 + len(params) + 2

    body = bytes([length, address, command]) + params

    crc = crc16_mcrf4xx(body)

    return body + bytes([
        crc & 0xFF,
        (crc >> 8) & 0xFF
    ])


ser = serial.Serial(
    port=PORT,
    baudrate=BAUD,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    timeout=3
)

# Inventory_G2 parameters:
# AdrTID = 0
# LenTID = 0
# TIDFlag = 0
params = bytes([
    0x00,
    0x00,
    0x00
])

cmd = make_command(
    address=0x00,
    command=0x01,
    params=params
)

print("Inventory_G2 parameter test")
print("---------------------------")
print("Port:", PORT)
print("Baud:", BAUD)
print("TX HEX:", cmd.hex(" ").upper())
print()
print("Keep ONE tag close to the reader...")

ser.reset_input_buffer()
ser.write(cmd)
ser.flush()

time.sleep(1.5)

response = ser.read(4096)

if response:
    print()
    print("RX HEX:")
    print(response.hex(" ").upper())
    print("RX LEN:", len(response))
else:
    print("NO RESPONSE")

ser.close()
