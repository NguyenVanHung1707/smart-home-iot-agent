import sys
import serial
import time

sys.stdout.reconfigure(encoding="utf-8")

ser = serial.Serial()
ser.port = "COM3"
ser.baudrate = 115200
ser.dtr = False
ser.rts = False
ser.open()

# Proper reset pulse: pull EN low by toggling DTR/RTS properly for CP2102
# CP2102 auto-reset circuit: RTS controls EN (inverted), DTR controls IO0 (inverted)
ser.dtr = False  # IO0 = HIGH (Normal boot, not download mode)
ser.rts = True   # EN = LOW (Reset)
time.sleep(0.1)
ser.rts = False  # EN = HIGH (Boot)
time.sleep(0.05)
ser.dtr = False

print("Reset pulse sent. Reading boot messages...")
t0 = time.time()
while time.time() - t0 < 5.0:
    if ser.in_waiting > 0:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line:
            print(f"[BOOT]: {line}")
    time.sleep(0.01)

ser.close()
