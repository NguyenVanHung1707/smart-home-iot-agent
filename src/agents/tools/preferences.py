"""LangChain tools for managing user habit preferences and long-term memory."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool
from pydantic import Field

from src.agents.tools.base import _StrictToolInput, _tool_result


class SaveUserPreferenceInput(_StrictToolInput):
    key: str = Field(
        description="Tên định danh thói quen/sở thích (ví dụ: 'preferred_temp', 'night_brightness', 'wake_time', 'music_genre')",
    )
    value: str = Field(
        description="Giá trị của sở thích (ví dụ: '25', '20', '06:30', 'Acoustic Lo-Fi')",
    )
    category: str = Field(
        default="general",
        description="Phân loại: 'climate', 'lighting', 'schedule', 'routine', hoặc 'general'",
    )
    description: str | None = Field(
        default=None,
        description="Mô tả ngắn gọn bằng tiếng Việt về thói quen này",
    )


class GetUserPreferencesInput(_StrictToolInput):
    category: str | None = Field(
        default=None,
        description="Tùy chọn: Lọc danh sách thói quen theo phân loại ('climate', 'lighting', etc.)",
    )


@tool("save_user_preference", args_schema=SaveUserPreferenceInput)
def save_user_preference(
    key: str,
    value: str,
    category: str = "general",
    description: str | None = None,
) -> dict[str, Any]:
    """Lưu hoặc cập nhật thói quen, sở thích cá nhân của người dùng vào bộ nhớ dài hạn (Long-term memory).
    Sử dụng khi người dùng dặn AI ghi nhớ thói quen, mức nhiệt độ hay bật, độ sáng ưa thích, v.v.
    """
    from src.database import db_save_preference

    # Attempt to convert to int or float if purely numeric
    parsed_val: Any = value
    val_str = str(value).strip()
    if val_str.isdigit():
        parsed_val = int(val_str)
    else:
        try:
            parsed_val = float(val_str)
        except ValueError:
            parsed_val = val_str

    res = db_save_preference(
        key=key.strip(),
        value=parsed_val,
        category=category.strip().lower(),
        description=description.strip() if description else None,
    )
    desc_str = f" ({description})" if description else ""
    return _tool_result(
        status="success",
        data=res,
        message=f"Đã lưu thói quen '{key}': {value}{desc_str} vào bộ nhớ dài hạn.",
    )


@tool("get_user_preferences", args_schema=GetUserPreferencesInput)
def get_user_preferences(category: str | None = None) -> dict[str, Any]:
    """Tra cứu các thói quen và sở thích đã lưu trong bộ nhớ dài hạn của người dùng.
    Hữu ích khi cần biết thói quen của người dùng để điều chỉnh thiết bị phù hợp.
    """
    from src.database import db_get_preferences

    prefs = db_get_preferences(category=category.strip().lower() if category else None)
    if not prefs:
        return _tool_result(
            status="success",
            data=[],
            message="Chưa có thói quen hoặc sở thích nào được lưu cho phân loại này.",
        )
    return _tool_result(
        status="success",
        data=prefs,
        count=len(prefs),
        message=f"Đã tìm thấy {len(prefs)} thói quen đã lưu.",
    )
