from __future__ import annotations

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests

from app.models import Article

logger = logging.getLogger(__name__)

DEFAULT_RSS_SOURCES = [
    {"name": "Reuters World", "url": "https://feeds.reuters.com/Reuters/worldNews", "enabled": True},
    {"name": "BBC World", "url": "http://feeds.bbci.co.uk/news/world/rss.xml", "enabled": True},
    {"name": "AP Top News", "url": "https://feeds.apnews.com/apf-topnews", "enabled": True},
]


class SourceManager:
    def __init__(self, db) -> None:
        self.db = db

    def get_sources(self) -> list[dict]:
        saved = self.db.get_json_setting("rss_sources", DEFAULT_RSS_SOURCES)
        return saved if isinstance(saved, list) else DEFAULT_RSS_SOURCES

    def save_sources(self, sources: list[dict]) -> None:
        self.db.set_json_setting("rss_sources", sources)

    def fetch_articles(self) -> list[Article]:
        articles: list[Article] = []
        for source in self.get_sources():
            if not source.get("enabled", True):
                continue
            name = source.get("name", "Ukjent")
            url = source.get("url", "")
            if not url:
                continue
            try:
                response = requests.get(url, timeout=20)
                response.raise_for_status()
                feed = feedparser.parse(response.content)
                for entry in feed.entries:
                    title = (entry.get("title") or "").strip()
                    summary = (entry.get("summary") or "").strip()
                    link = (entry.get("link") or "").strip()
                    published = self._extract_date(entry)
                    if title:
                        articles.append(
                            Article(
                                title=title,
                                source=name,
                                published_at=published,
                                url=link,
                                summary=summary,
                            )
                        )
            except Exception as exc:
                logger.exception("Kunne ikke lese kilde %s (%s): %s", name, url, exc)
        return articles

    @staticmethod
    def _extract_date(entry: dict) -> datetime:
        for field in ("published", "updated"):
            value = entry.get(field)
            if value:
                try:
                    dt = parsedate_to_datetime(value)
                    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                except Exception:
                    pass
        return datetime.now(timezone.utc)
