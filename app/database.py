from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB_PATH = Path("media_monitor.db")


class Database:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    include_terms TEXT NOT NULL,
                    exclude_terms TEXT DEFAULT '',
                    date_from TEXT,
                    date_to TEXT,
                    last_x_days INTEGER
                );

                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    search_ids_csv TEXT NOT NULL,
                    frequency TEXT NOT NULL,
                    send_time TEXT NOT NULL,
                    recipient_email TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_run_at TEXT,
                    last_status TEXT
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS articles_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dedup_key TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    url TEXT,
                    summary TEXT,
                    fetched_at TEXT NOT NULL
                );
                """
            )

    def get_setting(self, key: str, default: str = "") -> str:
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def get_json_setting(self, key: str, default_value: list[dict] | dict) -> list[dict] | dict:
        raw = self.get_setting(key, "")
        if not raw:
            return default_value
        return json.loads(raw)

    def set_json_setting(self, key: str, value: list[dict] | dict) -> None:
        self.set_setting(key, json.dumps(value, ensure_ascii=False))
