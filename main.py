from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.database import Database
from app.logging_config import setup_logging
from app.mailer import Mailer
from app.scheduler_service import SchedulerService
from app.search_engine import SearchEngine
from app.services import ReportService, SearchService
from app.sources import SourceManager
from app.ui.main_window import MainWindow, apply_windows_neutral_style


def main() -> int:
    setup_logging()
    db = Database()
    source_manager = SourceManager(db)
    search_engine = SearchEngine(db, source_manager)
    search_service = SearchService(db)
    report_service = ReportService(db)
    mailer = Mailer(db)
    scheduler = SchedulerService(report_service, search_service, search_engine, mailer)

    app = QApplication(sys.argv)
    apply_windows_neutral_style(app)
    window = MainWindow(db, source_manager, search_engine, search_service, report_service, mailer, scheduler)
    window.show()
    scheduler.start()

    try:
        return app.exec()
    finally:
        scheduler.stop()


if __name__ == "__main__":
    raise SystemExit(main())
