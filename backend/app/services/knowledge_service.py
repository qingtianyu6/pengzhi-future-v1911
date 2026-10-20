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


@lru_cache(maxsize=2)
def _read_knowledge(files: tuple[tuple[str,int], ...]) -> list[dict[str, Any]]:
    entries=[]
    for filename,_ in files:
        data=json.loads(Path(filename).read_text(encoding="utf-8"))
        if isinstance(data,list):entries.extend(data)
    return entries


def load_knowledge() -> list[dict[str, Any]]:
    paths=[KNOWLEDGE_FILE,KNOWLEDGE_FILE.with_name("knowledge_zh.json")]
    return _read_knowledge(tuple((str(p),p.stat().st_mtime_ns) for p in paths if p.is_file()))


def _category(item):
    if item.get("category"):return item["category"]
    if item.get("id") in {"greenhouse-data-quality","agent-safety-boundary","sensor-integration-guide"}:return "平台与数据"
    if "disease" in item.get("topics",[]) or any(w in item.get("title","") for w in ("病","病毒")):return "病害与虫害"
    return "环境与气象"


def _stage_matches(stages,stage):
    if not stage or not stages:return True
    return stage in stages


def _entry_text(entry: dict[str, Any]) -> str:
    return " ".join([
        str(entry.get("title", "")),
        str(entry.get("summary", "")),
        " ".join(entry.get("keywords", [])),
        " ".join(entry.get("topics", [])),
        " ".join(entry.get("crops", [])),
        " ".join(entry.get("guidance", [])),
    ])


def search_knowledge(query: str, limit: int = 4, *, db=None, crop=None, stage=None) -> list[dict[str, Any]]:
    crop = crop or ("muskmelon" if "甜瓜" in query else "tomato" if "番茄" in query else None)
    query_tokens = _tokens(query)
    entries = load_knowledge()
    scored: list[tuple[float, dict[str, Any]]] = []
    for entry in entries:
        crops = entry.get("crops", [])
        if crop and crop not in crops:
            continue
        if not _stage_matches(entry.get("stages",[]),stage):
            continue
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
            meaningful = {t for t in query_tokens if len(t) >= 2}
            if score <= 0 or not meaningful.intersection(body_tokens):
                continue
        else:
            score = 0.1
        scored.append((score, entry))

    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [entry for _, entry in scored[:limit]]
    result = [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "summary": item.get("summary"),
            "guidance": item.get("guidance", []),
            "sources": item.get("sources", []),
            "source_type": "curated_local",
            "position": "本地农业知识条目",
            "source_quality": "curated_reference",
            "crops": item.get("crops", []),
            "stages": item.get("stages", []),
            "category": _category(item),
            "topics": item.get("topics", []),
            "applicability": item.get("applicability", "通用参考，请核对作物、地区与现场条件。"),
            "updated_at": item.get("updated_at"),
            "language": item.get("language", "zh-CN"),
        }
        for item in selected
    ]
    if db is not None:
        from sqlalchemy import select
        from app.models.community import KnowledgeDocument, KnowledgeChunk
        from app.services.access import actor
        rows = db.execute(select(KnowledgeDocument, KnowledgeChunk).join(KnowledgeChunk).where(
            KnowledgeDocument.organization_id == actor().organization_id,
            KnowledgeDocument.status == "ready", KnowledgeDocument.source_quality == "reviewed"))
        ranked = []
        for d, c in rows:
            if crop and crop not in d.crops: continue
            if stage and d.stages and stage not in d.stages: continue
            tokens = _tokens(d.title+" "+c.content)
            overlap = {t for t in query_tokens & tokens if len(t) >= 2}
            if not overlap: continue
            ranked.append((len(overlap), d, c))
        ranked.sort(key=lambda row: row[0], reverse=True)
        imported = [{"id": f"document-{d.id}-chunk-{c.id}", "title": d.title, "summary": c.content,
            "guidance": [], "sources": [{"name": d.title, "url": d.source_url, "document_id": d.id,
                                       "chunk_id": c.id, "position": c.position}],
            "source_type": "document", "source_quality": d.source_quality, "position": c.position,
            "updated_at": d.updated_at.isoformat(), "applicability": d.applicability, "crops": d.crops}
            for _, d, c in ranked[:limit]]
        result = imported + result
    return result[:limit]


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
