"""LangChain tool for managing household grocery and supplies shopping list."""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from langchain_core.tools import tool
from pydantic import ConfigDict, Field

from src.agents.tools.base import _StrictToolInput, _tool_result

logger = logging.getLogger(__name__)

_SHOPPING_FILE = Path("data/shopping_list.json")
_SHOPPING_LOCK = threading.Lock()
_SHOPPING_CACHE: list[dict[str, Any]] | None = None


def _load_shopping_list() -> list[dict[str, Any]]:
    global _SHOPPING_CACHE
    with _SHOPPING_LOCK:
        if _SHOPPING_CACHE is not None:
            return [dict(x) for x in _SHOPPING_CACHE]
        if not _SHOPPING_FILE.exists():
            _SHOPPING_CACHE = []
            return []
        try:
            data = json.loads(_SHOPPING_FILE.read_text(encoding="utf-8"))
            _SHOPPING_CACHE = data if isinstance(data, list) else []
            return [dict(x) for x in _SHOPPING_CACHE]
        except Exception as exc:
            logger.warning(f"Error reading shopping list file: {exc}")
            _SHOPPING_CACHE = []
            return []


def _save_shopping_list(items: list[dict[str, Any]]) -> bool:
    global _SHOPPING_CACHE
    with _SHOPPING_LOCK:
        _SHOPPING_CACHE = [dict(x) for x in items]
        try:
            _SHOPPING_FILE.parent.mkdir(parents=True, exist_ok=True)
            _SHOPPING_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except Exception as exc:
            logger.error(f"Error saving shopping list file: {exc}")
            return False


class ManageShoppingListInput(_StrictToolInput):
    model_config = ConfigDict(extra="ignore")

    action: Literal["add", "get", "list", "mark_bought", "delete", "clear"] = Field(
        default="get",
        description="Hành động: 'add' (thêm món đồ), 'get' / 'list' (xem danh sách), 'mark_bought' (đánh dấu đã mua), 'delete' (xóa món đồ), 'clear' (dọn dẹp danh sách).",
    )
    item: str | None = Field(
        default=None,
        description="Tên món đồ cần mua (ví dụ: 'sữa tươi', 'trứng gà', 'nước rửa bát', 'pin AA').",
    )
    quantity: str | None = Field(
        default=None,
        description="Số lượng hoặc quy cách (ví dụ: '2 hộp', '1 vỉ', '5 kg').",
    )
    category: str = Field(
        default="thực phẩm",
        description="Phân loại: 'thực phẩm', 'gia dụng', 'thiết bị', hoặc 'chung'.",
    )


@tool(args_schema=ManageShoppingListInput)
def manage_shopping_list(
    action: Literal["add", "get", "list", "mark_bought", "delete", "clear"] = "get",
    item: str | None = None,
    quantity: str | None = None,
    category: str = "thực phẩm",
) -> str:
    """Quản lý danh sách mua sắm gia đình: thêm món cần mua, xem danh sách đi chợ, đánh dấu đồ đã mua và dọn dẹp danh sách."""
    items = _load_shopping_list()
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    # 1. Thêm món đồ cần mua
    if action == "add":
        if not item or not item.strip():
            return _tool_result("invalid_request", message="Vui lòng cung cấp tên món đồ cần mua.")

        clean_item = item.strip()
        new_entry = {
            "id": len(items) + 1,
            "item": clean_item,
            "quantity": quantity.strip() if quantity else "1",
            "category": category.strip(),
            "status": "pending",  # 'pending' hoặc 'bought'
            "created_at": now_str,
        }
        items.append(new_entry)
        _save_shopping_list(items)

        qty_str = f" (số lượng: {new_entry['quantity']})" if quantity else ""
        return _tool_result(
            "success",
            action="add",
            item=new_entry,
            message=f"Đã thêm '{clean_item}'{qty_str} vào danh sách mua sắm ({category}).",
        )

    # 2. Đánh dấu đã mua xong
    if action == "mark_bought":
        if not item or not item.strip():
            return _tool_result("invalid_request", message="Vui lòng cung cấp tên món đồ đã mua xong.")

        target = item.strip().lower()
        found = False
        for entry in items:
            if target in entry["item"].lower() or entry["item"].lower() in target:
                entry["status"] = "bought"
                entry["bought_at"] = now_str
                found = True

        if found:
            _save_shopping_list(items)
            return _tool_result(
                "success",
                action="mark_bought",
                item=item,
                message=f"Tuyệt vời! Đã đánh dấu món '{item}' là ĐÃ MUA xong.",
            )
        return _tool_result(
            "not_found",
            item=item,
            message=f"Không tìm thấy món '{item}' trong danh sách mua sắm hiện tại.",
        )

    # 3. Xóa món đồ
    if action == "delete":
        if not item or not item.strip():
            return _tool_result("invalid_request", message="Vui lòng cung cấp tên món đồ muốn xóa.")

        target = item.strip().lower()
        remaining = [e for e in items if target not in e["item"].lower() and e["item"].lower() not in target]
        if len(remaining) < len(items):
            _save_shopping_list(remaining)
            return _tool_result(
                "success",
                action="delete",
                item=item,
                message=f"Đã xóa món '{item}' khỏi danh sách mua sắm.",
            )
        return _tool_result("not_found", message=f"Không tìm thấy món '{item}' để xóa.")

    # 4. Xóa sạch các món đã mua hoặc làm mới danh sách
    if action == "clear":
        unbought = [e for e in items if e.get("status") == "pending"]
        _save_shopping_list(unbought)
        return _tool_result(
            "success",
            action="clear",
            message="Đã dọn dẹp các món đã mua. Danh sách hiện chỉ giữ lại các món đang cần mua.",
        )

    # 5. Xem danh sách mua sắm (action == "get")
    pending_items = [e for e in items if e.get("status") == "pending"]
    bought_items = [e for e in items if e.get("status") == "bought"]

    if not items:
        return _tool_result(
            "success",
            action="get",
            total=0,
            pending_count=0,
            items=[],
            message="Danh sách mua sắm hiện đang trống. Bạn có thể nhờ tôi thêm đồ bằng cách nói: 'Thêm sữa tươi vào danh sách mua sắm'.",
        )

    lines = [f"🛒 **Danh sách mua sắm gia đình ({len(pending_items)} món cần mua):**"]
    if pending_items:
        for idx, it in enumerate(pending_items, 1):
            qty = f" [{it['quantity']}]" if it.get("quantity") else ""
            cat = f" ({it['category']})" if it.get("category") else ""
            lines.append(f"{idx}. ⏳ **{it['item']}**{qty}{cat}")
    else:
        lines.append("🎉 Tuyệt vời! Bạn đã mua đầy đủ tất cả các món đồ.")

    if bought_items:
        lines.append(f"\n✅ **Đã mua xong gần đây ({len(bought_items)} món):**")
        for it in bought_items[-3:]:
            lines.append(f"- ~{it['item']}~ (Đã xong)")

    summary_text = "\n".join(lines)
    return _tool_result(
        "success",
        action="get",
        total=len(items),
        pending_count=len(pending_items),
        items=pending_items,
        message=summary_text,
    )
