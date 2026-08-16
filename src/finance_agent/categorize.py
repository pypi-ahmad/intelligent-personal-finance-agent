"""Rule-first categories; leftover fill is local LLM then occasional API."""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from finance_agent.config import CATEGORIES

RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("swiggy", "zomato", "ubereats", "uber eats", "restaurant", "cafe", "starbucks", "dominos"), "FOOD"),
    (("bigbasket", "blinkit", "zepto", "grocery", "supermarket", "dmart", "reliance fresh"), "GROCERIES"),
    (("uber", "ola", "metro", "irctc", "petrol", "diesel", "fuel", "parking", "rapido"), "TRANSPORT"),
    (("electricity", "bescom", "water board", "gas bill", "broadband", "airtel", "jio", "vi "), "UTILITIES"),
    (("rent", "landlord"), "RENT"),
    (("amazon", "flipkart", "myntra", "ajio", "nykaa"), "SHOPPING"),
    (("pharmacy", "apollo", "practo", "hospital", "clinic"), "HEALTH"),
    (("netflix", "spotify", "hotstar", "prime video", "bookmyshow"), "ENTERTAINMENT"),
    (("upi/", "neft", "imps", "rtgs", "transfer", "p2p"), "TRANSFER"),
    (("salary", "payroll", "interest credit", "refund"), "INCOME"),
    (("gst", "fee", "charge", "penalty", "late fee"), "FEES"),
)

LLM_PROMPT = """Categorize each transaction. Allowed categories:
{cats}
Return ONLY a JSON array of {{"id": <int>, "category": "<CAT>"}}.
Transactions:
{rows}
"""


def apply_rules(description: str) -> str:
    text = description.lower()
    for needles, category in RULES:
        if any(n in text for n in needles):
            return category
    return "OTHER"


def categorize_with_llm(rows: list[dict[str, Any]], complete: Any) -> list[dict[str, Any]]:
    pending = [r for r in rows if r.get("category") == "OTHER"]
    if not pending:
        return rows
    payload = [
        {"id": i, "description": r["description"], "amount": r["amount"]} for i, r in enumerate(pending)
    ]
    raw = complete(LLM_PROMPT.format(cats=", ".join(CATEGORIES), rows=payload))
    from finance_agent.ingest import parse_json_payload

    mapped = parse_json_payload(raw)
    by_id: dict[int, str] = {}
    if isinstance(mapped, list):
        for item in mapped:
            if not isinstance(item, dict):
                continue
            try:
                idx = int(item["id"])
            except (KeyError, TypeError, ValueError):
                continue
            cat = str(item.get("category") or "").upper()
            if cat in CATEGORIES:
                by_id[idx] = cat
    for i, row in enumerate(pending):
        if i in by_id:
            row["category"] = by_id[i]
    return rows


def categorize_hybrid(
    rows: list[dict[str, Any]],
    *,
    local_complete: Any | None = None,
    api_complete: Any | None = None,
) -> list[dict[str, Any]]:
    """Rules already on rows. Local model first, API only for leftovers."""
    if local_complete:
        with suppress(ValueError, TypeError, OSError, RuntimeError):
            categorize_with_llm(rows, local_complete)
    if api_complete:
        with suppress(ValueError, TypeError, OSError, RuntimeError):
            categorize_with_llm(rows, api_complete)
    return rows
