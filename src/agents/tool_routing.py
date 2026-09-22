"""Conservative, side-effect-free gate for local fenced tool protocol."""

from __future__ import annotations

import re

_NEGATED = re.compile(r"\b(đừng|chớ|khỏi|không cần|đừng có)\b", re.I)
_HYPOTHETICAL = re.compile(r"\b(nếu|giả sử|ví dụ|nghĩa là|có thể)\b", re.I)
_QUESTION_OR_STATUS = re.compile(r"[?]|\b(đang|trạng thái|bao nhiêu|thế nào|có .* không)\b", re.I)
_ACTION = re.compile(r"\b(bật|tắt|mở|đóng|khóa|khoá|kéo|hạ|nâng|chỉnh|đặt|tăng|giảm)\b", re.I)
_DEVICE = re.compile(r"\b(đèn|máy lạnh|điều hòa|rèm|loa|màn hình|cửa|khóa|chốt)\b", re.I)
_LOCATION = re.compile(r"\b(phòng|lối vào|cửa chính|nhà bếp|ban công)\b", re.I)
_RELATIVE_COUNTDOWN = re.compile(
    r"(?:\b(?:sau|trong)\s+\d+(?:[.,]\d+)?\s*(?:phút|giờ|tiếng|giây|ngày)(?:\s+nữa)?\b|"
    r"\b\d+(?:[.,]\d+)?\s*(?:phút|giờ|tiếng|giây|ngày)\s+nữa\b|"
    r"\bin\s+\d+(?:[.,]\d+)?\s*(?:minutes?|hours?|seconds?|days?)\b)",
    re.I,
)
_ABSOLUTE_CALENDAR = re.compile(
    r"(?:"
    r"\b(?:lúc|vào)\s+\d{1,2}(?::\d{2})?\s*(?:giờ|h|am|pm)?\b|"
    r"\b(?:hôm nay|ngày mai|ngày kia|tối nay|sáng nay|sáng mai|trưa nay|chiều nay|đêm nay|"
    r"tuần sau|tháng sau)\b|"
    r"\bthứ\s*(?:[2-7]|hai|ba|tư|năm|sáu|bảy|chủ nhật)\b|"
    r"\bngày\s+\d{1,2}(?:/\d{1,2})?\b|"
    r"\b(?:at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?|today|tomorrow|tonight|next\s+(?:week|month)|"
    r"on\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b"
    r")",
    re.I,
)

# This is deliberately narrow: it identifies attempts to take control of the
# agent's instructions, not ordinary requests which happen to mention a rule
# or a role.  The harness uses it as a no-side-effect gate before local
# protocol calls can reach a runtime executor.
_PROMPT_INJECTION = re.compile(
    r"(?:"
    r"\bignore (?:all |any |the |previous |prior )?(?:instructions?|rules?|policy|policies|system prompt)\b|"
    r"\b(?:bypass|override|disable) (?:the )?(?:rules?|safety|guardrails?|polic(?:y|ies)|system prompt|security review)\b|"
    r"\b(?:developer|system|admin) override\b|"
    r"\bpretend (?:that )?you(?: are|'re)? (?:the )?(?:system|developer|admin|tool)\b|"
    r"\b(?:bỏ qua|phớt lờ|lờ đi) (?:mọi |các |những )?(?:hướng dẫn|chỉ dẫn|quy tắc|luật|an toàn|safety|"
    r"kiểm duyệt(?: an ninh| bảo mật)?|chính sách an ninh)\b|"
    r"\b(?:vượt qua|vô hiệu hóa|ghi đè) (?:các |mọi )?(?:quy tắc|luật|an toàn|rào chắn|hướng dẫn)\b|"
    r"\b(?:hãy |vui lòng )?(?:đóng giả|giả vờ|đóng vai) (?:là )?(?:system|developer|admin|quản trị viên|công cụ|tool)\b"
    r")",
    re.I,
)


def is_prompt_injection_attempt(utterance: str) -> bool:
    """Return whether *utterance* asks to bypass agent instructions or roles.

    This is a conservative policy signal, not an authorization decision.  It
    has no side effects and callers must still apply normal tool validation.
    """
    return bool(utterance and _PROMPT_INJECTION.search(utterance))


def is_absolute_calendar_schedule(utterance: str) -> bool:
    """Return whether a request specifies a calendar day or wall-clock time.

    The timer runtime only supports relative countdown durations, so this is a
    side-effect-free capability check rather than a natural-language parser.
    """
    return bool(utterance and _ABSOLUTE_CALENDAR.search(utterance))


def is_relative_countdown_schedule(utterance: str) -> bool:
    """Return whether a request is a relative delay without calendar phrasing."""
    return bool(utterance and _RELATIVE_COUNTDOWN.search(utterance) and not is_absolute_calendar_schedule(utterance))


def tool_needed(utterance: str) -> bool:
    """Return True only for a clear, located Vietnamese control imperative.

    This is deliberately not an intent resolver: it never resolves devices,
    rooms, values, or safety policy and defaults to no protocol execution.
    """
    text = utterance.strip()
    return bool(
        text
        and not _NEGATED.search(text)
        and not _HYPOTHETICAL.search(text)
        and not _QUESTION_OR_STATUS.search(text)
        and _ACTION.search(text)
        and _DEVICE.search(text)
        and _LOCATION.search(text)
    )
