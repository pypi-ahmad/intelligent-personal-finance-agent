from pathlib import Path

import pytest

from finance_agent.reports import tax_year_markdown
from finance_agent.vault import decrypt_bytes, encrypt_bytes, lock_db, unlock_db


def test_encrypt_roundtrip() -> None:
    blob = encrypt_bytes(b"ledger-bytes", "pass-1")
    assert blob.startswith(b"PFENC1")
    assert decrypt_bytes(blob, "pass-1") == b"ledger-bytes"
    with pytest.raises(ValueError, match="Wrong passphrase"):
        decrypt_bytes(blob, "nope")


def test_lock_unlock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from finance_agent import vault

    db_path = tmp_path / "finance.db"
    db_path.write_bytes(b"sqlite-bytes")
    monkeypatch.setattr(vault, "DATA_DIR", tmp_path)
    monkeypatch.setattr(vault, "DB_PATH", db_path)
    monkeypatch.setattr(vault, "ENC_PATH", tmp_path / "finance.db.enc")
    lock_db("secret")
    assert not db_path.exists()
    assert vault.is_locked()
    unlock_db("secret")
    assert db_path.read_bytes() == b"sqlite-bytes"
    assert not vault.is_locked()


def test_tax_report_lists_year() -> None:
    text = tax_year_markdown(
        2026,
        [
            {
                "date": "2026-03-01",
                "category": "TRANSPORT",
                "amount": -80.0,
                "description": "IRCTC",
                "merchant": "IRCTC",
            },
            {
                "date": "2026-03-02",
                "category": "INCOME",
                "amount": 500.0,
                "description": "client",
                "merchant": None,
            },
            {
                "date": "2025-03-01",
                "category": "FOOD",
                "amount": -10.0,
                "description": "old",
                "merchant": None,
            },
        ],
    )
    assert "Tax-ready expense report 2026" in text
    assert "TRANSPORT: 80.00" in text
    assert "Income: 500.00" in text
    assert "old" not in text


def test_export_zip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from finance_agent import db

    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    db.insert_many(
        [
            {
                "date": "2026-01-01",
                "description": "SWIGGY",
                "amount": -12.0,
                "currency": "INR",
                "category": "FOOD",
                "source_file": "a.csv",
            }
        ]
    )
    blob = db.export_zip()
    assert blob[:2] == b"PK"
