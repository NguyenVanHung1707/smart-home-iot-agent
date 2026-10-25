import sys
import time
import os
import threading
import queue
import wave
import numpy as np
import serial
import sounddevice as sd
import pygame
from gtts import gTTS

sys.stdout.reconfigure(encoding="utf-8")

def run_test(phrase="bật đèn phòng khách"):
    print(f"\n=======================================================")
    print(f"RUNNING HIL TEST: '{phrase}'")
    print(f"=======================================================")

    # 1. Generate Prompt Audio using gTTS
    prompt_file = "scripts/test_prompt.mp3"
    tts = gTTS(text=phrase, lang="vi", slow=False)
    tts.save(prompt_file)
    print(f"1. Generated speech prompt: '{phrase}' -> {prompt_file}")

    # 2. Open Serial COM3 without resetting ESP32
    ser = serial.Serial()
    ser.port = "COM3"
    ser.baudrate = 115200
    ser.dtr = False
    ser.rts = False
    ser.timeout = 0.5
    ser.open()

    esp_lines = []
    stop_event = threading.Event()

    def serial_reader():
        while not stop_event.is_set():
            try:
                if ser.in_waiting > 0:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        esp_lines.append(line)
                        if any(k in line for k in ["[XIAOZHI", "[MIC", "[AUDIO", "BAN VUA NOI", "Hub phan hoi", "dispatch"]):
                            print(f"   [ESP32]: {line}")
            except Exception:
                break
            time.sleep(0.01)

    t_reader = threading.Thread(target=serial_reader, daemon=True)
    t_reader.start()

    # Clear previous buffer
    time.sleep(1.0)
    esp_lines.clear()

    # 3. Initialize pygame audio playback
    if not pygame.mixer.get_init():
        pygame.mixer.init()
    pygame.mixer.music.load(prompt_file)
    pygame.mixer.music.set_volume(1.0)

    # 4. Start recording on computer mic
    sample_rate = 16000
    rec_duration = 11.0 # 11s to capture prompt + ESP32 response
    print(f"2. Playing prompt out loud and recording mic for {rec_duration}s...")
    rec_frames = sd.rec(int(rec_duration * sample_rate), samplerate=sample_rate, channels=1, dtype="int16")

    # Play audio through computer speaker
    time.sleep(0.5)
    pygame.mixer.music.play()

    # Wait for recording
    sd.wait()
    print("3. Audio playback and recording completed.")

    # 5. Stop serial reader
    stop_event.set()
    time.sleep(0.5)
    ser.close()

    # 6. Analyze recorded mic audio
    rec_rms = float(np.sqrt(np.mean(rec_frames.astype(np.float32) ** 2)))
    rec_max = int(np.max(np.abs(rec_frames)))
    print(f"4. Computer Mic captured audio: RMS = {rec_rms:.1f}, Peak = {rec_max}")

    # Save capture
    rec_file = f"scripts/captured_{int(time.time())}.wav"
    with wave.open(rec_file, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(rec_frames.tobytes())
    print(f"   Saved room recording to {rec_file}")

    # 7. Check ESP32 detections
    vad_detected = any("[XIAOZHI MIC VAD]" in ln for ln in esp_lines)
    asr_done = any("[MIC ASR] Da thu xong" in ln for ln in esp_lines)
    user_said = ""
    hub_reply = ""
    for ln in esp_lines:
        if "BAN VUA NOI:" in ln:
            user_said = ln.split("BAN VUA NOI:")[-1].strip().strip("'")
        if "Hub phan hoi:" in ln:
            hub_reply = ln.split("Hub phan hoi:")[-1].strip()

    print("\n---------------- TEST RESULT SUMMARY ----------------")
    print(f"Target Phrase     : {phrase}")
    print(f"ESP32 VAD Trigger : {'YES' if vad_detected else 'NO'}")
    print(f"ESP32 ASR Sent    : {'YES' if asr_done else 'NO'}")
    print(f"ESP32 Heard (ASR) : {user_said or '(No ASR result detected)'}")
    print(f"Server Reply      : {hub_reply or '(No Hub reply)'}")
    print("-----------------------------------------------------\n")
    return {
        "phrase": phrase,
        "vad": vad_detected,
        "asr_done": asr_done,
        "user_said": user_said,
        "hub_reply": hub_reply,
        "rec_rms": rec_rms,
        "rec_file": rec_file
    }

if __name__ == "__main__":
    run_test("bật đèn phòng khách")
