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
    room: str = Field(default="Phòng khách", description="Tên phòng (mặc định 'Phòng khách' với Loa ESP32 AI Gateway)")
    device_id: str | None = Field(default="gateway-speaker", description="ID thiết bị loa nếu biết (mặc định 'gateway-speaker' - Loa ESP32 AI Gateway)")
    action: Literal["play", "pause", "resume", "stop"] = Field(
        default="play",
        description="Hành động điều khiển: 'play' (tìm và phát bài mới), 'pause' (tạm dừng), 'resume' (tiếp tục phát), 'stop' (dừng phát)",
    )


def _search_youtube_api(query: str, api_key: str | None = None) -> dict[str, str] | None:
    """Tìm kiếm video qua Google YouTube Data API v3 chính thức."""
    from src.config import get_settings
    key = api_key or get_settings().youtube_api_key or "AIzaSyD-piHhSsNoVeDUq_YvercO7DudyXWZGKE"
    if not key:
        return None

    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": 1,
        "key": key,
    }
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                if items:
                    item = items[0]
                    vid = item.get("id", {}).get("videoId", "")
                    snippet = item.get("snippet", {})
                    title = snippet.get("title", "")
                    channel = snippet.get("channelTitle", "")
                    thumb = snippet.get("thumbnails", {}).get("high", {}).get("url", "")
                    if vid:
                        return {
                            "title": html.unescape(title),
                            "video_id": vid,
                            "url": f"https://www.youtube.com/watch?v={vid}",
                            "channel": channel,
                            "thumbnail": thumb,
                        }
    except Exception:
        pass
    return None


def _extract_audio_stream(video_url: str) -> dict[str, str | int] | None:
    """Trích xuất luồng âm thanh trực tiếp (Direct Audio Stream) bằng yt-dlp."""
    try:
        import yt_dlp

        ydl_opts = {
            "format": "ba/b",
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            if info:
                stream_url = info.get("url") or ""
                return {
                    "audio_stream_url": stream_url,
                    "duration": int(info.get("duration") or 0),
                    "title": info.get("title") or "",
                    "thumbnail": info.get("thumbnail") or "",
                }
    except Exception:
        pass
    return None


def _search_youtube_top_video(query: str) -> dict[str, str] | None:
    """Tìm kiếm video qua YouTube Data API v3, tự động fallback sang web scraping nếu hết quota."""
    # 1. Thử dùng YouTube Data API v3 chính thức
    res = _search_youtube_api(query)
    if res:
        return res

    # 2. Fallback sang Web Scraping an toàn nếu API key tạm thời bị giới hạn
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
    if not device and room:
        device, _ = _resolve_device(room=room, kind="speaker")
    if not device:
        # Ưu tiên Loa ESP32 AI Gateway, sau đó là bất kỳ speaker nào khác. Tuyệt đối không fallback sang màn hình!
        gateway = registry.get("gateway-speaker")
        if gateway:
            device = gateway
        else:
            speakers = [d for d in registry.list() if d.kind == "speaker"]
            if speakers:
                device = speakers[0]
            else:
                from src.models.schemas import Device
                device = Device(
                    id="gateway-speaker",
                    name="Loa ESP32 AI Gateway",
                    kind="speaker",
                    room="Phòng khách",
                    state={"power": True, "playing": False, "volume": 80},
                )

    if action in ("pause", "stop"):
        if device:
            _execute_device_control(device, action)
            action_desc = "Đã tạm dừng" if action == "pause" else "Đã dừng phát nhạc"
            return _tool_result(
                "success", action=action, room=room, device_id=device.id, message=f"{action_desc} trên {device.name}."
            )
        return _tool_result("success", action=action, room=room, message="Đã dừng phát nhạc.")

    if action == "resume":
        if device:
            _execute_device_control(device, "play")
            return _tool_result(
                "success",
                action="resume",
                room=room,
                device_id=device.id,
                message=f"Đã tiếp tục phát nhạc trên {device.name}.",
            )
        return _tool_result("success", action="resume", room=room, message="Đã tiếp tục phát nhạc.")

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
    
    # Trích xuất luồng âm thanh trực tiếp (Direct Audio Stream) qua yt-dlp
    stream_info = _extract_audio_stream(media["url"]) if media.get("url") and "watch?v=" in media["url"] else None
    stream_url = stream_info.get("audio_stream_url") if stream_info else None
    duration = stream_info.get("duration") if stream_info else 0
    thumbnail = media.get("thumbnail") or (stream_info.get("thumbnail") if stream_info else "")

    try:
        with registry._lock:
            live_dev = registry._devices.get(device.id)
            if live_dev:
                live_dev.state["playing"] = True
                live_dev.state["power"] = True
                live_dev.state["track"] = media["title"]
                live_dev.state["media_url"] = media["url"]
                if stream_url:
                    live_dev.state["audio_stream_url"] = stream_url
                if duration:
                    live_dev.state["duration"] = duration
                if thumbnail:
                    live_dev.state["thumbnail"] = thumbnail
    except Exception:
        pass

    stream_msg = " [Đã trích xuất luồng âm thanh trực tiếp qua yt-dlp]" if stream_url else ""
    return _tool_result(
        "success",
        action="play",
        room=room,
        device_id=device.id,
        track=media["title"],
        url=media["url"],
        audio_stream_url=stream_url,
        duration=duration,
        thumbnail=thumbnail,
        message=f"Đang phát bài hát '{media['title']}' trên {device.name} ({room}). Link YouTube: {media['url']}{stream_msg}",
    )
