from pathlib import Path

KNOWLEDGE_DIR = Path("data/knowledge")


def search_device_guides(query: str) -> list[dict[str, str]]:
    """Dependency-free RAG fallback; replace with Chroma embeddings when indexed."""
    terms = {term.lower() for term in query.split() if len(term) > 2}
    results: list[dict[str, str]] = []
    for path in KNOWLEDGE_DIR.glob("*.md"):
        content = path.read_text(encoding="utf-8")
        score = sum(term in content.lower() for term in terms)
        if score:
            results.append({"source": path.name, "content": content[:900], "score": str(score)})
    return sorted(results, key=lambda item: int(item["score"]), reverse=True)[:3]
