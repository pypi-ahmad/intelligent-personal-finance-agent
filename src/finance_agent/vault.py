"""Optional at-rest lock for the SQLite file. Passphrase never stored.

Swaps data/finance.db for an encrypted data/finance.db.enc and back.
db.py assumes DB_PATH exists and is plaintext SQLite; callers must check
is_locked() (streamlit_app.py does, before any db.py access) rather than
letting db.py fail on a missing file.
"""

from __future__ import annotations

import base64
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from finance_agent.config import DATA_DIR, DB_PATH

# On-disk blob layout: MAGIC + salt + Fernet token. A fresh random salt per
# encrypt_bytes() call means the same passphrase never produces the same
# ciphertext twice.
MAGIC = b"PFENC1"
SALT_LEN = 16
KDF_ROUNDS = 200_000  # PBKDF2-HMAC-SHA256 iterations: higher = slower brute force, slower unlock.
ENC_PATH = DATA_DIR / "finance.db.enc"


def is_locked() -> bool:
    # Locked state is inferred purely from file presence. If both files exist
    # (e.g. an unlock was interrupted, or a plaintext copy was restored by
    # hand) this reports unlocked and DB_PATH is used, leaving the stale
    # .enc file untouched rather than raising.
    return ENC_PATH.exists() and not DB_PATH.exists()


def encrypt_bytes(raw: bytes, passphrase: str) -> bytes:
    if not passphrase:
        msg = "Passphrase required"
        raise ValueError(msg)
    salt = os.urandom(SALT_LEN)
    token = Fernet(_fernet_key(passphrase, salt)).encrypt(raw)
    return MAGIC + salt + token


def decrypt_bytes(blob: bytes, passphrase: str) -> bytes:
    if not blob.startswith(MAGIC):
        msg = "Not an encrypted finance database"
        raise ValueError(msg)
    salt = blob[len(MAGIC) : len(MAGIC) + SALT_LEN]
    token = blob[len(MAGIC) + SALT_LEN :]
    try:
        return Fernet(_fernet_key(passphrase, salt)).decrypt(token)
    except InvalidToken as exc:
        msg = "Wrong passphrase"
        raise ValueError(msg) from exc


def lock_db(passphrase: str) -> None:
    if not DB_PATH.exists():
        msg = "No database to lock"
        raise ValueError(msg)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ENC_PATH.write_bytes(encrypt_bytes(DB_PATH.read_bytes(), passphrase))
    DB_PATH.unlink()


def unlock_db(passphrase: str) -> None:
    if not ENC_PATH.exists():
        msg = "No encrypted database"
        raise ValueError(msg)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.write_bytes(decrypt_bytes(ENC_PATH.read_bytes(), passphrase))
    ENC_PATH.unlink()


def _fernet_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=KDF_ROUNDS)
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))
