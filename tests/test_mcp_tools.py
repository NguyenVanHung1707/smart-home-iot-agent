"""Unit and integration tests for YouTube, Tavily Search, and Social Media MCP tools."""

from __future__ import annotations

import json
import pytest

from src.agents.tools.media_player import play_youtube_music
from src.agents.tools.internet_search import search_internet
from src.agents.tools.social_search import search_social_media
from src.services.mcp_server import mcp_server


def test_youtube_music_mcp_tool():
    """Kiểm tra YouTube Data API v3 và trích xuất luồng âm thanh yt-dlp."""
    res_str = play_youtube_music.invoke({"query": "Numb Linkin Park", "room": "Phòng khách"})
    res = json.loads(res_str) if isinstance(res_str, str) else res_str

    assert res.get("status") == "success"
    assert "youtube.com" in res.get("url", "")
    assert res.get("track") is not None
    # Kiểm tra luồng stream hoặc video url
    assert res.get("audio_stream_url") or res.get("url")
    assert "Đang phát bài hát" in res.get("message", "")


def test_tavily_internet_search_mcp_tool():
    """Kiểm tra tìm kiếm Internet thông minh qua Tavily AI Search."""
    res_str = search_internet.invoke({"query": "thời tiết Hà Nội hôm nay", "max_results": 2})
    res = json.loads(res_str) if isinstance(res_str, str) else res_str

    assert res.get("status") in ("success", "not_found")
    if res.get("status") == "success":
        assert len(res.get("results", [])) > 0
        assert res.get("summary") is not None


def test_twitter_social_search_mcp_tool():
    """Kiểm tra tìm kiếm mạng xã hội Twitter / X qua RapidAPI."""
    res_str = search_social_media.invoke({"query": "Artificial Intelligence", "max_results": 2})
    res = json.loads(res_str) if isinstance(res_str, str) else res_str

    assert res.get("status") in ("success", "not_found")
    if res.get("status") == "success":
        assert res.get("platform") == "twitter"
        posts = res.get("posts", [])
        assert len(posts) > 0
        assert "author" in posts[0]
        assert "text" in posts[0]


def test_mcp_server_protocol_integration():
    """Kiểm tra MCP Server Protocol JSON-RPC 2.0 phản hồi chính xác tools mới."""
    # 1. tools/list
    list_req = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    list_resp = mcp_server.handle_request(list_req)
    tools = [t["name"] for t in list_resp.get("result", {}).get("tools", [])]

    assert "play_youtube_music" in tools
    assert "search_internet" in tools
    assert "search_social_media" in tools

    # 2. tools/call search_internet
    call_req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "search_internet", "arguments": {"query": "Hà Nội"}}
    }
    call_resp = mcp_server.handle_request(call_req)
    content = call_resp.get("result", {}).get("content", [])
    assert len(content) > 0
    assert len(content[0].get("text", "")) > 10
