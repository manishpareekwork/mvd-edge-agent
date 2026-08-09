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


def make_command(address, command):
    body = bytes([
        0x04,
        address,
        command
    ])

    crc = crc16_mcrf4xx(body)

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

# Reader's actual address is 0x00
# Gen2 inventory command is 0x01
cmd = make_command(0x00, 0x01)

print("RFID inventory - address 00")
print("---------------------------")
print("Port :", PORT)
print("Baud :", BAUD)
print("TX   :", cmd.hex(" ").upper())
print()
print("Keep ONE RFID tag near the reader...")
print()

ser.reset_input_buffer()

ser.write(cmd)
ser.flush()

time.sleep(1.5)

response = ser.read(4096)

if response:
    print("RX HEX:")
    print(response.hex(" ").upper())
    print()
    print("RX LEN:", len(response))
else:
    print("NO RESPONSE")

ser.close()
