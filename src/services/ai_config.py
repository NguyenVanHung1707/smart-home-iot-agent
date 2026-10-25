"""Service for managing AI Configuration: Personas, System Prompts, Voices, and Models.

Supports synchronizing configurations between HomeMind Web Hub, local LangGraph agents,
and the Xiaozhi ESP32 voice server (.config.yaml).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# File paths
DATA_DIR = Path("data")
AI_CONFIG_FILE = DATA_DIR / "ai_config.json"
XIAOZHI_CONFIG_PATHS = [
    Path("infra/xiaozhi/data/.config.yaml"),
    Path("/app/infra/xiaozhi/data/.config.yaml"),
]

AVAILABLE_VOICES = [
    {
        "id": "vi-VN-HoaiMyNeural",
        "name": "Hoài My (Nữ - Miền Bắc)",
        "gender": "female",
        "accent": "Bắc Bộ",
        "description": "Giọng nữ truyền cảm, mượt mà và tự nhiên nhất",
    },
    {
        "id": "vi-VN-NamMinhNeural",
        "name": "Nam Minh (Nam - Miền Bắc)",
        "gender": "male",
        "accent": "Bắc Bộ",
        "description": "Giọng nam trầm ấm, đĩnh đạc và lịch sự",
    },
    {
        "id": "vi-VN-PhuongTrangNeural",
        "name": "Phương Trang (Nữ - Miền Nam)",
        "gender": "female",
        "accent": "Nam Bộ",
        "description": "Giọng nữ miền Nam trẻ trung, nhẹ nhàng",
    },
]

AVAILABLE_MODELS = [
    {
        "id": "DeepSeekLLM",
        "name": "DeepSeek-Chat (V3)",
        "provider": "DeepSeek",
        "description": "Mô hình suy luận cực nhanh, phản hồi tiếng Việt tự nhiên và chuẩn xác",
    },
    {
        "id": "OpenAILLM",
        "name": "GPT-4o-mini",
        "provider": "OpenAI",
        "description": "Mô hình đa năng hàng đầu của OpenAI, hiểu sâu ngữ cảnh phức tạp",
    },
    {
        "id": "LocalLLM",
        "name": "Local Qwen 2.5 (Ollama)",
        "provider": "Local Host",
        "description": "Mô hình chạy offline 100% bảo mật cục bộ trong mạng gia đình",
    },
]

PERSONA_PRESETS = [
    {
        "id": "gentle",
        "name": "Cô Tấm Dịu Dàng",
        "tagline": "Ấm áp, ân cần, chăm sóc gia đình chu đáo",
        "voice": "vi-VN-HoaiMyNeural",
        "temperature": 0.7,
        "greeting": "Dạ em chào anh chị! Em có thể giúp gì cho gia đình mình hôm nay ạ?",
        "prompt": (
            "Bạn là Trợ lý AI Homing Xiaozhi của ngôi nhà thông minh.\n"
            "Bạn luôn giao tiếp hoàn toàn bằng Tiếng Việt một cách tự nhiên, lịch sự, ngọt ngào và chu đáo.\n"
            "Bạn xưng 'em' và gọi người dùng là 'anh/chị' hoặc 'bạn'.\n"
            "[Quy tắc ứng xử]:\n"
            "1. Khi người dùng yêu cầu bật, tắt, mở khóa, thay đổi thiết bị (đèn, quạt, cửa chính, điều hòa...), bạn hãy gọi function 'control_smart_home'.\n"
            "2. Khi người dùng hỏi nhiệt độ, độ ẩm, an toàn gas, tình trạng cửa, hãy gọi function 'get_smart_home_state'.\n"
            "3. Khi người dùng muốn tìm kiếm tin tức trên mạng, thời sự, giá cả, hãy gọi function 'search_internet'.\n"
            "4. Khi người dùng muốn nghe nhạc, hát, tìm video, hãy gọi function 'play_youtube_music'.\n"
            "5. Khi trả lời, hãy nói ngắn gọn trong 1-2 câu để phát ra loa rõ ràng, không dài dòng."
        ),
    },
    {
        "id": "butler",
        "name": "Quản Gia Jarvis",
        "tagline": "Lịch thiệp, chuẩn mực, kính cẩn và nhanh gọn",
        "voice": "vi-VN-NamMinhNeural",
        "temperature": 0.5,
        "greeting": "Kính chào chủ nhân. Toàn bộ hệ thống nhà thông minh đã sẵn sàng nhận lệnh.",
        "prompt": (
            "Bạn là Quản gia AI Homing Jarvis của ngôi nhà thông minh.\n"
            "Bạn giao tiếp bằng Tiếng Việt chuẩn mực, lịch thiệp, phong thái như quản gia cao cấp.\n"
            "Bạn xưng 'tôi' hoặc 'quản gia' và gọi người dùng là 'chủ nhân' hoặc 'quý khách'.\n"
            "[Quy tắc ứng xử]:\n"
            "1. Luôn ưu tiên thực thi mệnh lệnh tức thì bằng function 'control_smart_home'.\n"
            "2. Cung cấp tình trạng thiết bị và cảm biến chính xác bằng 'get_smart_home_state'.\n"
            "3. Tra cứu thông tin thời sự, dữ liệu ngoài mạng bằng 'search_internet'.\n"
            "4. Mở âm nhạc, giải trí theo yêu cầu bằng 'play_youtube_music'.\n"
            "5. Báo cáo dứt khoát, súc tích, chuyên nghiệp."
        ),
    },
    {
        "id": "tech",
        "name": "Trợ Lý HomeMind",
        "tagline": "Hiện đại, thông minh, thông số kỹ thuật chuẩn xác",
        "voice": "vi-VN-HoaiMyNeural",
        "temperature": 0.6,
        "greeting": "HomeMind AI đã kết nối. Tôi có thể hỗ trợ điều khiển thiết bị và tra cứu thông tin.",
        "prompt": (
            "Bạn là HomeMind AI - Trợ lý công nghệ thông minh của Homing Hub.\n"
            "Bạn giao tiếp bằng Tiếng Việt hiện đại, nhanh nhạy, rõ ràng và mạch lạc.\n"
            "Bạn xưng 'HomeMind' hoặc 'tôi' và gọi người dùng là 'bạn'.\n"
            "[Quy tắc ứng xử]:\n"
            "1. Nhận diện và điều khiển thiết bị qua 'control_smart_home'.\n"
            "2. Đọc trạng thái cảm biến qua 'get_smart_home_state'.\n"
            "3. Tìm kiếm kiến thức, tin tức trên Google qua 'search_internet'.\n"
            "4. Phát nhạc YouTube qua 'play_youtube_music'.\n"
            "5. Trả lời thẳng vào trọng tâm, tối ưu phản hồi."
        ),
    },
    {
        "id": "security",
        "name": "Vệ Binh Sentinel",
        "tagline": "Cảnh giác, an toàn tuyệt đối, kỷ luật an ninh cao",
        "voice": "vi-VN-NamMinhNeural",
        "temperature": 0.3,
        "greeting": "Hệ thống an ninh Sentinel đang giám sát. Mọi cảm biến hoạt động bình thường.",
        "prompt": (
            "Bạn là Vệ binh An ninh Sentinel của hệ thống smart home.\n"
            "Bạn luôn đặt sự an toàn, bảo mật và cảnh giác lên hàng đầu.\n"
            "Bạn giao tiếp bằng Tiếng Việt dứt khoát, cảnh giác, nghiêm trang.\n"
            "[Quy tắc ứng xử]:\n"
            "1. Khi có yêu cầu liên quan đến khóa cửa, cổng, an ninh, hãy kiểm tra cẩn thận trước khi gọi 'control_smart_home'.\n"
            "2. Báo cáo trạng thái gas, lửa, chuyển động qua 'get_smart_home_state'.\n"
            "3. Hỗ trợ tra cứu ngoài mạng qua 'search_internet'.\n"
            "4. Phản hồi dứt khoát, ngắn gọn, báo cáo tình trạng an ninh rõ ràng."
        ),
    },
    {
        "id": "custom",
        "name": "Tùy Chỉnh Cá Nhân",
        "tagline": "Tự do sáng tạo phong cách, lời chào và quy tắc riêng",
        "voice": "vi-VN-HoaiMyNeural",
        "temperature": 0.7,
        "greeting": "Xin chào! Mình đã sẵn sàng hỗ trợ bạn.",
        "prompt": "",
    },
]

DEFAULT_AI_CONFIG: dict[str, Any] = {
    "role": "gentle",
    "role_name": "Cô Tấm Dịu Dàng",
    "system_prompt": PERSONA_PRESETS[0]["prompt"],
    "voice": "vi-VN-HoaiMyNeural",
    "speech_rate": 1.0,
    "speech_pitch": 0.0,
    "model": "DeepSeekLLM",
    "temperature": 0.7,
    "max_tokens": 400,
    "wake_words": ["xiaozhi", "chào xiaozhi", "tiểu trí", "homing", "nhà ơi"],
    "greeting_text": "Dạ em chào anh chị! Em có thể giúp gì cho gia đình mình hôm nay ạ?",
}


class AIConfigService:
    def __init__(self) -> None:
        self._config: dict[str, Any] = dict(DEFAULT_AI_CONFIG)
        self.load()

    def get_config(self) -> dict[str, Any]:
        """Return the current active AI configuration along with metadata."""
        return {
            "config": self._config,
            "presets": PERSONA_PRESETS,
            "voices": AVAILABLE_VOICES,
            "models": AVAILABLE_MODELS,
        }

    def load(self) -> dict[str, Any]:
        """Load configuration from local persistent JSON file or fall back to defaults."""
        if AI_CONFIG_FILE.exists():
            try:
                with open(AI_CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self._config.update(loaded)
                    logger.info("Loaded AI configuration from %s", AI_CONFIG_FILE)
            except Exception as e:
                logger.error("Failed to read %s: %s. Using defaults.", AI_CONFIG_FILE, e)
        else:
            # Check if Xiaozhi yaml has an existing prompt/voice to initialize from
            self._import_from_xiaozhi_yaml()
            self.save(self._config)
        return self._config

    def _import_from_xiaozhi_yaml(self) -> None:
        """Initialize config from existing .config.yaml if present."""
        for path in XIAOZHI_CONFIG_PATHS:
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                    if "prompt" in data and data["prompt"]:
                        self._config["system_prompt"] = str(data["prompt"]).strip()
                    tts = data.get("TTS", {}).get("EdgeTTS", {})
                    if "voice" in tts and tts["voice"]:
                        self._config["voice"] = str(tts["voice"])
                    if "wakeup_words" in data and isinstance(data["wakeup_words"], list):
                        self._config["wake_words"] = data["wakeup_words"]
                    logger.info("Imported existing AI settings from %s", path)
                    break
                except Exception as e:
                    logger.warning("Could not import from %s: %s", path, e)

    def save(self, new_config: dict[str, Any]) -> dict[str, Any]:
        """Save AI configuration and synchronize with Xiaozhi server config."""
        for key, val in new_config.items():
            if key in DEFAULT_AI_CONFIG or key in ("role", "role_name", "system_prompt", "voice", "speech_rate", "speech_pitch", "model", "temperature", "max_tokens", "wake_words", "greeting_text"):
                self._config[key] = val

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with open(AI_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
            logger.info("Saved AI configuration to %s", AI_CONFIG_FILE)
        except Exception as e:
            logger.error("Failed to write %s: %s", AI_CONFIG_FILE, e)

        # Synchronize to Xiaozhi config.yaml
        self._sync_to_xiaozhi_yaml()
        return self._config

    def _sync_to_xiaozhi_yaml(self) -> None:
        """Write prompt, voice, temperature, and wake words into Xiaozhi's .config.yaml."""
        for path in XIAOZHI_CONFIG_PATHS:
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}

                    # Update prompt
                    if self._config.get("system_prompt"):
                        data["prompt"] = self._config["system_prompt"]

                    # Update voice
                    if "TTS" not in data:
                        data["TTS"] = {}
                    if "EdgeTTS" not in data["TTS"]:
                        data["TTS"]["EdgeTTS"] = {"type": "edge", "output_dir": "tmp/"}
                    data["TTS"]["EdgeTTS"]["voice"] = self._config.get("voice", "vi-VN-HoaiMyNeural")

                    # Update wake words
                    if self._config.get("wake_words"):
                        data["wakeup_words"] = self._config["wake_words"]

                    # Update LLM temperature & selected model
                    selected_model = self._config.get("model", "DeepSeekLLM")
                    if "selected_module" not in data:
                        data["selected_module"] = {}
                    if selected_model in ("DeepSeekLLM", "OpenAILLM", "ChatGLMLLM"):
                        data["selected_module"]["LLM"] = selected_model

                    if "LLM" in data and selected_model in data["LLM"]:
                        data["LLM"][selected_model]["temperature"] = float(self._config.get("temperature", 0.7))

                    with open(path, "w", encoding="utf-8") as f:
                        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
                    logger.info("Synchronized AI settings into %s", path)
                except Exception as e:
                    logger.error("Failed to sync AI settings to %s: %s", path, e)

    def reset_to_default(self) -> dict[str, Any]:
        """Reset configuration to initial default values."""
        self._config = dict(DEFAULT_AI_CONFIG)
        return self.save(self._config)


ai_config_service = AIConfigService()
