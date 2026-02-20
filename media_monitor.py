#!/usr/bin/env python3
"""Medieovervåkning med søk, tidsfiltrering og daglig e-postrapport."""

from __future__ import annotations

import argparse
import dataclasses
import email.message
import json
import smtplib
import sqlite3
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable

DB_PATH = Path("autosok.db")
DEFAULT_FEED_SIZE = 100


@dataclasses.dataclass
class Article:
    title: str
    link: str
    source: str
    published: datetime


@dataclasses.dataclass
class AutoSearch:
    id: int
    keyword: str
    start_hour: int
    start_minute: int
    period_hours: int
    email_to: str


def parse_iso_datetime(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def fetch_google_news_rss(keyword: str, feed_size: int = DEFAULT_FEED_SIZE) -> bytes:
    query = urllib.parse.quote(keyword)
    url = (
        "https://news.google.com/rss/search?"
        f"q={query}&hl=no&gl=NO&ceid=NO:no&num={feed_size}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "media-monitor/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.read()
    except Exception as exc:
        raise RuntimeError(f"Kunne ikke hente nyhetsfeed: {exc}") from exc


def parse_rss(xml_bytes: bytes) -> list[Article]:
    root = ET.fromstring(xml_bytes)
    items = root.findall("./channel/item")
    articles: list[Article] = []
    for item in items:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        source = (item.findtext("source") or "Ukjent kilde").strip()
        published_text = (item.findtext("pubDate") or "").strip()

        if not title or not link or not published_text:
            continue

        published = parsedate_to_datetime(published_text)
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)

        articles.append(
            Article(
                title=title,
                link=link,
                source=source,
                published=published.astimezone(timezone.utc),
            )
        )

    return articles


def filter_articles(
    articles: Iterable[Article],
    start: datetime,
    end: datetime,
) -> list[Article]:
    start_utc = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)
    return [a for a in articles if start_utc <= a.published <= end_utc]


def format_report(keyword: str, start: datetime, end: datetime, articles: list[Article]) -> str:
    lines = [
        f"Rapport for søkeord: {keyword}",
        f"Tidsrom: {start.isoformat()} til {end.isoformat()}",
        f"Antall treff: {len(articles)}",
        "",
    ]

    for idx, article in enumerate(sorted(articles, key=lambda a: a.published, reverse=True), start=1):
        lines.append(f"{idx}. {article.title}")
        lines.append(f"   Kilde: {article.source}")
        lines.append(f"   Tid: {article.published.isoformat()}")
        lines.append(f"   Lenke: {article.link}")
        lines.append("")

    return "\n".join(lines)


def send_email_report(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    to_email: str,
    subject: str,
    body: str,
) -> None:
    msg = email.message.EmailMessage()
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=20) as smtp:
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(msg)


def ensure_db(db_path: Path = DB_PATH) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS autosok (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                start_hour INTEGER NOT NULL,
                start_minute INTEGER NOT NULL,
                period_hours INTEGER NOT NULL,
                email_to TEXT NOT NULL
            )
            """
        )


def add_autosok(
    keyword: str,
    time_of_day: str,
    period_hours: int,
    email_to: str,
    db_path: Path = DB_PATH,
) -> None:
    hour, minute = [int(x) for x in time_of_day.split(":", maxsplit=1)]
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO autosok (keyword, start_hour, start_minute, period_hours, email_to)
            VALUES (?, ?, ?, ?, ?)
            """,
            (keyword, hour, minute, period_hours, email_to),
        )


def load_autosok(db_path: Path = DB_PATH) -> list[AutoSearch]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, keyword, start_hour, start_minute, period_hours, email_to FROM autosok"
        ).fetchall()
    return [AutoSearch(*row) for row in rows]


def run_search(keyword: str, start: datetime, end: datetime) -> list[Article]:
    xml_data = fetch_google_news_rss(keyword)
    articles = parse_rss(xml_data)
    return filter_articles(articles, start, end)


def run_pending_autosok(config_path: Path) -> None:
    config = json.loads(config_path.read_text())
    smtp = config["smtp"]
    now = datetime.now(timezone.utc)

    for rule in load_autosok():
        if now.hour != rule.start_hour or now.minute != rule.start_minute:
            continue

        end = now
        start = end - timedelta(hours=rule.period_hours)

        try:
            articles = run_search(rule.keyword, start, end)
            body = format_report(rule.keyword, start, end, articles)
            send_email_report(
                smtp_host=smtp["host"],
                smtp_port=smtp["port"],
                smtp_user=smtp["user"],
                smtp_password=smtp["password"],
                to_email=rule.email_to,
                subject=f"Daglig medieovervåkning: {rule.keyword}",
                body=body,
            )
            print(f"[OK] Sendte rapport for regel {rule.id}")
        except Exception as exc:
            print(f"[FEIL] Regel {rule.id} feilet: {exc}")


def run_scheduler(config_path: Path) -> None:
    print("Starter autosøk-scheduler. Trykk Ctrl+C for å avslutte.")
    while True:
        run_pending_autosok(config_path)
        time.sleep(60)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Medieovervåkning med autosøk")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="Kjør et engangssøk")
    search.add_argument("--keyword", required=True)
    search.add_argument("--start", required=True, help="ISO-dato, f.eks. 2026-01-10T00:00:00+00:00")
    search.add_argument("--end", required=True, help="ISO-dato")

    sub.add_parser("init-db", help="Opprett lokal database for autosøk")

    add = sub.add_parser("add-autosok", help="Legg til daglig autosøk")
    add.add_argument("--keyword", required=True)
    add.add_argument("--time", required=True, help="Klokkeslett HH:MM i UTC")
    add.add_argument("--period-hours", type=int, required=True, help="Se tilbake N timer")
    add.add_argument("--email", required=True)

    scheduler = sub.add_parser("run-scheduler", help="Kjør scheduler som sender rapporter")
    scheduler.add_argument("--config", required=True, help="JSON-fil med SMTP-oppsett")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init-db":
        ensure_db()
        print("Database klar: autosok.db")
        return

    if args.command == "add-autosok":
        ensure_db()
        add_autosok(args.keyword, args.time, args.period_hours, args.email)
        print("Autosøk lagret")
        return

    if args.command == "search":
        start = parse_iso_datetime(args.start)
        end = parse_iso_datetime(args.end)
        try:
            articles = run_search(args.keyword, start, end)
            print(format_report(args.keyword, start, end, articles))
        except RuntimeError as exc:
            print(f"Feil ved søk: {exc}")
        return

    if args.command == "run-scheduler":
        ensure_db()
        run_scheduler(Path(args.config))
        return


if __name__ == "__main__":
    main()
