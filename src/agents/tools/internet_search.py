"""LangChain tool for general Internet information search."""

from __future__ import annotations

import html
import re
import urllib.parse

import httpx
from langchain_core.tools import tool
from pydantic import ConfigDict, Field

from src.agents.tools.base import _StrictToolInput, _tool_result


class SearchInternetInput(_StrictToolInput):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    query: str = Field(
        default="",
        description="Từ khóa, chủ đề hoặc câu hỏi cần tra cứu trên Internet (tin tức, thời tiết, sự kiện...)",
    )
    q: str | None = Field(default=None, description="Từ khóa tra cứu")
    keyword: str | None = Field(default=None, description="Từ khóa tra cứu")
    max_results: int = Field(default=3, ge=1, le=5, description="Số lượng kết quả tìm kiếm tối đa (1 đến 5)")


def _clean_html(raw_html: str) -> str:
    cleaned = re.sub(r"<[^<]+?>", "", raw_html)
    return html.unescape(cleaned).strip()


def _search_tavily(query: str, max_results: int = 3, api_key: str | None = None) -> dict | None:
    """Tìm kiếm thông tin chính xác qua Tavily AI Search Engine."""
    from src.config import get_settings
    key = api_key or get_settings().tavily_api_key or "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"
    if not key:
        return None

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": key,
        "query": query,
        "search_depth": "basic",
        "include_answer": True,
        "max_results": max_results,
    }
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for item in data.get("results", [])[:max_results]:
                    results.append({
                        "title": item.get("title", ""),
                        "snippet": item.get("content", ""),
                        "url": item.get("url", ""),
                        "score": item.get("score", 0.0),
                    })
                return {
                    "answer": data.get("answer", ""),
                    "results": results,
                }
    except Exception:
        pass
    return None


def _search_duckduckgo(query: str, max_results: int = 3) -> list[dict[str, str]]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    try:
        with httpx.Client(timeout=8.0, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code != 200:
                return []

        snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
        links = re.findall(r'<a class="result__url"[^>]*href="([^"]+)"', resp.text)
        results: list[dict[str, str]] = []
        for i in range(min(max_results, len(snippets))):
            s = _clean_html(snippets[i])
            l = links[i].strip() if i < len(links) else ""
            if s:
                results.append({"title": f"Thông tin tra cứu {i+1}", "snippet": s, "url": l})
        return results
    except Exception:
        return []


def _search_bing(query: str, max_results: int = 3) -> list[dict[str, str]]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
    with httpx.Client(timeout=8.0, follow_redirects=True) as client:
        resp = client.get(url, headers=headers)
        if resp.status_code != 200:
            return []

    snippets = re.findall(r'<p class="b_lineclamp[^"]*"[^>]*>(.*?)</p>', resp.text, re.DOTALL)
    if not snippets:
        snippets = re.findall(r'<div class="b_caption"[^>]*><p[^>]*>(.*?)</p>', resp.text, re.DOTALL)

    titles_and_links = re.findall(r'<h2><a[^>]*href="([^"]+)"[^>]*>(.*?)</a></h2>', resp.text, re.DOTALL)
    results: list[dict[str, str]] = []

    for i in range(min(max_results, len(titles_and_links))):
        link, title_html = titles_and_links[i]
        snippet_html = snippets[i] if i < len(snippets) else ""
        title = _clean_html(title_html)
        snippet = _clean_html(snippet_html)
        if title:
            results.append({"title": title, "snippet": snippet, "url": link})

    return results


def _search_wikipedia(query: str, max_results: int = 3) -> list[dict[str, str]]:
    wiki_url = (
        f"https://vi.wikipedia.org/w/api.php?action=query&list=search&"
        f"srsearch={urllib.parse.quote(query)}&format=json&utf8=1"
    )
    headers = {"User-Agent": "HomingHubSmartHome/1.0 (admin@homing.dev)"}
    with httpx.Client(timeout=8.0, follow_redirects=True) as client:
        resp = client.get(wiki_url, headers=headers)
        if resp.status_code != 200:
            return []
        data = resp.json()

    items = data.get("query", {}).get("search", [])
    results: list[dict[str, str]] = []
    for item in items[:max_results]:
        title = item.get("title", "")
        snippet = _clean_html(item.get("snippet", ""))
        url = f"https://vi.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
        results.append({"title": title, "snippet": snippet, "url": url})

    return results


@tool(args_schema=SearchInternetInput)
def search_internet(
    query: str = "",
    q: str | None = None,
    keyword: str | None = None,
    max_results: int = 3,
) -> str:
    """Tìm kiếm thông tin trên Internet về tin tức, thời tiết, sự kiện, kiến thức tổng quát."""
    search_q = (query or q or keyword or "").strip()
    if not search_q:
        return _tool_result("invalid_request", message="Từ khóa tìm kiếm không được để trống.")

    # Loại bỏ các cụm từ đệm mệnh lệnh ("tra google", "hỏi google", "giúp tôi", v.v.)
    clean_q = re.sub(
        r"^(?:tra google|tìm trên google|tìm google|hỏi google|tra cứu google|tra cứu|tìm kiếm|tra|hỏi)\s+",
        "",
        search_q,
        flags=re.I,
    ).strip()
    clean_q = re.sub(r"\s+(?:tra google|trên google|giúp tôi|hộ tôi|nhé|nha)$", "", clean_q, flags=re.I).strip()
    target_q = clean_q or search_q

    try:
        # 1. Ưu tiên tìm kiếm thông minh chuyên sâu bằng Tavily AI Search
        tavily_data = _search_tavily(target_q, max_results=max_results)
        if tavily_data and (tavily_data.get("results") or tavily_data.get("answer")):
            results = tavily_data.get("results", [])
            answer = tavily_data.get("answer", "")
            summary_parts = []
            if answer:
                summary_parts.append(f"**Tóm tắt câu trả lời:** {answer}")
            if results:
                summary_parts.append("\n".join(f"- **{r['title']}**: {r['snippet']} (Nguồn: {r['url']})" for r in results))
            summary_text = "\n\n".join(summary_parts)
            return _tool_result(
                "success",
                engine="tavily",
                query=search_q,
                answer=answer,
                count=len(results),
                results=results,
                summary=summary_text,
            )

        # 2. Fallback sang DuckDuckGo, Bing, Wikipedia nếu không có kết nối Tavily
        results = _search_duckduckgo(target_q, max_results=max_results)
        if not results:
            results = _search_bing(target_q, max_results=max_results)
        if not results:
            results = _search_wikipedia(target_q, max_results=max_results)

        if not results:
            return _tool_result(
                "not_found",
                query=search_q,
                message=f"Không tìm thấy kết quả nào trên Internet cho từ khóa: '{search_q}'.",
            )

        return _tool_result(
            "success",
            engine="fallback",
            query=search_q,
            count=len(results),
            results=results,
            summary="\n\n".join(f"- **{r['title']}**: {r['snippet']} (Nguồn: {r['url']})" for r in results),
        )
    except Exception as exc:
        return _tool_result(
            "error",
            query=search_q,
            error=str(exc),
            message="Không thể kết nối đến dịch vụ tìm kiếm Internet. Vui lòng thử lại sau.",
        )
