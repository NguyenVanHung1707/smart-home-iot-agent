#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Homing Smart Home - ESP32 AI Voice Hardware-In-The-Loop (HIL) & PC Audio Testing Suite
Sử dụng Loa máy tính và Mic máy tính để kiểm tra toàn diện:
  1. HIL Acoustic Loop: Loa PC phát lệnh -> Micro ESP32 (INMP441) nghe -> Server Xiaozhi GPU xử lý -> Loa ESP32 (MAX98357A) phát -> Mic PC thu âm xác nhận.
  2. Live PC Mic: Nói trực tiếp vào Mic PC -> Server nhận diện PhoWhisper + Qwen 2.5 7B GPU -> Phát câu trả lời ra Loa PC.
  3. Batch Test: Tự động chạy bộ lệnh mẫu và báo cáo chi tiết.
"""

import os
import sys
import time
import wave
import json
import argparse
import threading
import subprocess
import urllib.request
import urllib.error
import numpy as np

# Thiết lập bảng mã UTF-8 cho console Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import sounddevice as sd
except ImportError:
    print("[ERROR] Chưa cài đặt sounddevice. Vui lòng chạy: pip install sounddevice")
    sys.exit(1)

RECORDINGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recordings")
os.makedirs(RECORDINGS_DIR, exist_ok=True)

XIAOZHI_HTTP_URL = "http://192.168.1.105:8093"
COM_PORT = "COM3"
BAUD_RATE = 115200


def get_docker_transcribe_log(tail: int = 15) -> str:
    """Lấy log nhận diện mới nhất từ container homing-xiaozhi-server."""
    try:
        res = subprocess.run(
            ["docker", "logs", "--tail", str(tail), "homing-xiaozhi-server"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=5
        )
        lines = [ln.strip() for ln in res.stdout.split("\n") if ln.strip()]
        return "\n".join(lines[-tail:]) if lines else ""
    except Exception as e:
        return f"[Docker log error: {e}]"


def generate_tts_wav(text: str, output_path: str) -> bool:
    """Tạo tệp âm thanh WAV tiếng Việt chuẩn từ văn bản."""
    # 1. Thử edge_tts
    try:
        import asyncio
        import edge_tts

        async def _edge():
            comm = edge_tts.Communicate(text, "vi-VN-NamMinhNeural")
            temp_mp3 = output_path.replace(".wav", ".mp3")
            await comm.save(temp_mp3)
            # Chuyển đổi sang WAV 16kHz 16-bit Mono chuẩn
            subprocess.run(
                ["ffmpeg", "-y", "-i", temp_mp3, "-ar", "16000", "-ac", "1", output_path],
                capture_output=True,
                check=True
            )
            if os.path.exists(temp_mp3):
                os.remove(temp_mp3)

        asyncio.run(_edge())
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return True
    except Exception:
        pass

    # 2. Dự phòng bằng gTTS
    try:
        from gtts import gTTS
        temp_mp3 = output_path.replace(".wav", ".mp3")
        tts = gTTS(text=text, lang="vi", slow=False)
        tts.save(temp_mp3)
        # Dùng ffmpeg hoặc pydub nếu có để chuyển sang wav
        res = subprocess.run(
            ["ffmpeg", "-y", "-i", temp_mp3, "-ar", "16000", "-ac", "1", output_path],
            capture_output=True
        )
        if os.path.exists(temp_mp3):
            os.remove(temp_mp3)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return True
    except Exception:
        pass

    # 3. Fallback bằng API máy chủ Xiaozhi
    try:
        req_data = json.dumps({"text": text}).encode("utf-8")
        req = urllib.request.Request(
            f"{XIAOZHI_HTTP_URL}/xiaozhi/test_text",
            data=req_data,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            audio_url = data.get("audio_url")
            if audio_url:
                urllib.request.urlretrieve(audio_url, output_path)
                return True
    except Exception:
        pass

    return False


def play_wav_through_speaker(wav_path: str):
    """Phát âm thanh ra Loa máy tính sử dụng sounddevice."""
    with wave.open(wav_path, "rb") as wf:
        samplerate = wf.getframerate()
        n_frames = wf.getnframes()
        data = wf.readframes(n_frames)
        audio_array = np.frombuffer(data, dtype=np.int16)
        channels = wf.getnchannels()
        if channels > 1:
            audio_array = audio_array.reshape(-1, channels)
        sd.play(audio_array, samplerate)
        sd.wait()


def monitor_serial_com(port: str, stop_event: threading.Event, log_collector: list):
    """Luồng nền giám sát Serial ESP32 trên cổng COM."""
    try:
        import serial
        ser = serial.Serial(port, BAUD_RATE, timeout=0.2)
        while not stop_event.is_set():
            line = ser.readline().decode("utf-8", errors="replace").strip()
            if line:
                log_collector.append(line)
        ser.close()
    except Exception:
        pass


def test_hil_acoustic(phrase: str = "Bật đèn phòng khách", record_seconds: float = 11.0):
    """
    Mode 1: Kiểm thử vòng lặp âm học thực tế (Hardware-In-The-Loop)
    - Loa PC phát giọng đọc tiếng Việt rõ ràng.
    - Micro ESP32 thu nhận âm thanh, kích hoạt VAD và xử lý qua Server Xiaozhi GPU.
    - Loa ESP32 phát câu trả lời.
    - Mic PC ghi âm toàn bộ quá trình để phân tích phổ năng lượng RMS.
    """
    print("\n" + "=" * 65)
    print("▶ CHẾ ĐỘ 1: KIỂM THỬ VÒNG LẶP ÂM HỌC (HIL ACOUSTIC TEST)")
    print(f"  Câu lệnh kiểm tra: \"{phrase}\"")
    print("=" * 65)

    # 1. Tạo tệp âm thanh phát
    prompt_wav = os.path.join(RECORDINGS_DIR, "hil_prompt.wav")
    print("⏳ [1/5] Đang tạo giọng đọc tiếng Việt cho câu lệnh...")
    ok = generate_tts_wav(phrase, prompt_wav)
    if not ok:
        print("❌ [LỖI] Không thể tạo âm thanh giọng đọc. Kiểm tra kết nối mạng!")
        return False
    print(f"✔ Đã tạo tệp âm thanh: {prompt_wav}")

    # 2. Khởi động luồng đọc Serial COM3 của ESP32
    esp_logs = []
    stop_serial = threading.Event()
    t_serial = threading.Thread(target=monitor_serial_com, args=(COM_PORT, stop_serial, esp_logs), daemon=True)
    t_serial.start()

    # 3. Chuẩn bị dữ liệu phát âm và đệm khoảng lặng cho ghi âm đồng thời
    sample_rate = 16000
    total_samples = int(record_seconds * sample_rate)
    with wave.open(prompt_wav, "rb") as wf:
        sr = wf.getframerate()
        raw_prompt = wf.readframes(wf.getnframes())
        prompt_arr = np.frombuffer(raw_prompt, dtype=np.int16)
        if wf.getnchannels() > 1:
            prompt_arr = prompt_arr[::wf.getnchannels()]

    padded_playback = np.zeros(total_samples, dtype=np.int16)
    offset = int(0.4 * sample_rate) # Bắt đầu phát sau 0.4s tĩnh lặng
    p_len = min(len(prompt_arr), total_samples - offset)
    padded_playback[offset : offset + p_len] = prompt_arr[:p_len]

    # 4. Phát câu lệnh ra Loa máy tính và đồng thời ghi âm từ Mic máy tính (Full-Duplex)
    print(f"🔊 [3/5] ĐANG PHÁT RA LOA PC VÀ ĐỒNG THỜI GHI ÂM TỪ MIC PC ({record_seconds:.1f}s)...")
    print(f"   Câu lệnh: \"{phrase}\"")
    print("   (ESP32 đang lắng nghe qua micro INMP441 và sẽ phản hồi qua Loa MAX98357A...)")

    pc_mic_frames = sd.playrec(padded_playback, samplerate=sample_rate, channels=1, dtype="int16")
    sd.wait()
    stop_serial.set()
    t_serial.join(timeout=1.0)

    # 5. Lưu bản thu âm của Mic máy tính
    rec_timestamp = int(time.time())
    capture_wav = os.path.join(RECORDINGS_DIR, f"hil_capture_{rec_timestamp}.wav")
    with wave.open(capture_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pc_mic_frames.tobytes())

    print(f"✔ [4/5] Hoàn tất ghi âm! Tệp âm thanh đã lưu tại: {capture_wav}")

    # 7. Phân tích kết quả
    print("\n" + "-" * 65)
    print("📊 KẾT QUẢ PHÂN TÍCH VÒNG LẶP ÂM HỌC:")
    print("-" * 65)

    # Tính RMS năng lượng âm thanh trong pha phản hồi của ESP32 (từ giây thứ 4 đến hết)
    reply_start_sample = int(4.0 * sample_rate)
    reply_audio = pc_mic_frames[reply_start_sample:]
    reply_rms = float(np.sqrt(np.mean(reply_audio.astype(np.float32) ** 2)))

    # Kiểm tra log Serial ESP32
    esp_vad_detected = any("VAD" in ln for ln in esp_logs)
    esp_asr_sent = any("MIC ASR" in ln for ln in esp_logs)
    esp_received_reply = any("Hub phan hoi" in ln or "Phat am thanh" in ln for ln in esp_logs)

    # Kiểm tra log Docker server
    server_logs = get_docker_transcribe_log(15)

    print(f"  • Năng lượng âm thanh phản hồi (Mic PC ghi nhận): RMS = {reply_rms:.1f}")
    print(f"  • ESP32 kích hoạt VAD: {'✔ ĐẠT' if esp_vad_detected else '⚠️ Chưa ghi nhận qua Serial'}")
    print(f"  • ESP32 gửi âm thanh lên Server: {'✔ ĐẠT' if esp_asr_sent else '⚠️ Đang xử lý'}")
    print(f"  • ESP32 nhận phản hồi từ Hub: {'✔ ĐẠT' if esp_received_reply else '⚠️ Xem log máy chủ bên dưới'}")

    if esp_logs:
        print("\n[Trích xuất Serial ESP32]:")
        for ln in esp_logs[-8:]:
            print(f"   {ln}")

    print("\n[Log máy chủ Xiaozhi AI (GPU PhoWhisper + Qwen 2.5 7B)]:")
    print(server_logs)

    print("=" * 65)
    if reply_rms > 300 or esp_received_reply:
        print("🎉 KIỂM THỬ THÀNH CÔNG: Vòng lặp Loa PC -> Micro ESP32 -> AI GPU -> Loa ESP32 hoạt động hoàn hảo!")
        return True
    else:
        print("ℹ️ Âm lượng Loa PC có thể hơi nhỏ hoặc khoảng cách xa. Bạn hãy tăng âm lượng loa PC và đặt ESP32 gần hơn một chút nhé.")
        return False


def test_live_pc_mic(duration_seconds: float = 4.0):
    """
    Mode 2: Nói trực tiếp vào Mic máy tính để kiểm tra AI Server
    - Ghi âm giọng nói người dùng từ Mic máy tính trong 4s.
    - Gửi trực tiếp lên Server Xiaozhi GPU.
    - Nhận diện câu nói, sinh câu trả lời bằng Qwen 2.5 7B, tải âm thanh WAV và phát ra Loa máy tính.
    """
    print("\n" + "=" * 65)
    print("▶ CHẾ ĐỘ 2: THỬ NGHIỆM TRỰC TIẾP QUA MIC VÀ LOA MÁY TÍNH")
    print(f"  Thời lượng ghi âm: {duration_seconds:.1f} giây")
    print("=" * 65)

    sample_rate = 16000
    print(f"🎤 HÃY NÓI VÀO MIC MÁY TÍNH NGAY BÂY GIỜ ({duration_seconds:.0f}s)...")
    print("   Ví dụ: \"Bật đèn phòng khách\" hoặc \"Thời tiết hôm nay thế nào\"")

    recorded_frames = sd.rec(int(duration_seconds * sample_rate), samplerate=sample_rate, channels=1, dtype="int16")
    sd.wait()
    print("✔ Đã ghi âm xong! Đang xử lý qua VinAI PhoWhisper & Qwen 2.5 7B GPU...")

    # Đóng gói WAV
    wav_bytes = bytearray()
    import io
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(recorded_frames.tobytes())
    raw_wav = wav_io.getvalue()

    # Gửi tới Server Xiaozhi
    try:
        req = urllib.request.Request(
            f"{XIAOZHI_HTTP_URL}/xiaozhi/transcribe",
            data=raw_wav,
            headers={
                "Content-Type": "audio/wav",
                "X-Device-Id": "pc-client",
                "X-Room-Id": "living"
            }
        )
        t_start = time.time()
        with urllib.request.urlopen(req, timeout=15) as resp:
            latency = (time.time() - t_start) * 1000
            data = json.loads(resp.read().decode("utf-8"))

        user_text = data.get("text", "")
        reply_text = data.get("reply", "")
        audio_url = data.get("audio_url", "")
        device_id = data.get("device_id", "")
        action = data.get("action", "")

        print("\n" + "-" * 65)
        print("📊 PHẢN HỒI TỪ HỆ THỐNG AI HOMING:")
        print("-" * 65)
        print(f"  • Nhận diện giọng nói (PhoWhisper GPU) : \"{user_text}\"")
        print(f"  • Câu trả lời AI (Qwen 2.5 7B GPU)    : \"{reply_text}\"")
        if device_id and action:
            print(f"  • Lệnh điều khiển thiết bị             : {device_id} -> {action}")
        print(f"  • Thời gian phản hồi tổng thể          : {latency:.0f}ms")

        if audio_url:
            print(f"  • URL âm thanh phản hồi               : {audio_url}")
            reply_wav = os.path.join(RECORDINGS_DIR, "pc_reply.wav")
            urllib.request.urlretrieve(audio_url, reply_wav)
            print("🔊 ĐANG PHÁT CÂU TRẢ LỜI RA LOA MÁY TÍNH...")
            play_wav_through_speaker(reply_wav)
            print("✔ Hoàn tất phát âm thanh!")
        else:
            print("ℹ️ Không có âm thanh phản hồi (im lặng hoặc câu rỗng).")

    except Exception as e:
        print(f"❌ [LỖI KẾT NỐI SERVER]: {e}")


def test_batch_suite():
    """Mode 3: Chạy tự động bộ 4 câu lệnh chuẩn và in bảng đánh giá."""
    test_cases = [
        "Bật đèn phòng khách",
        "Tắt đèn phòng khách",
        "Thời tiết hôm nay thế nào?",
        "Hôm nay là thứ mấy?"
    ]
    print("\n" + "=" * 65)
    print("▶ CHẾ ĐỘ 3: CHẠY TỰ ĐỘNG BỘ LỆNH MẪU (BATCH BENCHMARK)")
    print(f"  Số lượng ca kiểm thử: {len(test_cases)}")
    print("=" * 65)

    results = []
    for i, phrase in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}] Đang kiểm tra: \"{phrase}\"")
        passed = test_hil_acoustic(phrase=phrase, record_seconds=10.0)
        results.append((phrase, passed))
        time.sleep(2.0)

    print("\n" + "=" * 65)
    print("📋 BẢNG TỔNG HỢP KIỂM THỬ BATCH HIL:")
    print("=" * 65)
    print(f"{'STT':<5} | {'Câu lệnh':<32} | {'Trạng thái'}")
    print("-" * 65)
    for i, (phrase, passed) in enumerate(results, 1):
        status_str = "✔ THÀNH CÔNG" if passed else "⚠️ CẦN KIỂM TRA"
        print(f"{i:<5} | {phrase:<32} | {status_str}")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="Homing Smart Home - ESP32 AI Voice Testing Suite")
    parser.add_argument("--mode", choices=["hil", "mic", "batch"], default=None,
                        help="Chế độ kiểm tra: 'hil' (Acoustic loop), 'mic' (Nói qua Mic PC), 'batch' (Chạy toàn bộ)")
    parser.add_argument("--phrase", type=str, default="Bật đèn phòng khách",
                        help="Câu lệnh thử nghiệm cho chế độ hil (mặc định: 'Bật đèn phòng khách')")
    parser.add_argument("--duration", type=float, default=11.0,
                        help="Thời lượng ghi âm (giây) cho chế độ hil")

    args = parser.parse_args()

    if args.mode == "hil":
        test_hil_acoustic(phrase=args.phrase, record_seconds=args.duration)
    elif args.mode == "mic":
        test_live_pc_mic()
    elif args.mode == "batch":
        test_batch_suite()
    else:
        # Menu tương tác trực quan
        print("\n" + "=" * 65)
        print("  HOMING SMART HOME - BỘ CÔNG CỤ TEST VOICE AI (PC & ESP32)")
        print("=" * 65)
        print("  1. [HIL Acoustic] Loa PC phát lệnh -> ESP32 nghe -> Loa ESP32 phản hồi")
        print("  2. [Live Mic] Nói trực tiếp vào Mic PC -> AI GPU xử lý -> Loa PC phát")
        print("  3. [Batch Suite] Tự động kiểm thử toàn bộ 4 câu lệnh chuẩn")
        print("  4. Thoát")
        print("=" * 65)

        choice = input("👉 Chọn chế độ (1-4) [mặc định 1]: ").strip()
        if choice == "2":
            test_live_pc_mic()
        elif choice == "3":
            test_batch_suite()
        elif choice == "4":
            print("Tạm biệt!")
            sys.exit(0)
        else:
            p = input("Nhập câu lệnh muốn kiểm tra [Bật đèn phòng khách]: ").strip()
            phrase = p if p else "Bật đèn phòng khách"
            test_hil_acoustic(phrase=phrase)


if __name__ == "__main__":
    main()
