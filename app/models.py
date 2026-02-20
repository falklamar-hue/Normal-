from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Article:
    title: str
    source: str
    published_at: datetime
    url: str
    summary: str

    def dedup_key(self) -> str:
        if self.url:
            return f"url:{self.url.strip().lower()}"
        date_part = self.published_at.date().isoformat()
        return f"fallback:{self.title.strip().lower()}|{date_part}|{self.source.strip().lower()}"


@dataclass
class SavedSearch:
    id: int | None
    name: str
    include_terms: str
    exclude_terms: str
    date_from: str | None
    date_to: str | None
    last_x_days: int | None


@dataclass
class ReportConfig:
    id: int | None
    name: str
    search_ids_csv: str
    frequency: str
    send_time: str
    recipient_email: str
    enabled: int
    last_run_at: str | None
    last_status: str | None
