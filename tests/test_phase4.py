from pathlib import Path

import pytest

from finance_agent.categorize import apply_rules, assign_category
from finance_agent.merchants import merchant_key, normalize_merchant


def test_merchant_aliases() -> None:
    assert normalize_merchant("AMZN MKTP IN 123") == "Amazon"
    assert normalize_merchant("SWIGGY BANGALORE") == "Swiggy"
    assert normalize_merchant("Uber Eats Delhi") == "Uber Eats"
    assert normalize_merchant("UBER trip") == "Uber"
    assert normalize_merchant("mystery shop") is None


def test_user_rule_beats_builtin() -> None:
    cat, merchant = assign_category(
        "SWIGGY ORDER",
        user_rules=[{"needle": "swiggy", "category": "ENTERTAINMENT"}],
    )
    assert cat == "ENTERTAINMENT"
    assert merchant == "Swiggy"


def test_correction_beats_builtin() -> None:
    cat, merchant = assign_category(
        "AMZN MKTP",
        correction_map={"Amazon": "GROCERIES"},
    )
    assert merchant == "Amazon"
    assert cat == "GROCERIES"
    assert apply_rules("AMAZON MKTP") == "SHOPPING"


def test_learn_and_split(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from finance_agent import db

    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    db.insert_many(
        [
            {
                "date": "2026-01-12",
                "description": "AMZN MKTP IN",
                "amount": -100.0,
                "currency": "INR",
                "category": "SHOPPING",
                "merchant": "Amazon",
                "source_file": "a.csv",
            }
        ]
    )
    row = db.list_transactions()[0]
    db.update_category(row["id"], "GROCERIES")
    assert db.latest_correction_map()["Amazon"] == "GROCERIES"
    shots = db.list_fewshot()
    assert any(item["merchant"] == "Amazon" and item["category"] == "GROCERIES" for item in shots)

    db.upsert_user_rule("corner cafe", "FOOD")
    assert db.list_user_rules()[0]["needle"] == "corner cafe"

    n = db.split_transaction(
        row["id"],
        [
            {"amount": -40.0, "category": "GROCERIES"},
            {"amount": -60.0, "category": "SHOPPING"},
        ],
    )
    assert n == 2
    leftover = db.list_transactions()
    assert len(leftover) == 2
    assert all("(split)" in item["description"] for item in leftover)
    assert abs(sum(item["amount"] for item in leftover) - -100.0) < 0.01


def test_merchant_key_fallback() -> None:
    assert merchant_key("Random Mart 99") == "random mart 99"
