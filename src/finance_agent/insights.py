"""Spend insights, month/week compare, and anomaly flags. No extra models."""

from __future__ import annotations

import calendar
import statistics
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

MIN_SAMPLES = 4
MONTHS = 12


def month_bounds(period: str) -> tuple[str, str]:
    year, month = (int(part) for part in period.split("-"))
    last = calendar.monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last:02d}"


def shift_month(period: str, delta: int) -> str:
    year, month = (int(part) for part in period.split("-"))
    month += delta
    while month < 1:
        month += MONTHS
        year -= 1
    while month > MONTHS:
        month -= MONTHS
        year += 1
    return f"{year:04d}-{month:02d}"


def week_bounds(day: date) -> tuple[str, str, str]:
    # ISO week: Monday-start (date.weekday() is 0 for Monday), not Sunday-start.
    start = day - timedelta(days=day.weekday())
    end = start + timedelta(days=6)
    iso = start.isocalendar()
    return start.isoformat(), end.isoformat(), f"{iso[0]}-W{iso[1]:02d}"


def spent_of(rows: list[dict[str, Any]]) -> float:
    return sum(float(r["amount"]) for r in rows if float(r["amount"]) < 0)


def income_of(rows: list[dict[str, Any]]) -> float:
    return sum(float(r["amount"]) for r in rows if float(r["amount"]) > 0)


def in_range(rows: list[dict[str, Any]], start: str, end: str) -> list[dict[str, Any]]:
    return [r for r in rows if start <= r["date"] <= end]


def top_categories(rows: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        amount = float(row["amount"])
        if amount < 0:
            totals[str(row["category"])] += abs(amount)
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    return [{"category": cat, "spent": amt} for cat, amt in ranked[:limit]]


def monthly_series(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, float]] = defaultdict(lambda: {"spent": 0.0, "income": 0.0})
    for row in rows:
        key = str(row["date"])[:7]
        amount = float(row["amount"])
        if amount < 0:
            buckets[key]["spent"] += abs(amount)
        elif amount > 0:
            buckets[key]["income"] += amount
    return [{"month": key, **buckets[key]} for key in sorted(buckets)]


def weekly_series(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, float] = defaultdict(float)
    for row in rows:
        amount = float(row["amount"])
        if amount >= 0:
            continue
        iso = date.fromisoformat(str(row["date"])).isocalendar()
        buckets[f"{iso[0]}-W{iso[1]:02d}"] += abs(amount)
    return [{"week": key, "spent": buckets[key]} for key in sorted(buckets)]


def range_compare(
    rows: list[dict[str, Any]],
    start: str,
    end: str,
    prev_start: str,
    prev_end: str,
) -> dict[str, Any]:
    current = in_range(rows, start, end)
    previous = in_range(rows, prev_start, prev_end)
    spent = spent_of(current)
    prev_spent = spent_of(previous)
    return {
        "spent": spent,
        "prev_spent": prev_spent,
        "delta": spent - prev_spent,
        "income": income_of(current),
        "count": len(current),
    }


def month_compare(rows: list[dict[str, Any]], period: str) -> dict[str, Any]:
    start, end = month_bounds(period)
    prev = shift_month(period, -1)
    prev_start, prev_end = month_bounds(prev)
    data = range_compare(rows, start, end, prev_start, prev_end)
    data["period"] = period
    data["prev_period"] = prev
    return data


def anomalies(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expenses = [r for r in rows if float(r["amount"]) < 0]
    if len(expenses) < MIN_SAMPLES:
        return []
    by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in expenses:
        by_cat[str(row["category"])].append(row)
    global_abs = [abs(float(r["amount"])) for r in expenses]
    global_med, global_fence = _fence(global_abs)
    flagged: list[dict[str, Any]] = []
    for cat, items in by_cat.items():
        values = [abs(float(r["amount"])) for r in items]
        median, fence = _fence(values) if len(values) >= MIN_SAMPLES else (global_med, global_fence)
        for row in items:
            amount = abs(float(row["amount"]))
            # Both conditions must hold: `fence` alone can trip on trivial
            # differences when the category's median is tiny, so also
            # require at least 2x the typical spend for that category.
            if amount > fence and amount > median * 2:
                flagged.append(
                    {
                        "id": row.get("id"),
                        "date": row["date"],
                        "description": row["description"],
                        "amount": row["amount"],
                        "category": cat,
                        "reason": f"{cat} typical {median:.2f}, this {amount:.2f}",
                    }
                )
    flagged.sort(key=lambda item: abs(float(item["amount"])), reverse=True)
    return flagged


def budget_status(
    rows: list[dict[str, Any]],
    budgets: list[dict[str, Any]],
    period: str,
) -> list[dict[str, Any]]:
    start, end = month_bounds(period)
    spent: dict[str, float] = defaultdict(float)
    for row in in_range(rows, start, end):
        amount = float(row["amount"])
        if amount < 0:
            spent[str(row["category"])] += abs(amount)
    out: list[dict[str, Any]] = []
    for budget in budgets:
        limit = float(budget["amount"])
        actual = spent.get(str(budget["category"]), 0.0)
        out.append(
            {
                "category": budget["category"],
                "budget": limit,
                "actual": actual,
                "remaining": limit - actual,
                "over": actual > limit,
            }
        )
    return out


def snapshot() -> str:
    from finance_agent.db import list_budgets, list_transactions

    rows = list_transactions(500)
    if not rows:
        return "(no transactions)"
    period = datetime.now(UTC).date().strftime("%Y-%m")
    compare = month_compare(rows, period)
    tops = top_categories(in_range(rows, *month_bounds(period)))
    flags = anomalies(in_range(rows, *month_bounds(period)))
    status = budget_status(rows, list_budgets(period), period)
    lines = [
        (
            f"Month {period} spent {compare['spent']:.2f} vs {compare['prev_period']} "
            f"{compare['prev_spent']:.2f} (delta {compare['delta']:.2f})"
        ),
        "Top: " + ", ".join(f"{item['category']} {item['spent']:.2f}" for item in tops)
        if tops
        else "Top: none",
        f"Anomalies this month: {len(flags)}",
    ]
    if status:
        bits = [f"{s['category']} {s['actual']:.2f}/{s['budget']:.2f}" for s in status]
        lines.append("Budgets: " + "; ".join(bits))
    return "\n".join(lines)


def _fence(values: list[float]) -> tuple[float, float]:
    # Robust outlier fence via median absolute deviation (MAD), so a single
    # huge transaction can't skew the threshold the way a mean/stdev would.
    # 1.4826 rescales MAD to be comparable to a normal distribution's
    # standard deviation; 3x that is the fence. If every value is equal
    # (mad == 0) there's no spread to scale, so fall back to 3x the median.
    if len(values) < MIN_SAMPLES:
        return 0.0, 0.0
    median = statistics.median(values)
    mad = statistics.median([abs(value - median) for value in values])
    if mad == 0:
        return median, median * 3
    return median, median + 3 * 1.4826 * mad
