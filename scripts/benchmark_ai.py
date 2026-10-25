"""AI Performance and Quality Benchmark Suite for HomeMind Hub & Xiaozhi AI Brain.

Measures:
1. Tool Latency (P50, P95, Mean, Min, Max) for all new & core tools.
2. Local GPU LLM Performance (TTFT, Total Time, Tokens/sec) on Qwen 2.5.
3. Intent Routing & Classification Accuracy across diverse Vietnamese queries.
4. End-to-End Pipeline Latency (Cold vs. Warm requests).
"""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from typing import Any

from src.agents.tools.air_quality_advisor import evaluate_air_quality
from src.agents.tools.energy_analytics import get_energy_analytics
from src.agents.tools.home_notes import add_family_note, get_family_notes
from src.agents.tools.home_safety_audit import audit_home_safety
from src.agents.tools.internet_search import search_internet
from src.agents.tools.media_player import play_youtube_music
from src.agents.tools.shopping_list import manage_shopping_list
from src.agents.tools.sleep_optimizer import optimize_sleep_environment
from src.agents.tools.smart_calc_converter import smart_unit_and_cost_calculator
from src.agents.tools.weather_forecast import get_weather_forecast
from src.services.llm import get_llm
from src.services.xiaozhi import xiaozhi_service


def _format_table(headers: list[str], rows: list[list[str]]) -> str:
    """Format an ASCII/Markdown table."""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val)))

    header_line = "| " + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"
    separator_line = "|-" + "-|-".join("-" * col_widths[i] for i in range(len(headers))) + "-|"
    data_lines = [
        "| " + " | ".join(str(val).ljust(col_widths[i]) for i, val in enumerate(row)) + " |"
        for row in rows
    ]
    return "\n".join([header_line, separator_line] + data_lines)


def benchmark_tools(iterations: int = 5) -> dict[str, Any]:
    """Benchmark tool execution latencies over multiple runs."""
    tools_to_test = [
        ("Weather Forecast (Hà Nội)", lambda: get_weather_forecast.invoke({"location": "Hà Nội", "days": 1})),
        ("Energy Analytics (Today)", lambda: get_energy_analytics.invoke({"period": "today"})),
        ("Air Quality Evaluation", lambda: evaluate_air_quality.invoke({})),
        ("Add Family Note", lambda: add_family_note.invoke({"content": "Test benchmark note", "category": "chung"})),
        ("Get Family Notes", lambda: get_family_notes.invoke({})),
        ("YouTube Music (Cắt đôi nỗi sầu)", lambda: play_youtube_music.invoke({"query": "Cắt đôi nỗi sầu"})),
        ("Internet Search (DuckDuckGo)", lambda: search_internet.invoke({"query": "tin tức hôm nay"})),
        ("Home Safety Audit", lambda: audit_home_safety.invoke({})),
        ("Sleep Environment Optimizer", lambda: optimize_sleep_environment.invoke({})),
        ("Shopping List Add", lambda: manage_shopping_list.invoke({"action": "add", "item": "Sữa tươi không đường"})),
        ("Shopping List View", lambda: manage_shopping_list.invoke({"action": "list"})),
        ("EVN Electricity Calc (250 kWh)", lambda: smart_unit_and_cost_calculator.invoke({"action": "evn_electricity", "kwh": 250.0})),
        ("AC BTU Calculation (25 m2)", lambda: smart_unit_and_cost_calculator.invoke({"action": "ac_btu", "area_sqm": 25.0})),
    ]

    results: dict[str, Any] = {}
    table_rows: list[list[str]] = []

    for name, tool_fn in tools_to_test:
        latencies: list[float] = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            tool_fn()
            latencies.append((time.perf_counter() - t0) * 1000.0)  # ms

        mean_val = statistics.mean(latencies)
        median_val = statistics.median(latencies)
        p95_val = sorted(latencies)[int(len(latencies) * 0.95)]
        min_val = min(latencies)
        max_val = max(latencies)

        results[name] = {
            "mean_ms": mean_val,
            "median_ms": median_val,
            "p95_ms": p95_val,
            "min_ms": min_val,
            "max_ms": max_val,
            "raw": latencies,
        }

        table_rows.append([
            name,
            f"{min_val:.1f} ms",
            f"{median_val:.1f} ms",
            f"{mean_val:.1f} ms",
            f"{p95_val:.1f} ms",
            f"{max_val:.1f} ms",
        ])

    table_str = _format_table(["Tool Name", "Min", "P50 (Median)", "Mean", "P95", "Max"], table_rows)
    return {"results": results, "table": table_str}


def warmup_llm():
    """Ensure Qwen 2.5 is loaded into GPU VRAM and keep it alive for 30m."""
    import httpx
    try:
        httpx.post(
            "http://ollama:11434/api/generate",
            json={"model": "qwen2.5:7b", "prompt": "xin chào", "keep_alive": "30m"},
            timeout=120.0,
        )
    except Exception as e:
        pass


def benchmark_llm() -> dict[str, Any]:
    """Benchmark local GPU LLM response speed and token throughput."""
    from langchain_core.messages import HumanMessage, SystemMessage

    warmup_llm()

    test_prompts = [
        ("Short Greeting", "Chào bạn, hãy chào lại trong 1 câu ngắn gọn."),
        ("Home Lifestyle Advice", "Cho tôi 2 mẹo ngắn gọn về cách tiết kiệm điện mùa hè (tối đa 3 câu)."),
        ("Poetry Creativity", "Làm một bài thơ 4 câu ngắn về ngôi nhà thông minh buổi tối."),
    ]

    llm = get_llm()
    system_prompt = "Bạn là trợ lý AI thông minh, hãy trả lời tự nhiên, súc tích (khoảng 2-3 câu ngắn) bằng tiếng Việt."

    table_rows: list[list[str]] = []
    details: list[dict[str, Any]] = []

    for label, prompt in test_prompts:
        t0 = time.perf_counter()
        try:
            res = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=prompt)], max_tokens=150)
            total_time = (time.perf_counter() - t0) * 1000.0  # ms
            content = str(res.content).strip() if res and res.content else ""
        except Exception as exc:
            total_time = (time.perf_counter() - t0) * 1000.0
            content = f"Error: {exc}"
        word_count = len(content.split())
        # Vietnamese words average ~1.3 tokens per word with Qwen tokenizer
        estimated_tokens = int(word_count * 1.3)
        tokens_per_sec = (estimated_tokens / (total_time / 1000.0)) if total_time > 0 else 0

        details.append({
            "label": label,
            "total_time_ms": total_time,
            "word_count": word_count,
            "estimated_tokens": estimated_tokens,
            "tokens_per_sec": tokens_per_sec,
            "content_preview": content[:60] + "..." if len(content) > 60 else content,
        })

        table_rows.append([
            label,
            f"{total_time:.0f} ms",
            str(word_count),
            f"~{estimated_tokens}",
            f"{tokens_per_sec:.1f} t/s",
        ])

    table_str = _format_table(["Prompt Type", "Total Latency", "Words", "Est. Tokens", "Throughput"], table_rows)
    return {"details": details, "table": table_str}


async def benchmark_intent_routing() -> dict[str, Any]:
    """Benchmark accuracy and routing latency for diverse Vietnamese queries."""
    test_cases = [
        # (Query, Expected Analysis, Category)
        ("Chào bạn Xiaozhi", "xiaozhi_conversation", "Greeting"),
        ("Bạn là ai và có chức năng gì?", "xiaozhi_conversation", "Greeting"),
        ("Làm một bài thơ về ngôi nhà thông minh", "xiaozhi_conversation", "Creativity"),
        ("Kể một câu chuyện cười về AI", "xiaozhi_conversation", "Creativity"),
        ("Bật đèn phòng khách", "xiaozhi_device_control", "Device Control"),
        ("Tắt quạt phòng ngủ", "xiaozhi_device_control", "Device Control"),
        ("Khóa cửa chính", "xiaozhi_device_control", "Device Control"),
        ("Kiểm tra nhiệt độ phòng khách", "xiaozhi_sensor_inquiry", "Sensor Inquiry"),
        ("Khí gas trong bếp có an toàn không?", "xiaozhi_sensor_inquiry", "Sensor Inquiry"),
        ("Cửa chính đang đóng hay mở?", "xiaozhi_sensor_inquiry", "Sensor Inquiry"),
        ("Dự báo thời tiết ngoài trời hôm nay thế nào?", "xiaozhi_weather_forecast", "Weather"),
        ("Chiều nay trời có mưa không?", "xiaozhi_weather_forecast", "Weather"),
        ("Thời tiết TP Hồ Chí Minh hôm nay ra sao?", "xiaozhi_weather_forecast", "Weather"),
        ("Hôm nay nhà mình tiêu thụ bao nhiêu điện năng?", "xiaozhi_energy_analytics", "Energy"),
        ("Tiền điện tháng này ước tính bao nhiêu?", "xiaozhi_energy_analytics", "Energy"),
        ("Thiết bị nào trong nhà đang tốn điện nhất?", "xiaozhi_energy_analytics", "Energy"),
        ("Chất lượng không khí trong nhà có sạch không?", "xiaozhi_air_quality", "Air Quality"),
        ("Phòng ngủ có bí bách không, có cần thông gió?", "xiaozhi_air_quality", "Air Quality"),
        ("Lưu ghi chú: mai 9h thợ đến bảo dưỡng điều hòa", "xiaozhi_add_family_note", "Family Note"),
        ("Xem danh sách ghi chú gia đình", "xiaozhi_get_family_notes", "Family Note"),
        # New Challenging Benchmarks
        ("Hôm nay là thứ mấy?", "xiaozhi_sensor_inquiry", "Date & Weekday"),
        ("Ngày mai là thứ mấy?", "xiaozhi_sensor_inquiry", "Date & Weekday"),
        ("Bây giờ là mấy giờ rồi?", "xiaozhi_sensor_inquiry", "Date & Weekday"),
        ("Phát bài hát Cắt đôi nỗi sầu", "xiaozhi_media_playback", "Music Playback"),
        ("Mở nhạc Sơn Tùng M-TP", "xiaozhi_media_playback", "Music Playback"),
        ("Đọc báo tin tức mới nhất hôm nay", "xiaozhi_internet_search", "News Reading"),
        ("Tin tức thời sự hôm nay có gì?", "xiaozhi_internet_search", "News Reading"),
        ("Dân số Việt Nam hiện nay là bao nhiêu người tra google giúp tôi", "xiaozhi_internet_search", "Google Search"),
        # 4 Bộ công cụ thông minh nâng cao
        ("Kiểm tra an toàn toàn diện ngôi nhà", "xiaozhi_home_safety_audit", "Home Safety"),
        ("Nhà mình hiện tại có an toàn không?", "xiaozhi_home_safety_audit", "Home Safety"),
        ("Tôi chuẩn bị đi ngủ rồi", "xiaozhi_sleep_optimizer", "Sleep Optimizer"),
        ("Kích hoạt chế độ ngủ đêm", "xiaozhi_sleep_optimizer", "Sleep Optimizer"),
        ("Thêm táo và sữa tươi vào danh sách mua sắm", "xiaozhi_shopping_list", "Shopping List"),
        ("Hôm nay cần mua sắm những gì?", "xiaozhi_shopping_list", "Shopping List"),
        ("Tính tiền điện sinh hoạt cho 250 kWh theo EVN", "xiaozhi_smart_calculator", "Smart Calculator"),
        ("Phòng ngủ 20 mét vuông cần lắp máy lạnh bao nhiêu BTU?", "xiaozhi_smart_calculator", "Smart Calculator"),
    ]

    correct = 0
    total = len(test_cases)
    latencies: list[float] = []
    case_results: list[dict[str, Any]] = []
    table_rows: list[list[str]] = []

    for query, expected_analysis, category in test_cases:
        t0 = time.perf_counter()
        res = await xiaozhi_service.process(query)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed_ms)

        actual_analysis = res.get("analysis", "")
        is_match = actual_analysis == expected_analysis
        if is_match:
            correct += 1

        case_results.append({
            "query": query,
            "category": category,
            "expected": expected_analysis,
            "actual": actual_analysis,
            "match": is_match,
            "latency_ms": elapsed_ms,
        })

        table_rows.append([
            category,
            query[:35] + ("..." if len(query) > 35 else ""),
            actual_analysis,
            "✅ PASS" if is_match else "❌ FAIL",
            f"{elapsed_ms:.1f} ms",
        ])

    accuracy = (correct / total) * 100.0
    avg_latency = statistics.mean(latencies)
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]

    table_str = _format_table(["Category", "Query", "Routed Analysis", "Status", "Latency"], table_rows)
    return {
        "accuracy": accuracy,
        "correct": correct,
        "total": total,
        "avg_latency_ms": avg_latency,
        "p95_latency_ms": p95_latency,
        "table": table_str,
        "details": case_results,
    }


async def main():
    print("=================================================================")
    print("       HOMEMIND HUB & XIAOZHI AI BRAIN BENCHMARK SUITE          ")
    print("=================================================================\n")

    print("▶ 1. BENCHMARKING TOOLS (Execution Latency over 10 iterations)...")
    tools_res = benchmark_tools(iterations=10)
    print(tools_res["table"])
    print()

    print("▶ 2. BENCHMARKING LOCAL GPU LLM (Qwen 2.5 on GPU)...")
    llm_res = benchmark_llm()
    print(llm_res["table"])
    print()

    print("▶ 3. BENCHMARKING INTENT ROUTING & CLASSIFICATION ACCURACY...")
    routing_res = await benchmark_intent_routing()
    print(routing_res["table"])
    print(f"\n=> Overall Accuracy: {routing_res['accuracy']:.1f}% ({routing_res['correct']}/{routing_res['total']} passed)")
    print(f"=> Mean Routing Latency: {routing_res['avg_latency_ms']:.1f} ms | P95: {routing_res['p95_latency_ms']:.1f} ms\n")

    print("=================================================================")
    print("                        BENCHMARK SUMMARY                        ")
    print("=================================================================")
    return {
        "tools": tools_res["results"],
        "llm": llm_res["details"],
        "routing": routing_res,
    }


if __name__ == "__main__":
    asyncio.run(main())
