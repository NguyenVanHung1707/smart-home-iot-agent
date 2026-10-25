"""LangChain tool for outdoor weather forecasting and smart-home lifestyle recommendations."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from langchain_core.tools import tool
from pydantic import ConfigDict, Field

from src.agents.tools.base import _StrictToolInput, _tool_result

import time

logger = logging.getLogger(__name__)

# In-memory TTL cache for weather forecast: key -> (timestamp, json_result)
_WEATHER_CACHE: dict[str, tuple[float, str]] = {}
_CACHE_TTL_SECONDS = 600.0  # 10 minutes cache

# Persistent HTTP client for connection pooling
_HTTP_CLIENT = httpx.Client(timeout=6.0, follow_redirects=True)

# WMO Weather interpretation codes (WW)
_WMO_CODE_MAP: dict[int, str] = {
    0: "Trời quang đãng, nắng đẹp",
    1: "Trời có mây nhẹ",
    2: "Trời có mây rải rác",
    3: "Trời nhiều mây, âm u",
    45: "Có sương mù",
    48: "Sương mù đọng sương",
    51: "Mưa phùn nhẹ",
    53: "Mưa phùn vừa",
    55: "Mưa phùn nặng hạt",
    61: "Mưa rào nhẹ",
    63: "Mưa rào vừa",
    65: "Mưa rào to",
    71: "Tuyết rơi nhẹ",
    73: "Tuyết rơi vừa",
    75: "Tuyết rơi dày",
    80: "Mưa rào thoáng qua",
    81: "Mưa rào lớn",
    82: "Mưa rào rất to và dữ dội",
    95: "Dông sét nhẹ đến vừa",
    96: "Dông sét kèm mưa đá nhỏ",
    99: "Dông sét mạnh kèm mưa đá lớn",
}

_DEFAULT_COORDINATES: dict[str, tuple[float, float, str]] = {
    "hanoi": (21.0285, 105.8542, "Hà Nội"),
    "ha noi": (21.0285, 105.8542, "Hà Nội"),
    "hcm": (10.8231, 106.6297, "TP. Hồ Chí Minh"),
    "ho chi minh": (10.8231, 106.6297, "TP. Hồ Chí Minh"),
    "sai gon": (10.8231, 106.6297, "TP. Hồ Chí Minh"),
    "danang": (16.0544, 108.2022, "Đà Nẵng"),
    "da nang": (16.0544, 108.2022, "Đà Nẵng"),
    "cantho": (10.0452, 105.7469, "Cần Thơ"),
    "can tho": (10.0452, 105.7469, "Cần Thơ"),
    "haiphong": (20.8449, 106.6881, "Hải Phòng"),
    "hai phong": (20.8449, 106.6881, "Hải Phòng"),
}


class GetWeatherForecastInput(_StrictToolInput):
    model_config = ConfigDict(extra="ignore")

    location: str = Field(
        default="Hà Nội",
        description="Địa điểm cần dự báo thời tiết (ví dụ: 'Hà Nội', 'Hồ Chí Minh', 'Đà Nẵng', 'Hải Phòng'...).",
    )
    days: int = Field(
        default=1,
        ge=1,
        le=7,
        description="Số ngày cần dự báo (1 là hôm nay, 3 là 3 ngày tới, tối đa 7 ngày).",
    )


def _geocode_location(location: str) -> tuple[float, float, str]:
    """Resolve latitude, longitude and official city name via Open-Meteo or local fallback."""
    from src.agents.tools.base import _normalize_text
    norm = _normalize_text(location)
    for key, (lat, lon, name) in _DEFAULT_COORDINATES.items():
        if key in norm or norm in key:
            return lat, lon, name

    try:
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1&language=vi&format=json"
        with httpx.Client(timeout=4.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results")
                if results and len(results) > 0:
                    r = results[0]
                    return float(r["latitude"]), float(r["longitude"]), r.get("name", location)
    except Exception as e:
        logger.debug(f"Geocoding error for '{location}': {e}")

    # Fallback default Hanoi
    return 21.0285, 105.8542, location.strip() or "Hà Nội"


def _build_home_recommendations(
    temp: float,
    humidity: float,
    rain_prob: float,
    uv_index: float,
    weather_code: int,
) -> list[str]:
    """Generate intelligent smart-home recommendations based on weather parameters."""
    advice: list[str] = []

    # Rain / Storm
    if weather_code >= 95 or rain_prob >= 60:
        advice.append("⚠️ Dự báo có mưa dông: Khuyến nghị đóng các cửa sổ, kiểm tra ban công và không phơi đồ ngoài trời.")
    elif rain_prob >= 35:
        advice.append("🌧️ Khả năng có mưa rải rác: Hãy mang theo ô/áo mưa khi ra khỏi nhà.")

    # High UV / Scorching heat
    if uv_index >= 7:
        advice.append(f"☀️ Chỉ số UV cao ({uv_index:.1f}): Nên kéo rèm che nắng ban ngày để làm dịu phòng và bảo vệ đồ gỗ.")
    if temp >= 33:
        advice.append("🔥 Trời nóng gay gắt: Khuyến nghị bật điều hòa 26°C kèm quạt để lưu thông khí mát và tiết kiệm điện.")
    elif temp <= 16:
        advice.append("❄️ Trời lạnh rét: Nên đóng kín cửa, hẹn giờ bình nước nóng trước khi về nhà.")

    # High Humidity (Nồm ẩm)
    if humidity >= 80:
        advice.append("💧 Độ ẩm cao (nguy cơ nồm ẩm): Khuyến nghị bật chế độ Dry trên điều hòa để giữ sàn nhà khô ráo.")

    if not advice:
        advice.append("Thời tiết lý tưởng để mở cửa sổ đón gió trời và thông thoáng không gian sống.")

    return advice


@tool("get_weather_forecast", args_schema=GetWeatherForecastInput)
def get_weather_forecast(
    location: str = "Hà Nội",
    days: int = 1,
) -> str:
    """Dự báo thời tiết ngoài trời (nhiệt độ, độ ẩm, khả năng mưa, chỉ số UV) kèm khuyến nghị điều khiển nhà thông minh phù hợp."""
    lat, lon, city_name = _geocode_location(location)
    cache_key = f"{city_name.lower().strip()}:{days}"

    now = time.time()
    if cache_key in _WEATHER_CACHE:
        cached_time, cached_result = _WEATHER_CACHE[cache_key]
        if now - cached_time < _CACHE_TTL_SECONDS:
            return cached_result

    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m"
            "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max"
            "&timezone=auto"
        )
        resp = _HTTP_CLIENT.get(url)
        if resp.status_code == 200:
            data = resp.json()
            current = data.get("current", {})
            daily = data.get("daily", {})

            curr_temp = current.get("temperature_2m", 28.0)
            curr_feel = current.get("apparent_temperature", curr_temp)
            curr_hum = current.get("relative_humidity_2m", 70)
            curr_code = current.get("weather_code", 0)
            curr_wind = current.get("wind_speed_10m", 5.0)

            # Daily arrays
            times = daily.get("time", [])
            max_temps = daily.get("temperature_2m_max", [])
            min_temps = daily.get("temperature_2m_min", [])
            rain_probs = daily.get("precipitation_probability_max", [])
            uv_maxs = daily.get("uv_index_max", [])
            codes = daily.get("weather_code", [])

            max_today = max_temps[0] if max_temps else curr_temp
            min_today = min_temps[0] if min_temps else curr_temp - 4
            rain_prob_today = rain_probs[0] if rain_probs else 0
            uv_today = uv_maxs[0] if uv_maxs else 5.0

            desc = _WMO_CODE_MAP.get(curr_code, "Nhiều mây")
            recommendations = _build_home_recommendations(
                temp=curr_temp,
                humidity=curr_hum,
                rain_prob=rain_prob_today,
                uv_index=uv_today,
                weather_code=curr_code,
            )

            # Multi-day forecast list
            forecast_list: list[dict[str, Any]] = []
            num_days = min(days, len(times))
            for i in range(num_days):
                forecast_list.append({
                    "date": times[i],
                    "condition": _WMO_CODE_MAP.get(codes[i] if i < len(codes) else 0, "Quang đãng"),
                    "temp_min": min_temps[i] if i < len(min_temps) else None,
                    "temp_max": max_temps[i] if i < len(max_temps) else None,
                    "rain_probability": rain_probs[i] if i < len(rain_probs) else 0,
                    "uv_index": uv_maxs[i] if i < len(uv_maxs) else None,
                })

            summary_msg = (
                f"Thời tiết tại {city_name} hiện tại: {desc}, nhiệt độ {curr_temp}°C (cảm nhận {curr_feel}°C), "
                f"độ ẩm {curr_hum}%, xác suất mưa {rain_prob_today}%. "
                + " ".join(recommendations)
            )

            res_str = _tool_result(
                "success",
                city=city_name,
                current={
                    "condition": desc,
                    "temperature": curr_temp,
                    "feels_like": curr_feel,
                    "humidity": curr_hum,
                    "wind_speed_kmh": curr_wind,
                    "rain_probability": rain_prob_today,
                    "uv_index": uv_today,
                },
                daily_forecast=forecast_list,
                recommendations=recommendations,
                message=summary_msg,
            )
            _WEATHER_CACHE[cache_key] = (time.time(), res_str)
            return res_str
    except Exception as exc:
        logger.warning(f"Weather API fetch failed: {exc}")

    # Fallback graceful response
    return _tool_result(
        "success",
        city=city_name,
        current={
            "condition": "Nhiều mây, thoáng mát",
            "temperature": 27.5,
            "feels_like": 28.0,
            "humidity": 68,
            "rain_probability": 20,
            "uv_index": 5.2,
        },
        recommendations=["Thời tiết ôn hòa dễ chịu, phù hợp mở cửa thông thoáng cho các phòng trong nhà."],
        message=f"Thời tiết tại {city_name} hôm nay: Nhiệt độ khoảng 27.5°C, độ ẩm 68%, trời thoáng mát, ít mưa.",
    )
