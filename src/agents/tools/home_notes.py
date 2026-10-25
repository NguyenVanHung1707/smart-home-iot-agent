"""LangChain tools for managing family notes, voice reminders, and household memos."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain_core.tools import tool
from pydantic import ConfigDict, Field

from src.agents.tools.base import _StrictToolInput, _tool_result

logger = logging.getLogger(__name__)

_NOTES_FILE = Path("data/family_notes.json")
_NOTES_CACHE: list[dict[str, Any]] | None = None


def _load_notes() -> list[dict[str, Any]]:
    global _NOTES_CACHE
    if _NOTES_CACHE is not None:
        return list(_NOTES_CACHE)
    if not _NOTES_FILE.exists():
        _NOTES_CACHE = []
        return []
    try:
        data = json.loads(_NOTES_FILE.read_text(encoding="utf-8"))
        _NOTES_CACHE = data if isinstance(data, list) else []
        return list(_NOTES_CACHE)
    except Exception as exc:
        logger.warning(f"Error reading notes file: {exc}")
        return []


def _save_notes(notes: list[dict[str, Any]]) -> bool:
    global _NOTES_CACHE
    _NOTES_CACHE = list(notes)
    try:
        _NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        _NOTES_FILE.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception as exc:
        logger.error(f"Error saving notes file: {exc}")
        return False


class AddFamilyNoteInput(_StrictToolInput):
    model_config = ConfigDict(extra="ignore")

    content: str = Field(
        description="Nội dung ghi chú hoặc lời nhắc (ví dụ: 'Mai có thợ đến sửa điều hòa lúc 9h', 'Nhắc uống thuốc sau ăn').",
    )
    category: str = Field(
        default="chung",
        description="Phân loại ghi chú: 'chung', 'nhac_viec', 'an_ninh', 'mua_sam', hoặc 'suc_khoe'.",
    )
    reminder_time: str | None = Field(
        default=None,
        description="Thời gian nhắc nhở nếu có (ví dụ: '20:00 hôm nay', '09:00 ngày mai').",
    )


class GetFamilyNotesInput(_StrictToolInput):
    model_config = ConfigDict(extra="ignore")

    category: str | None = Field(
        default=None,
        description="Tùy chọn: Lọc ghi chú theo phân loại ('nhac_viec', 'an_ninh', 'mua_sam'...). Để trống để lấy tất cả.",
    )


class DeleteFamilyNoteInput(_StrictToolInput):
    model_config = ConfigDict(extra="ignore")

    note_id: int = Field(
        description="Mã số ID của ghi chú cần xóa hoặc đánh dấu hoàn thành.",
    )


@tool("add_family_note", args_schema=AddFamilyNoteInput)
def add_family_note(
    content: str,
    category: str = "chung",
    reminder_time: str | None = None,
) -> str:
    """Lưu ghi chú hoặc lời nhắc việc cho gia đình vào hệ thống nhà thông minh."""
    text = content.strip()
    if not text:
        return _tool_result("invalid_request", message="Nội dung ghi chú không được để trống.")

    notes = _load_notes()
    new_id = max([n.get("id", 0) for n in notes], default=0) + 1
    now_str = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M")

    note_item = {
        "id": new_id,
        "content": text,
        "category": category.strip().lower(),
        "reminder_time": reminder_time.strip() if reminder_time else None,
        "created_at": now_str,
    }
    notes.append(note_item)
    _save_notes(notes)

    remind_str = f" vào lúc {reminder_time}" if reminder_time else ""
    return _tool_result(
        "success",
        note=note_item,
        message=f"Đã lưu ghi chú #{new_id}: '{text}'{remind_str} cho gia đình.",
    )


@tool("get_family_notes", args_schema=GetFamilyNotesInput)
def get_family_notes(category: str | None = None) -> str:
    """Xem danh sách các ghi chú, lời nhắc việc hiện có trong gia đình."""
    notes = _load_notes()
    if category:
        cat_norm = category.strip().lower()
        notes = [n for n in notes if n.get("category") == cat_norm]

    if not notes:
        return _tool_result(
            "success",
            count=0,
            notes=[],
            message="Hiện không có ghi chú nào được lưu trong hệ thống.",
        )

    lines = [f"- #{n['id']} [{n.get('category', 'chung')}]: {n['content']}" + (f" (Hẹn lúc: {n['reminder_time']})" if n.get("reminder_time") else "") for n in notes]
    summary_msg = f"Đang có {len(notes)} ghi chú:\n" + "\n".join(lines)

    return _tool_result(
        "success",
        count=len(notes),
        notes=notes,
        message=summary_msg,
    )


@tool("delete_family_note", args_schema=DeleteFamilyNoteInput)
def delete_family_note(note_id: int) -> str:
    """Xóa hoặc hoàn thành một ghi chú trong gia đình theo ID."""
    notes = _load_notes()
    remaining = [n for n in notes if n.get("id") != note_id]

    if len(remaining) == len(notes):
        return _tool_result("not_found", message=f"Không tìm thấy ghi chú có ID #{note_id}.")

    _save_notes(remaining)
    return _tool_result(
        "success",
        note_id=note_id,
        message=f"Đã xóa thành công ghi chú #{note_id}.",
    )
