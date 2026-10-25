import sys
import time
import serial
import numpy as np
import sounddevice as sd
import pygame
import pygame.sndarray as snd
from gtts import gTTS

sys.stdout.reconfigure(encoding="utf-8")

phrase = "bật đèn phòng khách"
tts = gTTS(text=phrase, lang="vi", slow=False)
tts.save("scripts/pilot_prompt.mp3")

if not pygame.mixer.get_init():
    pygame.mixer.init()

s = pygame.mixer.Sound("scripts/pilot_prompt.mp3")
arr = snd.array(s)
freq = pygame.mixer.get_init()[0]
gain = min(2.5, 31000.0 / max(1, np.max(np.abs(arr))))
arr = np.clip(arr.astype(np.float32) * gain, -32767, 32767).astype(np.int16)

ser = serial.Serial()
ser.port = "COM3"
ser.baudrate = 115200
ser.dtr = False
ser.rts = False
ser.open()
time.sleep(0.5)
ser.reset_input_buffer()

print("Waiting for ESP32 to be ready (WiFi + Mic)...")
for _ in range(20):
    if ser.in_waiting > 0:
        l = ser.readline().decode("utf-8", errors="ignore").strip()
        if "RMS hien tai" in l or "WiFi san sang" in l or "TASK MIC" in l:
            print("   ESP32 ready:", l)
            break
    time.sleep(0.3)

time.sleep(1.0)
ser.reset_input_buffer()

print(f"Playing '{phrase}' via sounddevice on Device 3 (Speakers Realtek Audio)...")
sd.play(arr, samplerate=freq, device=3)
sd.wait()
print("Playback done. Listening to ESP32 for 6 seconds...")

lines = []
t0 = time.time()
while time.time() - t0 < 6.0:
    if ser.in_waiting > 0:
        l = ser.readline().decode("utf-8", errors="ignore").strip()
        if l:
            lines.append(l)
            if any(k in l for k in ["[MIC", "[XIAOZHI", "BAN VUA NOI", "Hub phan hoi"]):
                print("   [ESP32]:", l)
    time.sleep(0.01)

ser.close()
