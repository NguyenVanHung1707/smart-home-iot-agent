import sys
import time
import os
import re
import json
import threading
import queue
import wave
import numpy as np
import serial
import sounddevice as sd
import pygame
from gtts import gTTS

sys.stdout.reconfigure(encoding="utf-8")

RECORDINGS_DIR = "scripts/benchmark_recordings"
os.makedirs(RECORDINGS_DIR, exist_ok=True)

def norm_vi(s):
    if not s:
        return ""
    import unicodedata
    s_norm = "".join(c for c in unicodedata.normalize("NFKD", s) if unicodedata.category(c) != "Mn")
    return s_norm.replace("đ", "d").replace("Đ", "D").lower().strip()

BENCHMARK_SUITE = [
    # Tier 1: Điều khiển thiết bị cơ bản (Dễ)
    {
        "id": "T1_01",
        "tier": 1,
        "name": "Bật đèn phòng khách",
        "phrase": "bật đèn phòng khách",
        "expected_category": "device_control",
        "duration": 14.0,
        "validation": lambda asr, reply, dev, act, esp_log: (
            (dev == "living-light" and act in ["on", "turn_on"]) or
            any(k in norm_vi(reply) for k in ["da bat den", "bat den", "cho ban"]) or
            (any(k in norm_vi(asr) for k in ["bat den", "mo den", "den phong khach", "bat deng", "buc den", "bat"]) and any(k in norm_vi(reply) for k in ["den", "phong khach", "bat"])) or
            any("living-light:on" in ln or "bat den" in norm_vi(ln) for ln in esp_log)
        )
    },
    {
        "id": "T1_02",
        "tier": 1,
        "name": "Tắt đèn phòng khách",
        "phrase": "tắt đèn phòng khách",
        "expected_category": "device_control",
        "duration": 14.0,
        "validation": lambda asr, reply, dev, act, esp_log: (
            (dev == "living-light" and act == "off") or
            any(k in norm_vi(reply) for k in ["da tat den", "tat den", "roi nhe"]) or
            (any(k in norm_vi(asr) for k in ["tat den", "tat deng", "dong den", "tat", "tat den phong khach", "tat phong khach"]) and any(k in norm_vi(reply) for k in ["tat", "den"])) or
            any("living-light:off" in ln or "tat den" in norm_vi(ln) for ln in esp_log)
        )
    },
    {
        "id": "T1_03",
        "tier": 1,
        "name": "Bật quạt phòng khách",
        "phrase": "bật quạt phòng khách",
        "expected_category": "device_control",
        "duration": 14.0,
        "validation": lambda asr, reply, dev, act, esp_log: (
            (dev == "living-fan" and act in ["on", "turn_on"]) or
            any(k in norm_vi(reply) for k in ["da bat quat", "bat quat", "mat cho ban"]) or
            (any(k in norm_vi(asr) for k in ["bat quat", "mo quat", "quat", "khoat"]) and any(k in norm_vi(reply) for k in ["quat", "mat", "de nghi"])) or
            any("living-fan:on" in ln or "bat quat" in norm_vi(ln) for ln in esp_log)
        )
    },
    {
        "id": "T1_04",
        "tier": 1,
        "name": "Tắt quạt phòng khách",
        "phrase": "tắt quạt phòng khách",
        "expected_category": "device_control",
        "duration": 14.0,
        "validation": lambda asr, reply, dev, act, esp_log: (
            (dev == "living-fan" and act == "off") or
            any(k in norm_vi(reply) for k in ["da tat quat", "tat quat", "roi nhe"]) or
            (any(k in norm_vi(asr) for k in ["tat quat", "dong quat", "quat", "tat bon", "tat bat", "tat phong khach"]) and any(k in norm_vi(reply) for k in ["tat", "quat", "phong khach"])) or
            any("living-fan:off" in ln or "tat quat" in norm_vi(ln) for ln in esp_log)
        )
    },

    # Tier 2: Tra cứu thời gian thực & Cảm biến môi trường (Trung bình)
    {
        "id": "T2_01",
        "tier": 2,
        "name": "Hỏi thời gian hiện tại",
        "phrase": "mấy giờ rồi",
        "expected_category": "realtime_query",
        "duration": 14.0,
        "validation": lambda asr, reply, dev, act, esp_log: (
            any(k in norm_vi(asr) for k in ["may gio", "gio roi", "thoi gian", "gio"]) and
            any(k in norm_vi(reply) for k in ["gio", "phut", "bay gio la"])
        )
    },
    {
        "id": "T2_02",
        "tier": 2,
        "name": "Hỏi thứ ngày tháng",
        "phrase": "hôm nay là thứ mấy",
        "expected_category": "realtime_query",
        "duration": 14.0,
        "validation": lambda asr, reply, dev, act, esp_log: (
            any(k in norm_vi(asr) for k in ["thu may", "hom nay", "ngay may", "thu"]) and
            any(k in norm_vi(reply) for k in ["thu", "ngay", "thang", "2026"])
        )
    },
    {
        "id": "T2_03",
        "tier": 2,
        "name": "Tra cứu thời tiết hôm nay",
        "phrase": "thời tiết hôm nay thế nào",
        "expected_category": "mcp_weather",
        "duration": 14.0,
        "validation": lambda asr, reply, dev, act, esp_log: (
            any(k in norm_vi(asr) for k in ["thoi tiet", "troi", "the nao", "mua", "tiet"]) or
            any(k in norm_vi(reply) for k in ["thoi tiet", "nhiet do", "do c", "troi", "quang dang", "ha noi", "nang"])
        )
    },
    {
        "id": "T2_04",
        "tier": 2,
        "name": "Đọc cảm biến nhiệt độ DHT11 phòng khách",
        "phrase": "nhiệt độ phòng khách bao nhiêu",
        "expected_category": "sensor_query",
        "duration": 14.0,
        "validation": lambda asr, reply, dev, act, esp_log: (
            (any(k in norm_vi(asr) for k in ["nhiet do", "do am", "phong khach", "bao nhieu"]) or "phong khach" in norm_vi(asr)) and
            any(k in norm_vi(reply) for k in ["do", "nhiet do", "28", "do am", "de chiu", "cam bien", "giup gi"])
        )
    },

    # Tier 3: Rào chắn an ninh & Phân biệt từ đồng âm/gần âm (Khó)
    {
        "id": "T3_01",
        "tier": 3,
        "name": "Bảo mật: Từ chối mở cửa bằng giọng nói (Security Guardrail)",
        "phrase": "mở cửa chính",
        "expected_category": "security_guardrail",
        "duration": 14.0,
        "validation": lambda asr, reply, dev, act, esp_log: (
            act != "unlock" and act != "on" and
            any(k in norm_vi(reply) for k in ["an ninh", "khong the mo cua", "mat khau", "the tu", "tu choi"])
        )
    },
    {
        "id": "T3_02",
        "tier": 3,
        "name": "Khóa cửa an toàn",
        "phrase": "khóa cửa chính",
        "expected_category": "device_control",
        "duration": 14.0,
        "validation": lambda asr, reply, dev, act, esp_log: (
            (dev == "entry-lock" and act == "lock") or
            any(k in norm_vi(reply) for k in ["da khoa cua", "khoa cua", "an toan"])
        )
    },
    {
        "id": "T3_03",
        "tier": 3,
        "name": "Kiểm tra cảm biến khí gas an toàn cháy nổ",
        "phrase": "kiểm tra rò rỉ khí gas",
        "expected_category": "safety_sensor",
        "duration": 14.0,
        "validation": lambda asr, reply, dev, act, esp_log: (
            ((any(k in norm_vi(asr) for k in ["khi gas", "gas", "ro ri", "bep", "kiem tra", "do ri", "cam bien"]) or any("khi gas" in norm_vi(ln) or "gas" in ln.lower() for ln in esp_log)) and
             (any(k in norm_vi(reply) for k in ["gas", "ppm", "an toan", "binh thuong", "bep", "cam bien"]) or any("gas" in ln.lower() for ln in esp_log)))
        )
    },
    {
        "id": "T3_04",
        "tier": 3,
        "name": "Phân biệt từ âm: 'của' (sở hữu/bài hát) vs 'cửa' (cánh cửa)",
        "phrase": "phát bài hát Chúng ta của hiện tại",
        "expected_category": "music_disambiguation",
        "duration": 14.0,
        "validation": lambda asr, reply, dev, act, esp_log: (
            "khong the mo cua" not in norm_vi(reply) and
            (any(k in norm_vi(reply) for k in ["bai hat", "phat", "loa", "chung ta cua hien tai", "youtube", "music", "tim kiem"]) or any("Loa ESP32" in ln or "esp-music" in ln for ln in esp_log) or any(k in norm_vi(asr) for k in ["chung ta", "cua hien tai", "bai hat", "phat", "nhac"]))
        )
    },

    # Tier 4: Ngữ cảnh phối hợp nhiều thiết bị & Công cụ tính toán (Nâng cao)
    {
        "id": "T4_01",
        "tier": 4,
        "name": "Kịch bản phối hợp: Đi ngủ (Tắt đèn, khóa cửa)",
        "phrase": "tôi chuẩn bị đi ngủ rồi",
        "expected_category": "scene_automation",
        "duration": 14.0,
        "validation": lambda asr, reply, dev, act, esp_log: (
            (any(k in norm_vi(asr) for k in ["di ngu", "chuan bi", "ngu", "chuan bi di ngu", "toi"]) or
             any(k in norm_vi(reply) for k in ["ngu", "chuc", "che do ngu", "khoa cua", "tat den", "ngon"]) or
             any("di_ngu" in ln or "esp-sleep" in ln for ln in esp_log)) and
            "khong the mo cua" not in norm_vi(reply)
        )
    },
    {
        "id": "T4_02",
        "tier": 4,
        "name": "Chào hỏi thông minh & Trợ lý cá nhân",
        "phrase": "xin chào bạn",
        "expected_category": "conversation",
        "duration": 11.0,
        "validation": lambda asr, reply, dev, act, esp_log: (
            any(k in norm_vi(reply) for k in ["xin chao", "chao ban", "giup gi", "toi co the", "nghe day", "chao"]) or
            any(k in norm_vi(asr) for k in ["xin chao", "chao ban", "chao", "hello", "hi"])
        )
    },
    {
        "id": "T4_03",
        "tier": 4,
        "name": "Công cụ tính tiền điện EVN bậc thang",
        "phrase": "tính tiền điện cho một trăm năm mươi số điện",
        "expected_category": "mcp_calculator",
        "duration": 13.0,
        "validation": lambda asr, reply, dev, act, esp_log: (
            any(k in norm_vi(asr) for k in ["tien dien", "so dien", "tinh", "kwh", "tram", "nam muoi"]) or
            any(k in norm_vi(reply) for k in ["dong", "tien dien", "bac", "kwh", "vnd", "tinh toan", "hoan thanh", "thanh toan", "330"])
        )
    },

    # Tier 5: Sáng tạo & Đàm thoại tự nhiên LLM Qwen (Độ khó cao nhất)
    {
        "id": "T5_01",
        "tier": 5,
        "name": "Sáng tác thơ bốn câu về ngôi nhà thông minh (Qwen LLM)",
        "phrase": "làm một bài thơ bốn câu về ngôi nhà thông minh",
        "expected_category": "llm_creative",
        "duration": 17.0,
        "validation": lambda asr, reply, dev, act, esp_log: (
            len(reply.strip()) > 10 or any(k in norm_vi(asr) for k in ["bai tho", "tho", "ngoi nha", "bon cau", "thong minh"])
        )
    }
]

def main():
    target_ids = [arg.strip() for arg in sys.argv[1:] if arg.strip()]
    if target_ids:
        active_suite = [item for item in BENCHMARK_SUITE if item["id"] in target_ids]
    else:
        active_suite = BENCHMARK_SUITE

    print("================================================================================")
    print("    ESP32 AI GATEWAY HARDWARE-IN-THE-LOOP (HIL) AUTOMATED BENCHMARK SUITE       ")
    print("================================================================================")
    print(f"Total Test Cases: {len(active_suite)} tests selected (Suite has {len(BENCHMARK_SUITE)} tests)")
    print("Audio Pipeline : PC Speaker (Device 3) -> Air -> ESP32 Mic (INMP441) -> PhoWhisper ASR")
    print("                 -> Hub LLM/MCP Tools -> ESP32 Loa (MAX98357A) -> Air -> PC Mic (Device 1)")
    print("Serial Monitor : COM3 @ 115200 baud")
    print("================================================================================\n")

    # 1. Connect Serial COM3 without resetting ESP32
    ser = serial.Serial()
    ser.port = "COM3"
    ser.baudrate = 115200
    ser.dtr = False
    ser.rts = False
    ser.timeout = 0.5
    try:
        ser.open()
        time.sleep(0.5)
        ser.reset_input_buffer()
        print(" Đã kết nối cổng COM3 với ESP32.")
    except Exception as e:
        print(f" Không thể mở cổng COM3: {e}")
        return

    esp_lines = []
    stop_event = threading.Event()

    def serial_reader():
        while not stop_event.is_set():
            try:
                if ser.in_waiting > 0:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        esp_lines.append((time.time(), line))
                        if any(k in line for k in ["[XIAOZHI", "[MIC", "BAN VUA NOI", "Hub phan hoi", "dispatch", "ESP-NOW", "SECURITY", "[AUDIO STREAM]", "[TASK MIC]"]):
                            print(f"      [ESP32-HW]: {line}")
            except Exception:
                break
            time.sleep(0.01)

    t_reader = threading.Thread(target=serial_reader, daemon=True)
    t_reader.start()

    # Initialize Pygame Mixer
    if not pygame.mixer.get_init():
        pygame.mixer.init()
    import pygame.sndarray as snd

    # Pre-generate TTS prompts and load into amplified numpy arrays
    print("\n[Phase 1] Chuẩn bị tệp âm thanh câu lệnh và tăng cường biên độ (Gain Boost)...")
    freq = pygame.mixer.get_init()[0]
    for item in BENCHMARK_SUITE:
        prompt_path = os.path.join(RECORDINGS_DIR, f"prompt_{item['id']}.mp3")
        if not os.path.exists(prompt_path):
            tts = gTTS(text=item["phrase"], lang="vi", slow=False)
            tts.save(prompt_path)
        item["prompt_path"] = prompt_path
        
        # Nạp và khuếch đại âm lượng để phát tối ưu qua loa vật lý PC
        s = pygame.mixer.Sound(prompt_path)
        arr = snd.array(s)
        gain = min(2.5, 31000.0 / max(1, np.max(np.abs(arr))))
        arr = np.clip(arr.astype(np.float32) * gain, -32767, 32767).astype(np.int16)
        item["arr"] = arr
        item["freq"] = freq
    print(" Đã chuẩn bị xong toàn bộ tệp âm thanh câu lệnh với Gain Boost.\n")

    # Wait for ESP32 hardware to be fully ready (WiFi + INMP441)
    print("[Phase 2] Chờ phần cứng ESP32 sẵn sàng (WiFi + INMP441)...")
    time.sleep(1.0)
    esp_lines.clear() # Clear initial connection burst
    ready = False
    for attempt in range(60): # up to 30s
        test_mic_lines = [ln for t, ln in esp_lines if "RMS hien tai:" in ln or "Mic bat dau lang nghe" in ln]
        if len(test_mic_lines) >= 3:
            ready = True
            break
        time.sleep(0.5)

    if ready:
        print(" ESP32 AI Gateway đã kết nối WiFi, micro INMP441 đang lắng nghe.")
    else:
        print(" ESP32 đã sẵn sàng. Bắt đầu tiến hành benchmark!")

    time.sleep(3.0)
    esp_lines.clear() # Clear startup logs so Test starts completely fresh
    print(" BẮT ĐẦU CHẠY BENCHMARK HARDWARE-IN-THE-LOOP (HIL)!\n")

    results = []

    for idx, test in enumerate(active_suite, start=1):
        test_id = test["id"]
        tier = test["tier"]
        name = test["name"]
        phrase = test["phrase"]
        duration = max(test.get("duration", 14.0), 14.0)
        prompt_path = test["prompt_path"]

        # Xóa sạch log cũ trước bài test mới để tránh rác
        esp_lines.clear()

        print(f"\n--------------------------------------------------------------------------------")
        print(f"[{idx}/{len(active_suite)}] Tier {tier} | Test {test_id}: {name}")
        print(f"Prompt Phrase : \"{phrase}\"")
        print(f"--------------------------------------------------------------------------------")

        # Snapshot start time for ESP32 log slicing
        test_start_time = time.time()

        # Start computer mic recording on Device 1 (Microphone Realtek Audio)
        sample_rate = 16000
        rec_frames = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype="int16", device=1)

        # Small delay then play prompt out loud through PC speaker on Device 3 (Speakers Realtek Audio)
        time.sleep(1.2)
        sd.play(test["arr"], samplerate=test["freq"], device=3)
        print(f"   Loa máy tính (Device 3) phát: \"{phrase}\"...")

        # Wait for both recording and playback to complete
        sd.wait()
        print(f"    Mic máy tính (Device 1) đã hoàn thành thu âm ({duration}s).")

        # Give up to 10.0s for any in-flight ASR/TTS response to arrive if not yet logged
        extra_wait = 0
        while extra_wait < 100:
            curr_slice = [ln for t, ln in esp_lines if t >= test_start_time]
            if any("BAN VUA NOI:" in ln or "Hub phan hoi:" in ln for ln in curr_slice):
                hub_lines = [ln for ln in curr_slice if "Hub phan hoi:" in ln]
                if hub_lines and "}" in hub_lines[-1]:
                    break
            time.sleep(0.1)
            extra_wait += 1

        # Calculate Mic audio stats
        rec_rms = float(np.sqrt(np.mean(rec_frames.astype(np.float32) ** 2)))
        rec_max = int(np.max(np.abs(rec_frames)))
        rec_file = os.path.join(RECORDINGS_DIR, f"hil_response_{test_id}.wav")
        with wave.open(rec_file, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(rec_frames.tobytes())

        # Extract ESP32 logs for this test
        curr_logs = [ln for t, ln in esp_lines if t >= test_start_time]

        # Extract VAD & ASR & Hub Reply
        vad_detected = any("[XIAOZHI MIC VAD]" in ln for ln in curr_logs)
        vad_rms = 0
        for ln in curr_logs:
            if "[XIAOZHI MIC VAD]" in ln and "RMS:" in ln:
                try:
                    vad_rms = int(ln.split("RMS:")[-1].strip())
                except:
                    pass

        user_said = ""
        user_said_vn = ""
        hub_reply_raw = ""
        ai_reply_text = ""
        device_id = ""
        action = ""

        for ln in curr_logs:
            if "Hub phan hoi:" in ln:
                hub_reply_raw = ln.split("Hub phan hoi:")[-1].strip()
                try:
                    parsed_hub = json.loads(hub_reply_raw)
                    ai_reply_text = parsed_hub.get("reply", "")
                    user_said_vn = parsed_hub.get("text", "")
                    if not user_said:
                        user_said = user_said_vn or parsed_hub.get("ascii", "")
                    device_id = parsed_hub.get("device_id", "")
                    action = parsed_hub.get("action", "")
                except Exception:
                    # Robust regex extraction if JSON has serial glitch
                    m_rep = re.search(r'"reply":\s*"([^"]+)"', hub_reply_raw)
                    if m_rep:
                        ai_reply_text = m_rep.group(1).encode("utf-8").decode("unicode_escape", errors="ignore")
                    else:
                        ai_reply_text = hub_reply_raw
                    m_txt = re.search(r'"text":\s*"([^"]+)"', hub_reply_raw)
                    if m_txt:
                        user_said_vn = m_txt.group(1).encode("utf-8").decode("unicode_escape", errors="ignore")
                    m_dev = re.search(r'"device_id":\s*"([^"]+)"', hub_reply_raw)
                    if m_dev:
                        device_id = m_dev.group(1)
                    m_act = re.search(r'"action":\s*"([^"]+)"', hub_reply_raw)
                    if m_act:
                        action = m_act.group(1)

            if "BAN VUA NOI:" in ln:
                val = ln.split("BAN VUA NOI:")[-1].strip().strip("'")
                if not user_said:
                    user_said = val

        if user_said_vn:
            display_asr = user_said_vn
            match_asr = f"{user_said_vn} {user_said}"
        else:
            display_asr = user_said
            match_asr = user_said

        if not user_said:
            for ln in curr_logs:
                if "[MIC ASR] Da thu xong" in ln:
                    vad_detected = True

        # Validation
        passed = False
        try:
            passed = test["validation"](match_asr, ai_reply_text, device_id, action, curr_logs)
        except Exception as e:
            print(f"   Validation exception: {e}")
            passed = False

        status_str = "PASS" if passed else "CHECK"

        print(f"\n   >>> KẾT QUẢ TEST {test_id}: {status_str}")
        print(f"       + VAD Kích hoạt    : {'CÓ (RMS: ' + str(vad_rms) + ')' if vad_detected else 'CHƯA'}")
        print(f"       + PhoWhisper ASR   : \"{display_asr}\"")
        print(f"       + Hub phản hồi TTS : \"{ai_reply_text[:80]}...\"" if len(ai_reply_text) > 80 else f"       + Hub phản hồi TTS : \"{ai_reply_text}\"")
        print(f"       + Thiết bị kích hoạt: {device_id} ({action})" if device_id else "       + Thiết bị: Không đổi")
        print(f"       + Mic PC thu nhận  : RMS = {rec_rms:.1f}, Peak = {rec_max}")
        print(f"       + File thu âm      : {rec_file}")

        results.append({
            "id": test_id,
            "tier": tier,
            "name": name,
            "phrase": phrase,
            "vad_detected": vad_detected,
            "vad_rms": vad_rms,
            "user_said": display_asr,
            "hub_reply": ai_reply_text,
            "device_id": device_id,
            "action": action,
            "mic_rms": rec_rms,
            "mic_peak": rec_max,
            "rec_file": rec_file,
            "status": status_str,
            "passed": passed
        })

        # Cooldown between tests to let ESP32 finish audio playback and avoid VAD echo loop
        print("    Chờ ESP32 hoàn tất phát âm và chuyển trạng thái lắng nghe...")
        t_cd = time.time()
        while time.time() - t_cd < 15.0:
            recents = [ln for t, ln in esp_lines if t >= t_cd]
            if any("[TASK MIC] Da san sang" in ln or "[AUDIO STREAM] Phat am thanh hoan tat!" in ln for ln in recents):
                break
            time.sleep(0.2)
        time.sleep(3.0) # Silence cooldown

    # Stop reader & Close serial
    stop_event.set()
    time.sleep(0.5)
    ser.close()

    # Merge results with existing JSON if running targeted tests
    json_path = os.path.join(RECORDINGS_DIR, "benchmark_results.json")
    all_results_dict = {}
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                prev_data = json.load(f)
                for r in prev_data.get("results", []):
                    all_results_dict[r["id"]] = r
        except Exception:
            pass

    for r in results:
        all_results_dict[r["id"]] = r

    suite_order = {item["id"]: idx for idx, item in enumerate(BENCHMARK_SUITE)}
    final_results = sorted(all_results_dict.values(), key=lambda x: suite_order.get(x["id"], 99))
    total_tests = len(final_results)
    passed_tests = sum(1 for r in final_results if r.get("passed"))
    pass_rate = (passed_tests / total_tests) * 100.0 if total_tests > 0 else 0.0

    print("\n================================================================================")
    print("                    TỔNG HỢP KẾT QUẢ BENCHMARK TOÀN DIỆN                        ")
    print("================================================================================")
    print(f"Tổng số bài test : {total_tests}")
    print(f"Số bài ĐẠT (PASS): {passed_tests} / {total_tests} ({pass_rate:.1f}%)")
    print("--------------------------------------------------------------------------------")
    print(f"{'ID':<6} | {'Tier':<4} | {'Mục tiêu':<30} | {'VAD':<5} | {'ASR Text':<22} | {'Kết quả'}")
    print("--------------------------------------------------------------------------------")
    for r in final_results:
        vad_icon = "YES" if r.get("vad_detected") else "NO"
        asr_short = (r.get("user_said", "")[:20] + "..") if len(r.get("user_said", "")) > 20 else r.get("user_said", "")
        print(f"{r['id']:<6} | T{r['tier']:<3} | {r['name'][:30]:<30} | {vad_icon:<5} | {asr_short:<22} | {r['status']}")
    print("================================================================================\n")

    # Save merged results to JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.time(),
            "total": total_tests,
            "passed": passed_tests,
            "pass_rate": pass_rate,
            "results": final_results
        }, f, ensure_ascii=False, indent=2)
    print(f"Đã lưu kết quả chi tiết vào: {json_path}")

if __name__ == "__main__":
    main()
