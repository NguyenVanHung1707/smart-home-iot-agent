import json
from unittest.mock import Mock, patch

import pytest

from src.agents.tools.internet_search import search_internet
from src.agents.tools.media_player import play_youtube_music
from src.models.schemas import Device


def test_search_internet_empty_query():
    raw = search_internet.invoke({"query": "   "})
    data = json.loads(raw)
    assert data["status"] == "invalid_request"


def test_search_internet_success():
    mock_results = [
        {"title": "Dự báo thời tiết Hà Nội", "snippet": "Trời mát, nhiệt độ 25 độ C", "url": "https://example.com/weather"}
    ]
    with patch("src.agents.tools.internet_search._search_bing", return_value=mock_results):
        raw = search_internet.invoke({"query": "thời tiết Hà Nội", "max_results": 2})
        data = json.loads(raw)
        assert data["status"] == "success"
        assert data["count"] == 1
        assert "Dự báo thời tiết" in data["summary"]


def test_search_internet_wikipedia_fallback():
    mock_wiki = [
        {"title": "Hà Nội", "snippet": "Thủ đô của Việt Nam", "url": "https://vi.wikipedia.org/wiki/Hà_Nội"}
    ]
    with patch("src.agents.tools.internet_search._search_bing", return_value=[]), \
         patch("src.agents.tools.internet_search._search_wikipedia", return_value=mock_wiki):
        raw = search_internet.invoke({"query": "Hà Nội"})
        data = json.loads(raw)
        assert data["status"] == "success"
        assert "Hà Nội" in data["summary"]


def test_play_youtube_music_play(monkeypatch):
    speaker = Device(
        id="hub-speaker",
        name="Loa Homing",
        room="Phòng khách",
        kind="speaker",
        online=True,
        state={"power": False, "volume": 50, "playing": False},
    )
    monkeypatch.setattr("src.agents.tools.media_player._resolve_device", lambda room, kind: (speaker, None))
    control_mock = Mock(return_value=(speaker, None))
    monkeypatch.setattr("src.agents.tools.media_player._execute_device_control", control_mock)

    mock_yt = {
        "title": "Lạc Trôi - Sơn Tùng M-TP",
        "video_id": "Llw9Q6akRo4",
        "url": "https://www.youtube.com/watch?v=Llw9Q6akRo4",
    }
    with patch("src.agents.tools.media_player._search_youtube_top_video", return_value=mock_yt):
        raw = play_youtube_music.invoke({"query": "lạc trôi", "room": "Phòng khách", "action": "play"})
        data = json.loads(raw)
        assert data["status"] == "success"
        assert data["action"] == "play"
        assert "Lạc Trôi" in data["track"]
        assert "Llw9Q6akRo4" in data["url"]
        control_mock.assert_called_once()


def test_play_youtube_music_pause_and_stop(monkeypatch):
    speaker = Device(
        id="hub-speaker",
        name="Loa Homing",
        room="Phòng khách",
        kind="speaker",
        online=True,
        state={"power": True, "volume": 50, "playing": True},
    )
    monkeypatch.setattr("src.agents.tools.media_player._resolve_device", lambda room, kind: (speaker, None))
    control_mock = Mock(return_value=(speaker, None))
    monkeypatch.setattr("src.agents.tools.media_player._execute_device_control", control_mock)

    raw_pause = play_youtube_music.invoke({"query": "", "room": "Phòng khách", "action": "pause"})
    data_pause = json.loads(raw_pause)
    assert data_pause["status"] == "success"
    assert data_pause["action"] == "pause"

    raw_stop = play_youtube_music.invoke({"query": "", "room": "Phòng khách", "action": "stop"})
    data_stop = json.loads(raw_stop)
    assert data_stop["status"] == "success"
    assert data_stop["action"] == "stop"
