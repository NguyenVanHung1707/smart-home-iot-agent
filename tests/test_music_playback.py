import asyncio
import pytest
from src.agents.tools.media_player import parse_music_intent
from src.services.xiaozhi import xiaozhi_service


def test_parse_music_intent_positive_queries():
    queries = [
        ("Mở cho tôi một vài bất kỳ của Sơn Tùng.", "Sơn Tùng"),
        ("Mở cho tôi vài em của ngày hôm qua.", "em của ngày hôm qua"),
        ("Mở bài Lạc Trôi", "Lạc Trôi"),
        ("Phát nhạc Đen Vâu", "Đen Vâu"),
        ("Bật bài Em của ngày hôm qua đi", "Em của ngày hôm qua"),
        ("Cho tôi nghe nhạc Mono", "Mono"),
        ("Hát bài Cơn mưa ngang qua", "Cơn mưa ngang qua"),
    ]
    for q, expected_clean in queries:
        is_music, action, clean_query = parse_music_intent(q)
        assert is_music is True, f"Failed for {q}"
        assert action == "play"
        assert expected_clean.lower() in clean_query.lower(), f"Expected '{expected_clean}' in '{clean_query}'"


def test_parse_music_intent_control():
    stop_queries = [
        "Dừng nhạc",
        "Tắt nhạc đi",
        "Tạm dừng nhạc",
        "Ngừng phát nhạc",
        "stop music",
    ]
    for q in stop_queries:
        is_music, action, _ = parse_music_intent(q)
        assert is_music is True, f"Failed for {q}"
        assert action in ("stop", "pause")


def test_parse_music_intent_negative_home_controls():
    non_music = [
        "Mở đèn phòng khách",
        "Mở cửa chính",
        "Bật quạt phòng ngủ",
        "Mở rèm cửa",
        "Tắt điều hòa",
        "Nhiệt độ hiện tại bao nhiêu",
    ]
    for q in non_music:
        is_music, _, _ = parse_music_intent(q)
        assert is_music is False, f"Incorrectly detected as music: {q}"


def test_xiaozhi_music_processing():
    async def _run():
        # Test query from user screenshot 1
        res1 = await xiaozhi_service.process("Mở cho tôi một vài bất kỳ của Sơn Tùng.", session_id="test_sess_1")
        assert res1["analysis"] == "xiaozhi_media_playback"
        assert res1["track"] != ""
        assert res1["url"] != ""
        assert "Đang phát bài" in res1["response"] or "Sơn Tùng" in res1["response"]

        # Test query from user screenshot 2
        res2 = await xiaozhi_service.process("Mở cho tôi vài em của ngày hôm qua.", session_id="test_sess_2")
        assert res2["analysis"] == "xiaozhi_media_playback"
        assert "Em của ngày hôm qua" in res2["track"] or "em của ngày hôm qua" in res2["response"].lower()

        # Test stop music
        res_stop = await xiaozhi_service.process("Dừng nhạc", session_id="test_sess_3")
        assert res_stop["analysis"] == "xiaozhi_media_playback"
        assert "dừng" in res_stop["response"].lower()

    asyncio.run(_run())
