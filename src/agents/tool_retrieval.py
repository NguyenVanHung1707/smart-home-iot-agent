"""Registry-derived candidate selection for compact local tool prompts."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from typing import Any

_TOKEN = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)
_STOP_WORDS = frozenset({"cho", "một", "các", "và", "trong", "với", "của", "để", "theo", "này", "đó", "không", "thuộc", "từ", "vựng"})


def _tokens(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFC", value).casefold()
    return {token for token in _TOKEN.findall(normalized) if len(token) > 1 and token not in _STOP_WORDS}


def _tool_document(tool: Any) -> str:
    schema = tool.args_schema.model_json_schema()
    fields = " ".join(f"{name} {definition.get('description', '')}" for name, definition in schema.get("properties", {}).items())
    return " ".join((tool.name.replace("_", " "), tool.description or "", fields))


def retrieve_runtime_tools(query: str, tools: Sequence[Any], *, limit: int = 5, fallback: int = 3) -> list[Any]:
    """Rank live registry schemas by query overlap; retain safe fallback tools.

    This is prompt retrieval only, never intent resolution or an authorization
    decision. All names/schemas come from the runtime tool registry.
    """
    if limit < 1 or fallback < 1:
        raise ValueError("limit and fallback must be positive")
    query_terms = _tokens(query)
    documents = [_tokens(_tool_document(tool)) for tool in tools]
    document_frequency = {term: sum(term in document for document in documents) for term in query_terms}
    # Broad control words such as "bật" and "phòng" are useful to the model,
    # but not discriminative retrieval signals. Prefer terms carried by fewer
    # than half of the live registry descriptions/schemas.
    distinctive_terms = {term for term, count in document_frequency.items() if count and count * 2 < len(tools)}
    scored = []
    for index, (tool, vocabulary) in enumerate(zip(tools, documents, strict=True)):
        score = len(distinctive_terms & vocabulary)
        scored.append((score, index, tool))
    scored.sort(key=lambda item: (-item[0], item[1]))
    chosen = [tool for score, _, tool in scored if score][:limit]
    # Fall back only when retrieval has no evidence.  Once a query does match
    # runtime metadata, adding unrelated static tools defeats prompt reduction.
    if not chosen:
        for _, _, tool in scored:
            if len(chosen) >= min(fallback, limit):
                break
            chosen.append(tool)
    return chosen
