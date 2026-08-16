"""SQLite storage. Parameterized queries only."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from finance_agent.config import ACCOUNT_KINDS, CATEGORIES, DATA_DIR, DB_PATH, GOAL_KINDS

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'INR',
    category TEXT NOT NULL DEFAULT 'OTHER',
    source_file TEXT,
    account TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_tx_category ON transactions(category);
CREATE TABLE IF NOT EXISTS budgets (
    category TEXT NOT NULL,
    period TEXT NOT NULL,
    amount REAL NOT NULL,
    PRIMARY KEY (category, period)
);
CREATE TABLE IF NOT EXISTS accounts (
    name TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    balance REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    target REAL NOT NULL,
    current REAL NOT NULL DEFAULT 0,
    deadline TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def insert_many(rows: Iterable[dict[str, Any]]) -> int:
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    added = 0
    with connect() as conn:
        for row in rows:
            exists = conn.execute(
                """
                SELECT 1 FROM transactions
                WHERE date = ? AND description = ? AND amount = ?
                LIMIT 1
                """,
                (row["date"], row["description"], row["amount"]),
            ).fetchone()
            if exists:
                continue
            conn.execute(
                """
                INSERT INTO transactions
                    (date, description, amount, currency, category, source_file, account, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["date"],
                    row["description"],
                    float(row["amount"]),
                    row.get("currency") or "INR",
                    row.get("category") or "OTHER",
                    row.get("source_file"),
                    row.get("account"),
                    now,
                ),
            )
            added += 1
    return added


def list_transactions(limit: int = 500) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, date, description, amount, currency, category, source_file, account
            FROM transactions
            ORDER BY date DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def search(  # noqa: PLR0913
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | None = None,
    text: str | None = None,
    account: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    sql = [
        "SELECT id, date, description, amount, currency, category, source_file, account",
        "FROM transactions WHERE 1=1",
    ]
    params: list[Any] = []
    if start_date:
        sql.append("AND date >= ?")
        params.append(start_date)
    if end_date:
        sql.append("AND date <= ?")
        params.append(end_date)
    if category:
        sql.append("AND category = ?")
        params.append(category)
    if text:
        sql.append("AND description LIKE ?")
        params.append(f"%{text}%")
    if account:
        sql.append("AND account = ?")
        params.append(account)
    sql.append("ORDER BY date DESC, id DESC LIMIT ?")
    params.append(min(max(int(limit), 1), 500))
    with connect() as conn:
        rows = conn.execute(" ".join(sql), params).fetchall()
    return [dict(r) for r in rows]


def summary() -> dict[str, float | int]:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS n,
                COALESCE(SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END), 0) AS spent,
                COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) AS income
            FROM transactions
            """
        ).fetchone()
    return {"count": int(row["n"]), "spent": float(row["spent"]), "income": float(row["income"])}


def date_span() -> tuple[str | None, str | None]:
    with connect() as conn:
        row = conn.execute("SELECT MIN(date) AS a, MAX(date) AS b FROM transactions").fetchone()
    if not row or not row["a"]:
        return None, None
    return str(row["a"]), str(row["b"])


def upsert_budget(category: str, period: str, amount: float) -> None:
    if category not in CATEGORIES:
        msg = f"Unknown category: {category}"
        raise ValueError(msg)
    if amount < 0:
        msg = "Budget must be >= 0"
        raise ValueError(msg)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO budgets (category, period, amount) VALUES (?, ?, ?)
            ON CONFLICT(category, period) DO UPDATE SET amount = excluded.amount
            """,
            (category, period, float(amount)),
        )


def list_budgets(period: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT category, period, amount FROM budgets WHERE period = ? ORDER BY category",
            (period,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_category(tx_id: int, category: str) -> None:
    if category not in CATEGORIES:
        msg = f"Unknown category: {category}"
        raise ValueError(msg)
    with connect() as conn:
        conn.execute("UPDATE transactions SET category = ? WHERE id = ?", (category, tx_id))


def update_account(tx_id: int, account: str | None) -> None:
    with connect() as conn:
        conn.execute("UPDATE transactions SET account = ? WHERE id = ?", (account or None, tx_id))


def upsert_account(name: str, kind: str, balance: float) -> None:
    label = name.strip()
    if not label:
        msg = "Account name required"
        raise ValueError(msg)
    if kind not in ACCOUNT_KINDS:
        msg = f"Unknown account kind: {kind}"
        raise ValueError(msg)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO accounts (name, kind, balance) VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET kind = excluded.kind, balance = excluded.balance
            """,
            (label, kind, float(balance)),
        )


def list_accounts() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT name, kind, balance FROM accounts ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def upsert_goal(name: str, kind: str, target: float, current: float, deadline: str | None) -> None:
    if kind not in GOAL_KINDS:
        msg = f"Unknown goal kind: {kind}"
        raise ValueError(msg)
    if target <= 0:
        msg = "Target must be > 0"
        raise ValueError(msg)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO goals (name, kind, target, current, deadline)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name.strip(), kind, float(target), float(current), deadline or None),
        )


def list_goals() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, name, kind, target, current, deadline FROM goals ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def append_message(role: str, content: str) -> None:
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    with connect() as conn:
        conn.execute(
            "INSERT INTO messages (role, content, created_at) VALUES (?, ?, ?)",
            (role, content, now),
        )


def list_messages(limit: int = 40) -> list[dict[str, str]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?",
            (min(max(int(limit), 1), 100),),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def get_setting(key: str, default: str = "") -> str:
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return str(row["value"]) if row else default


def set_setting(key: str, value: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


def is_local_only() -> bool:
    return get_setting("local_only", "0") == "1"


def set_local_only(*, on: bool) -> None:
    set_setting("local_only", "1" if on else "0")


def privacy_stats() -> dict[str, Any]:
    with connect() as conn:
        counts = {
            "transactions": conn.execute("SELECT COUNT(*) AS n FROM transactions").fetchone()["n"],
            "budgets": conn.execute("SELECT COUNT(*) AS n FROM budgets").fetchone()["n"],
            "accounts": conn.execute("SELECT COUNT(*) AS n FROM accounts").fetchone()["n"],
            "goals": conn.execute("SELECT COUNT(*) AS n FROM goals").fetchone()["n"],
            "messages": conn.execute("SELECT COUNT(*) AS n FROM messages").fetchone()["n"],
        }
    return {"db_path": str(DB_PATH), "local_only": is_local_only(), **counts}


def clear_messages() -> None:
    with connect() as conn:
        conn.execute("DELETE FROM messages")


def wipe_ledger() -> None:
    with connect() as conn:
        conn.execute("DELETE FROM transactions")


def wipe_all() -> None:
    with connect() as conn:
        conn.execute("DELETE FROM transactions")
        conn.execute("DELETE FROM budgets")
        conn.execute("DELETE FROM accounts")
        conn.execute("DELETE FROM goals")
        conn.execute("DELETE FROM messages")
