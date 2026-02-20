from __future__ import annotations

import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.models import ReportConfig, SavedSearch
from app.reporting import default_report_filename, export_report_html, render_report_html


class MainWindow(QMainWindow):
    def __init__(self, db, source_manager, search_engine, search_service, report_service, mailer, scheduler_service) -> None:
        super().__init__()
        self.db = db
        self.source_manager = source_manager
        self.search_engine = search_engine
        self.search_service = search_service
        self.report_service = report_service
        self.mailer = mailer
        self.scheduler_service = scheduler_service

        self.setWindowTitle("Medieovervåkning")
        self.resize(1200, 760)
        self._build_ui()
        self._load_searches()
        self._load_reports()
        self._load_settings()

    def _build_ui(self) -> None:
        tabs = QTabWidget()
        tabs.addTab(self._build_search_tab(), "Søk & treff")
        tabs.addTab(self._build_auto_search_tab(), "Automatiske søk")
        tabs.addTab(self._build_reports_tab(), "Rapporter")
        tabs.addTab(self._build_settings_tab(), "Innstillinger")
        self.setCentralWidget(tabs)

    def _build_search_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        form_box = QGroupBox("Søkekriterier")
        form = QGridLayout(form_box)
        self.include_input = QTextEdit()
        self.include_input.setPlaceholderText('Inkluder-ord, f.eks: "ode" torsk, francisella')
        self.exclude_input = QTextEdit()
        self.exclude_input.setPlaceholderText("Ekskluder-ord")
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(datetime.now().date())
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(datetime.now().date())
        self.last_days = QSpinBox()
        self.last_days.setRange(0, 365)
        self.last_days.setValue(7)

        run_btn = QPushButton("Kjør søk")
        run_btn.clicked.connect(self.run_manual_search)
        refresh_btn = QPushButton("Oppdater kilder nå")
        refresh_btn.clicked.connect(lambda: self.run_manual_search(force_refresh=True))

        form.addWidget(QLabel("Inkluder"), 0, 0)
        form.addWidget(self.include_input, 0, 1)
        form.addWidget(QLabel("Ekskluder"), 1, 0)
        form.addWidget(self.exclude_input, 1, 1)
        form.addWidget(QLabel("Fra dato"), 2, 0)
        form.addWidget(self.from_date, 2, 1)
        form.addWidget(QLabel("Til dato"), 3, 0)
        form.addWidget(self.to_date, 3, 1)
        form.addWidget(QLabel("Siste X dager (0=bruk datoer)"), 4, 0)
        form.addWidget(self.last_days, 4, 1)

        buttons = QHBoxLayout()
        buttons.addWidget(run_btn)
        buttons.addWidget(refresh_btn)
        form.addLayout(buttons, 5, 1)

        self.results_table = QTableWidget(0, 4)
        self.results_table.setHorizontalHeaderLabels(["Dato", "Kilde", "Tittel", "Link"])
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.results_table.setSortingEnabled(True)
        self.results_table.cellDoubleClicked.connect(self.open_result_link)

        export_btn = QPushButton("Eksporter HTML-rapport")
        export_btn.clicked.connect(self.export_current_results)

        layout.addWidget(form_box)
        layout.addWidget(self.results_table)
        layout.addWidget(export_btn)
        return page

    def _build_auto_search_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)

        form_box = QGroupBox("Lagre/rediger søk")
        form = QFormLayout(form_box)
        self.search_id_hidden = QLineEdit()
        self.search_id_hidden.hide()
        self.search_name = QLineEdit()
        self.search_include = QLineEdit()
        self.search_exclude = QLineEdit()
        self.search_date_from = QLineEdit()
        self.search_date_from.setPlaceholderText("YYYY-MM-DD")
        self.search_date_to = QLineEdit()
        self.search_date_to.setPlaceholderText("YYYY-MM-DD")
        self.search_last_days = QSpinBox()
        self.search_last_days.setRange(0, 365)

        save_btn = QPushButton("Lagre søk")
        save_btn.clicked.connect(self.save_search)
        clear_btn = QPushButton("Nytt")
        clear_btn.clicked.connect(self.clear_search_form)

        form.addRow("Navn", self.search_name)
        form.addRow("Inkluder", self.search_include)
        form.addRow("Ekskluder", self.search_exclude)
        form.addRow("Fra dato", self.search_date_from)
        form.addRow("Til dato", self.search_date_to)
        form.addRow("Siste X dager", self.search_last_days)
        form.addRow(save_btn, clear_btn)

        right = QVBoxLayout()
        self.searches_list = QListWidget()
        self.searches_list.itemClicked.connect(self.load_search_to_form)
        del_btn = QPushButton("Slett valgt søk")
        del_btn.clicked.connect(self.delete_selected_search)
        right.addWidget(QLabel("Lagrede søk"))
        right.addWidget(self.searches_list)
        right.addWidget(del_btn)

        layout.addWidget(form_box, 2)
        right_wrap = QWidget()
        right_wrap.setLayout(right)
        layout.addWidget(right_wrap, 1)
        return page

    def _build_reports_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)

        form_box = QGroupBox("Rapportoppsett")
        form = QFormLayout(form_box)
        self.report_id_hidden = QLineEdit(); self.report_id_hidden.hide()
        self.report_name = QLineEdit()
        self.report_frequency = QComboBox(); self.report_frequency.addItems(["Daglig", "Ukentlig", "Månedlig"])
        self.report_time = QLineEdit("08:00")
        self.report_email = QLineEdit()
        self.report_enabled = QCheckBox("Aktiv")
        self.report_enabled.setChecked(True)
        self.report_searches = QListWidget(); self.report_searches.setSelectionMode(QAbstractItemView.MultiSelection)

        save_btn = QPushButton("Lagre rapport")
        save_btn.clicked.connect(self.save_report)
        send_test_btn = QPushButton("Send test-epost")
        send_test_btn.clicked.connect(self.send_test_email)

        form.addRow("Navn", self.report_name)
        form.addRow("Frekvens", self.report_frequency)
        form.addRow("Sendetid (HH:MM)", self.report_time)
        form.addRow("Mottaker e-post", self.report_email)
        form.addRow("Knyttede søk", self.report_searches)
        form.addRow("", self.report_enabled)
        form.addRow(save_btn, send_test_btn)

        right = QVBoxLayout()
        self.reports_list = QListWidget()
        self.reports_list.itemClicked.connect(self.load_report_to_form)
        self.scheduler_status = QLabel("Scheduler kjører i bakgrunnen.")
        run_now_btn = QPushButton("Kjør rapport-jobber nå")
        run_now_btn.clicked.connect(self.run_reports_now)
        del_btn = QPushButton("Slett valgt rapport")
        del_btn.clicked.connect(self.delete_selected_report)
        right.addWidget(QLabel("Lagrede rapporter"))
        right.addWidget(self.reports_list)
        right.addWidget(self.scheduler_status)
        right.addWidget(run_now_btn)
        right.addWidget(del_btn)

        layout.addWidget(form_box, 2)
        right_wrap = QWidget(); right_wrap.setLayout(right)
        layout.addWidget(right_wrap, 1)
        return page

    def _build_settings_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        smtp = QGroupBox("E-post (SMTP)")
        smtp_form = QFormLayout(smtp)
        self.smtp_host = QLineEdit()
        self.smtp_port = QLineEdit("465")
        self.smtp_user = QLineEdit()
        self.smtp_password = QLineEdit(); self.smtp_password.setEchoMode(QLineEdit.Password)
        self.smtp_from = QLineEdit()
        save_smtp = QPushButton("Lagre SMTP")
        save_smtp.clicked.connect(self.save_smtp)
        smtp_form.addRow("Host", self.smtp_host)
        smtp_form.addRow("Port", self.smtp_port)
        smtp_form.addRow("Bruker", self.smtp_user)
        smtp_form.addRow("Passord (app-passord)", self.smtp_password)
        smtp_form.addRow("Fra e-post", self.smtp_from)
        smtp_form.addRow(save_smtp)

        sources = QGroupBox("RSS-kilder")
        src_layout = QVBoxLayout(sources)
        self.sources_text = QTextEdit()
        self.sources_text.setPlaceholderText("Ett objekt per linje: Navn|https://...|1")
        save_sources = QPushButton("Lagre kilder")
        save_sources.clicked.connect(self.save_sources)
        src_layout.addWidget(QLabel("Format: Navn|URL|Aktiv(1/0)"))
        src_layout.addWidget(self.sources_text)
        src_layout.addWidget(save_sources)

        layout.addWidget(smtp)
        layout.addWidget(sources)
        return page

    def run_manual_search(self, force_refresh: bool = True) -> None:
        try:
            include = self.include_input.toPlainText()
            exclude = self.exclude_input.toPlainText()
            fx = self.last_days.value() or None
            from_dt = datetime.combine(self.from_date.date().toPython(), datetime.min.time()).replace(tzinfo=timezone.utc)
            to_dt = datetime.combine(self.to_date.date().toPython(), datetime.max.time()).replace(tzinfo=timezone.utc)
            results = self.search_engine.run_search(include, exclude, from_dt, to_dt, fx, refresh_sources=force_refresh)
            self._fill_results_table(results)
            self._current_result_articles = results
        except Exception as exc:
            QMessageBox.critical(self, "Feil", str(exc))

    def _fill_results_table(self, articles) -> None:
        self.results_table.setRowCount(0)
        for art in articles:
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)
            self.results_table.setItem(row, 0, QTableWidgetItem(art.published_at.strftime("%Y-%m-%d %H:%M")))
            self.results_table.setItem(row, 1, QTableWidgetItem(art.source))
            self.results_table.setItem(row, 2, QTableWidgetItem(art.title))
            self.results_table.setItem(row, 3, QTableWidgetItem(art.url))

    def open_result_link(self, row: int, _col: int) -> None:
        item = self.results_table.item(row, 3)
        if item and item.text():
            webbrowser.open(item.text())

    def export_current_results(self) -> None:
        articles = getattr(self, "_current_result_articles", [])
        html = render_report_html("Manuell rapport", "Valgt periode", [], articles)
        default = str(default_report_filename("manuell_rapport"))
        path, _ = QFileDialog.getSaveFileName(self, "Lagre HTML", default, "HTML Files (*.html)")
        if path:
            export_report_html(Path(path), html)
            QMessageBox.information(self, "OK", f"Lagret: {path}")

    def _load_searches(self) -> None:
        self.searches_list.clear()
        self.report_searches.clear()
        for s in self.search_service.list_searches():
            label = f"#{s.id} {s.name}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, s)
            self.searches_list.addItem(item)

            ritem = QListWidgetItem(label)
            ritem.setData(Qt.UserRole, s)
            self.report_searches.addItem(ritem)

    def save_search(self) -> None:
        sid = int(self.search_id_hidden.text()) if self.search_id_hidden.text().strip() else None
        item = SavedSearch(
            id=sid,
            name=self.search_name.text().strip(),
            include_terms=self.search_include.text().strip(),
            exclude_terms=self.search_exclude.text().strip(),
            date_from=self.search_date_from.text().strip() or None,
            date_to=self.search_date_to.text().strip() or None,
            last_x_days=self.search_last_days.value() or None,
        )
        self.search_service.save_search(item)
        self.clear_search_form()
        self._load_searches()

    def clear_search_form(self) -> None:
        self.search_id_hidden.clear(); self.search_name.clear(); self.search_include.clear(); self.search_exclude.clear()
        self.search_date_from.clear(); self.search_date_to.clear(); self.search_last_days.setValue(0)

    def load_search_to_form(self, item: QListWidgetItem) -> None:
        s = item.data(Qt.UserRole)
        self.search_id_hidden.setText(str(s.id))
        self.search_name.setText(s.name)
        self.search_include.setText(s.include_terms)
        self.search_exclude.setText(s.exclude_terms)
        self.search_date_from.setText(s.date_from or "")
        self.search_date_to.setText(s.date_to or "")
        self.search_last_days.setValue(s.last_x_days or 0)

    def delete_selected_search(self) -> None:
        item = self.searches_list.currentItem()
        if not item:
            return
        s = item.data(Qt.UserRole)
        self.search_service.delete_search(s.id)
        self._load_searches()

    def _load_reports(self) -> None:
        self.reports_list.clear()
        for r in self.report_service.list_reports():
            text = f"#{r.id} {r.name} ({r.frequency} {r.send_time}) [{r.last_status or '-'}]"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, r)
            self.reports_list.addItem(item)

    def save_report(self) -> None:
        rid = int(self.report_id_hidden.text()) if self.report_id_hidden.text().strip() else None
        selected_search_ids = []
        for i in range(self.report_searches.count()):
            item = self.report_searches.item(i)
            if item.isSelected():
                selected_search_ids.append(str(item.data(Qt.UserRole).id))
        report = ReportConfig(
            id=rid,
            name=self.report_name.text().strip(),
            search_ids_csv=",".join(selected_search_ids),
            frequency=self.report_frequency.currentText(),
            send_time=self.report_time.text().strip(),
            recipient_email=self.report_email.text().strip(),
            enabled=1 if self.report_enabled.isChecked() else 0,
            last_run_at=None,
            last_status=None,
        )
        self.report_service.save_report(report)
        self._load_reports()

    def load_report_to_form(self, item: QListWidgetItem) -> None:
        r = item.data(Qt.UserRole)
        self.report_id_hidden.setText(str(r.id))
        self.report_name.setText(r.name)
        self.report_frequency.setCurrentText(r.frequency)
        self.report_time.setText(r.send_time)
        self.report_email.setText(r.recipient_email)
        self.report_enabled.setChecked(bool(r.enabled))

    def delete_selected_report(self) -> None:
        item = self.reports_list.currentItem()
        if not item:
            return
        r = item.data(Qt.UserRole)
        self.report_service.delete_report(r.id)
        self._load_reports()

    def run_reports_now(self) -> None:
        self.scheduler_service.run_due_reports()
        self._load_reports()
        QMessageBox.information(self, "Ferdig", "Rapport-jobber kjørt.")

    def send_test_email(self) -> None:
        try:
            html = "<html><body><h3>Test-epost</h3><p>SMTP-oppsett virker.</p></body></html>"
            self.mailer.send_html(self.report_email.text().strip(), "Test fra Medieovervåkning", html)
            QMessageBox.information(self, "OK", "Test-epost sendt")
        except Exception as exc:
            QMessageBox.critical(self, "Feil", str(exc))

    def _load_settings(self) -> None:
        self.smtp_host.setText(self.db.get_setting("smtp_host", ""))
        self.smtp_port.setText(self.db.get_setting("smtp_port", "465"))
        self.smtp_user.setText(self.db.get_setting("smtp_user", ""))
        self.smtp_password.setText(self.db.get_setting("smtp_password", ""))
        self.smtp_from.setText(self.db.get_setting("smtp_from", ""))

        lines = []
        for s in self.source_manager.get_sources():
            lines.append(f"{s.get('name','')}|{s.get('url','')}|{1 if s.get('enabled', True) else 0}")
        self.sources_text.setPlainText("\n".join(lines))

    def save_smtp(self) -> None:
        self.db.set_setting("smtp_host", self.smtp_host.text().strip())
        self.db.set_setting("smtp_port", self.smtp_port.text().strip())
        self.db.set_setting("smtp_user", self.smtp_user.text().strip())
        self.db.set_setting("smtp_password", self.smtp_password.text().strip())
        self.db.set_setting("smtp_from", self.smtp_from.text().strip())
        QMessageBox.information(self, "OK", "SMTP lagret")

    def save_sources(self) -> None:
        sources = []
        for line in self.sources_text.toPlainText().splitlines():
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 2:
                continue
            enabled = len(parts) < 3 or parts[2] != "0"
            sources.append({"name": parts[0], "url": parts[1], "enabled": enabled})
        self.source_manager.save_sources(sources)
        QMessageBox.information(self, "OK", "Kilder lagret")


def apply_windows_neutral_style(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(
        """
        QWidget { font-family: 'Segoe UI'; font-size: 10pt; color: #202020; }
        QMainWindow, QTabWidget::pane { background: #f5f5f5; }
        QGroupBox { border: 1px solid #cfcfcf; border-radius: 4px; margin-top: 10px; padding: 10px; background: #ffffff; }
        QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #303030; }
        QLineEdit, QTextEdit, QDateEdit, QComboBox, QSpinBox, QListWidget, QTableWidget { background: #ffffff; border: 1px solid #c8c8c8; padding: 4px; }
        QPushButton { background: #e9e9e9; border: 1px solid #bdbdbd; padding: 6px 12px; border-radius: 4px; }
        QPushButton:hover { background: #dddddd; }
        QHeaderView::section { background: #efefef; border: 1px solid #d0d0d0; padding: 4px; }
        """
    )
