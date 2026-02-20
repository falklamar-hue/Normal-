from __future__ import annotations

from app.models import ReportConfig, SavedSearch


class SearchService:
    def __init__(self, db) -> None:
        self.db = db

    def list_searches(self) -> list[SavedSearch]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM searches ORDER BY id DESC").fetchall()
        return [SavedSearch(**dict(row)) for row in rows]

    def save_search(self, item: SavedSearch) -> None:
        with self.db.connect() as conn:
            if item.id:
                conn.execute(
                    """UPDATE searches SET name=?, include_terms=?, exclude_terms=?, date_from=?, date_to=?, last_x_days=? WHERE id=?""",
                    (item.name, item.include_terms, item.exclude_terms, item.date_from, item.date_to, item.last_x_days, item.id),
                )
            else:
                conn.execute(
                    """INSERT INTO searches(name, include_terms, exclude_terms, date_from, date_to, last_x_days) VALUES(?,?,?,?,?,?)""",
                    (item.name, item.include_terms, item.exclude_terms, item.date_from, item.date_to, item.last_x_days),
                )

    def delete_search(self, search_id: int) -> None:
        with self.db.connect() as conn:
            conn.execute("DELETE FROM searches WHERE id=?", (search_id,))


class ReportService:
    def __init__(self, db) -> None:
        self.db = db

    def list_reports(self) -> list[ReportConfig]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM reports ORDER BY id DESC").fetchall()
        return [ReportConfig(**dict(row)) for row in rows]

    def save_report(self, report: ReportConfig) -> None:
        with self.db.connect() as conn:
            if report.id:
                conn.execute(
                    """UPDATE reports SET name=?, search_ids_csv=?, frequency=?, send_time=?, recipient_email=?, enabled=? WHERE id=?""",
                    (report.name, report.search_ids_csv, report.frequency, report.send_time, report.recipient_email, report.enabled, report.id),
                )
            else:
                conn.execute(
                    """INSERT INTO reports(name, search_ids_csv, frequency, send_time, recipient_email, enabled, last_run_at, last_status) VALUES(?,?,?,?,?,?,?,?)""",
                    (
                        report.name,
                        report.search_ids_csv,
                        report.frequency,
                        report.send_time,
                        report.recipient_email,
                        report.enabled,
                        report.last_run_at,
                        report.last_status,
                    ),
                )

    def delete_report(self, report_id: int) -> None:
        with self.db.connect() as conn:
            conn.execute("DELETE FROM reports WHERE id=?", (report_id,))

    def update_report_status(self, report_id: int, ran_at: str, status: str) -> None:
        with self.db.connect() as conn:
            conn.execute("UPDATE reports SET last_run_at=?, last_status=? WHERE id=?", (ran_at, status, report_id))
