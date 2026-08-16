from datetime import date
from pathlib import Path

import pytest

from finance_agent.categorize import categorize_hybrid
from finance_agent.insights import anomalies, month_compare, top_categories
from finance_agent.reports import month_markdown, report_pdf


def test_hybrid_local_then_api() -> None:
    rows = [
        {"description": "SWIGGY", "amount": -10.0, "category": "FOOD"},
        {"description": "mystery", "amount": -20.0, "category": "OTHER"},
        {"description": "unknown2", "amount": -30.0, "category": "OTHER"},
    ]

    def local(_prompt: str) -> str:
        return '[{"id": 0, "category": "SHOPPING"}]'

    def api(_prompt: str) -> str:
        return '[{"id": 0, "category": "HEALTH"}]'

    out = categorize_hybrid(rows, local_complete=local, api_complete=api)
    assert out[0]["category"] == "FOOD"
    assert out[1]["category"] == "SHOPPING"
    assert out[2]["category"] == "HEALTH"


def test_hybrid_api_after_local_fail() -> None:
    rows = [{"description": "x", "amount": -1.0, "category": "OTHER"}]

    def boom(_prompt: str) -> str:
        raise RuntimeError("down")

    def api(_prompt: str) -> str:
        return '[{"id": 0, "category": "FEES"}]'

    out = categorize_hybrid(rows, local_complete=boom, api_complete=api)
    assert out[0]["category"] == "FEES"


def test_top_and_month_compare() -> None:
    rows = [
        {"date": "2026-01-05", "category": "FOOD", "amount": -100.0},
        {"date": "2026-01-06", "category": "FOOD", "amount": -50.0},
        {"date": "2026-01-07", "category": "TRANSPORT", "amount": -20.0},
        {"date": "2026-01-08", "category": "INCOME", "amount": 500.0},
        {"date": "2025-12-20", "category": "FOOD", "amount": -80.0},
    ]
    top = top_categories(rows, limit=2)
    assert top[0] == {"category": "FOOD", "spent": 230.0}
    assert top[1]["category"] == "TRANSPORT"
    cmp = month_compare(rows, "2026-01")
    assert cmp["spent"] == -170.0
    assert cmp["prev_spent"] == -80.0
    assert cmp["income"] == 500.0
    assert cmp["prev_period"] == "2025-12"


def test_anomalies_flag_outlier() -> None:
    rows = [
        {"id": 1, "date": "2026-01-01", "category": "FOOD", "description": "a", "amount": -10.0},
        {"id": 2, "date": "2026-01-02", "category": "FOOD", "description": "b", "amount": -11.0},
        {"id": 3, "date": "2026-01-03", "category": "FOOD", "description": "c", "amount": -12.0},
        {"id": 4, "date": "2026-01-04", "category": "FOOD", "description": "d", "amount": -10.0},
        {"id": 5, "date": "2026-01-05", "category": "FOOD", "description": "huge", "amount": -400.0},
    ]
    flags = anomalies(rows)
    assert any(item["description"] == "huge" for item in flags)
    assert not any(item["description"] == "a" for item in flags)


def test_budget_and_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from finance_agent import db

    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    db.insert_many(
        [
            {
                "date": "2026-01-05",
                "description": "SWIGGY",
                "amount": -120.0,
                "currency": "INR",
                "category": "FOOD",
                "source_file": "a.csv",
            },
            {
                "date": "2026-01-06",
                "description": "UBER",
                "amount": -40.0,
                "currency": "INR",
                "category": "TRANSPORT",
                "source_file": "a.csv",
            },
        ]
    )
    db.upsert_budget("FOOD", "2026-01", 100.0)
    rows = db.list_transactions()
    text = month_markdown("2026-01", rows, db.list_budgets("2026-01"))
    assert "Monthly report 2026-01" in text
    assert "FOOD: 120.00 / 100.00" in text
    assert "OVER" in text
    pdf = report_pdf(text)
    assert pdf.startswith(b"%PDF")


def test_week_bounds_monday() -> None:
    from finance_agent.insights import week_bounds

    start, end, tag = week_bounds(date(2026, 1, 7))  # Wednesday
    assert start == "2026-01-05"
    assert end == "2026-01-11"
    assert tag == "2026-W02"
