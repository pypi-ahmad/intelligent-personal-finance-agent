from datetime import date
from pathlib import Path

import pytest

from finance_agent.notify import bill_reminders, refresh_inbox, week_delta, week_monday


def test_week_monday_and_bills() -> None:
    assert week_monday(date(2026, 1, 7)) == date(2026, 1, 5)
    bills = bill_reminders(
        [{"description": "netflix", "amount": -199.0, "cadence": "monthly", "last": "2025-12-20"}],
        date(2026, 1, 15),
    )
    assert len(bills) == 1
    assert bills[0]["due"] == "2026-01-19"


def test_week_delta() -> None:
    rows = [
        {"date": "2026-01-06", "amount": -10.0},
        {"date": "2026-01-07", "amount": -20.0},
        {"date": "2025-12-30", "amount": -40.0},
    ]
    delta = week_delta(rows, date(2026, 1, 7))
    assert delta["this_count"] == 2
    assert delta["this_spent"] == -30.0
    assert delta["last_spent"] == -40.0


def test_refresh_inbox_dedupes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from finance_agent import db

    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    db.insert_many(
        [
            {
                "date": "2026-01-06",
                "description": "SWIGGY",
                "amount": -12.0,
                "currency": "INR",
                "category": "FOOD",
                "source_file": "a.csv",
            }
        ]
    )
    first = refresh_inbox(date(2026, 1, 5))
    second = refresh_inbox(date(2026, 1, 5))
    assert first >= 1
    assert second == 0
    kinds = {n["kind"] for n in db.list_notifications()}
    assert "digest" in kinds
    assert "week" in kinds
