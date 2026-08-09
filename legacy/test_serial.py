import serial
import time

PORT = "/dev/cu.usbserial-2120"
BAUD = 9600

print(f"Opening {PORT} at {BAUD}...")

ser = serial.Serial(
    port=PORT,
    baudrate=BAUD,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    timeout=1
)

print("Serial port opened successfully.")
print("Listening for 10 seconds...")

end = time.time() + 10

while time.time() < end:
    data = ser.read(256)

    if data:
        print("RAW :", data)
        print("HEX :", data.hex(" ").upper())

ser.close()
print("Done.")
