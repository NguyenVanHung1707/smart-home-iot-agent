"""LangChain tool for searching smart home guides and documentation."""

from __future__ import annotations

from langchain_core.tools import tool
from pydantic import Field, field_validator

from src.agents.tools.base import (
    _StrictToolInput,
    _tool_result,
)
from src.services.rag import search_device_guides


class SearchHomeGuidesInput(_StrictToolInput):
    query: str = Field(min_length=2, max_length=500, description="Focused Vietnamese support question or keywords.")

    @field_validator("query", mode="before")
    @classmethod
    def strip_query(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


@tool(args_schema=SearchHomeGuidesInput)
def search_home_guides(query: str) -> str:
    """Tìm tài liệu hỗ trợ cho cách dùng, bảo trì hoặc khắc phục sự cố."""
    guides = search_device_guides(query)
    if not guides:
        return _tool_result(
            "not_found",
            query=query,
            message="Không tìm thấy hướng dẫn phù hợp trong kho tri thức.",
        )
    results = [
        {
            "source": str(guide.get("source", "unknown")),
            "content": str(guide.get("content", ""))[:500],
        }
        for guide in guides[:5]
    ]
    return _tool_result("success", query=query, count=len(results), results=results)
