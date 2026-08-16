"""Parse uploaded statements into normalized transaction dicts."""

from __future__ import annotations

import io
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pypdf import PdfReader

from finance_agent.categorize import apply_rules
from finance_agent.config import CATEGORIES
from finance_agent.merchants import normalize_merchant

DATE_COLS = ("date", "txn date", "transaction date", "value date", "posted", "trans date")
DESC_COLS = ("description", "particulars", "narration", "details", "merchant", "remarks", "narrative")
AMOUNT_COLS = ("amount", "amt", "transaction amount", "inr")
DEBIT_COLS = ("debit", "withdrawal", "withdrawals", "dr")
CREDIT_COLS = ("credit", "deposit", "deposits", "cr")

EXTRACT_PROMPT = """Extract bank/card/UPI transactions from this statement text.
Return ONLY a JSON array. Each item:
{"date": "YYYY-MM-DD", "description": "...", "amount": -12.50, "currency": "INR"}
Use negative amount for expenses/debits, positive for income/credits.
Skip balances, headers, and totals. Unknown date -> omit the row.
"""


def parse_file(name: str, data: bytes, llm_extract: Any | None = None) -> list[dict[str, Any]]:
    suffix = Path(name).suffix.lower()
    if suffix in {".csv", ".tsv"}:
        rows = _from_table(pd.read_csv(io.BytesIO(data)))
    elif suffix in {".xlsx", ".xls"}:
        rows = _from_table(pd.read_excel(io.BytesIO(data)))
    elif suffix == ".pdf":
        text = _pdf_text(data)
        rows = _from_llm(text, name, llm_extract) if llm_extract else []
        if not rows and text.strip():
            rows = _from_loose_text(text)
    elif suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        if not llm_extract:
            msg = "Image statements need a selected model."
            raise ValueError(msg)
        rows = _from_llm(f"(image file: {name})", name, llm_extract, image=data)
    else:
        msg = f"Unsupported file type: {suffix or name}"
        raise ValueError(msg)
    for row in rows:
        row["source_file"] = name
        row["category"] = apply_rules(row["description"])
        row["merchant"] = normalize_merchant(row["description"])
    return rows


def _norm(col: str) -> str:
    return re.sub(r"\s+", " ", str(col).strip().lower())


def _pick(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    for cand in candidates:
        for col in columns:
            if col == cand or cand in col:
                return col
    return None


def _parse_date(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if hasattr(value, "isoformat") and not isinstance(value, str):
        try:
            return value.isoformat()[:10]
        except (TypeError, ValueError):
            return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%d %b %Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(text[:32], fmt).date().isoformat()
        except ValueError:
            continue
    parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date().isoformat()


def _parse_amount(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    text = re.sub(r"[₹$€£]", "", text)
    if text.endswith("CR"):
        text = text.removesuffix("CR")
    if text.endswith("DR"):
        text = "-" + text.removesuffix("DR")
    text = text.replace("(", "-").replace(")", "")
    if not text or text in {"-", "—"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _from_table(frame: pd.DataFrame) -> list[dict[str, Any]]:
    frame = frame.copy()
    frame.columns = [_norm(c) for c in frame.columns]
    cols = list(frame.columns)
    date_col = _pick(cols, DATE_COLS)
    desc_col = _pick(cols, DESC_COLS)
    amount_col = _pick(cols, AMOUNT_COLS)
    debit_col = _pick(cols, DEBIT_COLS)
    credit_col = _pick(cols, CREDIT_COLS)
    if not date_col or not desc_col:
        msg = f"Could not find date/description columns. Saw: {cols}"
        raise ValueError(msg)
    if not amount_col and not debit_col and not credit_col:
        msg = f"Could not find amount columns. Saw: {cols}"
        raise ValueError(msg)

    rows: list[dict[str, Any]] = []
    for rec in frame.to_dict(orient="records"):
        date = _parse_date(rec.get(date_col))
        desc = str(rec.get(desc_col) or "").strip()
        if not date or not desc:
            continue
        amount: float | None = None
        if debit_col or credit_col:
            debit = _parse_amount(rec.get(debit_col)) if debit_col else None
            credit = _parse_amount(rec.get(credit_col)) if credit_col else None
            if debit:
                amount = -abs(debit)
            elif credit:
                amount = abs(credit)
        if amount is None and amount_col:
            amount = _parse_amount(rec.get(amount_col))
        if amount is None:
            continue
        rows.append(
            {
                "date": date,
                "description": desc,
                "amount": amount,
                "currency": "INR",
            }
        )
    return rows


def _pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _from_loose_text(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        date_match = re.search(r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})", line)
        amount_match = re.search(r"[-+]?\d[\d,]*\.\d{2}", line)
        if not date_match or not amount_match:
            continue
        date = _parse_date(date_match.group(1))
        amount = _parse_amount(amount_match.group(0))
        desc = line.replace(date_match.group(1), "").replace(amount_match.group(0), "").strip(" |-")
        if date and desc and amount is not None:
            rows.append({"date": date, "description": desc, "amount": -abs(amount), "currency": "INR"})
    return rows


def parse_json_payload(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start_arr, end_arr = cleaned.find("["), cleaned.rfind("]")
    start_obj, end_obj = cleaned.find("{"), cleaned.rfind("}")
    if start_arr != -1 and end_arr > start_arr and (start_obj == -1 or start_arr <= start_obj):
        return json.loads(cleaned[start_arr : end_arr + 1])
    if start_obj != -1 and end_obj > start_obj:
        return json.loads(cleaned[start_obj : end_obj + 1])
    return json.loads(cleaned)


def _from_llm(text: str, name: str, llm_extract: Any, image: bytes | None = None) -> list[dict[str, Any]]:
    raw = llm_extract(EXTRACT_PROMPT + "\n\n" + text[:12000], image=image)
    payload = parse_json_payload(raw)
    if not isinstance(payload, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        date = _parse_date(item.get("date"))
        desc = str(item.get("description") or "").strip()
        amount = _parse_amount(item.get("amount"))
        if not date or not desc or amount is None:
            continue
        currency = str(item.get("currency") or "INR").upper()[:8]
        if currency not in {"INR", "USD", "EUR", "GBP"}:
            currency = "INR"
        category = str(item.get("category") or "").upper()
        rows.append(
            {
                "date": date,
                "description": desc,
                "amount": amount,
                "currency": currency,
                "category": category if category in CATEGORIES else "OTHER",
            }
        )
    return rows
