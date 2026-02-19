#!/usr/bin/env python3
"""Enkel web-UI for medieovervåkning uten eksterne avhengigheter."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from media_monitor import (
    add_autosok,
    ensure_db,
    format_report,
    load_autosok,
    parse_iso_datetime,
    run_search,
)

HOST = "0.0.0.0"
PORT = 8080


class MediaMonitorHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/":
            self.send_error(HTTPStatus.NOT_FOUND, "Fant ikke siden")
            return

        self._send_html(self._render_page())

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in {"/search", "/add-autosok"}:
            self.send_error(HTTPStatus.NOT_FOUND, "Fant ikke siden")
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(content_length).decode("utf-8")
        form = parse_qs(payload)

        if self.path == "/search":
            html = self._handle_search(form)
            self._send_html(html)
            return

        html = self._handle_add_autosok(form)
        self._send_html(html)

    def _handle_search(self, form: dict[str, list[str]]) -> str:
        keyword = form.get("keyword", [""])[0].strip()
        start_text = form.get("start", [""])[0].strip()
        end_text = form.get("end", [""])[0].strip()

        if not keyword or not start_text or not end_text:
            return self._render_page(error="Fyll inn søkeord, start og sluttid.")

        try:
            start = parse_iso_datetime(start_text)
            end = parse_iso_datetime(end_text)
            articles = run_search(keyword, start, end)
            report = format_report(keyword, start, end, articles)
            return self._render_page(report=report)
        except ValueError:
            return self._render_page(error="Ugyldig datoformat. Bruk ISO-format.")
        except RuntimeError as exc:
            return self._render_page(error=f"Kunne ikke fullføre søket: {exc}")

    def _handle_add_autosok(self, form: dict[str, list[str]]) -> str:
        keyword = form.get("keyword", [""])[0].strip()
        time_of_day = form.get("time", [""])[0].strip()
        period_text = form.get("period_hours", [""])[0].strip()
        email = form.get("email", [""])[0].strip()

        if not keyword or not time_of_day or not period_text or not email:
            return self._render_page(error="Fyll inn alle felter for autosøk.")

        try:
            period_hours = int(period_text)
            add_autosok(keyword, time_of_day, period_hours, email)
            return self._render_page(message="Autosøk lagret.")
        except ValueError:
            return self._render_page(error="Ugyldig input. Sjekk klokkeslett (HH:MM) og antall timer.")

    def _render_page(self, report: str = "", message: str = "", error: str = "") -> str:
        ensure_db()
        autosok = load_autosok()
        now = datetime.now(timezone.utc).replace(microsecond=0)
        table_rows = "".join(
            "<tr>"
            f"<td>{rule.id}</td>"
            f"<td>{escape(rule.keyword)}</td>"
            f"<td>{rule.start_hour:02d}:{rule.start_minute:02d} UTC</td>"
            f"<td>{rule.period_hours}</td>"
            f"<td>{escape(rule.email_to)}</td>"
            "</tr>"
            for rule in autosok
        )
        if not table_rows:
            table_rows = "<tr><td colspan='5'>Ingen autosøk lagret ennå.</td></tr>"

        notice = ""
        if message:
            notice = f"<p style='color: #0a7a00'><b>{escape(message)}</b></p>"
        if error:
            notice = f"<p style='color: #c60000'><b>{escape(error)}</b></p>"

        report_html = ""
        if report:
            report_html = f"<h2>Søkeresultat</h2><pre>{escape(report)}</pre>"

        return f"""
<!doctype html>
<html lang="no">
<head>
  <meta charset="utf-8">
  <title>Medieovervåkning</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem auto; max-width: 980px; line-height: 1.4; }}
    h1, h2 {{ margin-bottom: 0.5rem; }}
    .box {{ border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }}
    label {{ display: block; margin-top: 0.6rem; font-weight: 600; }}
    input {{ width: 100%; padding: 0.5rem; margin-top: 0.2rem; box-sizing: border-box; }}
    button {{ margin-top: 0.8rem; padding: 0.6rem 1rem; cursor: pointer; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border: 1px solid #ddd; padding: 0.5rem; text-align: left; }}
    pre {{ white-space: pre-wrap; background: #f7f7f7; padding: 1rem; border-radius: 8px; }}
    .muted {{ color: #666; }}
  </style>
</head>
<body>
  <h1>Medieovervåkning</h1>
  <p class="muted">Nå: {now.isoformat()} (UTC)</p>
  {notice}

  <div class="box">
    <h2>Engangssøk</h2>
    <form method="post" action="/search">
      <label for="search-keyword">Søkeord</label>
      <input id="search-keyword" name="keyword" placeholder="f.eks. Equinor" required>

      <label for="search-start">Starttid (ISO)</label>
      <input id="search-start" name="start" value="{now.replace(hour=0, minute=0, second=0).isoformat()}" required>

      <label for="search-end">Sluttid (ISO)</label>
      <input id="search-end" name="end" value="{now.isoformat()}" required>

      <button type="submit">Kjør søk</button>
    </form>
  </div>

  <div class="box">
    <h2>Legg til daglig autosøk</h2>
    <form method="post" action="/add-autosok">
      <label for="auto-keyword">Søkeord</label>
      <input id="auto-keyword" name="keyword" required>

      <label for="auto-time">Tidspunkt (HH:MM i UTC)</label>
      <input id="auto-time" name="time" placeholder="07:30" required>

      <label for="auto-period">Se tilbake (timer)</label>
      <input id="auto-period" type="number" min="1" name="period_hours" value="24" required>

      <label for="auto-email">E-post mottaker</label>
      <input id="auto-email" type="email" name="email" placeholder="deg@eksempel.no" required>

      <button type="submit">Lagre autosøk</button>
    </form>
  </div>

  <div class="box">
    <h2>Lagrede autosøk</h2>
    <table>
      <thead>
        <tr><th>ID</th><th>Søkeord</th><th>Tidspunkt</th><th>Timer</th><th>E-post</th></tr>
      </thead>
      <tbody>{table_rows}</tbody>
    </table>
  </div>

  {report_html}
</body>
</html>
"""

    def _send_html(self, html: str) -> None:
        data = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    ensure_db()
    server = ThreadingHTTPServer((HOST, PORT), MediaMonitorHandler)
    print(f"Webgrensesnitt startet på http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
