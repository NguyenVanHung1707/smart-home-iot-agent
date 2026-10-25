import os
import sys
import time
import wave
import numpy as np
import sounddevice as sd
import pygame
from gtts import gTTS
import subprocess
import json

# Reconfigure stdout to UTF-8
sys.stdout.reconfigure(encoding="utf-8")

def get_latest_transcribe_log():
    res = subprocess.run(
        ["docker", "logs", "homing-xiaozhi-server", "--tail", "15"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore"
    )
    lines = [ln for ln in res.stdout.split("\n") if "[HTTP TRANSCRIBE]" in ln]
    return lines[-1] if lines else ""

def run_pilot(phrase="bật đèn phòng khách"):
    print(f"\n=======================================================")
    print(f"PILOT HIL TEST: '{phrase}'")
    print(f"=======================================================")

    # 1. Generate Prompt Audio using gTTS
    prompt_file = "scripts/pilot_prompt.mp3"
    os.makedirs("scripts", exist_ok=True)
    tts = gTTS(text=phrase, lang="vi", slow=False)
    tts.save(prompt_file)
    print(f"1. Prompt audio generated: {prompt_file}")

    # 2. Record starting log position
    before_log = get_latest_transcribe_log()

    # 3. Play through Computer Speaker and Record Mic simultaneously
    pygame.mixer.init()
    pygame.mixer.music.load(prompt_file)
    pygame.mixer.music.set_volume(1.0) # Maximum volume for clear acoustic transmission

    sample_rate = 16000
    rec_duration = 9.0 # 9 seconds to cover prompt + ESP32 VAD + LLM + ESP32 speaker response
    print(f"2. Playing prompt through computer speaker and recording mic for {rec_duration}s...")

    rec_frames = sd.rec(int(rec_duration * sample_rate), samplerate=sample_rate, channels=1, dtype="int16")
    time.sleep(0.3)
    pygame.mixer.music.play()

    # Wait for recording to complete
    sd.wait()
    print("3. Audio playback and microphone capture finished.")

    # 4. Save recorded mic audio to inspect
    rec_file = "scripts/pilot_mic_capture.wav"
    with wave.open(rec_file, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(rec_frames.tobytes())

    rec_rms = float(np.sqrt(np.mean(rec_frames.astype(np.float32) ** 2)))
    print(f"4. Mic capture saved to {rec_file} (RMS energy: {rec_rms:.1f})")

    # 5. Check Docker Logs to see what ESP32 sent
    time.sleep(1.0)
    after_log = get_latest_transcribe_log()
    print(f"5. Latest Xiaozhi Server Log: {after_log}")

if __name__ == "__main__":
    run_pilot()
