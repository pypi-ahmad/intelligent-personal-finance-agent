from datetime import date

from finance_agent.dashboard import (
    cancel_suggestions,
    cashflow_forecast,
    income_expense_series,
    lifestyle_inflation,
    savings_rate_series,
    spend_by_month_category,
    top_merchants,
)


def _rows() -> list[dict]:
    return [
        {"date": "2025-07-05", "category": "FOOD", "amount": -100.0, "merchant": "Swiggy"},
        {"date": "2025-08-05", "category": "FOOD", "amount": -110.0, "merchant": "Swiggy"},
        {"date": "2025-09-05", "category": "FOOD", "amount": -120.0, "merchant": "Swiggy"},
        {"date": "2025-10-05", "category": "FOOD", "amount": -200.0, "merchant": "Swiggy"},
        {"date": "2025-11-05", "category": "FOOD", "amount": -220.0, "merchant": "Zomato"},
        {"date": "2025-12-05", "category": "FOOD", "amount": -240.0, "merchant": "Zomato"},
        {"date": "2025-12-01", "category": "INCOME", "amount": 1000.0, "merchant": None},
        {"date": "2026-01-10", "category": "FOOD", "amount": -50.0, "merchant": "Swiggy"},
        {"date": "2026-01-10", "category": "INCOME", "amount": 500.0, "merchant": None},
    ]


def test_chart_series() -> None:
    rows = _rows()
    by_cat = spend_by_month_category(rows)
    assert any(item["category"] == "FOOD" and item["month"] == "2026-01" for item in by_cat)
    ie = income_expense_series(rows)
    assert {item["kind"] for item in ie} == {"Expense", "Income"}
    rates = savings_rate_series(rows)
    jan = next(item for item in rates if item["month"] == "2026-01")
    assert jan["savings_rate"] == (500.0 - 50.0) / 500.0
    tops = top_merchants(rows, limit=2)
    assert tops[0]["merchant"] in {"Swiggy", "Zomato"}


def test_forecast_and_cancel() -> None:
    rec = [{"description": "netflix", "amount": -199.0, "cadence": "monthly", "last": "2026-01-01"}]
    out = cashflow_forecast(_rows(), rec, date(2026, 1, 15), 30)
    assert out["days"] == 30
    assert out["recurring"] < 0
    tips = cancel_suggestions(rec)
    assert tips[0]["yearly_savings"] == 199.0 * 12


def test_lifestyle_inflation_flags_rise() -> None:
    result = lifestyle_inflation(_rows(), date(2026, 1, 15))
    assert result is not None
    assert result["flagged"] is True
