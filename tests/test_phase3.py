from datetime import date
from pathlib import Path

import pytest

from finance_agent.agent import _history_text
from finance_agent.copilot import (
    alerts,
    detect_recurring,
    filter_travel,
    infer_range,
    last_quarter,
    net_worth,
    wants_travel,
)


def test_last_quarter_and_infer() -> None:
    assert last_quarter(date(2026, 5, 15)) == ("2026-01-01", "2026-03-31")
    assert last_quarter(date(2026, 2, 1)) == ("2025-10-01", "2025-12-31")
    start, end = infer_range("How much on food while traveling last quarter?", date(2026, 5, 15))
    assert (start, end) == ("2026-01-01", "2026-03-31")
    assert wants_travel("food while traveling last quarter")


def test_travel_food_filter() -> None:
    rows = [
        {"date": "2026-01-10", "description": "IRCTC ticket", "category": "TRANSPORT", "amount": -800.0},
        {"date": "2026-01-10", "description": "SWIGGY hotel area", "category": "FOOD", "amount": -220.0},
        {"date": "2026-01-20", "description": "SWIGGY home", "category": "FOOD", "amount": -50.0},
    ]
    out = filter_travel(rows, category="FOOD")
    assert len(out) == 1
    assert out[0]["amount"] == -220.0


def test_recurring_monthly() -> None:
    rows = [
        {"date": "2026-01-02", "description": "NETFLIX 1", "amount": -199.0},
        {"date": "2026-02-02", "description": "NETFLIX 2", "amount": -199.0},
        {"date": "2026-03-02", "description": "NETFLIX 3", "amount": -199.0},
    ]
    found = detect_recurring(rows)
    assert len(found) == 1
    assert found[0]["cadence"] == "monthly"


def test_net_worth() -> None:
    worth = net_worth(
        [
            {"name": "Bank", "kind": "asset", "balance": 1000.0},
            {"name": "Card", "kind": "liability", "balance": 200.0},
        ]
    )
    assert worth["net"] == 800.0


def test_history_text_keeps_tail() -> None:
    hist = [{"role": "user", "content": "food?"}, {"role": "assistant", "content": "120"}]
    text = _history_text(hist)
    assert "user: food?" in text
    assert "assistant: 120" in text


def test_local_only_blocks_cloud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from finance_agent import db
    from finance_agent.llm import complete

    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    db.set_local_only(on=True)
    with pytest.raises(PermissionError, match="Local-first"):
        complete("OpenAI", "gpt-5.6-luna", "hi")


def test_memory_and_wipe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from finance_agent import db

    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    db.append_message("user", "hello")
    db.append_message("assistant", "hi")
    assert [m["content"] for m in db.list_messages()] == ["hello", "hi"]
    db.upsert_account("Bank", "asset", 10)
    db.upsert_goal("Emergency", "savings", 1000, 100, "2026-12-31")
    db.clear_messages()
    assert db.list_messages() == []
    db.wipe_all()
    assert db.privacy_stats()["accounts"] == 0
    assert db.privacy_stats()["goals"] == 0


def test_budget_alert() -> None:
    rows = [{"date": "2026-01-05", "category": "FOOD", "amount": -80.0, "description": "x"}]
    notes = alerts(
        rows=rows,
        budgets=[{"category": "FOOD", "period": "2026-01", "amount": 50.0}],
        period="2026-01",
        goals=[],
        today=date(2026, 1, 20),
    )
    assert any("Over budget" in note for note in notes)
