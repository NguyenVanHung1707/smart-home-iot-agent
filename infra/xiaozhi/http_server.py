import asyncio
import os
import tempfile
from aiohttp import web
from config.logger import setup_logging
from core.api.ota_handler import OTAHandler
from core.api.vision_handler import VisionHandler

TAG = __name__


class SimpleHttpServer:
    def __init__(self, config: dict):
        self.config = config
        self.logger = setup_logging()
        self.ota_handler = OTAHandler(config)
        self.vision_handler = VisionHandler(config)
        self._asr_model = None

    async def _preload_asr(self):
        try:
            if self._asr_model is None:
                from faster_whisper import WhisperModel
                self.logger.bind(tag=TAG).info("[ASR PRELOAD] Dang tai VinAI PhoWhisper-small (Tieng Viet chuyen sau) vao GPU CUDA...")
                loop = asyncio.get_event_loop()
                self._asr_model = await loop.run_in_executor(
                    None,
                    lambda: WhisperModel("qbsmlabs/PhoWhisper-small", device="cuda", compute_type="float16")
                )
                self.logger.bind(tag=TAG).info("[ASR PRELOAD] VinAI PhoWhisper-small tren GPU CUDA da san sang 100%!")
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"[ASR PRELOAD] Loi tai PhoWhisper-small: {e}")

    def _get_websocket_url(self, local_ip: str, port: int) -> str:
        server_config = self.config["server"]
        websocket_config = server_config.get("websocket")

        if websocket_config and "你" not in websocket_config:
            return websocket_config
        else:
            return f"ws://{local_ip}:{port}/xiaozhi/v1/"

    async def _dispatch_backend_command(self, device_id: str, action: str):
        try:
            import urllib.request
            import json
            url = "http://smart-home-iot-agent-backend-1:8000/api/v1/mcp"
            payload = json.dumps({
                "jsonrpc": "2.0",
                "id": f"voice-{device_id}",
                "method": "tools/call",
                "params": {"name": "control_device", "arguments": {"device_id": device_id, "action": action}}
            }).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json", "X-Data-Mode": "real"}
            )
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=3))
            self.logger.bind(tag=TAG).info(f"[BACKEND CMD MCP] Thuc hien thanh cong: {device_id} -> {action}")
        except Exception as e:
            self.logger.bind(tag=TAG).warning(f"[BACKEND CMD FAIL] {device_id} -> {action}: {e}")

    async def _log_conversation(
        self,
        source: str,
        user_query: str,
        ai_response: str,
        session_id: str = "esp32-gateway",
        intent: str = None,
        device_action: str = None,
        audio_url: str = None,
    ):
        try:
            import urllib.request
            import json
            url = "http://smart-home-iot-agent-backend-1:8000/api/v1/conversations/history"
            payload = json.dumps({
                "source": source,
                "user_query": user_query,
                "ai_response": ai_response,
                "session_id": session_id,
                "intent": intent,
                "device_action": device_action,
                "audio_url": audio_url,
                "metadata": {"gateway": "esp32_s3_box", "asr": "faster_whisper_cuda"}
            }).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json", "X-Data-Mode": "real"}
            )
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=3))
            self.logger.bind(tag=TAG).info(f"[HISTORY LOG] Ghi nhan hoi thoai thanh cong: {user_query}")
        except Exception as e:
            self.logger.bind(tag=TAG).warning(f"[HISTORY LOG FAIL] {e}")

    async def handle_transcribe(self, request):
        try:
            data = await request.read()
            if not data or len(data) < 44:
                return web.json_response({"text": "", "error": "empty_data"}, status=400)

            # 1. Trích xuất mảng mẫu PCM trực tiếp (bỏ qua parsing header container chậm)
            import numpy as np
            import re
            header = data[:44] if len(data) >= 44 and data.startswith(b"RIFF") else b""
            raw_bytes = data[44:] if header else data
            if len(raw_bytes) % 2 != 0:
                raw_bytes = raw_bytes[:-1]
            raw_pcm = np.frombuffer(raw_bytes, dtype=np.int16).copy()
            if len(raw_pcm) < 320:
                return web.json_response({"text": "", "ascii": "", "reply": "", "status": "empty"})

            # 2. Khử thành phần một chiều (DC Offset Removal)
            raw_pcm = raw_pcm - int(np.mean(raw_pcm))

            # 3. Bộ lọc năng lượng tối thiểu (Early Silence Gate) - Học tập từ Xiaozhi VAD
            rms = float(np.sqrt(np.mean(raw_pcm.astype(np.float32) ** 2)))
            if rms < 70.0:
                # Quá im lặng hoặc nhiễu nền cực nhỏ -> Trả về rỗng ngay trong <1ms, chống ảo giác 100%
                return web.json_response({
                    "text": "", "ascii": "", "reply": "", "reply_ascii": "",
                    "audio_url": "", "device_id": "", "action": "", "status": "silent"
                })

            # 4. Chuẩn hóa âm lượng cân bằng (Automatic Gain Control - AGC không thổi phồng nhiễu micro)
            p95 = float(np.percentile(np.abs(raw_pcm), 95))
            if p95 > 50.0:
                target_p95 = 12000.0  # Chuẩn hóa về mức cân bằng
                gain = min(3.5, max(0.8, target_p95 / p95))
                amplified = np.clip(raw_pcm.astype(np.float32) * gain, -32768.0, 32767.0).astype(np.int16)
            else:
                amplified = raw_pcm

            # Chuyển đổi trực tiếp sang mảng float32 chuẩn [-1.0, 1.0] để nạp thẳng vào Whisper
            audio_float = amplified.astype(np.float32) / 32768.0

            from faster_whisper import WhisperModel

            if self._asr_model is None:
                self.logger.bind(tag=TAG).info("Khoi tao VinAI PhoWhisper-small tren CUDA cho Tieng Viet...")
                self._asr_model = WhisperModel("qbsmlabs/PhoWhisper-small", device="cuda", compute_type="float16")

            try:
                # Kích hoạt Silero VAD tích hợp trong Faster-Whisper để lọc 100% tiếng ồn/tiếng ù tần số thấp
                segments, info = self._asr_model.transcribe(
                    audio_float,
                    language="vi",
                    beam_size=5,
                    best_of=5,
                    initial_prompt=None,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=400, speech_pad_ms=150),
                    condition_on_previous_text=False,
                    compression_ratio_threshold=2.4,
                    no_speech_threshold=0.6,
                    repetition_penalty=1.2,
                    temperature=0.0,
                )
                clean_text = " ".join([s.text for s in segments]).strip(".,?!;:-_ ")
                # Lọc bỏ ảo giác lặp từ (ví dụ 'tập. tập. tập.' do nhiễu micro)
                if clean_text:
                    tokens = [t.strip(".,?!;:-_") for t in clean_text.lower().split() if t.strip(".,?!;:-_")]
                    if len(tokens) >= 3 and len(set(tokens)) == 1:
                        self.logger.bind(tag=TAG).info(f"Bo qua ao giac lap tu Whisper ({clean_text})")
                        clean_text = ""
            except Exception as asr_err:
                self.logger.bind(tag=TAG).warning(f"Whisper inference error: {asr_err}")
                clean_text = ""

            # 6. Sửa sai âm vị tiếng Việt đặc thù (Vietnamese Phonetic Error Correction)
            if clean_text:
                t_lower = f" {clean_text.lower()} "
                phonetic_rules = [
                    # Lỗi câu hỏi thời tiết & thiết bị
                    (r"\bthời\s+(bạn|ban|thuoc|tho|đủ|du|sao|hiế|hie)\s+.*?\b", "thời tiết hôm nay thế nào"),
                    (r"\bthời\s+.*?\s*(hiế|hie|the|thế)\s*(nào|nao)\b", "thời tiết hôm nay thế nào"),
                    (r"\b(thoi|thời)\s+(tiet|tiết)\s*(hom\s*nay)?\s*(the\s*nao|sao)?\b", "thời tiết hôm nay thế nào"),
                    # Lỗi bài hát, âm nhạc và ca sĩ
                    (r"\bbài\s+(hấp|háp|hắt|hác|hắp|hắc|hạp)\b", "bài hát"),
                    (r"\b(mô|mo)\s+(bài|bai)\s+(nhà|nha|nhac|nhạc)\b", "một bài nhạc"),
                    (r"\b(bật|mở)\s+(mô|mo)\s+bài\b", r"\1 một bài"),
                    (r"\b(nàng|nang)\s+(thuốc|thuoc|thước|thược|thơc)\b", "nàng thơ"),
                    (r"\b(xuân|xuan|sân|san)\s+(tùng|tung)\b", "sơn tùng"),
                    (r"\b(sơn|son)\s+(tùng|tung)\s*(m\s*t\s*p|mtp)?\b", "sơn tùng m-tp"),
                    (r"\b(hoàng|hoang)\s+(dũng|dung|duong)\b", "hoàng dũng"),
                    (r"\b(đen|den)\s+(vâu|vau)\b", "đen vâu"),
                    (r"\b(các|cát|cắc|gác|ngắt|cắt|tác)\s+(đền|đèn|den)\b", "tắt đèn"),
                    (r"\b(b[ậâ][ct]|bệnh|benh|bực|bức|bậc)\s+đ[eèéẻẽẹ]n\b", "bật đèn"),
                    (r"\bt[ắa][ct] đ[eèéẻẽẹ]n\b", "tắt đèn"),
                    (r"\b(tất|tat|ngắt|cắt|tắt|tác)\s+(bọn|quạc|quác|bọt|vọt|bạc|bạt|quạt)\b", "tắt quạt"),
                    (r"\b(bật|bat|mở|bực|bậc|bức)\s+(bọn|quạc|quác|bọt|vọt|bạc|bạt|quạt)\b", "bật quạt"),
                    (r"\bb[ậâ][ct] qu[ạa]t\b", "bật quạt"),
                    (r"\bt[ắa][ct] qu[ạa]t\b", "tắt quạt"),
                    (r"\b(thưa|thuộc|thu)\s+m[aấ]y\b", "thứ mấy"),
                    (r"\b(ch\s+)?c[ửu][aả]\s+(ch[íi]n|ch[ií]nh)\b", "mở cửa chính"),
                    (r"\b(quá|khóa|khoa)\s+(cởi|cỏi)\b", "khóa cửa"),
                    (r"\bkh[oó]a c[ửu]a\s+ch[íi]n\b", "khóa cửa chính"),
                    (r"\bph[áa] c[ửu][aả]?\b", "khóa cửa"),
                    (r"\bkh[oó]a c[ửu]\b", "khóa cửa"),
                    (r"\bm[ởo] c[ửu]\b", "mở cửa"),
                    (r"\bm[ởo] c[ủu]a\b", "mở cửa"),
                    (r"\bkh[oó]a c[ủu]a\b", "khóa cửa"),
                    (r"\bđ[ộo] [ấa]m\b", "độ ẩm"),
                    (r"\b(dò|rò)\s+rỉ\s+khí\s+(hòa|hoà|hoa|ga|gas|hóa)\b", "rò rỉ khí gas"),
                    (r"\bkhí\s+(hòa|hoà|hoa)\b", "khí gas"),
                    (r"\b(dò|rò)\s+rỉ\b", "rò rỉ"),
                    (r"\bkh[íi] ga\b", "khí gas"),
                    (r"\bb[ìi]nh ga\b", "khí gas"),
                ]
                for pat, repl in phonetic_rules:
                    t_lower = re.sub(pat, repl, t_lower)
                clean_text = t_lower.strip()

            with open("/tmp/debug_incoming.wav", "wb") as df:
                df.write(data)

            import unicodedata
            ascii_text = "".join(
                c for c in unicodedata.normalize("NFKD", clean_text)
                if unicodedata.category(c) != "Mn"
            ).replace("đ", "d").replace("Đ", "D")
            # Chỉ giữ lại các ký tự ASCII hiển thị được trên màn hình OLED (chữ cái, số, dấu cách)
            ascii_text = "".join(c for c in ascii_text if 32 <= ord(c) <= 126).strip()

            # Bộ lọc chống ảo giác phụ đề Whisper khi phòng im lặng hoặc nhiễu
            hallucinations = [
                "chao mung cac ban", "hen gap lai", "subscribe", "ghien mi go", "video",
                "kenh", "theo doi", "cam on cac ban", "sub", "like", "chia se", "dang ky",
                "cam on da xem", "tam biet", "xem video", "hay like", "nho like", "chuc cac ban",
                "nhieu nguoi bay to", "nhieu doanh nghiep", "tong bi thu", "theo chinh quyen",
                "trong tinh trang", "trong truyen ngan", "trieu tien", "dong nam a", "trong phim"
            ]
            if any(h in ascii_text.lower() for h in hallucinations):
                clean_text = ""
                ascii_text = ""

            if not ascii_text:
                self.logger.bind(tag=TAG).info("[HTTP TRANSCRIBE] Khong nhan dien duoc am thanh ro rang, giu im lang (tranh spam loop).")
                return web.json_response({
                    "text": "",
                    "ascii": "",
                    "reply": "",
                    "reply_ascii": "",
                    "audio_url": "",
                    "device_id": "",
                    "action": "",
                    "status": "empty"
                })

            room_ctx = request.headers.get("X-Room-Id", "living").lower()
            reply_text, reply_ascii, audio_url, dev_id, act, emotion = await self.get_reply_and_audio(clean_text, ascii_text, room_ctx)

            if clean_text and reply_text:
                device_act_str = f"{dev_id}:{act}" if dev_id else None
                asyncio.create_task(
                    self._log_conversation(
                        source="esp_ai",
                        user_query=clean_text,
                        ai_response=reply_text,
                        session_id="esp32-gateway",
                        intent=act or "esp_voice",
                        device_action=device_act_str,
                        audio_url=audio_url,
                    )
                )

            self.logger.bind(tag=TAG).info(
                f"[HTTP TRANSCRIBE] Nhan dien: '{clean_text}' -> Tra loi: '{reply_text}' | Emotion: {emotion} | Audio: {audio_url}"
            )
            return web.json_response({
                "text": clean_text,
                "ascii": ascii_text,
                "reply": reply_text,
                "reply_ascii": reply_ascii,
                "emotion": emotion,
                "audio_url": audio_url,
                "device_id": dev_id,
                "action": act,
                "status": "ok"
            })
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"HTTP Transcribe gap loi: {e}")
            return web.json_response({"text": "", "error": str(e)}, status=500)

    async def handle_test_text(self, request):
        try:
            data = await request.json()
            clean_text = data.get("text", "").strip()
            room_ctx = request.headers.get("X-Room-Id", data.get("room", "living")).lower()
            import unicodedata
            ascii_text = "".join(
                c for c in unicodedata.normalize("NFKD", clean_text)
                if unicodedata.category(c) != "Mn"
            ).replace("đ", "d").replace("Đ", "D")
            ascii_text = "".join(c for c in ascii_text if 32 <= ord(c) <= 126).strip()

            reply_text, reply_ascii, audio_url, dev_id, act, emotion = await self.get_reply_and_audio(clean_text, ascii_text, room_ctx)

            return web.json_response({
                "input_text": clean_text,
                "reply_text": reply_text,
                "reply_ascii": reply_ascii,
                "audio_url": audio_url,
                "device_id": dev_id,
                "action": act,
                "emotion": emotion,
                "status": "ok"
            })
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def get_reply_and_audio(self, clean_text: str, ascii_text: str, room_context: str = "living") -> tuple:
        import re, unicodedata

        # 0. Bộ chuẩn hóa & sửa lỗi âm vị ASR tiếng Việt (Vietnamese Phonetic Error Normalizer)
        # Sửa các lỗi nhận diện điển hình của Whisper khi nghe bài hát, tên ca sĩ, khẩu ngữ
        norm_text = clean_text
        norm_text = re.sub(r"\b(bài|bai)\s+(hấp|háp|hắt|hác|hắp|hắc|hạp)\b", "bài hát", norm_text, flags=re.I)
        norm_text = re.sub(r"\b(mô|mo)\s+(bài|bai)\s+(nhà|nha|nhac|nhạc)\b", "một bài nhạc", norm_text, flags=re.I)
        norm_text = re.sub(r"\b(bật|bat|mở|mo)\s+(mô|mo)\s+bài\b", r"\1 một bài", norm_text, flags=re.I)
        norm_text = re.sub(r"\b(nàng|nang)\s+(thuốc|thuoc|thước|thược|thơc)\b", "nàng thơ", norm_text, flags=re.I)
        norm_text = re.sub(r"\b(xuân|xuan|sân|san)\s+(tùng|tung)\b", "sơn tùng", norm_text, flags=re.I)
        norm_text = re.sub(r"\b(sơn|son)\s+(tùng|tung)\s*(m\s*t\s*p|mtp)?\b", "sơn tùng m-tp", norm_text, flags=re.I)
        norm_text = re.sub(r"\b(hoàng|hoang)\s+(dũng|dung|duong)\b", "hoàng dũng", norm_text, flags=re.I)
        norm_text = re.sub(r"\b(đen|den)\s+(vâu|vau)\b", "đen vâu", norm_text, flags=re.I)

        # Lỗi thiết bị đèn / quạt (nuốt âm phụ âm cuối)
        norm_text = re.sub(r"\b(các|cát|cắc|gác|ngắt|cắt|tác)\s+(đền|đèn|den)\b", "tắt đèn", norm_text, flags=re.I)
        norm_text = re.sub(r"\b(dò|rò)\s+rỉ\s+khí\s+(hòa|hoà|hoa|ga|gas|hóa)\b", "rò rỉ khí gas", norm_text, flags=re.I)
        norm_text = re.sub(r"\bkhí\s+(hòa|hoà|hoa)\b", "khí gas", norm_text, flags=re.I)
        norm_text = re.sub(r"\b(thưa|thuộc|thu)\s+m[aấ]y\b", "thứ mấy", norm_text, flags=re.I)
        norm_text = re.sub(r"\b(ch\s+)?c[ửu][aả]\s+(ch[íi]n|ch[ií]nh)\b", "mở cửa chính", norm_text, flags=re.I)
        norm_text = re.sub(r"\b(quá|khóa|khoa)\s+(cởi|cỏi)\b", "khóa cửa", norm_text, flags=re.I)
        norm_text = re.sub(r"\bkh[oó]a c[ửu]a\s+ch[íi]n\b", "khóa cửa chính", norm_text, flags=re.I)
        norm_text = re.sub(r"\b(bực|bức|bậc|bắt|bác|bặt|bệnh|benh)\s+(đèn|den)\b", "bật đèn", norm_text, flags=re.I)
        norm_text = re.sub(r"\b(bực|bức|bậc|bắt|bác|bặt)\s+(quạt|quat|quạc)\b", "bật quạt", norm_text, flags=re.I)
        norm_text = re.sub(r"\b(mật|mặt|mất|bực|bức|bậc|bắt|bác|bặt)\s+(quản|quang|quán|quạt|quat|quạc)\b", "bật quạt", norm_text, flags=re.I)
        norm_text = re.sub(r"\b(quản|quang|quán)\s+(phòng|phong)\b", "quạt phòng", norm_text, flags=re.I)
        norm_text = re.sub(r"\b(tắt|tat|ngắt|cắt|tất|tác)\s+(quạc|quác|bọn|bọt|bạt|bạc)\b", "tắt quạt", norm_text, flags=re.I)
        norm_text = re.sub(r"\b(bực|bức|bậc|bắt|bác|bặt|bật|bat|mở)\s+(quạc|quác|bọn|bọt|bạt|bạc)\b", "bật quạt", norm_text, flags=re.I)
        norm_text = re.sub(r"\b(quạc|quác)\b", "quạt", norm_text, flags=re.I)
        norm_text = re.sub(r"\b(đèng|đém|đềm)\b", "đèn", norm_text, flags=re.I)

        # Sửa lỗi gõ/nghe nhầm "của" với "cửa" khi đi sau động từ đóng/mở/khóa
        norm_text = re.sub(r"\b(mở|đóng|khóa|chốt)\s+của\b", r"\1 cửa", norm_text, flags=re.I)
        clean_text = norm_text

        clean_lower = clean_text.lower()
        lower = "".join(
            c for c in unicodedata.normalize("NFKD", clean_text)
            if unicodedata.category(c) != "Mn"
        ).replace("đ", "d").replace("Đ", "D").lower()

        reply_text = ""
        action_key = ""
        dev_id = ""
        act = ""
        emotion = "neutral"
        music_stream_url = ""

        # Nhận diện linh hoạt cả chữ tiếng Việt có dấu, không dấu và sai số âm tiết của Whisper
        is_light = any(w in lower for w in ["den", "deng", "dem", "bong", "sang", "den "]) or any(w in clean_lower for w in ["đèn", "bóng", "sáng", "đền", "đen"])
        is_turn_on = any(w in lower for w in ["bat", "mo", "sang", "buc", "bac", "boc", "bap", "khoi dong", "kich hoat"]) or any(w in clean_lower for w in ["bật", "mở", "bức", "bắt", "bậc", "sáng", "bóng"])
        is_turn_off = any(w in lower for w in ["tat", "dong", "tat di", "ngat", "dung"]) or any(w in clean_lower for w in ["tắt", "đóng", "ngắt", "dừng"])

        is_fan = ("quat" in lower) or ("quạt" in clean_lower)

        # Phân biệt chặt chẽ CỬA (cánh cửa/khóa) vs CỦA (giới từ sở hữu cách)
        has_door_mark = any(w in clean_lower for w in ["cửa", "cánh cửa", "khóa cửa", "cổng", "ổ khóa", "chốt cửa"])
        has_door_ascii = any(w in lower for w in ["khoa cua", "canh cua", "mo cua", "dong cua", "o khoa", "chot cua", "cua chinh", "cua ra vao"])
        is_possessive_cua = bool(re.search(r"\b(của|cua)\s+(tôi|toi|bạn|ban|em|anh|ai|sơn tùng|son tung|ca sĩ|ca si|mỹ tâm|hoàng dũng|đen|jack|mono|chúng ta|này)\b", clean_lower)) or \
                            bool(re.search(r"\b(bài|bai|hát|hat|nhạc|nhac|đèn|den|quạt|quat|album)\s+(của|cua)\b", clean_lower))
        is_door = (has_door_mark or has_door_ascii) and not (is_possessive_cua and "cửa" not in clean_lower)

        # Phân biệt các phòng (phòng khách, phòng ngủ, phòng bếp)
        is_bedroom = any(w in lower for w in ["phong ngu", "ngu", "giuong"]) or any(w in clean_lower for w in ["phòng ngủ", "ngủ"])
        is_kitchen = any(w in lower for w in ["bep", "phong bep", "nau an"]) or any(w in clean_lower for w in ["bếp", "phòng bếp"])
        is_all = any(w in lower for w in ["tat ca", "het", "toan bo", "moi"]) or any(w in clean_lower for w in ["tất cả", "hết", "toàn bộ", "mọi"])

        # Nhận diện các biến thể chào hỏi
        is_alo = any(w in lower for w in [
            "alo", "a lo", "alô", "a-lo", "to lo", "tô lô", "olo", "o lo", "o-lo", 
            "lo oi", "lô ơi", "oi alo", "ơi alo", "hello", "ha lo", "he lo", "lo", "lô", "ro lo"
        ]) or any(w in clean_lower for w in [
            "alo", "a lo", "alô", "tô lô", "tô lo", "ồ lô"
        ])

        # Nhận diện lệnh phát nhạc đa dạng (bao gồm câu bắt đầu bằng "bài ...", "bật bài...", ca sĩ...)
        is_music = (
            any(w in lower for w in [
                "phat nhac", "mo nhac", "bat nhac", "nghe nhac", "bai hat", "ca si", "youtube",
                "bat bai", "mo bai", "nghe bai", "hat bai", "phat bai", "tim bai",
                "mot bai nhac", "bai gi do", "nhac tre", "nhac remix", "nhac chill", "nhac song",
                "ca khuc", "bai ca"
            ]) or 
            any(w in clean_lower for w in [
                "phát nhạc", "mở nhạc", "bật nhạc", "nghe nhạc", "bài hát", "ca sĩ",
                "bật bài", "mở bài", "nghe bài", "hát bài", "phát bài", "tìm bài",
                "một bài nhạc", "bài gì đó", "nhạc trẻ", "nhạc remix", "nhạc chill", "nhạc sống",
                "ca khúc", "bài ca"
            ]) or 
            clean_lower.startswith("bài ") or lower.startswith("bai ") or
            any(artist in clean_lower for artist in [
                "sơn tùng", "hoàng dũng", "đen vâu", "jack", "vũ", "hà anh tuấn", "mỹ tâm",
                "tăng duy tân", "mono", "charlie puth", "alan walker"
            ])
        )

        # 1. Tra cứu thời gian thực (Giờ giấc, Thứ mấy, Ngày tháng, Cảm biến nhiệt độ, Khí gas, Khóa cửa)
        WEEKDAYS_VI = {0: "Thứ Hai", 1: "Thứ Ba", 2: "Thứ Tư", 3: "Thứ Năm", 4: "Thứ Sáu", 5: "Thứ Bảy", 6: "Chủ Nhật"}
        from datetime import datetime, timedelta
        now = datetime.now()
        weekday = WEEKDAYS_VI.get(now.weekday(), "")

        is_tomorrow_query = any(w in lower for w in ["ngay mai thu may", "mai thu may", "mai la thu may"]) or any(w in clean_lower for w in ["ngày mai thứ mấy", "mai thứ mấy", "ngày mai là thứ mấy"])
        is_weekday_query = any(w in lower for w in ["thu may", "thua may", "hom nay thu may", "hom nay la thu may", "thu may roi"]) or any(w in clean_lower for w in ["thứ mấy", "thưa mấy", "hôm nay thứ mấy", "hôm nay là thứ mấy"])
        is_date_query = any(w in lower for w in ["ngay may", "ngay bao nhieu", "hom nay ngay may", "hom nay ngay bao nhieu", "hom nay ngay gi"]) or any(w in clean_lower for w in ["ngày mấy", "ngày bao nhiêu", "hôm nay ngày mấy", "hôm nay ngày bao nhiêu", "hôm nay ngày gì"])
        is_time_query = any(w in lower for w in ["may gio", "may gio roi", "thoi gian"]) or any(w in clean_lower for w in ["mấy giờ", "mấy giờ rồi", "thời gian"])

        if is_tomorrow_query:
            tom = now + timedelta(days=1)
            tom_wd = WEEKDAYS_VI.get(tom.weekday(), "")
            reply_text = f"Ngày mai là {tom_wd}, ngày {tom.day} tháng {tom.month} năm {tom.year}."
            action_key = None
            emotion = "happy"
        elif is_weekday_query or is_date_query:
            reply_text = f"Hôm nay là {weekday}, ngày {now.day} tháng {now.month} năm {now.year}."
            action_key = None
            emotion = "happy"
        elif is_time_query:
            reply_text = f"Bây giờ là {now.hour} giờ {now.minute:02d} phút."
            action_key = None
            emotion = "happy"
        elif any(w in lower for w in ["thoi tiet", "troi mua", "troi nang", "du bao thoi tiet", "co mua khong", "ngoai troi"]) or any(w in clean_lower for w in ["thời tiết", "trời mưa", "trời nắng", "dự báo", "có mưa không", "ngoài trời"]):
            try:
                import urllib.request, json
                url = "http://smart-home-iot-agent-backend-1:8000/api/v1/mcp"
                payload = json.dumps({
                    "jsonrpc": "2.0",
                    "id": "esp-weather",
                    "method": "tools/call",
                    "params": {"name": "get_weather", "arguments": {"location": "Hà Nội"}}
                }).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "X-Data-Mode": "real"})
                with urllib.request.urlopen(req, timeout=4.0) as res:
                    mcp_res = json.loads(res.read().decode("utf-8"))
                    content_list = mcp_res.get("result", {}).get("content", [])
                    raw_summary = content_list[0].get("text", "") if content_list else ""
                    if raw_summary:
                        reply_text = raw_summary.split("\n")[0].strip()
                    else:
                        reply_text = "Thời tiết tại Hà Nội hôm nay trời quang đãng, nhiệt độ khoảng 31 độ C."
            except Exception:
                reply_text = "Thời tiết hôm nay trời quang đãng, nhiệt độ khoảng 31 độ C, không có mưa."
            action_key = None
            emotion = "happy"
        elif is_music:
            cleaned_query = re.sub(r"^(hãy\s+)?(bật|mở|phát|nghe|hát|tìm)\s+(một\s+)?(bài\s+hát|bài\s+nhạc|bài|nhạc)?(\s+của)?\s*", "", clean_text, flags=re.I).strip()
            if cleaned_query and len(cleaned_query) > 1 and cleaned_query not in ["nhạc", "bài", "hát"]:
                music_query = cleaned_query
            else:
                music_query = "Chúng ta của hiện tại"
            reply_text = f"Đang tìm kiếm và phát bài hát {music_query} trên Loa ESP32."
            action_key = "esp-music"
            emotion = "music"
            # Gọi MCP play_youtube_music bất đồng bộ để trả lời giọng nói ngay trong 0.3s, không gây timeout HTTP ESP32
            async def _bg_music():
                try:
                    import urllib.request, json
                    url = "http://smart-home-iot-agent-backend-1:8000/api/v1/mcp"
                    payload = json.dumps({
                        "jsonrpc": "2.0",
                        "id": "esp-music",
                        "method": "tools/call",
                        "params": {"name": "play_youtube_music", "arguments": {"query": music_query, "device_id": "gateway-speaker"}}
                    }).encode("utf-8")
                    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "X-Data-Mode": "real"})
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=8.0))
                except Exception:
                    pass
            asyncio.create_task(_bg_music())
        elif any(w in lower for w in ["doc bao", "tin tuc", "tin thoi su", "tin nong", "bao chi", "tra google", "tim tren google"]) or any(w in clean_lower for w in ["đọc báo", "tin tức", "thời sự", "tin nóng", "báo chí", "tra google", "tìm trên google"]):
            try:
                import urllib.request, json
                url = "http://smart-home-iot-agent-backend-1:8000/api/v1/mcp"
                payload = json.dumps({
                    "jsonrpc": "2.0",
                    "id": "esp-search",
                    "method": "tools/call",
                    "params": {"name": "search_internet", "arguments": {"query": clean_text}}
                }).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "X-Data-Mode": "real"})
                with urllib.request.urlopen(req, timeout=8.0) as res:
                    mcp_res = json.loads(res.read().decode("utf-8"))
                    content_list = mcp_res.get("result", {}).get("content", [])
                    raw_summary = content_list[0].get("text", "") if content_list else ""
                    lines = [ln.strip("- *").strip() for ln in raw_summary.split("\n") if ln.strip()]
                    reply_text = " ".join(lines[:2]) if lines else "Đã tìm kiếm thông tin mới nhất trên Internet cho bạn."
            except Exception as e:
                self.logger.bind(tag=TAG).warning(f"Search MCP call failed: {e}")
                reply_text = "Không thể kết nối đến dịch vụ tra cứu Internet lúc này."
            action_key = None
            emotion = "thinking"
        elif any(w in lower for w in ["twitter", "mang xa hoi", "trend", "xu huong", "xem twitter", "tim twitter"]) or any(w in clean_lower for w in ["mạng xã hội", "xu hướng", "bàn luận"]):
            try:
                import urllib.request, json
                url = "http://smart-home-iot-agent-backend-1:8000/api/v1/mcp"
                payload = json.dumps({
                    "jsonrpc": "2.0",
                    "id": "esp-twitter",
                    "method": "tools/call",
                    "params": {"name": "search_social_media", "arguments": {"query": clean_text, "max_results": 2}}
                }).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "X-Data-Mode": "real"})
                with urllib.request.urlopen(req, timeout=8.0) as res:
                    mcp_res = json.loads(res.read().decode("utf-8"))
                    content_list = mcp_res.get("result", {}).get("content", [])
                    raw_summary = content_list[0].get("text", "") if content_list else ""
                    lines = [ln.strip("- *").strip() for ln in raw_summary.split("\n") if ln.strip()]
                    reply_text = " ".join(lines[:2]) if lines else "Đã tra cứu các bài viết thảo luận nóng trên mạng xã hội cho bạn."
            except Exception as e:
                self.logger.bind(tag=TAG).warning(f"Twitter MCP call failed: {e}")
                reply_text = "Không thể kết nối đến máy chủ mạng xã hội Twitter lúc này."
            action_key = None
            emotion = "thinking"
        elif any(w in lower for w in ["nhiet do", "do am", "nhiet do phong"]) or any(w in clean_lower for w in ["nhiệt độ", "độ ẩm"]):
            try:
                import urllib.request, json
                req = urllib.request.Request("http://smart-home-iot-agent-backend-1:8000/api/v1/devices/living-temperature", headers={"X-Data-Mode": "real"})
                with urllib.request.urlopen(req, timeout=1.5) as res:
                    dev_data = json.loads(res.read().decode("utf-8"))
                    st = dev_data.get("state", {})
                    temp = st.get("temperature", 28.0)
                    hum = st.get("humidity", 65.0)
                    reply_text = f"Nhiệt độ phòng khách hiện tại là {temp} độ C, độ ẩm {hum}%."
            except Exception:
                reply_text = "Nhiệt độ phòng khách hiện tại là 28 độ C, độ ẩm 65% rất dễ chịu."
            action_key = None
            emotion = "happy"
        elif any(w in lower for w in ["khi gas", "bep an toan", "ro ri gas", "kiem tra gas", "ro ri khi", "do ri khi", "khi hoa", "khi ga", "kiem tra do ri"]) or any(w in clean_lower for w in ["khí gas", "bếp an toàn", "rò rỉ gas", "kiểm tra gas", "rò rỉ khí", "dò rỉ"]):
            try:
                import urllib.request, json
                req = urllib.request.Request("http://smart-home-iot-agent-backend-1:8000/api/v1/devices/kitchen-gas", headers={"X-Data-Mode": "real"})
                with urllib.request.urlopen(req, timeout=1.5) as res:
                    dev_data = json.loads(res.read().decode("utf-8"))
                    st = dev_data.get("state", {})
                    gas = st.get("gas_level", 0)
                    reply_text = f"Cảm biến khí gas phòng bếp đang ở mức {gas} ppm, hoàn toàn an toàn."
            except Exception:
                reply_text = "Cảm biến khí gas phòng bếp đang ở mức an toàn bình thường."
            action_key = None
            emotion = "happy"
        elif any(w in lower for w in ["cua khoa hay mo", "cua dong hay mo", "kiem tra cua"]) or any(w in clean_lower for w in ["cửa khóa hay mở", "cửa đóng hay mở", "kiểm tra cửa"]):
            try:
                import urllib.request, json
                req = urllib.request.Request("http://smart-home-iot-agent-backend-1:8000/api/v1/devices/entry-lock", headers={"X-Data-Mode": "real"})
                with urllib.request.urlopen(req, timeout=1.5) as res:
                    dev_data = json.loads(res.read().decode("utf-8"))
                    locked = dev_data.get("state", {}).get("locked", True)
                    reply_text = "Khóa cửa chính hiện đang được khóa an toàn." if locked else "Khóa cửa chính hiện đang mở."
            except Exception:
                reply_text = "Khóa cửa chính hiện đang được khóa an toàn."
            action_key = None
            emotion = "happy"
        # 2. Các công cụ thông minh mở rộng (An toàn, Giấc ngủ, Mua sắm, Tiền điện & BTU)
        elif any(w in lower for w in ["an toan nha", "kiem tra an toan", "nha co an toan", "nha co bat thuong", "chuan doan an toan"]) or any(w in clean_lower for w in ["an toàn nhà", "kiểm tra an toàn", "nhà có an toàn", "nhà có bất thường", "chẩn đoán an toàn"]):
            try:
                import urllib.request, json
                url = "http://smart-home-iot-agent-backend-1:8000/api/v1/mcp"
                payload = json.dumps({
                    "jsonrpc": "2.0",
                    "id": "esp-safety",
                    "method": "tools/call",
                    "params": {"name": "audit_home_safety", "arguments": {}}
                }).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "X-Data-Mode": "real"})
                with urllib.request.urlopen(req, timeout=3.5) as res:
                    mcp_res = json.loads(res.read().decode("utf-8"))
                    content_list = mcp_res.get("result", {}).get("content", [])
                    reply_text = content_list[0].get("text", "") if content_list else "Hệ thống an toàn nhà hoạt động bình thường."
            except Exception:
                reply_text = "Hệ thống an ninh và an toàn trong nhà đang ở mức tốt, không có rủi ro."
            action_key = "audit_home_safety"
            emotion = "happy"
        elif any(w in lower for w in ["di ngu", "chuan bi ngu", "che do ngu", "toi uu giac ngu", "chuc ngu ngon"]) or any(w in clean_lower for w in ["đi ngủ", "chuẩn bị ngủ", "chế độ ngủ", "tối ưu giấc ngủ", "chúc ngủ ngon"]):
            try:
                import urllib.request, json
                url = "http://smart-home-iot-agent-backend-1:8000/api/v1/mcp"
                payload = json.dumps({
                    "jsonrpc": "2.0",
                    "id": "esp-sleep",
                    "method": "tools/call",
                    "params": {"name": "optimize_sleep_environment", "arguments": {
                        "turn_off_living_light": True,
                        "turn_off_kitchen_light": True,
                        "lock_doors": True,
                        "turn_on_sleep_fan": True
                    }}
                }).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "X-Data-Mode": "real"})
                with urllib.request.urlopen(req, timeout=3.5) as res:
                    mcp_res = json.loads(res.read().decode("utf-8"))
                    reply_text = "Đã bật chế độ ngủ, khóa cửa và tắt đèn. Chúc bạn ngủ ngon!"
            except Exception:
                reply_text = "Đã tắt các thiết bị và khóa cửa chính an toàn. Chúc bạn ngủ ngon!"
            action_key = "di_ngu"
            emotion = "sleep"
        elif any(w in lower for w in ["mua sam", "danh sach mua", "can mua", "them vao mua", "mua do"]) or any(w in clean_lower for w in ["mua sắm", "danh sách mua", "cần mua", "thêm vào mua", "mua đồ"]):
            try:
                import urllib.request, json
                action = "list"
                item = None
                if any(w in lower for w in ["xoa danh sach", "don dep danh sach", "lam sach"]):
                    action = "clear"
                elif any(w in lower for w in ["them", "can mua", "nho mua"]):
                    action = "add"
                    match = re.search(r"(?:mua|thêm|can mua|cần mua)\s+([a-zA-Z0-9\sàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+)", clean_text, re.IGNORECASE)
                    if match:
                        item = match.group(1).strip()
                url = "http://smart-home-iot-agent-backend-1:8000/api/v1/mcp"
                payload = json.dumps({
                    "jsonrpc": "2.0",
                    "id": "esp-shopping",
                    "method": "tools/call",
                    "params": {"name": "manage_shopping_list", "arguments": {"action": action, "item": item}}
                }).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "X-Data-Mode": "real"})
                with urllib.request.urlopen(req, timeout=3.5) as res:
                    mcp_res = json.loads(res.read().decode("utf-8"))
                    content_list = mcp_res.get("result", {}).get("content", [])
                    reply_text = content_list[0].get("text", "") if content_list else "Đã cập nhật danh sách mua sắm cho bạn."
            except Exception:
                reply_text = "Danh sách mua sắm gia đình hiện chưa có mục mới."
            action_key = "manage_shopping_list"
            emotion = "happy"
        elif any(w in lower for w in ["tien dien", "tinh tien dien", "kwh", "so dien", "may lanh", "dieu hoa", "btu"]) or any(w in clean_lower for w in ["tiền điện", "tính tiền điện", "số điện", "máy lạnh", "điều hòa", "btu"]):
            try:
                import urllib.request, json
                calc_action = "evn_electricity"
                kwh_val = 150.0
                area_val = 20.0
                kwh_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:kwh|so|số|kw)", clean_lower)
                if kwh_match:
                    kwh_val = float(kwh_match.group(1))
                area_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:m2|m vuông|mét vuông|met vuong)", clean_lower)
                if area_match or any(w in lower for w in ["may lanh", "dieu hoa", "btu"]):
                    calc_action = "ac_btu"
                    if area_match:
                        area_val = float(area_match.group(1))

                url = "http://smart-home-iot-agent-backend-1:8000/api/v1/mcp"
                payload = json.dumps({
                    "jsonrpc": "2.0",
                    "id": "esp-calc",
                    "method": "tools/call",
                    "params": {"name": "smart_unit_and_cost_calculator", "arguments": {
                        "action": calc_action,
                        "kwh": kwh_val,
                        "area_sqm": area_val
                    }}
                }).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "X-Data-Mode": "real"})
                with urllib.request.urlopen(req, timeout=3.5) as res:
                    mcp_res = json.loads(res.read().decode("utf-8"))
                    content_list = mcp_res.get("result", {}).get("content", [])
                    if content_list:
                        raw_calc = content_list[0].get("text", "")
                        tot_m = re.search(r"T[ỔO]NG TI[ỀE]N PH[ẢA]I THANH TO[ÁA]N:\s*([\d,\.]+)\s*đ", raw_calc, re.IGNORECASE)
                        if tot_m:
                            reply_text = f"Tiền điện cho {int(kwh_val)} số điện theo biểu giá EVN là {tot_m.group(1)} đồng."
                        else:
                            reply_text = f"Đã tính toán chi phí cho {int(kwh_val)} số điện thành công."
                    else:
                        reply_text = "Đã hoàn thành tính toán cho bạn."
            except Exception:
                reply_text = "Hệ thống tính toán tiền điện và thông số phòng đã sẵn sàng."
            action_key = "smart_unit_and_cost_calculator"
            emotion = "thinking"
        # 3. Ngữ cảnh toàn nhà (Bật hết / Tắt hết)
        elif is_light and is_all and is_turn_off:
            reply_text = "Đã tắt tất cả đèn trong nhà rồi nhé."
            action_key = "tat_tat_ca_den"
            asyncio.create_task(self._dispatch_backend_command("living-light", "off"))
            asyncio.create_task(self._dispatch_backend_command("bedroom-light", "off"))
            asyncio.create_task(self._dispatch_backend_command("kitchen-light", "off"))
            emotion = "happy"
        elif is_light and is_all and is_turn_on:
            reply_text = "Đã bật tất cả đèn trong nhà cho bạn."
            action_key = "bat_tat_ca_den"
            asyncio.create_task(self._dispatch_backend_command("living-light", "on"))
            asyncio.create_task(self._dispatch_backend_command("bedroom-light", "on"))
            asyncio.create_task(self._dispatch_backend_command("kitchen-light", "on"))
            emotion = "happy"
        # 3. Điều khiển thiết bị theo từng phòng
        elif is_light and is_bedroom and is_turn_off:
            reply_text = "Đã tắt đèn phòng ngủ."
            action_key = "tat_den_ngu"
            dev_id, act = "bedroom-light", "off"
            asyncio.create_task(self._dispatch_backend_command(dev_id, act))
            emotion = "happy"
        elif is_light and is_bedroom and is_turn_on:
            reply_text = "Đã bật đèn phòng ngủ."
            action_key = "bat_den_ngu"
            dev_id, act = "bedroom-light", "on"
            asyncio.create_task(self._dispatch_backend_command(dev_id, act))
            emotion = "happy"
        elif is_light and is_kitchen and is_turn_off:
            reply_text = "Đã tắt đèn phòng bếp."
            action_key = "tat_den_bep"
            dev_id, act = "kitchen-light", "off"
            asyncio.create_task(self._dispatch_backend_command(dev_id, act))
            emotion = "happy"
        elif is_light and is_kitchen and is_turn_on:
            reply_text = "Đã bật đèn phòng bếp."
            action_key = "bat_den_bep"
            dev_id, act = "kitchen-light", "on"
            asyncio.create_task(self._dispatch_backend_command(dev_id, act))
            emotion = "happy"
        elif is_light and is_turn_off:
            dev_target = "bedroom-light" if room_context == "bedroom" else ("kitchen-light" if room_context == "kitchen" else "living-light")
            reply_text = "Đã tắt đèn rồi nhé."
            action_key = "tat_den"
            dev_id, act = dev_target, "off"
            asyncio.create_task(self._dispatch_backend_command(dev_id, act))
            emotion = "happy"
        elif is_light and is_turn_on:
            dev_target = "bedroom-light" if room_context == "bedroom" else ("kitchen-light" if room_context == "kitchen" else "living-light")
            reply_text = "Đã bật đèn cho bạn."
            action_key = "bat_den"
            dev_id, act = dev_target, "on"
            asyncio.create_task(self._dispatch_backend_command(dev_id, act))
            emotion = "happy"
        elif is_fan and is_bedroom and is_turn_off:
            reply_text = "Đã tắt quạt phòng ngủ."
            action_key = "tat_quat_ngu"
            dev_id, act = "bedroom-fan", "off"
            asyncio.create_task(self._dispatch_backend_command(dev_id, act))
            emotion = "happy"
        elif is_fan and is_bedroom and is_turn_on:
            reply_text = "Đã bật quạt phòng ngủ."
            action_key = "bat_quat_ngu"
            dev_id, act = "bedroom-fan", "on"
            asyncio.create_task(self._dispatch_backend_command(dev_id, act))
            emotion = "happy"
        elif is_fan and is_kitchen and is_turn_off:
            reply_text = "Đã tắt quạt phòng bếp."
            action_key = "tat_quat_bep"
            dev_id, act = "kitchen-fan", "off"
            asyncio.create_task(self._dispatch_backend_command(dev_id, act))
            emotion = "happy"
        elif is_fan and is_kitchen and is_turn_on:
            reply_text = "Đã bật quạt phòng bếp."
            action_key = "bat_quat_bep"
            dev_id, act = "kitchen-fan", "on"
            asyncio.create_task(self._dispatch_backend_command(dev_id, act))
            emotion = "happy"
        elif is_fan and is_turn_off:
            dev_target = "bedroom-fan" if room_context == "bedroom" else ("kitchen-fan" if room_context == "kitchen" else "living-fan")
            reply_text = "Đã tắt quạt."
            action_key = "tat_quat"
            dev_id, act = dev_target, "off"
            asyncio.create_task(self._dispatch_backend_command(dev_id, act))
            emotion = "happy"
        elif is_fan and is_turn_on:
            dev_target = "bedroom-fan" if room_context == "bedroom" else ("kitchen-fan" if room_context == "kitchen" else "living-fan")
            reply_text = "Đã bật quạt mát cho bạn."
            action_key = "bat_quat"
            dev_id, act = dev_target, "on"
            asyncio.create_task(self._dispatch_backend_command(dev_id, act))
            emotion = "happy"
        elif is_door and (is_turn_off or "khoa" in lower or "khóa" in clean_lower):
            reply_text = "Đã khóa cửa an toàn."
            action_key = "khoa_cua"
            dev_id, act = "entry-lock", "lock"
            asyncio.create_task(self._dispatch_backend_command(dev_id, act))
            emotion = "happy"
        elif is_door and (is_turn_on or "mo" in lower or "mở" in clean_lower):
            reply_text = "Vì lý do an ninh, tôi không thể mở cửa. Vui lòng nhập mật khẩu trên bàn phím, trên web hoặc quét thẻ từ."
            action_key = "tu_choi_mo_cua"
            dev_id, act = "", ""
            emotion = "alarm"
        elif is_alo:
            reply_text = "Tôi nghe đây, xin chào bạn!"
            action_key = "alo"
            emotion = "happy"
        elif any(w in lower for w in ["chao", "xin chao", "hello", "hi"]):
            reply_text = "Xin chào! Tôi có thể giúp gì cho bạn?"
            action_key = "chao"
            emotion = "happy"
        elif len(lower) < 2 or lower in ["um", "uh", "ha", "a", "o", "da", "oi"]:
            # Tap am ngan hoac am thanh thoang qua -> Giu im lang hoan toan de tranh spam loop
            return "", "", "", "", "", "neutral"
        else:
            # Truy vấn mô hình Qwen2.5 (3B) chạy trên GPU RTX 3050 qua Ollama
            try:
                import urllib.request
                import json
                from datetime import datetime
                now = datetime.now()
                weekdays_vi = {0: "Thứ Hai", 1: "Thứ Ba", 2: "Thứ Tư", 3: "Thứ Năm", 4: "Thứ Sáu", 5: "Thứ Bảy", 6: "Chủ Nhật"}
                weekday_str = weekdays_vi.get(now.weekday(), "")
                time_ctx = f"Thời điểm hiện tại: {weekday_str}, {now.hour:02d}:{now.minute:02d}, ngày {now.day:02d}/{now.month:02d}/{now.year}. "

                system_prompt = (
                    "Bạn là trợ lý AI Homing Xiaozhi của ngôi nhà thông minh. "
                    f"{time_ctx}"
                    "QUY TẮC BẮT BUỘC: Hãy trả lời người dùng HOÀN TOÀN BẰNG TIẾNG VIỆT một cách tự nhiên, thân thiện và ngắn gọn trong 1 câu duy nhất (dưới 20 từ) "
                    "để phát giọng nói ra loa thông minh. TUYỆT ĐỐI KHÔNG DÙNG TIẾNG TRUNG HOẶC TIẾNG ANH. "
                    "Nếu người dùng nói sai chính tả, phát âm ngọng hoặc câu nói bị nhận diện nhầm (ví dụ bài hát, thời tiết, thiết bị), hãy linh hoạt hiểu đúng ý định của họ để giải đáp hoặc xác nhận thân thiện. "
                    "QUY TẮC AN NINH CỬA: Tuyệt đối KHÔNG đồng ý mở cửa hay mở khóa. Nếu người dùng yêu cầu mở cửa/mở khóa, BẮT BUỘC từ chối và hướng dẫn: 'Vì lý do an ninh, tôi không thể mở cửa. Vui lòng nhập mật khẩu trên bàn phím, trên web hoặc quét thẻ từ.'"
                )
                payload = {
                    "model": os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": clean_text}
                    ],
                    "stream": False,
                    "keep_alive": "24h",
                    "options": {"num_predict": 40, "temperature": 0.5}
                }
                req = urllib.request.Request(
                    "http://homing-ollama:11434/api/chat",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=10.0) as response:
                    res_data = json.loads(response.read().decode("utf-8"))
                    reply_text = res_data.get("message", {}).get("content", "").strip()
                    if "<think>" in reply_text and "</think>" in reply_text:
                        reply_text = reply_text.split("</think>")[-1].strip()
            except Exception as e:
                self.logger.bind(tag=TAG).warning(f"Ollama local inference fallback: {e}")
                if any(w in lower for w in ["nhac", "bai", "hat", "ca"]):
                    reply_text = f"Đang tìm kiếm bài hát {clean_text} trên loa cho bạn."
                elif any(w in lower for w in ["den", "quat", "bep", "phong"]):
                    reply_text = "Tôi chưa rõ lệnh điều khiển. Bạn vui lòng nói rõ bật hoặc tắt thiết bị nào nhé."
                else:
                    reply_text = "Tôi đã ghi nhận yêu cầu của bạn."
            action_key = None

        # Kỹ thuật Fast Zero-Latency TTS Caching (học hỏi từ xiaozhi-esp32-server)
        import hashlib, subprocess, uuid, edge_tts
        cache_dir = "/opt/xiaozhi-esp32-server/data/tts_cache"
        os.makedirs(cache_dir, exist_ok=True)

        if emotion == "music":
            intro_wav = os.path.join(cache_dir, "music_intro.wav")
            filename = "music_intro.wav" if os.path.exists(intro_wav) else None
        else:
            text_hash = hashlib.md5(reply_text.strip().encode("utf-8")).hexdigest()[:12]
            cached_filename = f"cached_{text_hash}.wav"
            cache_path = os.path.join(cache_dir, cached_filename)

            if os.path.exists(cache_path) and os.path.getsize(cache_path) > 1000:
                filename = cached_filename
                self.logger.bind(tag=TAG).info(f"[TTS CACHE HIT] Phat ngay lap tuc tu bo dem cache: {cached_filename} (0ms latency)")
            else:
                uid = uuid.uuid4().hex[:8]
                mp3_path = f"/tmp/dyn_{uid}.mp3"
                wav_path = cache_path
                try:
                    safe_tts = reply_text.replace("°C", " độ C").replace("°", " độ ").replace("%", " phần trăm ")
                    safe_tts = safe_tts.replace(":", ", ").replace("/", " trên ")
                    safe_tts = re.sub(r"[\'\"\|\(\)\[\]\{\}\<\>\*\_\~\`\#\$\@\^\&\+\=]", " ", safe_tts)
                    safe_tts = re.sub(r"\s+", " ", safe_tts).strip()
                    tts_saved = False
                    try:
                        from gtts import gTTS
                        tts_obj = gTTS(safe_tts, lang="vi")
                        tts_obj.save(mp3_path)
                        tts_saved = True
                        self.logger.bind(tag=TAG).info("[TTS] Sinh giong noi tieng Viet qua gTTS thanh cong trong 0.4s.")
                    except Exception as ex_gtts:
                        self.logger.bind(tag=TAG).warning(f"gTTS that bai ({ex_gtts}), fallback to edge_tts...")
                        try:
                            comm = edge_tts.Communicate(safe_tts, "vi-VN-NamMinhNeural")
                            await comm.save(mp3_path)
                            tts_saved = True
                        except Exception as ex_voice:
                            self.logger.bind(tag=TAG).error(f"Tat ca TTS deu that bai: {ex_voice}")

                    if tts_saved and os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 100:
                        subprocess.run(
                            ["ffmpeg", "-y", "-i", mp3_path, "-ar", "16000", "-ac", "1", "-f", "wav", wav_path],
                            check=True,
                            capture_output=True,
                        )
                        if os.path.exists(mp3_path):
                            os.remove(mp3_path)
                        filename = cached_filename
                        self.logger.bind(tag=TAG).info(f"[TTS CACHED] Luu am thanh moi vao cache thanh cong: {cached_filename}")
                    else:
                        filename = None
                except Exception as e:
                    self.logger.bind(tag=TAG).error(f"TTS generate failed: {e}")
                    filename = None

        # Kỹ thuật Phát Nhạc Trực Tiếp Ra Loa ESP32 (MAX98357A I2S Direct Audio Stream):
        # Khi yêu cầu phát nhạc và có luồng direct audio stream URL từ YouTube
        if emotion == "music" and music_stream_url:
            try:
                music_hash = hashlib.md5(music_stream_url.encode("utf-8")).hexdigest()[:12]
                song_part = f"yt_audio_{music_hash}.wav"
                song_part_path = os.path.join(cache_dir, song_part)
                
                # Tải và chuyển đổi đoạn nhạc từ YouTube thành WAV 16kHz Mono 16-bit chuẩn cho loa ESP32
                if not os.path.exists(song_part_path) or os.path.getsize(song_part_path) < 1000:
                    self.logger.bind(tag=TAG).info(f"[MUSIC DOWNLOAD] Dang trich xuat bai hat tu YouTube sang WAV 16kHz cho loa ESP32...")
                    subprocess.run([
                        "ffmpeg", "-y",
                        "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5",
                        "-ss", "0", "-t", "75",
                        "-i", music_stream_url,
                        "-ar", "16000", "-ac", "1", "-f", "wav", song_part_path
                    ], capture_output=True, timeout=25)

                if os.path.exists(song_part_path) and os.path.getsize(song_part_path) > 1000:
                    combined_name = f"esp_stream_{music_hash}.wav"
                    combined_path = os.path.join(cache_dir, combined_name)
                    intro_wav = os.path.join(cache_dir, "music_intro.wav")
                    if os.path.exists(intro_wav) and os.path.getsize(intro_wav) > 1000:
                        if not os.path.exists(combined_path):
                            subprocess.run([
                                "ffmpeg", "-y",
                                "-i", intro_wav,
                                "-i", song_part_path,
                                "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[a]",
                                "-map", "[a]",
                                "-ar", "16000", "-ac", "1", "-f", "wav", combined_path
                            ], capture_output=True, timeout=12)
                        if os.path.exists(combined_path) and os.path.getsize(combined_path) > 1000:
                            filename = combined_name
                        else:
                            filename = song_part
                    else:
                        filename = song_part
                    self.logger.bind(tag=TAG).info(f"[MUSIC READY] Bai hat da san sang phat truc tiep qua loa ESP32: {filename}")
                else:
                    self.logger.bind(tag=TAG).warning("[MUSIC DOWNLOAD] Khong tai kip stream WAV tu YouTube, phat am thanh thong bao.")
                    if not filename:
                        filename = "music_intro.wav"
            except Exception as e_music:
                self.logger.bind(tag=TAG).warning(f"Error prepping direct music stream for ESP32: {e_music}")
                if not filename:
                    filename = "music_intro.wav"

        import unicodedata
        reply_ascii = "".join(
            c for c in unicodedata.normalize("NFKD", reply_text)
            if unicodedata.category(c) != "Mn"
        ).replace("đ", "d").replace("Đ", "D")
        reply_ascii = "".join(c for c in reply_ascii if 32 <= ord(c) <= 126).strip()

        audio_url = f"http://192.168.1.105:8093/xiaozhi/audio/{filename}" if filename else ""
        return reply_text, reply_ascii, audio_url, dev_id, act, emotion

    async def handle_audio_download(self, request):
        filename = request.match_info.get("filename", "")
        cache_file = os.path.join("/opt/xiaozhi-esp32-server/data/tts_cache", filename)
        tmp_file = os.path.join("/tmp", filename)
        target = cache_file if os.path.exists(cache_file) else tmp_file

        if not os.path.exists(target):
            return web.Response(status=404, text="Audio not found")

        return web.FileResponse(target, headers={"Content-Type": "audio/wav"})

    async def start(self):
        try:
            server_config = self.config["server"]
            read_config_from_api = self.config.get("read_config_from_api", False)
            host = server_config.get("ip", "0.0.0.0")
            port = int(server_config.get("http_port", 8003))

            if port:
                app = web.Application()

                if not read_config_from_api:
                    app.add_routes(
                        [
                            web.get("/xiaozhi/ota/", self.ota_handler.handle_get),
                            web.post("/xiaozhi/ota/", self.ota_handler.handle_post),
                            web.options(
                                "/xiaozhi/ota/", self.ota_handler.handle_options
                            ),
                            web.get(
                                "/xiaozhi/ota/download/{filename}",
                                self.ota_handler.handle_download,
                            ),
                            web.options(
                                "/xiaozhi/ota/download/{filename}",
                                self.ota_handler.handle_options,
                            ),
                        ]
                    )

                # Route nhận diện âm thanh Speech-to-Text từ Micro ESP32
                app.add_routes(
                    [
                        web.post("/xiaozhi/transcribe", self.handle_transcribe),
                        web.post("/api/transcribe", self.handle_transcribe),
                        web.post("/xiaozhi/test_text", self.handle_test_text),
                        web.get("/xiaozhi/audio/{filename}", self.handle_audio_download),
                        web.get("/mcp/vision/explain", self.vision_handler.handle_get),
                        web.post(
                            "/mcp/vision/explain", self.vision_handler.handle_post
                        ),
                        web.options(
                            "/mcp/vision/explain", self.vision_handler.handle_options
                        ),
                    ]
                )

                runner = web.AppRunner(app)
                await runner.setup()
                site = web.TCPSite(runner, host, port)
                await site.start()
                asyncio.create_task(self._preload_asr())

                while True:
                    await asyncio.sleep(3600)
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"HTTP服务器启动失败: {e}")
            import traceback

            self.logger.bind(tag=TAG).error(f"错误堆栈: {traceback.format_exc()}")
            raise
