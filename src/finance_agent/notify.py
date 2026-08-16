"""Phase 6 inbox: Monday digest, bills, anomalies, week delta."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from finance_agent.copilot import GOAL_BEHIND, detect_recurring, goal_progress, weekly_digest
from finance_agent.insights import anomalies, spent_of, week_bounds


def week_monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def next_bill_date(last: str, cadence: str) -> date:
    step = 30 if cadence == "monthly" else 7
    return date.fromisoformat(last) + timedelta(days=step)


def bill_reminders(recurring: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    horizon = today + timedelta(days=7)
    out: list[dict[str, Any]] = []
    for rec in recurring:
        due = next_bill_date(str(rec["last"]), str(rec.get("cadence") or "monthly"))
        if today <= due <= horizon:
            out.append(
                {
                    "description": rec["description"],
                    "due": due.isoformat(),
                    "amount": rec["amount"],
                    "cadence": rec.get("cadence"),
                }
            )
    return out


def week_delta(rows: list[dict[str, Any]], today: date) -> dict[str, Any]:
    start, end, tag = week_bounds(today)
    prev_end = date.fromisoformat(start) - timedelta(days=1)
    prev_start, prev_last, prev_tag = week_bounds(prev_end)
    this = [row for row in rows if start <= row["date"] <= end]
    last = [row for row in rows if prev_start <= row["date"] <= prev_last]
    this_spent = spent_of(this)
    last_spent = spent_of(last)
    return {
        "week": tag,
        "prev_week": prev_tag,
        "this_spent": this_spent,
        "last_spent": last_spent,
        "delta": this_spent - last_spent,
        "this_count": len(this),
        "last_count": len(last),
    }


def refresh_inbox(today: date) -> int:
    from finance_agent.db import (
        add_notification,
        list_accounts,
        list_budgets,
        list_goals,
        list_transactions,
    )

    rows = list_transactions(500)
    period = today.strftime("%Y-%m")
    rec = detect_recurring(rows)
    added = 0
    monday = week_monday(today)
    if today >= monday:
        digest = weekly_digest(
            rows=rows,
            budgets=list_budgets(period),
            period=period,
            goals=list_goals(),
            accounts=list_accounts(),
            today=today,
        )
        changed = week_delta(rows, today)
        digest += (
            f"\n## What changed this week ({changed['week']})\n"
            f"- Spend {changed['this_spent']:.2f} vs {changed['prev_week']} {changed['last_spent']:.2f} "
            f"(delta {changed['delta']:.2f})\n"
            f"- Transactions {changed['this_count']} vs {changed['last_count']}\n"
        )
        title = f"Weekly digest {monday.isoformat()}"
        if add_notification("digest", f"digest-{monday.isoformat()}", title, digest):
            added += 1
        summary = (
            f"Spend {changed['this_spent']:.2f} vs last week {changed['last_spent']:.2f}. "
            f"{changed['this_count']} txs this week."
        )
        if add_notification("week", f"week-{monday.isoformat()}", "What changed this week", summary):
            added += 1
    start, end, _tag = week_bounds(today)
    week_rows = [row for row in rows if start <= row["date"] <= end]
    for flag in anomalies(week_rows):
        key = f"anomaly-{flag.get('id') or flag['date']}-{flag['description']}"
        body = f"{flag['date']} {flag['category']} {flag['amount']} {flag['description']}"
        if add_notification("anomaly", key, "Unusual spend", body):
            added += 1
    for bill in bill_reminders(rec, today):
        key = f"bill-{bill['description']}-{bill['due']}"
        body = f"{bill['description']} due {bill['due']} ({bill['amount']})"
        if add_notification("bill", key, "Bill reminder", body):
            added += 1
    added += _goal_notes(list_goals())
    return added


def _goal_notes(goals: list[dict[str, Any]]) -> int:
    from finance_agent.db import add_notification

    added = 0
    for goal in goals:
        ratio = goal_progress(goal)
        due = goal.get("deadline") or "n/a"
        body = f"{goal['name']}: {goal['current']:.2f}/{goal['target']:.2f} ({ratio:.0%}) due {due}"
        if ratio < GOAL_BEHIND and goal.get("deadline"):
            key = f"goal-{goal['id']}-{goal.get('deadline')}"
            if add_notification("goal", key, "Goal needs attention", body):
                added += 1
    return added
