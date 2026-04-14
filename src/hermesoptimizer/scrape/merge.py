from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ScrapedChunk:
    url: str
    title: str
    text: str
    links: list[str]


def merge_chunks(chunks: list[ScrapedChunk]) -> list[ScrapedChunk]:
    seen: set[str] = set()
    merged: list[ScrapedChunk] = []
    for chunk in chunks:
        if chunk.url in seen:
            continue
        seen.add(chunk.url)
        merged.append(chunk)
    return merged
