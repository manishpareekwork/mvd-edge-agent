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
    PORT,
    BAUD,
    bytesize=8,
    parity="N",
    stopbits=1,
    timeout=3
)

cmd = make_command(0xFF, 0x0F)

print("Port:", PORT)
print("Baud:", BAUD)
print("TX HEX:", cmd.hex(" ").upper())
print()
print("Keep ONE RFID tag near reader...")

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
