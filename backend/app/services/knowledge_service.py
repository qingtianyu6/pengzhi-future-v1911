from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any

from app.config import BACKEND_DIR


KNOWLEDGE_FILE = BACKEND_DIR / "knowledge_base" / "knowledge.json"


def _tokens(text: str) -> set[str]:
    normalized = text.lower().strip()
    ascii_words = set(re.findall(r"[a-z0-9_+-]{2,}", normalized))
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", normalized))
    chars = {ch for ch in chinese if ch.strip()}
    bigrams = {chinese[index:index + 2] for index in range(max(0, len(chinese) - 1))}
    return ascii_words | chars | bigrams


@lru_cache(maxsize=1)
def load_knowledge() -> list[dict[str, Any]]:
    if not KNOWLEDGE_FILE.is_file():
        return []
    with KNOWLEDGE_FILE.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, list) else []


def _entry_text(entry: dict[str, Any]) -> str:
    return " ".join([
        str(entry.get("title", "")),
        str(entry.get("summary", "")),
        " ".join(entry.get("keywords", [])),
        " ".join(entry.get("topics", [])),
        " ".join(entry.get("crops", [])),
        " ".join(entry.get("guidance", [])),
    ])


def search_knowledge(query: str, limit: int = 4) -> list[dict[str, Any]]:
    query_tokens = _tokens(query)
    entries = load_knowledge()
    scored: list[tuple[float, dict[str, Any]]] = []
    for entry in entries:
        title_tokens = _tokens(str(entry.get("title", "")))
        keyword_tokens = _tokens(" ".join(entry.get("keywords", [])))
        body_tokens = _tokens(_entry_text(entry))
        if query_tokens:
            score = (
                4.0 * len(query_tokens & title_tokens)
                + 3.0 * len(query_tokens & keyword_tokens)
                + 1.0 * len(query_tokens & body_tokens)
            )
            # 长问题中常有“怎么、如何、现在”等通用词，至少命中一个主题词才算相关。
            if score <= 0:
                continue
        else:
            score = 0.1
        scored.append((score, entry))

    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [entry for _, entry in scored[:limit]]
    if not selected and entries:
        selected = entries[: min(limit, len(entries))]
    return [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "summary": item.get("summary"),
            "guidance": item.get("guidance", []),
            "sources": item.get("sources", []),
        }
        for item in selected
    ]


def knowledge_catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "topics": item.get("topics", []),
            "crops": item.get("crops", []),
        }
        for item in load_knowledge()
    ]
