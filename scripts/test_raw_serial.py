import serial
import time

ser = serial.Serial('COM3', 115200, timeout=0.5)
ser.dtr = False
ser.rts = False
time.sleep(0.2)
ser.reset_input_buffer()
ser.reset_output_buffer()

print("Reading lines from COM3 for 4 seconds...")
t0 = time.time()
while time.time() - t0 < 4.0:
    if ser.in_waiting > 0:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line:
            print(f"   [ESP32]: {line}")
    time.sleep(0.01)

ser.close()
