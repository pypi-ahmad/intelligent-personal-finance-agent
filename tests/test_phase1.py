from pathlib import Path

import pytest

from finance_agent.categorize import apply_rules
from finance_agent.ingest import parse_file, parse_json_payload
from finance_agent.llm import _image_mime, models_for


def test_rule_categories() -> None:
    assert apply_rules("SWIGGY Bangalore") == "FOOD"
    assert apply_rules("UBER trip") == "TRANSPORT"
    assert apply_rules("mystery shop") == "OTHER"


def test_csv_debit_credit() -> None:
    csv = (
        b"Date,Narration,Debit,Credit\n12-01-2026,SWIGGY ORDER,250.00,\n13-01-2026,SALARY CREDIT,,50000.00\n"
    )
    rows = parse_file("upi.csv", csv)
    assert len(rows) == 2
    assert rows[0]["amount"] == -250.0
    assert rows[0]["category"] == "FOOD"
    assert rows[1]["amount"] == 50000.0
    assert rows[0]["date"] == "2026-01-12"
    assert rows[1]["date"] == "2026-01-13"


def test_json_fence() -> None:
    data = parse_json_payload('```json\n[{"id": 1, "category": "FOOD"}]\n```')
    assert data[0]["category"] == "FOOD"


def test_provider_models() -> None:
    assert models_for("OpenAI") == ["gpt-5.6-luna"]
    assert models_for("Agnes AI") == ["agnes-2.5-flash"]
    assert models_for("Google") == ["gemini-3.5-flash-lite", "gemini-3.7-flash"]


def test_image_mime() -> None:
    assert _image_mime(b"\x89PNG\r\n\x1a\nxxxx") == "image/png"
    assert _image_mime(b"\xff\xd8\xffxxxx") == "image/jpeg"
    assert _image_mime(b"RIFF\x00\x00\x00\x00WEBP") == "image/webp"


def test_insert_dedup_and_update(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from finance_agent import db

    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    row = {
        "date": "2026-01-12",
        "description": "SWIGGY ORDER",
        "amount": -250.0,
        "currency": "INR",
        "category": "FOOD",
        "source_file": "upi.csv",
    }
    assert db.insert_many([row]) == 1
    assert db.insert_many([row]) == 0
    stored = db.list_transactions()
    assert stored[0]["category"] == "FOOD"
    db.update_category(stored[0]["id"], "SHOPPING")
    assert db.list_transactions()[0]["category"] == "SHOPPING"
    with pytest.raises(ValueError, match="Unknown category"):
        db.update_category(stored[0]["id"], "NOT_A_CAT")
