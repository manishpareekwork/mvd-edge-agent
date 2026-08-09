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


def make_command(address, command, params):
    # Set WorkMode has:
    # Len = 0x0A
    # Adr
    # Cmd = 0x35
    # 6 parameter bytes
    body = bytes([
        0x0A,
        address,
        command
    ]) + params

    crc = crc16(body)

    return body + bytes([
        crc & 0xFF,
        (crc >> 8) & 0xFF
    ])


ser = serial.Serial(
    PORT,
    BAUD,
    bytesize=8,
    parity="N",
    stopbits=1,
    timeout=2
)

# Existing parameters:
#
# Read_mode  = 00  -> ANSWER MODE
# Mode_state = 00
# Mem_Inven  = 05
# First_Adr  = 00
# Word_Num   = 01
# Tag_Time   = 00
#
params = bytes([
    0x00,
    0x00,
    0x05,
    0x00,
    0x01,
    0x00
])

cmd = make_command(
    address=0x00,
    command=0x35,
    params=params
)

print("SET ANSWER MODE")
print("----------------")
print("TX HEX:", cmd.hex(" ").upper())

ser.reset_input_buffer()
ser.write(cmd)
ser.flush()

time.sleep(0.5)

response = ser.read(256)

if response:
    print("RX HEX:", response.hex(" ").upper())
else:
    print("NO RESPONSE")

ser.close()
