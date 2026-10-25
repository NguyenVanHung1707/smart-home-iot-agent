"""LangChain tool for social media (Twitter / X) search via RapidAPI."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

import httpx
from langchain_core.tools import tool
from pydantic import ConfigDict, Field

from src.agents.tools.base import _StrictToolInput, _tool_result


class SearchSocialMediaInput(_StrictToolInput):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    query: str = Field(
        default="",
        description="Từ khóa, chủ đề, hashtag hoặc tên nhân vật cần tra cứu trên mạng xã hội Twitter/X",
    )
    q: str | None = Field(default=None, description="Từ khóa tra cứu")
    keyword: str | None = Field(default=None, description="Từ khóa tra cứu")
    max_results: int = Field(default=5, ge=1, le=10, description="Số lượng bài viết tối đa cần lấy (1 đến 10)")


def _search_twitter_rapidapi(
    query: str, max_results: int = 5, api_key: str | None = None
) -> list[dict[str, Any]]:
    """Tìm kiếm bài viết trên Twitter/X qua RapidAPI."""
    from src.config import get_settings

    key = api_key or get_settings().rapidapi_key or "85385cb9aemsh46ef170c034215bp15032cjsn14cee3a8beaa"
    if not key:
        return []

    url = f"https://twitter-api45.p.rapidapi.com/search.php?query={urllib.parse.quote(query)}"
    headers = {
        "x-rapidapi-key": key,
        "x-rapidapi-host": "twitter-api45.p.rapidapi.com",
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code != 200:
                return []
            data = resp.json()

        timeline = data.get("timeline", [])
        posts: list[dict[str, Any]] = []

        for item in timeline:
            if not isinstance(item, dict):
                continue
            text = (item.get("text") or "").strip()
            screen_name = item.get("screen_name") or "unknown"
            tweet_id = item.get("tweet_id") or ""
            favorites = item.get("favorites") or 0
            retweets = item.get("retweets") or 0
            views = item.get("views") or 0
            created_at = item.get("created_at") or ""

            if text:
                tweet_url = f"https://x.com/{screen_name}/status/{tweet_id}" if tweet_id else ""
                posts.append({
                    "author": f"@{screen_name}",
                    "text": text,
                    "url": tweet_url,
                    "favorites": favorites,
                    "retweets": retweets,
                    "views": views,
                    "created_at": created_at,
                })
                if len(posts) >= max_results:
                    break

        return posts
    except Exception:
        return []


@tool(args_schema=SearchSocialMediaInput)
def search_social_media(
    query: str = "",
    q: str | None = None,
    keyword: str | None = None,
    max_results: int = 5,
) -> str:
    """Tìm kiếm bài viết, xu hướng (trends) và dư luận trên mạng xã hội Twitter/X."""
    search_q = (query or q or keyword or "").strip()
    if not search_q:
        return _tool_result("invalid_request", message="Từ khóa tìm kiếm mạng xã hội không được để trống.")

    # Làm sạch các từ đệm
    clean_q = re.sub(
        r"^(?:tìm trên twitter|tìm twitter|tìm x|tra twitter|xem twitter|tìm kiếm mạng xã hội|mạng xã hội)\s+",
        "",
        search_q,
        flags=re.I,
    ).strip()
    target_q = clean_q or search_q

    posts = _search_twitter_rapidapi(target_q, max_results=max_results)
    if not posts:
        return _tool_result(
            "not_found",
            query=search_q,
            message=f"Không tìm thấy bài viết nào trên Twitter/X cho từ khóa: '{search_q}'.",
        )

    lines = []
    for idx, p in enumerate(posts, 1):
        lines.append(
            f"{idx}. **{p['author']}** (❤️ {p['favorites']} | 🔁 {p['retweets']}):\n"
            f"   \"{p['text']}\"\n"
            f"   🔗 Link: {p['url']}"
        )

    summary_text = f"**Các bài thảo luận nóng trên Twitter/X về '{target_q}':**\n\n" + "\n\n".join(lines)
    return _tool_result(
        "success",
        platform="twitter",
        query=search_q,
        count=len(posts),
        posts=posts,
        summary=summary_text,
        message=summary_text,
    )
