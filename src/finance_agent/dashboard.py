"""Phase 5 dashboard series: charts, forecast, inflation, cancel suggestions."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from finance_agent.insights import monthly_series

INFLATION_THRESHOLD = 0.15
INFLATION_MONTHS = 6
FORECAST_LOOKBACK = 30


def spend_by_month_category(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], float] = defaultdict(float)
    for row in rows:
        amount = float(row["amount"])
        if amount >= 0:
            continue
        month = str(row["date"])[:7]
        buckets[(month, str(row.get("category") or "OTHER"))] += abs(amount)
    return [
        {"month": month, "category": cat, "spent": spent}
        for (month, cat), spent in sorted(buckets.items())
    ]


def income_expense_series(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in monthly_series(rows):
        out.append({"month": item["month"], "kind": "Expense", "amount": item["spent"]})
        out.append({"month": item["month"], "kind": "Income", "amount": item["income"]})
    return out


def savings_rate_series(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in monthly_series(rows):
        income = float(item["income"])
        spent = float(item["spent"])  # already a positive magnitude, per monthly_series()
        rate = (income - spent) / income if income > 0 else 0.0
        out.append({"month": item["month"], "savings_rate": rate})
    return out


def top_merchants(rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        amount = float(row["amount"])
        if amount >= 0:
            continue
        name = str(row.get("merchant") or row.get("description") or "Unknown")
        totals[name] += abs(amount)
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    return [{"merchant": name, "spent": amt} for name, amt in ranked[:limit]]


def cashflow_forecast(
    rows: list[dict[str, Any]],
    recurring: list[dict[str, Any]],
    today: date,
    days: int,
) -> dict[str, float]:
    # Naive linear projection, not a statistical model: trailing 30-day net
    # cashflow scaled to the forecast horizon, plus known recurring charges
    # (from copilot.detect_recurring) explicitly due within that horizon.
    start = (today - timedelta(days=FORECAST_LOOKBACK)).isoformat()
    window = [row for row in rows if str(row["date"]) >= start]
    net = sum(float(row["amount"]) for row in window)
    run_rate = net / FORECAST_LOOKBACK * days
    extra = 0.0
    end = today + timedelta(days=days)
    for rec in recurring:
        last = date.fromisoformat(str(rec["last"]))
        step = 30 if rec.get("cadence") == "monthly" else 7
        nxt = last + timedelta(days=step)
        while nxt <= end:
            if nxt > today:
                extra += float(rec["amount"])
            nxt += timedelta(days=step)
    return {
        "days": float(days),
        "run_rate": run_rate,
        "recurring": extra,
        "forecast": run_rate + extra,
    }


def cancel_suggestions(recurring: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for rec in recurring:
        yearly = abs(float(rec["amount"])) * (12 if rec.get("cadence") == "monthly" else 52)
        out.append(
            {
                "description": rec["description"],
                "cadence": rec.get("cadence"),
                "amount": rec["amount"],
                "yearly_savings": yearly,
                "hint": "You can cancel this",
            }
        )
    out.sort(key=lambda item: item["yearly_savings"], reverse=True)
    return out


def lifestyle_inflation(
    rows: list[dict[str, Any]],
    today: date,
) -> dict[str, Any] | None:
    complete = [item for item in monthly_series(rows) if item["month"] < today.strftime("%Y-%m")]
    if len(complete) < INFLATION_MONTHS:
        return None
    # Compares the most recent `half` complete months against the `half`
    # before that (3 and 3, today). The literal "/ 3" divisors below assume
    # half == 3 — if INFLATION_MONTHS changes, these must change to match.
    half = INFLATION_MONTHS // 2
    recent = complete[-half:]
    prior = complete[-INFLATION_MONTHS:-half]
    r_spend = sum(float(item["spent"]) for item in recent) / 3
    p_spend = sum(float(item["spent"]) for item in prior) / 3
    r_inc = sum(float(item["income"]) for item in recent) / 3
    p_inc = sum(float(item["income"]) for item in prior) / 3
    spend_up = (r_spend - p_spend) / p_spend if p_spend else 0.0
    inc_up = (r_inc - p_inc) / p_inc if p_inc else 0.0
    return {
        "recent_spend": r_spend,
        "prior_spend": p_spend,
        "spend_change": spend_up,
        "income_change": inc_up,
        "flagged": spend_up >= INFLATION_THRESHOLD and spend_up > inc_up + 0.05,
    }
