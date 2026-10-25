import serial, time
ser = serial.Serial()
ser.port = "COM3"
ser.baudrate = 115200
ser.dtr = False
ser.rts = False
ser.timeout = 0.5
ser.open()
time.sleep(0.2)
ser.reset_input_buffer()

print("Listening for fresh serial logs from ESP32 for 3 seconds...")
t0 = time.time()
while time.time() - t0 < 3.0:
    if ser.in_waiting > 0:
        l = ser.readline().decode('utf-8', errors='ignore').strip()
        if l:
            print(f"[COM3]: {l}")
    time.sleep(0.01)
ser.close()
