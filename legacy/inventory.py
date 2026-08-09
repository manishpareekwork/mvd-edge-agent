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
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    timeout=3
)

# Gen2 RFID inventory command
cmd = make_command(0xFF, 0x01)

print("RFID inventory test")
print("-------------------")
print("Port :", PORT)
print("Baud :", BAUD)
print("TX   :", cmd.hex(" ").upper())
print()
print("Place ONE RFID tag near the reader...")
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
    print("Received bytes:", len(response))
else:
    print("NO TAG RESPONSE")

ser.close()
