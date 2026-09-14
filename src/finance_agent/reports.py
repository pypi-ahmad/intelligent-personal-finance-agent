"""Monthly / weekly report text and PDF bytes."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fpdf import FPDF

from finance_agent.insights import (
    anomalies,
    budget_status,
    in_range,
    month_bounds,
    month_compare,
    range_compare,
    top_categories,
    week_bounds,
)


def month_markdown(
    period: str,
    rows: list[dict[str, Any]],
    budgets: list[dict[str, Any]],
) -> str:
    start, end = month_bounds(period)
    compare = month_compare(rows, period)
    return _markdown(
        title=f"Monthly report {period}",
        start=start,
        end=end,
        compare=compare,
        prev_label=str(compare["prev_period"]),
        rows=in_range(rows, start, end),
        budgets=budget_status(rows, budgets, period),
    )


def week_markdown(day: date, rows: list[dict[str, Any]]) -> str:
    start, end, tag = week_bounds(day)
    prev_day = date.fromisoformat(start) - timedelta(days=1)
    prev_start, prev_end, prev_tag = week_bounds(prev_day)
    window = in_range(rows, start, end)
    compare = range_compare(rows, start, end, prev_start, prev_end)
    return _markdown(
        title=f"Weekly report {tag}",
        start=start,
        end=end,
        compare=compare,
        prev_label=prev_tag,
        rows=window,
        budgets=[],
    )


TAX_HINTS = {
    "TRANSPORT": "Possible business travel / commute",
    "UTILITIES": "Possible home-office share",
    "RENT": "Possible workspace / home office",
    "HEALTH": "Possible medical",
    "FEES": "Possible professional fees",
    "OTHER": "Review for business use",
}


def tax_year_markdown(year: int, rows: list[dict[str, Any]]) -> str:
    year_s = f"{year:04d}"
    year_rows = [row for row in rows if str(row["date"]).startswith(year_s)]
    spent = sum(float(r["amount"]) for r in year_rows if float(r["amount"]) < 0)
    income = sum(float(r["amount"]) for r in year_rows if float(r["amount"]) > 0)
    by_cat = top_categories(year_rows, limit=20)
    lines = [
        f"# Tax-ready expense report {year_s}",
        "",
        "For your accountant. Not tax advice. Review every line.",
        "",
        f"Income: {income:.2f}",
        f"Expenses: {spent:.2f}",
        f"Net: {income + spent:.2f}",
        f"Transactions: {len(year_rows)}",
        "",
        "## Spend by category",
    ]
    if by_cat:
        for item in by_cat:
            hint = TAX_HINTS.get(item["category"], "")
            extra = f" — {hint}" if hint else ""
            lines.append(f"- {item['category']}: {item['spent']:.2f}{extra}")
    else:
        lines.append("- None")
    lines.extend(["", "## Expense lines"])
    for row in sorted(year_rows, key=lambda item: item["date"]):
        if float(row["amount"]) >= 0:
            continue
        merch = row.get("merchant") or ""
        lines.append(
            f"- {row['date']} | {row['category']} | {row['amount']} | "
            f"{merch} | {row['description']}"
        )
    return "\n".join(lines) + "\n"


def report_pdf(markdown: str) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    width = pdf.epw
    for raw in markdown.splitlines():
        # FPDF's built-in Helvetica core font only supports ASCII/Latin-1;
        # no Unicode font is embedded here. Non-ASCII characters (currency
        # symbols, non-Latin merchant/description text) become "?" rather
        # than raising or rendering as boxes.
        line = raw.encode("ascii", "replace").decode("ascii").strip()
        if not line:
            pdf.ln(3)
            continue
        if line.startswith("# "):
            pdf.set_font("Helvetica", "B", 16)
            pdf.multi_cell(width, 8, line[2:])
        elif line.startswith("## "):
            pdf.set_font("Helvetica", "B", 13)
            pdf.multi_cell(width, 7, line[3:])
        elif line.startswith("- "):
            pdf.set_font("Helvetica", size=11)
            pdf.multi_cell(width, 6, f"* {line[2:]}")
        else:
            pdf.set_font("Helvetica", size=11)
            pdf.multi_cell(width, 6, line)
    return bytes(pdf.output())


def _markdown(  # noqa: PLR0913
    *,
    title: str,
    start: str,
    end: str,
    compare: dict[str, Any],
    prev_label: str,
    rows: list[dict[str, Any]],
    budgets: list[dict[str, Any]],
) -> str:
    tops = top_categories(rows)
    flags = anomalies(rows)
    lines = [
        f"# {title}",
        "",
        f"Period: {start} to {end}",
        f"Transactions: {compare.get('count', len(rows))}",
        f"Spent: {compare['spent']:.2f}",
        f"Income: {compare['income']:.2f}",
        f"Previous ({prev_label}) spent: {compare['prev_spent']:.2f}",
        f"Change vs previous: {compare['delta']:.2f}",
        "",
        "## Top categories",
    ]
    if tops:
        lines.extend(f"- {item['category']}: {item['spent']:.2f}" for item in tops)
    else:
        lines.append("- None")
    lines.extend(["", "## Budgets"])
    if budgets:
        for item in budgets:
            flag = " OVER" if item["over"] else ""
            lines.append(
                f"- {item['category']}: {item['actual']:.2f} / {item['budget']:.2f}"
                f" remaining {item['remaining']:.2f}{flag}"
            )
    else:
        lines.append("- None set")
    lines.extend(["", "## Anomalies"])
    if flags:
        lines.extend(
            f"- {item['date']} {item['category']} {item['amount']} {item['description']} ({item['reason']})"
            for item in flags
        )
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"
