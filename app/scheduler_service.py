from __future__ import annotations

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.models import SavedSearch
from app.reporting import render_report_html

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self, report_service, search_service, search_engine, mailer) -> None:
        self.report_service = report_service
        self.search_service = search_service
        self.search_engine = search_engine
        self.mailer = mailer
        self.scheduler = BackgroundScheduler()

    def start(self) -> None:
        self.scheduler.add_job(self.run_due_reports, "interval", minutes=1, id="due_reports", replace_existing=True)
        self.scheduler.start()

    def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def run_due_reports(self) -> None:
        now = datetime.now()
        for report in self.report_service.list_reports():
            if not report.enabled:
                continue
            if not self._is_due(report.frequency, report.send_time, now):
                continue
            try:
                search_ids = [int(s) for s in report.search_ids_csv.split(",") if s.strip().isdigit()]
                saved_searches = [s for s in self.search_service.list_searches() if s.id in search_ids]
                articles = self._collect_articles(saved_searches)
                period = self._period_label(report.frequency, now)
                html = render_report_html(report.name, period, saved_searches, articles)
                self.mailer.send_html(report.recipient_email, f"Medierapport: {report.name}", html)
                self.report_service.update_report_status(report.id, now.isoformat(timespec="seconds"), "OK")
            except Exception as exc:
                logger.exception("Feil i scheduler for rapport %s", report.name)
                self.report_service.update_report_status(report.id, now.isoformat(timespec="seconds"), f"FEIL: {exc}")

    def _collect_articles(self, searches: list[SavedSearch]):
        all_articles = []
        seen = set()
        for s in searches:
            date_from = datetime.fromisoformat(s.date_from) if s.date_from else None
            date_to = datetime.fromisoformat(s.date_to) if s.date_to else None
            results = self.search_engine.run_search(
                s.include_terms,
                s.exclude_terms,
                date_from,
                date_to,
                s.last_x_days,
                refresh_sources=True,
            )
            for article in results:
                key = article.dedup_key()
                if key not in seen:
                    seen.add(key)
                    all_articles.append(article)
        all_articles.sort(key=lambda a: a.published_at, reverse=True)
        return all_articles

    @staticmethod
    def _is_due(frequency: str, send_time: str, now: datetime) -> bool:
        hh, mm = [int(x) for x in send_time.split(":")]
        if now.hour != hh or now.minute != mm:
            return False
        if frequency == "Daglig":
            return True
        if frequency == "Ukentlig":
            return now.weekday() == 0
        if frequency == "Månedlig":
            return now.day == 1
        return False

    @staticmethod
    def _period_label(frequency: str, now: datetime) -> str:
        if frequency == "Daglig":
            start = now - timedelta(days=1)
        elif frequency == "Ukentlig":
            start = now - timedelta(days=7)
        else:
            start = now - timedelta(days=30)
        return f"{start.strftime('%Y-%m-%d')} til {now.strftime('%Y-%m-%d')}"
