import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass
class EmailRecord:
    id: str
    sender_address: str
    sender_domain: str
    display_name: str | None
    subject: str
    date: int
    labels: list[str]
    has_unsubscribe: bool


@dataclass
class SenderRule:
    sender_address: str
    sender_domain: str
    display_name: str | None
    rule: Literal['delete', 'protect']
    source: Literal['auto', 'manual']
    created_at: int
    updated_at: int


@dataclass
class SyncState:
    last_synced_at: int | None
    total_fetched: int


class Database:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS emails (
                id              TEXT PRIMARY KEY,
                sender_address  TEXT NOT NULL,
                sender_domain   TEXT NOT NULL,
                display_name    TEXT,
                subject         TEXT NOT NULL,
                date            INTEGER NOT NULL,
                labels          TEXT NOT NULL,
                has_unsubscribe INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sender_rules (
                sender_address  TEXT PRIMARY KEY,
                sender_domain   TEXT NOT NULL,
                display_name    TEXT,
                rule            TEXT NOT NULL CHECK (rule IN ('delete', 'protect')),
                source          TEXT NOT NULL CHECK (source IN ('auto', 'manual')),
                created_at      INTEGER NOT NULL,
                updated_at      INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_sender_rules_domain
                ON sender_rules(sender_domain);

            CREATE TABLE IF NOT EXISTS sync_state (
                id              INTEGER PRIMARY KEY CHECK (id = 1),
                last_synced_at  INTEGER,
                total_fetched   INTEGER DEFAULT 0
            );

            INSERT OR IGNORE INTO sync_state (id, last_synced_at, total_fetched)
                VALUES (1, NULL, 0);
        """)
        self._conn.commit()

    # --- emails ---

    def replace_emails(self, emails: list[EmailRecord]) -> None:
        cur = self._conn.cursor()
        cur.execute("DELETE FROM emails")
        cur.executemany(
            """INSERT INTO emails
               (id, sender_address, sender_domain, display_name, subject, date, labels, has_unsubscribe)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    e.id,
                    e.sender_address,
                    e.sender_domain,
                    e.display_name,
                    e.subject,
                    e.date,
                    json.dumps(e.labels),
                    int(e.has_unsubscribe),
                )
                for e in emails
            ],
        )
        self._conn.commit()

    def delete_emails_by_ids(self, ids: list[str]) -> None:
        self._conn.executemany(
            "DELETE FROM emails WHERE id = ?", [(i,) for i in ids]
        )
        self._conn.commit()

    def list_emails(self) -> list[EmailRecord]:
        rows = self._conn.execute(
            "SELECT * FROM emails ORDER BY date DESC"
        ).fetchall()
        return [self._row_to_email(r) for r in rows]

    def get_emails_by_ids(self, ids: list[str]) -> list[EmailRecord]:
        placeholders = ','.join('?' * len(ids))
        rows = self._conn.execute(
            f"SELECT * FROM emails WHERE id IN ({placeholders})", ids
        ).fetchall()
        return [self._row_to_email(r) for r in rows]

    def _row_to_email(self, row: sqlite3.Row) -> EmailRecord:
        return EmailRecord(
            id=row['id'],
            sender_address=row['sender_address'],
            sender_domain=row['sender_domain'],
            display_name=row['display_name'],
            subject=row['subject'],
            date=row['date'],
            labels=json.loads(row['labels']),
            has_unsubscribe=bool(row['has_unsubscribe']),
        )

    # --- sender_rules ---

    def upsert_rule(self, rule: SenderRule) -> None:
        now = int(time.time())
        self._conn.execute(
            """INSERT INTO sender_rules
               (sender_address, sender_domain, display_name, rule, source, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(sender_address) DO UPDATE SET
                   rule       = excluded.rule,
                   source     = excluded.source,
                   display_name = COALESCE(excluded.display_name, display_name),
                   updated_at = excluded.updated_at""",
            (
                rule.sender_address,
                rule.sender_domain,
                rule.display_name,
                rule.rule,
                rule.source,
                rule.created_at or now,
                now,
            ),
        )
        self._conn.commit()

    def upsert_rule_no_overwrite_manual(self, rule: SenderRule) -> None:
        """Upsert a rule only if no manual rule already exists for the address."""
        existing = self.get_rule(rule.sender_address)
        if existing and existing.source == 'manual':
            return
        self.upsert_rule(rule)

    def delete_rule(self, sender_address: str) -> None:
        self._conn.execute(
            "DELETE FROM sender_rules WHERE sender_address = ?", (sender_address,)
        )
        self._conn.commit()

    def get_rule(self, sender_address: str) -> SenderRule | None:
        row = self._conn.execute(
            "SELECT * FROM sender_rules WHERE sender_address = ?", (sender_address,)
        ).fetchone()
        return self._row_to_rule(row) if row else None

    def list_rules(self) -> list[SenderRule]:
        rows = self._conn.execute(
            "SELECT * FROM sender_rules ORDER BY updated_at DESC"
        ).fetchall()
        return [self._row_to_rule(r) for r in rows]

    def _row_to_rule(self, row: sqlite3.Row) -> SenderRule:
        return SenderRule(
            sender_address=row['sender_address'],
            sender_domain=row['sender_domain'],
            display_name=row['display_name'],
            rule=row['rule'],
            source=row['source'],
            created_at=row['created_at'],
            updated_at=row['updated_at'],
        )

    # --- sync_state ---

    def get_sync_state(self) -> SyncState:
        row = self._conn.execute("SELECT * FROM sync_state WHERE id = 1").fetchone()
        return SyncState(
            last_synced_at=row['last_synced_at'],
            total_fetched=row['total_fetched'],
        )

    def set_sync_state(self, last_synced_at: int, total_fetched: int) -> None:
        self._conn.execute(
            "UPDATE sync_state SET last_synced_at = ?, total_fetched = ? WHERE id = 1",
            (last_synced_at, total_fetched),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
