"""SQLite storage. Parameterized queries only.

Owns the schema and every read/write to data/finance.db. Keep business
logic (categorization, insights, report text) in the other modules, not
here. See vault.py for the at-rest encryption that sits in front of
DB_PATH, and categorize.py for how a row's category/merchant are decided
before reaching insert_many().
"""

from __future__ import annotations

import csv
import io
import json
import sqlite3
import zipfile
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from finance_agent.config import ACCOUNT_KINDS, CATEGORIES, DATA_DIR, DB_PATH, GOAL_KINDS

# Additive-only schema: new columns for existing installs are added in
# _migrate() below, not by editing the CREATE TABLE here. Renaming or
# retyping a column would break older databases with no migration path.
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
    merchant TEXT,
    parent_id INTEGER,
    created_at TEXT NOT NULL
);
-- parent_id is meant to link a split's child rows back to the original
-- transaction, and list_transactions()/search() below filter on
-- "parent_id IS NULL" to hide children from the main ledger view. No code
-- path currently sets it to non-NULL: split_transaction() deletes the
-- original row and inserts replacements with parent_id left NULL.
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
CREATE TABLE IF NOT EXISTS user_rules (
    id INTEGER PRIMARY KEY,
    needle TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY,
    merchant TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_corr_merchant ON corrections(merchant);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    dedupe TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    read INTEGER NOT NULL DEFAULT 0
);
"""

TX_COLS = "id, date, description, amount, currency, category, source_file, account, merchant, parent_id"
GET_TX_SQL = (
    "SELECT id, date, description, amount, currency, category, source_file, account, merchant, parent_id "
    "FROM transactions WHERE id = ?"
)
SPLIT_MIN_PARTS = 2
SPLIT_TOL = 0.02  # amounts are stored as REAL; allow for float rounding when parts must sum to the original


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    # Runs on every connect(); cheap PRAGMA check makes each ALTER idempotent
    # so older databases (created before these columns existed) catch up
    # without a separate migration step.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(transactions)")}
    if "merchant" not in cols:
        conn.execute("ALTER TABLE transactions ADD COLUMN merchant TEXT")
    if "parent_id" not in cols:
        conn.execute("ALTER TABLE transactions ADD COLUMN parent_id INTEGER")


def insert_many(rows: Iterable[dict[str, Any]]) -> int:
    # Dedupe key is (date, description, amount) — exact match, no source_file
    # or id involved. Re-ingesting the same statement is a no-op, but two
    # genuinely different transactions that happen to share all three fields
    # will also be silently skipped as a false duplicate.
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
                    (date, description, amount, currency, category, source_file, account,
                     merchant, parent_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["date"],
                    row["description"],
                    float(row["amount"]),
                    row.get("currency") or "INR",
                    row.get("category") or "OTHER",
                    row.get("source_file"),
                    row.get("account"),
                    row.get("merchant"),
                    row.get("parent_id"),
                    now,
                ),
            )
            added += 1
    return added


def list_transactions(limit: int = 500) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, date, description, amount, currency, category, source_file, account, merchant
            FROM transactions
            WHERE parent_id IS NULL
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
        f"SELECT {TX_COLS}",
        "FROM transactions WHERE parent_id IS NULL",
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


def get_transaction(tx_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(GET_TX_SQL, (tx_id,)).fetchone()
    return dict(row) if row else None


def update_category(tx_id: int, category: str) -> None:
    if category not in CATEGORIES:
        msg = f"Unknown category: {category}"
        raise ValueError(msg)
    with connect() as conn:
        row = conn.execute("SELECT description FROM transactions WHERE id = ?", (tx_id,)).fetchone()
        conn.execute("UPDATE transactions SET category = ? WHERE id = ?", (category, tx_id))
    if row:
        from finance_agent.merchants import merchant_key

        record_correction(merchant_key(str(row["description"])), category, str(row["description"]))


def record_correction(merchant: str, category: str, description: str) -> None:
    if category not in CATEGORIES:
        msg = f"Unknown category: {category}"
        raise ValueError(msg)
    label = merchant.strip()
    if not label:
        return
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO corrections (merchant, category, description, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (label, category, description, now),
        )


def latest_correction_map() -> dict[str, str]:
    with connect() as conn:
        rows = conn.execute("SELECT merchant, category FROM corrections ORDER BY id").fetchall()
    out: dict[str, str] = {}
    for row in rows:
        out[str(row["merchant"])] = str(row["category"])
    return out


def list_fewshot(limit: int = 16) -> list[dict[str, str]]:
    mapping = latest_correction_map()
    items = [{"merchant": key, "category": cat} for key, cat in mapping.items()]
    return items[-min(max(int(limit), 1), 40) :]


def upsert_user_rule(needle: str, category: str) -> None:
    text = needle.strip().lower()
    if not text:
        msg = "Rule needle required"
        raise ValueError(msg)
    if category not in CATEGORIES:
        msg = f"Unknown category: {category}"
        raise ValueError(msg)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO user_rules (needle, category) VALUES (?, ?)
            ON CONFLICT(needle) DO UPDATE SET category = excluded.category
            """,
            (text, category),
        )


def list_user_rules() -> list[dict[str, str]]:
    with connect() as conn:
        rows = conn.execute("SELECT needle, category FROM user_rules ORDER BY needle").fetchall()
    return [dict(r) for r in rows]


def split_transaction(tx_id: int, parts: list[dict[str, Any]]) -> int:
    orig = get_transaction(tx_id)
    if not orig:
        msg = f"No transaction {tx_id}"
        raise ValueError(msg)
    cleaned: list[dict[str, Any]] = []
    for part in parts:
        amount = float(part["amount"])
        category = str(part.get("category") or orig["category"])
        if category not in CATEGORIES:
            msg = f"Unknown category: {category}"
            raise ValueError(msg)
        if amount == 0:
            continue
        cleaned.append({"amount": amount, "category": category})
    if len(cleaned) < SPLIT_MIN_PARTS:
        msg = "Need at least two non-zero parts"
        raise ValueError(msg)
    total = sum(item["amount"] for item in cleaned)
    if abs(total - float(orig["amount"])) > SPLIT_TOL:
        msg = "Parts must sum to the original amount"
        raise ValueError(msg)
    # Replaces the row rather than linking children to it: the original id
    # is deleted and each part is inserted fresh with parent_id left NULL,
    # so parent_id (see schema above) never actually links back to tx_id.
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    with connect() as conn:
        conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        for item in cleaned:
            conn.execute(
                """
                INSERT INTO transactions
                    (date, description, amount, currency, category, source_file, account,
                     merchant, parent_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    orig["date"],
                    f"{orig['description']} (split)",
                    item["amount"],
                    orig.get("currency") or "INR",
                    item["category"],
                    orig.get("source_file"),
                    orig.get("account"),
                    orig.get("merchant"),
                    None,
                    now,
                ),
            )
    return len(cleaned)


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
            "corrections": conn.execute("SELECT COUNT(*) AS n FROM corrections").fetchone()["n"],
            "user_rules": conn.execute("SELECT COUNT(*) AS n FROM user_rules").fetchone()["n"],
            "notifications": conn.execute("SELECT COUNT(*) AS n FROM notifications").fetchone()["n"],
        }
    return {"db_path": str(DB_PATH), "local_only": is_local_only(), **counts}


def clear_messages() -> None:
    with connect() as conn:
        conn.execute("DELETE FROM messages")


def add_notification(kind: str, dedupe: str, title: str, body: str) -> bool:
    # INSERT OR IGNORE against the UNIQUE dedupe column makes this idempotent:
    # callers (notify.refresh_inbox) can run on every page load and only get
    # a row (and a True return) the first time a given dedupe key is seen.
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO notifications (kind, dedupe, title, body, created_at, read)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (kind, dedupe, title, body, now),
        )
        return cur.rowcount > 0


def list_notifications(limit: int = 50) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, kind, title, body, created_at, read
            FROM notifications ORDER BY id DESC LIMIT ?
            """,
            (min(max(int(limit), 1), 100),),
        ).fetchall()
    return [dict(r) for r in rows]


def unread_count() -> int:
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM notifications WHERE read = 0").fetchone()
    return int(row["n"])


def mark_notification_read(note_id: int) -> None:
    with connect() as conn:
        conn.execute("UPDATE notifications SET read = 1 WHERE id = ?", (note_id,))


def mark_all_notifications_read() -> None:
    with connect() as conn:
        conn.execute("UPDATE notifications SET read = 1")


def export_snapshot() -> dict[str, list[dict[str, Any]]]:
    with connect() as conn:
        return {
            "transactions": [dict(r) for r in conn.execute("SELECT * FROM transactions").fetchall()],
            "budgets": [dict(r) for r in conn.execute("SELECT * FROM budgets").fetchall()],
            "accounts": [dict(r) for r in conn.execute("SELECT * FROM accounts").fetchall()],
            "goals": [dict(r) for r in conn.execute("SELECT * FROM goals").fetchall()],
            "messages": [dict(r) for r in conn.execute("SELECT * FROM messages").fetchall()],
            "user_rules": [dict(r) for r in conn.execute("SELECT * FROM user_rules").fetchall()],
            "corrections": [dict(r) for r in conn.execute("SELECT * FROM corrections").fetchall()],
        }


def export_zip() -> bytes:
    snap = export_snapshot()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("data.json", json.dumps(snap, default=str, indent=2))
        csv_buf = io.StringIO()
        fields = [
            "id",
            "date",
            "description",
            "amount",
            "currency",
            "category",
            "source_file",
            "account",
            "merchant",
        ]
        writer = csv.DictWriter(csv_buf, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(snap["transactions"])
        archive.writestr("transactions.csv", csv_buf.getvalue())
    return buf.getvalue()


def wipe_ledger() -> None:
    # Irreversible, no soft-delete. The confirmation gate (typed "DELETE")
    # lives in the UI layer (streamlit_app.py), not here — this function
    # trusts its caller.
    with connect() as conn:
        conn.execute("DELETE FROM transactions")


def wipe_all() -> None:
    with connect() as conn:
        conn.execute("DELETE FROM transactions")
        conn.execute("DELETE FROM budgets")
        conn.execute("DELETE FROM accounts")
        conn.execute("DELETE FROM goals")
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM corrections")
        conn.execute("DELETE FROM user_rules")
        conn.execute("DELETE FROM notifications")
