"""Exa web scraper adapter: minimal stub for web content extraction."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ScrapedChunk:
    url: str
    title: str
    text: str
    links: list[str]


def scrape(urls: list[str]) -> list[ScrapedChunk]:
    return [ScrapedChunk(url=url, title=url, text="", links=[]) for url in urls]
