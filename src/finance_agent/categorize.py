"""Rule-first categories; user rules and corrections beat builtins; LLM last."""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from finance_agent.config import CATEGORIES
from finance_agent.merchants import merchant_key, normalize_merchant

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
User-corrected examples (follow these when the merchant matches):
{examples}
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


def assign_category(
    description: str,
    *,
    user_rules: list[dict[str, str]] | None = None,
    correction_map: dict[str, str] | None = None,
) -> tuple[str, str | None]:
    merchant = normalize_merchant(description)
    key = merchant_key(description)
    text = description.lower()
    for rule in user_rules or []:
        needle = str(rule.get("needle") or "").strip().lower()
        cat = str(rule.get("category") or "").upper()
        if needle and needle in text and cat in CATEGORIES:
            return cat, merchant
    if correction_map:
        if merchant and merchant in correction_map:
            return correction_map[merchant], merchant
        if key in correction_map:
            return correction_map[key], merchant
    return apply_rules(description), merchant


def apply_learned(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from finance_agent.db import latest_correction_map, list_user_rules

    rules = list_user_rules()
    corrections = latest_correction_map()
    for row in rows:
        category, merchant = assign_category(
            str(row["description"]),
            user_rules=rules,
            correction_map=corrections,
        )
        row["category"] = category
        row["merchant"] = merchant
    return rows


def categorize_with_llm(
    rows: list[dict[str, Any]],
    complete: Any,
    *,
    examples: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    # Only rows no rule matched (still "OTHER") are sent to the LLM, to
    # limit calls/tokens to genuine leftovers.
    pending = [r for r in rows if r.get("category") == "OTHER"]
    if not pending:
        return rows
    payload = [
        {
            "id": i,
            "description": r["description"],
            "merchant": r.get("merchant"),
            "amount": r["amount"],
        }
        for i, r in enumerate(pending)
    ]
    shot = "(none)"
    if examples:
        shot = "\n".join(
            f"- {item.get('merchant') or item.get('description')}: {item['category']}" for item in examples
        )
    raw = complete(LLM_PROMPT.format(cats=", ".join(CATEGORIES), examples=shot, rows=payload))
    from finance_agent.ingest import parse_json_payload

    mapped = parse_json_payload(raw)
    # "id" here is the position of the row in `pending` (see enumerate()
    # above), not a transactions.id from the database — it only exists to
    # reconcile the LLM's response back to `pending` below.
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
    """Learned tags already on rows. Local model first, API only for leftovers."""
    from finance_agent.db import list_fewshot

    examples = list_fewshot(16)
    # LLM categorization is best-effort: a network error or a response that
    # doesn't parse as JSON must not block ingestion. Rows simply keep
    # whatever rule-based category (often OTHER) they already had.
    if local_complete:
        with suppress(ValueError, TypeError, OSError, RuntimeError):
            categorize_with_llm(rows, local_complete, examples=examples)
    if api_complete:
        with suppress(ValueError, TypeError, OSError, RuntimeError):
            categorize_with_llm(rows, api_complete, examples=examples)
    return rows
