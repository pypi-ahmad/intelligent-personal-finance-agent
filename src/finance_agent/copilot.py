"""Phase 3 analysis: time ranges, travel overlap, recurring, alerts, net worth."""

from __future__ import annotations

import calendar
import re
import statistics
from collections import defaultdict
from datetime import date, timedelta
from itertools import pairwise
from typing import Any

from finance_agent.config import TRAVEL_NEEDLES
from finance_agent.insights import MONTHS, anomalies, budget_status, month_bounds, spent_of

RECUR_MIN = 3
MONTHLY_GAP = (25, 35)
WEEKLY_GAP = (6, 8)
GOAL_BEHIND = 0.5


def last_quarter(today: date) -> tuple[str, str]:
    quarter = (today.month - 1) // 3
    if quarter == 0:
        year = today.year - 1
        return f"{year}-10-01", f"{year}-12-31"
    start_month = (quarter - 1) * 3 + 1
    end_month = quarter * 3
    last = calendar.monthrange(today.year, end_month)[1]
    return (
        f"{today.year:04d}-{start_month:02d}-01",
        f"{today.year:04d}-{end_month:02d}-{last:02d}",
    )


def infer_range(question: str, today: date) -> tuple[str | None, str | None]:
    text = question.lower()
    if "last quarter" in text or "previous quarter" in text:
        return last_quarter(today)
    if "this month" in text:
        start, end = month_bounds(today.strftime("%Y-%m"))
        return start, end
    if "last month" in text:
        month = today.month - 1 or MONTHS
        year = today.year if today.month > 1 else today.year - 1
        return month_bounds(f"{year:04d}-{month:02d}")
    if "last week" in text:
        end = today - timedelta(days=today.weekday() + 1)
        start = end - timedelta(days=6)
        return start.isoformat(), end.isoformat()
    return None, None


def wants_travel(question: str) -> bool:
    text = question.lower()
    return any(word in text for word in ("travel", "trip", "vacation", "holiday", "while away"))


def travel_dates(rows: list[dict[str, Any]]) -> set[str]:
    found: set[str] = set()
    for row in rows:
        desc = str(row.get("description") or "").lower()
        if any(needle in desc for needle in TRAVEL_NEEDLES):
            found.add(str(row["date"]))
            day = date.fromisoformat(str(row["date"]))
            found.add((day - timedelta(days=1)).isoformat())
            found.add((day + timedelta(days=1)).isoformat())
    return found


def filter_travel(
    rows: list[dict[str, Any]],
    *,
    category: str | None = None,
) -> list[dict[str, Any]]:
    days = travel_dates(rows)
    if not days:
        return []
    out = [row for row in rows if str(row["date"]) in days]
    if category:
        out = [row for row in out if row.get("category") == category]
    return out


def detect_recurring(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        amount = float(row["amount"])
        if amount >= 0:
            continue
        key = (_norm_desc(str(row["description"])), round(abs(amount)))
        groups[key].append(row)
    found: list[dict[str, Any]] = []
    for (desc, amt), items in groups.items():
        if len(items) < RECUR_MIN:
            continue
        days = sorted(date.fromisoformat(str(item["date"])) for item in items)
        gaps = [(later - prev).days for prev, later in pairwise(days)]
        if not gaps:
            continue
        median = statistics.median(gaps)
        if MONTHLY_GAP[0] <= median <= MONTHLY_GAP[1]:
            cadence = "monthly"
        elif WEEKLY_GAP[0] <= median <= WEEKLY_GAP[1]:
            cadence = "weekly"
        else:
            continue
        found.append(
            {
                "description": desc or "(blank)",
                "amount": -float(amt),
                "count": len(items),
                "cadence": cadence,
                "last": days[-1].isoformat(),
            }
        )
    found.sort(key=lambda item: item["last"], reverse=True)
    return found


def net_worth(accounts: list[dict[str, Any]]) -> dict[str, float]:
    assets = sum(float(a["balance"]) for a in accounts if a.get("kind") == "asset")
    debt = sum(float(a["balance"]) for a in accounts if a.get("kind") == "liability")
    return {"assets": assets, "liabilities": debt, "net": assets - debt}


def goal_progress(goal: dict[str, Any]) -> float:
    target = float(goal["target"])
    if target <= 0:
        return 0.0
    current = float(goal["current"])
    if goal.get("kind") == "debt":
        return max(0.0, min(1.0, current / target))
    return max(0.0, min(1.0, current / target))


def alerts(
    *,
    rows: list[dict[str, Any]],
    budgets: list[dict[str, Any]],
    period: str,
    goals: list[dict[str, Any]],
    today: date,
) -> list[str]:
    start, end = month_bounds(period)
    month_rows = [row for row in rows if start <= row["date"] <= end]
    notes = [
        f"Over budget: {item['category']} {item['actual']:.2f}/{item['budget']:.2f}"
        for item in budget_status(month_rows, budgets, period)
        if item["over"]
    ]
    flags = anomalies(month_rows)
    if flags:
        notes.append(f"{len(flags)} unusual transaction(s) this month")
    for rec in detect_recurring(rows):
        last = date.fromisoformat(str(rec["last"]))
        nxt = last + timedelta(days=30 if rec["cadence"] == "monthly" else 7)
        if today <= nxt <= today + timedelta(days=7):
            notes.append(f"Recurring due soon: {rec['description']} ({rec['cadence']})")
    horizon = today + timedelta(days=30)
    for goal in goals:
        deadline = goal.get("deadline")
        if not deadline:
            continue
        due = date.fromisoformat(str(deadline))
        if today <= due <= horizon and goal_progress(goal) < GOAL_BEHIND:
            notes.append(f"Goal behind: {goal['name']}")
    return notes


def weekly_digest(  # noqa: PLR0913
    *,
    rows: list[dict[str, Any]],
    budgets: list[dict[str, Any]],
    period: str,
    goals: list[dict[str, Any]],
    accounts: list[dict[str, Any]],
    today: date,
) -> str:
    start, end = month_bounds(period)
    month_rows = [row for row in rows if start <= row["date"] <= end]
    worth = net_worth(accounts)
    notes = alerts(rows=rows, budgets=budgets, period=period, goals=goals, today=today)
    recurring = detect_recurring(rows)
    lines = [
        f"# Weekly digest {today.isoformat()}",
        "",
        f"This month spent: {spent_of(month_rows):.2f}",
        f"Net worth: {worth['net']:.2f} (assets {worth['assets']:.2f}, debt {worth['liabilities']:.2f})",
        f"Recurring patterns: {len(recurring)}",
        "",
        "## Alerts",
    ]
    if notes:
        lines.extend(f"- {note}" for note in notes)
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def _norm_desc(text: str) -> str:
    cleaned = re.sub(r"\d+", "", text.lower())
    return re.sub(r"\s+", " ", cleaned).strip()
