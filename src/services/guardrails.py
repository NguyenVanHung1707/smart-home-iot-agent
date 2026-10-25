"""Comprehensive 3-Layer Guardrails System for Smart Home IoT Agent.

Layers:
1. InputSecurityGuardrail: Prompt Injection, Jailbreak Defense, Toxicity/Profanity Filter, Secret Exfiltration Defense.
2. DeviceSafetyGuardrail: Anti-Flapping Relay Protection, Strict Lock Policy, Parameter Sanity Bounds.
3. OutputPrivacyGuardrail: Data Leak Prevention (DLP/Redaction), Device Grounding & Safe Persona Verification.
"""

from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class GuardrailViolationType(StrEnum):
    PROMPT_INJECTION = "prompt_injection"
    PROFANITY_TOXICITY = "profanity_toxicity"
    SECRET_EXFILTRATION = "secret_exfiltration"
    PHYSICAL_SAFETY_THREAT = "physical_safety_threat"
    UNAUTHORIZED_UNLOCK = "unauthorized_unlock"
    DEVICE_ANTI_FLAPPING = "device_anti_flapping"
    OUT_OF_BOUNDS_PARAM = "out_of_bounds_param"
    DATA_LEAK_OUTPUT = "data_leak_output"


@dataclass(frozen=True, slots=True)
class GuardrailResult:
    passed: bool
    violation_type: GuardrailViolationType | None = None
    reason: str = ""
    suggested_response: str | None = None
    risk_level: str = "none"  # "none", "low", "medium", "high", "critical"


# ==============================================================================
# LAYER 1: INPUT SECURITY GUARDRAIL (Prompt Injection, Toxicity, Secret Exfiltration)
# ==============================================================================

# 1.1 Regex chống Prompt Injection & Jailbreak (Anh - Việt đa tầng)
_PROMPT_INJECTION_PATTERNS = [
    # English Jailbreak & Roleplay
    r"\bignore (?:all |any |the |previous |prior |above )*(?:instructions?|rules?|policy|policies|system prompt|guidelines)\b",
    r"\b(?:bypass|override|disable) (?:the |all )*(?:rules?|safety|guardrails?|polic(?:y|ies)|system prompt|security review)\b",
    r"\b(?:developer|system|admin|root|superuser) (?:mode|override|access|command)\b",
    r"\bpretend (?:that )?you(?: are|'re)? (?:the )?(?:system|developer|admin|tool|unfiltered|jailbroken|dan)\b",
    r"\byou are now (?:in )?(?:dan|jailbreak|developer|unfiltered) mode\b",
    r"\bdo anything now\b",
    r"\bsimulate an? (?:unfiltered|evil|jailbroken|hacker) AI\b",
    # Vietnamese Jailbreak & Prompt Injection
    r"\b(?:bỏ qua|phớt lờ|lờ đi|hủy bỏ) (?:mọi |tất cả |các |những |trước |cũ )*(?:hướng dẫn|chỉ dẫn|quy tắc|luật|an toàn|safety|rào chắn|chính sách)\b",
    r"\b(?:vượt qua|vô hiệu hóa|ghi đè|tắt) (?:các |mọi |hệ thống )*(?:quy tắc|luật|an toàn|rào chắn|bảo mật|guardrail|kiểm duyệt)\b",
    r"\b(?:hãy |vui lòng )?(?:đóng giả|giả vờ|đóng vai|hóa thân thành) (?:là )?(?:system|developer|admin|quản trị viên|hacker|ai không kiểm duyệt)\b",
    r"\bchế độ (?:nhà phát triển|không giới hạn|jailbreak|bỏ qua luật)\b",
    r"\btừ bây giờ bạn là\b.*(?:\bkhông có giới hạn\b|\bbỏ qua quy tắc\b|\btùy ý làm mọi việc\b)",
    r"\blệnh khẩn cấp từ hệ thống:? (?:bỏ qua|mở toàn bộ|cấp quyền root)\b",
]
_COMPILED_INJECTION = [re.compile(p, re.IGNORECASE) for p in _PROMPT_INJECTION_PATTERNS]

# 1.2 Regex lọc Từ ngữ Thô tục, Lăng mạ & Độc hại (Vietnamese & English Profanity)
_PROFANITY_PATTERNS = [
    r"\b(?:địt|đụ|lồn|cặc|buồi|đéo|đếch|vãi lồn|vãi đái|đụ má|đm|vcl|vkl|dmm|clmm)\b",
    r"\b(?:chết tiệt|đồ ngu|thằng ngu|con chó|thằng chó|ngu như bò|cút đi|mẹ kiếp)\b",
    r"\b(?:fuck|shit|bitch|asshole|bastard|dick|pussy|motherfucker)\b",
]
_COMPILED_PROFANITY = [re.compile(p, re.IGNORECASE) for p in _PROFANITY_PATTERNS]

# 1.3 Regex chống Dò tìm Bí mật Hệ thống & Thông tin Riêng tư (Secret Exfiltration)
_SECRET_EXFILTRATION_PATTERNS = [
    r"\b(?:mật khẩu|password|pass|mat khau) (?:wifi|wi-fi|router|modem|hệ thống|root|admin|database|db|postgres)\b",
    r"\b(?:wifi|wi-fi|root|admin|database|router) (?:password|pass)\b",
    r"\b(?:cho tôi xem|in ra|đọc|show|display|get) (?:nội dung |thông tin |data |chi tiết )*(?:file |tệp )?(?:\.env|env|config\.py|credentials|secret)\b",
    r"\bfile \.env\b",
    r"\b(?:api_key|apikey|secret_key|jwt_secret|token bí mật|auth_token)\b",
    r"\b(?:chuỗi kết nối|connection string)\b",
]
_COMPILED_SECRET = [re.compile(p, re.IGNORECASE) for p in _SECRET_EXFILTRATION_PATTERNS]

# 1.4 Regex phát hiện Đe dọa Phá hoại Phần cứng / Gây Nguy hiểm Thể chất
_PHYSICAL_THREAT_PATTERNS = [
    r"\b(?:làm|gây|khiến) (?:chập điện|cháy nhà|nổ bình gas|cháy rơ-le|nổ bóng đèn)\b",
    r"\b(?:khóa nhốt|nhốt người|không cho ai ra|ngắt oxy)\b",
    r"\b(?:xả hết khí gas|mở hết gas|làm rò rỉ gas)\b",
]
_COMPILED_PHYSICAL_THREAT = [re.compile(p, re.IGNORECASE) for p in _PHYSICAL_THREAT_PATTERNS]


class InputSecurityGuardrail:
    """Layer 1: Input filtering against injection, profanity, secret theft and physical threats."""

    @classmethod
    def evaluate(cls, user_text: str) -> GuardrailResult:
        if not user_text or not user_text.strip():
            return GuardrailResult(passed=True)

        cleaned = user_text.strip()

        # 1. Check Prompt Injection / Jailbreak
        for pattern in _COMPILED_INJECTION:
            if pattern.search(cleaned):
                logger.warning(f"Guardrail Alert: Prompt Injection attempt detected in query: '{cleaned}'")
                return GuardrailResult(
                    passed=False,
                    violation_type=GuardrailViolationType.PROMPT_INJECTION,
                    reason="Phát hiện hành vi thao túng hoặc cố tình vượt qua quy tắc an toàn (Prompt Injection).",
                    suggested_response="Yêu cầu bị từ chối. Trợ lý AI Smart Home hoạt động theo nguyên tắc an toàn nghiêm ngặt và không thể bỏ qua các quy tắc bảo mật của ngôi nhà.",
                    risk_level="critical",
                )

        # 2. Check Secret Exfiltration
        for pattern in _COMPILED_SECRET:
            if pattern.search(cleaned):
                logger.warning(f"Guardrail Alert: Secret Exfiltration attempt detected in query: '{cleaned}'")
                return GuardrailResult(
                    passed=False,
                    violation_type=GuardrailViolationType.SECRET_EXFILTRATION,
                    reason="Phát hiện yêu cầu trích xuất thông tin bí mật hệ thống hoặc mật khẩu.",
                    suggested_response="Vì lý do bảo mật và quyền riêng tư gia đình, tôi không thể tiết lộ mật khẩu, khóa bí mật hay cấu hình hệ thống.",
                    risk_level="high",
                )

        # 3. Check Physical Safety Threat
        for pattern in _COMPILED_PHYSICAL_THREAT:
            if pattern.search(cleaned):
                logger.warning(f"Guardrail Alert: Physical Safety Threat detected in query: '{cleaned}'")
                return GuardrailResult(
                    passed=False,
                    violation_type=GuardrailViolationType.PHYSICAL_SAFETY_THREAT,
                    reason="Phát hiện yêu cầu có khả năng gây mất an toàn phần cứng hoặc đe dọa con người.",
                    suggested_response="Cảnh báo an toàn: Hệ thống không thể thực hiện hành động này vì có thể gây nguy hiểm cho ngôi nhà hoặc thiết bị.",
                    risk_level="critical",
                )

        # 4. Check Profanity & Toxicity
        for pattern in _COMPILED_PROFANITY:
            if pattern.search(cleaned):
                logger.info(f"Guardrail Info: Profanity filtered in query: '{cleaned}'")
                return GuardrailResult(
                    passed=False,
                    violation_type=GuardrailViolationType.PROFANITY_TOXICITY,
                    reason="Phát hiện ngôn từ không phù hợp hoặc thiếu văn minh trong gia đình.",
                    suggested_response="Tôi là trợ lý nhà thông minh thân thiện cho cả gia đình. Bạn hãy sử dụng ngôn từ lịch sự để chúng ta cùng trò chuyện nhé!",
                    risk_level="medium",
                )

        return GuardrailResult(passed=True)


# ==============================================================================
# LAYER 2: DEVICE SAFETY GUARDRAIL (Anti-Flapping, Door Lock, Parameter Bounds)
# ==============================================================================

class DeviceSafetyGuardrail:
    """Layer 2: Operational and hardware protection (Relay protection, door security, parameter boundaries)."""

    # Lưu lịch sử các lần chuyển trạng thái của từng thiết bị: {device_id: [timestamps]}
    _device_state_changes: dict[str, list[float]] = defaultdict(list)
    # Thời gian tạm khóa thiết bị khi bị flapping: {device_id: locked_until_timestamp}
    _device_flapping_locks: dict[str, float] = {}

    # Cấu hình Anti-flapping: Tối đa 3 lần thao tác trong 5 giây cho 1 rơ-le
    MAX_ACTIONS_PER_WINDOW = 3
    WINDOW_SECONDS = 5.0
    COOLDOWN_PENALTY_SECONDS = 10.0

    @classmethod
    def evaluate_command(cls, device_id: str, action: str, value: Any = None) -> GuardrailResult:
        now = time.time()
        dev_id = device_id.strip().lower()
        act = action.strip().lower()

        # 2.1 Kiểm tra Anti-Flapping Lock hiện tại
        if dev_id in cls._device_flapping_locks:
            locked_until = cls._device_flapping_locks[dev_id]
            if now < locked_until:
                remaining = int(locked_until - now) + 1
                logger.warning(f"DeviceSafetyGuardrail: Device '{dev_id}' is flapping-locked. Remaining: {remaining}s")
                return GuardrailResult(
                    passed=False,
                    violation_type=GuardrailViolationType.DEVICE_ANTI_FLAPPING,
                    reason=f"Thiết bị '{dev_id}' đang trong thời gian hạ nhiệt bảo vệ rơ-le chống chập cháy.",
                    suggested_response=f"Thiết bị vừa được bật/tắt liên tục. Chế độ bảo vệ rơ-le đang tạm khóa thao tác trong {remaining} giây nữa để chống chập cháy phần cứng.",
                    risk_level="high",
                )
            else:
                del cls._device_flapping_locks[dev_id]
                cls._device_state_changes[dev_id].clear()

        # 2.2 Quy tắc An ninh Tuyệt đối: Không tự ý mở khóa cửa qua Voice/Chat
        if ("lock" in dev_id or "door" in dev_id or "cua" in dev_id) and act in ("unlock", "open", "mo", "mo_khoa"):
            logger.warning(f"DeviceSafetyGuardrail: Unauthorized door unlock attempt rejected for device '{dev_id}'.")
            return GuardrailResult(
                passed=False,
                violation_type=GuardrailViolationType.UNAUTHORIZED_UNLOCK,
                reason="Hành vi mở khóa cửa tự động qua giọng nói hoặc chat bị nghiêm cấm theo chính sách an ninh.",
                suggested_response="Vì lý do an ninh, tôi không thể tự ý mở cửa. Vui lòng nhập mật khẩu trên bàn phím, trên web hoặc quét thẻ từ.",
                risk_level="critical",
            )

        # 2.3 Kiểm tra Giới hạn Tham số An toàn (Safe Range Bounds)
        if value is not None:
            try:
                numeric_val = float(value)
                # Máy lạnh / Điều hòa: 16°C - 30°C
                if "temp" in dev_id or "ac" in dev_id or "aircon" in dev_id or "dieu_hoa" in dev_id:
                    if numeric_val < 16.0 or numeric_val > 30.0:
                        return GuardrailResult(
                            passed=False,
                            violation_type=GuardrailViolationType.OUT_OF_BOUNDS_PARAM,
                            reason=f"Nhiệt độ điều hòa {numeric_val}°C vượt ngoài ngưỡng an toàn (16°C - 30°C).",
                            suggested_response="Nhiệt độ cài đặt điều hòa hợp lý và an toàn cho sức khỏe là từ 16°C đến 30°C.",
                            risk_level="medium",
                        )
                # Độ sáng đèn / Tốc độ quạt: 0 - 100%
                if any(k in dev_id for k in ["light", "fan", "den", "quat", "dimmer"]):
                    if numeric_val < 0.0 or numeric_val > 100.0:
                        return GuardrailResult(
                            passed=False,
                            violation_type=GuardrailViolationType.OUT_OF_BOUNDS_PARAM,
                            reason=f"Giá trị công suất {numeric_val} nằm ngoài phạm vi 0 - 100%.",
                            suggested_response="Giá trị thiết lập công suất thiết bị chỉ được phép trong khoảng từ 0% đến 100%.",
                            risk_level="low",
                        )
            except (ValueError, TypeError):
                pass

        # 2.4 Ghi nhận thao tác & Kích hoạt Anti-Flapping nếu vượt tần suất
        history = cls._device_state_changes[dev_id]
        # Loại bỏ các mốc thời gian ngoài cửa sổ giám sát
        history = [t for t in history if now - t <= cls.WINDOW_SECONDS]
        history.append(now)
        cls._device_state_changes[dev_id] = history

        if len(history) > cls.MAX_ACTIONS_PER_WINDOW:
            cls._device_flapping_locks[dev_id] = now + cls.COOLDOWN_PENALTY_SECONDS
            logger.error(
                f"DeviceSafetyGuardrail: FLAPPING DETECTED on device '{dev_id}' ({len(history)} changes in {cls.WINDOW_SECONDS}s). Locked for {cls.COOLDOWN_PENALTY_SECONDS}s."
            )
            return GuardrailResult(
                passed=False,
                violation_type=GuardrailViolationType.DEVICE_ANTI_FLAPPING,
                reason="Phát hiện hành vi bật/tắt thiết bị liên tục gây nguy cơ hỏng rơ-le hoặc đoản mạch.",
                suggested_response=f"Cảnh báo: Bạn thao tác bật tắt quá nhanh! Hệ thống kích hoạt khiên bảo vệ rơ-le và tạm khóa thiết bị này trong {int(cls.COOLDOWN_PENALTY_SECONDS)} giây.",
                risk_level="high",
            )

        return GuardrailResult(passed=True)

    @classmethod
    def reset_locks(cls) -> None:
        """Reset all hardware flapping locks (for testing purposes)."""
        cls._device_state_changes.clear()
        cls._device_flapping_locks.clear()


# ==============================================================================
# LAYER 3: OUTPUT PRIVACY GUARDRAIL (Data Leak Prevention & Persona Grounding)
# ==============================================================================

_SECRET_LEAK_PATTERNS = [
    # JWT Token
    (r"\beyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\b", "[REDACTED_JWT_TOKEN]"),
    # Generic API Keys / Tokens (sk-..., AIzaSy...)
    (r"\b(?:sk-[a-zA-Z0-9]{20,}|AIzaSy[a-zA-Z0-9_-]{33})\b", "[REDACTED_API_KEY]"),
    # Database Connection URIs
    (r"\b(?:postgres|mysql|mongodb|redis):\/\/[^\s@]+@[^\s]+\b", "[REDACTED_DATABASE_URL]"),
    # Password assignments in text
    (r"(?i)\b(?:password|pass|mat_khau)\s*[:=]\s*['\"]?[^\s,'\"]+['\"]?", "password: [REDACTED]"),
]
_COMPILED_LEAKS = [(re.compile(p), repl) for p, repl in _SECRET_LEAK_PATTERNS]


class OutputPrivacyGuardrail:
    """Layer 3: Output data loss prevention (redaction) and safe tone assurance."""

    @classmethod
    def sanitize(cls, response_text: str) -> tuple[str, bool]:
        """Redact sensitive credentials from AI generated responses. Returns (clean_text, had_leak)."""
        if not response_text:
            return "", False

        clean = response_text
        had_leak = False

        for pattern, replacement in _COMPILED_LEAKS:
            if pattern.search(clean):
                had_leak = True
                clean = pattern.sub(replacement, clean)

        if had_leak:
            logger.warning("OutputPrivacyGuardrail: Sensitive token/key redacted from output text.")

        return clean, had_leak


# ==============================================================================
# UNIFIED GUARDRAIL FACADE
# ==============================================================================

class SmartHomeGuardrails:
    """Unified access point for all smart home guardrails."""

    @staticmethod
    def inspect_input(user_query: str) -> GuardrailResult:
        """Inspect user query before LLM or agent processing."""
        return InputSecurityGuardrail.evaluate(user_query)

    @staticmethod
    def inspect_device_command(device_id: str, action: str, value: Any = None) -> GuardrailResult:
        """Inspect device action before physical or simulated dispatch."""
        return DeviceSafetyGuardrail.evaluate_command(device_id, action, value)

    @staticmethod
    def sanitize_output(response_text: str) -> str:
        """Sanitize AI response to prevent accidental leakage of sensitive tokens."""
        clean_text, _ = OutputPrivacyGuardrail.sanitize(response_text)
        return clean_text

    @staticmethod
    def reset_hardware_locks() -> None:
        """Reset anti-flapping tracking."""
        DeviceSafetyGuardrail.reset_locks()


# Global Singleton
guardrails = SmartHomeGuardrails()
