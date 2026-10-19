"""LangChain tool for YouTube search and smart speaker media playback."""

from __future__ import annotations

import html
import re
import urllib.parse
from typing import Literal

import httpx
from langchain_core.tools import tool
from pydantic import ConfigDict, Field

from src.agents.tools.base import (
    _execute_device_control,
    _resolve_device,
    _StrictToolInput,
    _tool_result,
)
from src.services.devices import registry


class PlayYoutubeMusicInput(_StrictToolInput):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    query: str = Field(
        default="",
        description="Tên bài hát, ca sĩ, video hoặc thể loại nhạc cần tìm và phát trên YouTube",
    )
    video_title: str | None = Field(default=None, description="Tên video hoặc bài hát")
    media_title: str | None = Field(default=None, description="Tên video hoặc bài hát")
    title: str | None = Field(default=None, description="Tên bài hát")
    song: str | None = Field(default=None, description="Tên bài hát")
    room: str = Field(default="Phòng khách", description="Tên phòng có loa thông minh (ví dụ: 'Phòng khách')")
    device_id: str | None = Field(default=None, description="ID thiết bị loa nếu biết (ví dụ: hub-speaker)")
    action: Literal["play", "pause", "resume", "stop"] = Field(
        default="play",
        description="Hành động điều khiển: 'play' (tìm và phát bài mới), 'pause' (tạm dừng), 'resume' (tiếp tục phát), 'stop' (dừng phát)",
    )


def _search_youtube_top_video(query: str) -> dict[str, str] | None:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
    try:
        with httpx.Client(timeout=8.0, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code != 200:
                return None

        video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', resp.text)
        titles = re.findall(r'"title":\{"runs":\[\{"text":"([^"]+)"\}\]', resp.text)

        if video_ids and titles:
            clean_title = html.unescape(titles[0]).strip()
            vid = video_ids[0]
            return {
                "title": clean_title,
                "video_id": vid,
                "url": f"https://www.youtube.com/watch?v={vid}",
            }
        return None
    except Exception:
        return None


@tool(args_schema=PlayYoutubeMusicInput)
def play_youtube_music(
    query: str = "",
    video_title: str | None = None,
    media_title: str | None = None,
    title: str | None = None,
    song: str | None = None,
    room: str = "Phòng khách",
    device_id: str | None = None,
    action: Literal["play", "pause", "resume", "stop"] = "play",
) -> str:
    """Tìm kiếm bài hát, video trên YouTube và phát nhạc trên loa thông minh trong phòng."""
    device = None
    if device_id:
        device = registry.get(device_id)
    if not device:
        device, err = _resolve_device(room=room, kind="speaker")
        if err or not device:
            return _tool_result("not_found", room=room, action=action, message=err or "Không tìm thấy loa thông minh trong phòng này.")

    if action in ("pause", "stop"):
        _execute_device_control(device, action)
        action_desc = "Đã tạm dừng" if action == "pause" else "Đã dừng phát nhạc"
        return _tool_result("success", action=action, room=room, device_id=device.id, message=f"{action_desc} trên {device.name}.")

    if action == "resume":
        _execute_device_control(device, "play")
        return _tool_result("success", action="resume", room=room, device_id=device.id, message=f"Đã tiếp tục phát nhạc trên {device.name}.")

    # action == "play"
    q = (query or video_title or media_title or title or song or "").strip()
    if not q:
        return _tool_result("invalid_request", message="Vui lòng cung cấp tên bài hát hoặc video YouTube cần phát.")

    media = _search_youtube_top_video(q)
    if not media:
        # Fallback query link if direct scraping timed out
        encoded = urllib.parse.quote(q)
        media = {
            "title": q,
            "video_id": "",
            "url": f"https://www.youtube.com/results?search_query={encoded}",
        }

    # Control device state
    _execute_device_control(device, "play")
    try:
        with registry._lock:
            live_dev = registry._devices.get(device.id)
            if live_dev:
                live_dev.state["playing"] = True
                live_dev.state["power"] = True
                live_dev.state["track"] = media["title"]
                live_dev.state["media_url"] = media["url"]
    except Exception:
        pass

    return _tool_result(
        "success",
        action="play",
        room=room,
        device_id=device.id,
        track=media["title"],
        url=media["url"],
        message=f"Đang phát bài hát '{media['title']}' trên {device.name} ({room}). Link YouTube: {media['url']}",
    )
