from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from app.models import Article

logger = logging.getLogger(__name__)
PHRASE_RE = re.compile(r'"([^"]+)"')


def parse_terms(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    phrases = [p.strip().lower() for p in PHRASE_RE.findall(text) if p.strip()]
    remaining = PHRASE_RE.sub(" ", text)
    words = [w.strip().lower() for w in re.split(r"[\s,]+", remaining) if w.strip()]
    return phrases + words


class SearchEngine:
    def __init__(self, db, source_manager) -> None:
        self.db = db
        self.source_manager = source_manager

    def run_search(
        self,
        include_terms_text: str,
        exclude_terms_text: str,
        date_from: datetime | None,
        date_to: datetime | None,
        last_x_days: int | None,
        refresh_sources: bool = True,
    ) -> list[Article]:
        if refresh_sources:
            self._fetch_and_cache()

        include_terms = parse_terms(include_terms_text)
        exclude_terms = parse_terms(exclude_terms_text)
        from_dt, to_dt = self._resolve_range(date_from, date_to, last_x_days)

        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT title, source, published_at, url, summary FROM articles_cache WHERE published_at BETWEEN ? AND ? ORDER BY published_at DESC",
                (from_dt.isoformat(), to_dt.isoformat()),
            ).fetchall()

        results: list[Article] = []
        for row in rows:
            article = Article(
                title=row["title"],
                source=row["source"],
                published_at=datetime.fromisoformat(row["published_at"]),
                url=row["url"] or "",
                summary=row["summary"] or "",
            )
            if self._matches(article, include_terms, exclude_terms):
                results.append(article)
        return results

    def _fetch_and_cache(self) -> None:
        fetched = self.source_manager.fetch_articles()
        now = datetime.now(timezone.utc).isoformat()
        with self.db.connect() as conn:
            for article in fetched:
                try:
                    conn.execute(
                        """
                        INSERT INTO articles_cache(dedup_key, title, source, published_at, url, summary, fetched_at)
                        VALUES(?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(dedup_key) DO NOTHING
                        """,
                        (
                            article.dedup_key(),
                            article.title,
                            article.source,
                            article.published_at.isoformat(),
                            article.url,
                            article.summary,
                            now,
                        ),
                    )
                except Exception as exc:
                    logger.exception("Feil ved caching av artikkel: %s", exc)

    @staticmethod
    def _resolve_range(
        date_from: datetime | None,
        date_to: datetime | None,
        last_x_days: int | None,
    ) -> tuple[datetime, datetime]:
        now = datetime.now(timezone.utc)
        if last_x_days:
            return now - timedelta(days=last_x_days), now
        start = date_from or (now - timedelta(days=1))
        end = date_to or now
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        return start.astimezone(timezone.utc), end.astimezone(timezone.utc)

    @staticmethod
    def _matches(article: Article, include_terms: list[str], exclude_terms: list[str]) -> bool:
        haystack = f"{article.title} {article.summary}".lower()
        if include_terms and not all(term in haystack for term in include_terms):
            return False
        if any(term in haystack for term in exclude_terms):
            return False
        return True
