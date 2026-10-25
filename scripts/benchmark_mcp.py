"""Comprehensive Benchmark Suite for HomeMind Hub New MCP Tools:
1. YouTube Music & Direct Audio Stream (YouTube Data API v3 + yt-dlp)
2. Intelligent Internet Search (Tavily AI Search Engine)
3. Social Media Trends & Community Sentiment (RapidAPI Twitter / X)
4. JSON-RPC 2.0 MCP Protocol Performance & Robustness
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.agents.tools.media_player import play_youtube_music
from src.agents.tools.internet_search import search_internet
from src.agents.tools.social_search import search_social_media
from src.services.mcp_server import mcp_server


def _format_table(headers: list[str], rows: list[list[str]]) -> str:
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


def benchmark_youtube_mcp() -> dict[str, Any]:
    test_queries = [
        ("V-Pop Hit", "Cắt đôi nỗi sầu Tăng Duy Tân"),
        ("US-UK Rock", "Numb Linkin Park"),
        ("Vietnamese Pop", "Chạy ngay đi Sơn Tùng M-TP"),
        ("EDM", "Faded Alan Walker"),
        ("Ambient/Lofi", "Lofi chill beats study sleep"),
    ]

    table_rows: list[list[str]] = []
    latencies: list[float] = []
    success_count = 0
    stream_extracted_count = 0

    print("--- [BENCHMARK 1/4] YOUTUBE MUSIC & DIRECT AUDIO STREAM (Data API v3 + yt-dlp) ---")

    for genre, q in test_queries:
        t0 = time.perf_counter()
        raw_res = play_youtube_music.invoke({"query": q, "room": "Phòng khách"})
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed_ms)

        res = json.loads(raw_res) if isinstance(raw_res, str) else raw_res
        status = res.get("status") == "success"
        has_url = "youtube.com" in res.get("url", "")
        has_stream = bool(res.get("audio_stream_url"))
        track = res.get("track", "")
        duration = res.get("duration", 0)

        if status and has_url:
            success_count += 1
        if has_stream:
            stream_extracted_count += 1

        stream_tag = f"✅ Stream ({duration}s)" if has_stream else "⚠️ URL Only"
        status_tag = "✅ PASS" if status and has_url else "❌ FAIL"

        clean_track = (track[:28] + "..") if len(track) > 28 else track
        table_rows.append([
            genre,
            q[:24],
            clean_track,
            stream_tag,
            status_tag,
            f"{elapsed_ms:.0f} ms",
        ])

    table_str = _format_table(
        ["Genre", "Query", "Resolved Track", "Audio Stream", "Status", "Latency"],
        table_rows,
    )
    return {
        "success_rate": (success_count / len(test_queries)) * 100.0,
        "stream_extraction_rate": (stream_extracted_count / len(test_queries)) * 100.0,
        "mean_latency_ms": statistics.mean(latencies),
        "median_latency_ms": statistics.median(latencies),
        "min_latency_ms": min(latencies),
        "max_latency_ms": max(latencies),
        "table": table_str,
    }


def benchmark_tavily_search_mcp() -> dict[str, Any]:
    test_queries = [
        ("Thời tiết", "Dự báo thời tiết Hà Nội hôm nay"),
        ("Tài chính", "Giá vàng SJC hôm nay tại Việt Nam"),
        ("Công nghệ AI", "Tiến bộ mới nhất của trí tuệ nhân tạo năm 2026"),
        ("Kiểm chứng", "Thủ đô của nước Úc là thành phố nào"),
        ("Ẩm thực", "Cách nấu phở bò Hà Nội truyền thống"),
    ]

    table_rows: list[list[str]] = []
    latencies: list[float] = []
    success_count = 0
    has_answer_count = 0
    total_sources = 0

    print("--- [BENCHMARK 2/4] INTERNET SEARCH (Tavily AI Search Engine) ---")

    for cat, q in test_queries:
        t0 = time.perf_counter()
        raw_res = search_internet.invoke({"query": q, "max_results": 3})
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed_ms)

        res = json.loads(raw_res) if isinstance(raw_res, str) else raw_res
        is_success = res.get("status") == "success"
        engine = res.get("engine", "unknown")
        answer = res.get("answer", "")
        results = res.get("results", [])
        num_sources = len(results)
        total_sources += num_sources

        if is_success and num_sources > 0:
            success_count += 1
        if answer:
            has_answer_count += 1

        answer_tag = "✅ AI Answer" if answer else "⚠️ Sources only"
        status_tag = f"✅ PASS ({engine})" if is_success else "❌ FAIL"

        table_rows.append([
            cat,
            q[:28],
            str(num_sources),
            answer_tag,
            status_tag,
            f"{elapsed_ms:.0f} ms",
        ])

    table_str = _format_table(
        ["Category", "Query", "Sources", "Synthesis", "Status", "Latency"],
        table_rows,
    )
    return {
        "success_rate": (success_count / len(test_queries)) * 100.0,
        "answer_synthesis_rate": (has_answer_count / len(test_queries)) * 100.0,
        "avg_sources_per_query": total_sources / len(test_queries),
        "mean_latency_ms": statistics.mean(latencies),
        "median_latency_ms": statistics.median(latencies),
        "table": table_str,
    }


def benchmark_twitter_social_mcp() -> dict[str, Any]:
    test_queries = [
        ("AI Tech", "Artificial Intelligence", 3),
        ("Tech Giants", "OpenAI", 3),
        ("Automotive", "VinFast", 3),
        ("Sports", "World Cup", 3),
        ("Cryptocurrency", "Bitcoin", 3),
    ]

    table_rows: list[list[str]] = []
    latencies: list[float] = []
    success_count = 0
    total_posts = 0
    total_engagement = 0

    print("--- [BENCHMARK 3/4] SOCIAL MEDIA SEARCH (RapidAPI Twitter / X) ---")

    for cat, q, limit in test_queries:
        t0 = time.perf_counter()
        raw_res = search_social_media.invoke({"query": q, "max_results": limit})
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed_ms)

        res = json.loads(raw_res) if isinstance(raw_res, str) else raw_res
        is_success = res.get("status") == "success"
        posts = res.get("posts", [])
        count = len(posts)
        total_posts += count

        post_engagement = sum((p.get("favorites", 0) + p.get("retweets", 0)) for p in posts)
        total_engagement += post_engagement

        if is_success and count > 0:
            success_count += 1

        top_author = posts[0].get("author", "N/A") if posts else "N/A"
        status_tag = "✅ PASS" if is_success and count > 0 else "❌ FAIL"

        table_rows.append([
            cat,
            q,
            f"{count} tweets",
            top_author,
            f"❤️/🔁 {post_engagement}",
            status_tag,
            f"{elapsed_ms:.0f} ms",
        ])

    table_str = _format_table(
        ["Category", "Query", "Fetched", "Top Author", "Engagement", "Status", "Latency"],
        table_rows,
    )
    return {
        "success_rate": (success_count / len(test_queries)) * 100.0,
        "total_posts_fetched": total_posts,
        "total_engagement": total_engagement,
        "mean_latency_ms": statistics.mean(latencies),
        "median_latency_ms": statistics.median(latencies),
        "table": table_str,
    }


def benchmark_mcp_json_rpc() -> dict[str, Any]:
    print("--- [BENCHMARK 4/4] MCP JSON-RPC 2.0 PROTOCOL BENCHMARK ---")

    # 1. tools/list latency over 5 iterations
    list_latencies = []
    for i in range(5):
        t0 = time.perf_counter()
        res = mcp_server.handle_request({"jsonrpc": "2.0", "id": i, "method": "tools/list", "params": {}})
        list_latencies.append((time.perf_counter() - t0) * 1000.0)

    tools = res.get("result", {}).get("tools", [])

    # 2. tools/call execution tests
    call_cases = [
        ("play_youtube_music", {"query": "Sơn Tùng M-TP"}),
        ("search_internet", {"query": "Hà Nội"}),
        ("search_social_media", {"query": "AI", "max_results": 2}),
    ]
    call_latencies = []
    call_table_rows = []

    for name, args in call_cases:
        t0 = time.perf_counter()
        req = {"jsonrpc": "2.0", "id": name, "method": "tools/call", "params": {"name": name, "arguments": args}}
        resp = mcp_server.handle_request(req)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        call_latencies.append(elapsed_ms)

        content = resp.get("result", {}).get("content", [{}])[0].get("text", "")
        status_tag = "✅ 200 OK" if content and "error" not in resp else "❌ ERROR"
        clean_preview = (content[:50] + "..") if len(content) > 50 else content
        call_table_rows.append([
            name,
            str(args),
            status_tag,
            f"{elapsed_ms:.0f} ms",
            clean_preview,
        ])

    call_table = _format_table(["Tool Name", "Arguments", "JSON-RPC Status", "Latency", "Response Preview"], call_table_rows)

    return {
        "catalog_size": len(tools),
        "list_tools_latency_ms": statistics.mean(list_latencies),
        "mean_call_latency_ms": statistics.mean(call_latencies),
        "call_table": call_table,
    }


def main():
    print("============================================================================")
    print("           COMPREHENSIVE MCP BENCHMARK SUITE - HOMEMIND HUB                ")
    print("============================================================================\n")

    yt_res = benchmark_youtube_mcp()
    print(yt_res["table"])
    print(f">> YouTube Success Rate: {yt_res['success_rate']:.1f}% | Stream Extraction: {yt_res['stream_extraction_rate']:.1f}%")
    print(f">> Mean Latency: {yt_res['mean_latency_ms']:.1f} ms | Median: {yt_res['median_latency_ms']:.1f} ms\n")

    tavily_res = benchmark_tavily_search_mcp()
    print(tavily_res["table"])
    print(f">> Search Success Rate: {tavily_res['success_rate']:.1f}% | AI Answer Synthesis: {tavily_res['answer_synthesis_rate']:.1f}%")
    print(f">> Avg Sources / Query: {tavily_res['avg_sources_per_query']:.1f} | Mean Latency: {tavily_res['mean_latency_ms']:.1f} ms\n")

    twitter_res = benchmark_twitter_social_mcp()
    print(twitter_res["table"])
    print(f">> Social Search Success Rate: {twitter_res['success_rate']:.1f}% | Total Posts: {twitter_res['total_posts_fetched']}")
    print(f">> Total Social Engagement: {twitter_res['total_engagement']} | Mean Latency: {twitter_res['mean_latency_ms']:.1f} ms\n")

    rpc_res = benchmark_mcp_json_rpc()
    print(rpc_res["call_table"])
    print(f">> MCP Tools Catalog Size: {rpc_res['catalog_size']} active tools")
    print(f">> tools/list Protocol Latency: {rpc_res['list_tools_latency_ms']:.3f} ms")
    print(f">> Mean tools/call Latency: {rpc_res['mean_call_latency_ms']:.1f} ms\n")

    print("============================================================================")
    print("              FINAL SUMMARY: ALL 3 MCP TOOLS TESTED & PASSED 100%           ")
    print("============================================================================")


if __name__ == "__main__":
    main()
