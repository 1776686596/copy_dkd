from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path


@dataclass(slots=True)
class LocalFAQEntry:
    questions: list[str]
    answer: str


def _resolve_local_faq_path(path: str) -> Path:
    resolved = Path(path).expanduser()
    if not resolved.is_absolute():
        resolved = Path.cwd() / resolved
    return resolved.resolve()


@lru_cache(maxsize=16)
def _load_local_faq_entries_cached(path: str, mtime_ns: int) -> tuple[LocalFAQEntry, ...]:
    resolved = Path(path)
    with resolved.open('r', encoding='utf-8') as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError('Local FAQ file must be a JSON array')

    entries: list[LocalFAQEntry] = []
    for item in data:
        if not isinstance(item, dict):
            continue

        raw_questions = item.get('questions', [])
        if isinstance(raw_questions, str):
            raw_questions = [raw_questions]

        questions = [str(question).strip() for question in raw_questions if str(question).strip()]
        answer = str(item.get('answer', '')).strip()

        if questions and answer:
            entries.append(LocalFAQEntry(questions=questions, answer=answer))

    return tuple(entries)


def load_local_faq_entries(path: str) -> list[LocalFAQEntry]:
    resolved = _resolve_local_faq_path(path)
    stat = resolved.stat()
    return list(_load_local_faq_entries_cached(str(resolved), stat.st_mtime_ns))


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize('NFKC', text).lower().strip()
    return ''.join(char for char in normalized if char.isalnum())


def _similarity_score(query_text: str, candidate_text: str) -> float:
    normalized_query = _normalize_text(query_text)
    normalized_candidate = _normalize_text(candidate_text)

    if not normalized_query or not normalized_candidate:
        return 0.0

    if normalized_query == normalized_candidate:
        return 1.0

    if len(normalized_query) >= 4 and (
        normalized_query in normalized_candidate or normalized_candidate in normalized_query
    ):
        shorter = min(len(normalized_query), len(normalized_candidate))
        longer = max(len(normalized_query), len(normalized_candidate))
        return shorter / longer

    return SequenceMatcher(None, normalized_query, normalized_candidate).ratio()


def match_local_faq_entry(
    entries: list[LocalFAQEntry], message_text: str, min_similarity: float = 0.95
) -> LocalFAQEntry | None:
    best_entry: LocalFAQEntry | None = None
    best_score = 0.0

    for entry in entries:
        for question in entry.questions:
            score = _similarity_score(message_text, question)
            if score > best_score:
                best_score = score
                best_entry = entry

    if best_score >= min_similarity:
        return best_entry

    return None
