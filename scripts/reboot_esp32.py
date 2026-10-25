import serial
import time

ser = serial.Serial()
ser.port = "COM3"
ser.baudrate = 115200
ser.dtr = False
ser.rts = False
ser.open()

# Trigger EN (RST) reset
ser.dtr = True
ser.rts = True
time.sleep(0.15)
ser.dtr = False
ser.rts = False
print("Reset triggered, waiting for ESP32 to boot...")

t0 = time.time()
while time.time() - t0 < 6.0:
    if ser.in_waiting > 0:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line:
            print(f"[BOOT]: {line}")
    time.sleep(0.01)

ser.close()
