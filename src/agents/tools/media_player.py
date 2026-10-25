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


def parse_music_intent(query: str, norm_text: str | None = None) -> tuple[bool, str, str]:
    """Parse Vietnamese natural language request to detect music/media playback intent.

    Returns:
        (is_music, action, clean_query)
        action: 'play', 'stop', 'pause', 'resume'
    """
    import unicodedata

    if norm_text is None:
        lowered = unicodedata.normalize("NFD", query.lower())
        without_marks = "".join(c for c in lowered if unicodedata.category(c) != "Mn")
        norm = re.sub(r"[^a-z0-9\s]", " ", without_marks).strip()
    else:
        norm = norm_text

    padded = f" {norm} "

    # 1. Stop / Pause commands
    stop_cues = (
        "dung nhac", "tat nhac", "ngung nhac", "tat loa", "tam dung nhac",
        "dung phat nhac", "stop music", "pause music", "tat youtube",
        "tat bai hat", "dung bai hat", "ngung phat nhac", "tat am nhac",
        "tat bai ca", "dung hat", "ngung hat", "tat nhac di", "dung nhac lai"
    )
    if any(f" {cue} " in padded for cue in stop_cues):
        return True, "stop", ""

    # 2. Resume commands
    resume_cues = ("tiep tuc phat nhac", "tiep tuc phat bai", "tiep tuc hat", "phat tiep", "resume music")
    if any(f" {cue} " in padded for cue in resume_cues):
        return True, "resume", ""

    # 3. Safeguard: Non-music home automation commands
    home_appliances = (
        "den", "quat", "dieu hoa", "may lanh", "rem", "cua", "khoa cua",
        "nhiet do", "do am", "khi gas", "camera", "o cam", "binh nong lanh"
    )
    music_nouns = (
        "nhac", "bai", "vai", "ca khuc", "bai hat", "bai ca", "album",
        "playlist", "video", "mv", "youtube", "am nhac"
    )
    has_appliance = any(f" {a} " in padded for a in home_appliances)
    has_music_noun = any(f" {m} " in padded for m in music_nouns)

    if has_appliance and not has_music_noun:
        return False, "play", query

    # 4. Check explicit music playback cues
    is_music = False
    music_direct_cues = (
        "phat nhac", "mo nhac", "bat nhac", "nghe nhac",
        "mo bai", "phat bai", "bat bai", "nghe bai", "hat bai",
        "mo vai", "phat vai", "bat vai", "nghe vai",
        "cho toi nghe", "cho minh nghe", "cho em nghe", "cho anh nghe",
        "mo ca khuc", "phat ca khuc", "bat ca khuc", "nghe ca khuc",
        "youtube", "bai hat", "ca si", "nghe gi do", "bai ca",
        "mo playlist", "phat playlist", "bat playlist",
        "mo mv", "phat mv", "bat mv"
    )
    if any(f" {cue} " in padded for cue in music_direct_cues):
        is_music = True

    # 5. Starts with music/playback verb and contains music noun
    if not is_music:
        words = norm.split()
        if words and words[0] in ("mo", "phat", "bat", "nghe", "hat", "play"):
            if has_music_noun:
                is_music = True

    # 6. Famous singers / popular songs
    famous_artists = (
        "son tung", "den vau", "jack", "mono", "erik", "duc phuc", "my tam",
        "ha anh tuan", "hoang thuy linh", "chillies", "da lab", "b ray",
        "phan manh quynh", "vu", "soobin", "min", "amee", "truc nhan",
        "hoa minzy", "grey d", "hieuthuhai", "mck", "tlinh", "low g",
        "wren evans", "justatee", "phuong ly", "karik", "tang duy tan"
    )
    famous_songs = (
        "em cua ngay hom qua", "lac troi", "noi nay co anh", "chung ta cua hien tai",
        "chay ngay di", "buong doi tay nhau ra", "con mua ngang qua", "nang am xa dan",
        "dung lam trai tim anh dau", "muon roi ma sao con", "con mua bang gia",
        "cat doi noi sau", "ngay mai nguoi ta lay chong", "sai gon dau long qua"
    )
    if not is_music:
        has_artist_or_song = any(f" {a} " in padded for a in famous_artists) or any(f" {s} " in padded for s in famous_songs)
        if has_artist_or_song:
            if any(f" {v} " in padded for v in ("mo", "phat", "bat", "nghe", "hat", "bai", "vai", "nhac", "ca khuc", "cho", "tim")):
                is_music = True

    if not is_music:
        return False, "play", query

    # 7. Clean query extraction
    clean = query.strip()
    prefix_patterns = [
        r"^(?:xin\s+vui\s+lòng\s+|vui\s+lòng\s+|hãy\s+)?(?:mở|phát|bật|cho\s+tôi\s+nghe|cho\s+mình\s+nghe|cho\s+em\s+nghe|cho\s+anh\s+nghe|hát)\s+(?:cho\s+tôi\s+|cho\s+mình\s+|cho\s+em\s+|cho\s+anh\s+)?(?:nghe\s+)?(?:một\s+bài|một\s+vài|bài\s+hát|bài|vài|ca\s+khúc|nhạc)?\s*(?:bất\s+kỳ\s+)?(?:của\s+)?",
        r"^(?:mở|phát|bật|nghe|hát|tìm|play)\s+(?:bài\s+hát|bài|vài|ca\s+khúc|nhạc\s+của|nhạc|video|mv|youtube)?\s*(?:của\s+)?",
    ]
    for p in prefix_patterns:
        clean = re.sub(p, "", clean, flags=re.IGNORECASE).strip()

    clean = re.sub(r"\s+(?:đi|nhé|nha|giúp\s+tôi|hộ\s+tôi|với|trên\s+youtube|qua\s+loa)\s*$", "", clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r"^(?:bất\s+kỳ\s+của|bất\s+kỳ|của)\s+", "", clean, flags=re.IGNORECASE).strip()
    clean = clean.strip(".?!,: ")

    if not clean:
        clean = query.strip()

    return True, "play", clean

