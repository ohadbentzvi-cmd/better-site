"""Unit tests for api/auth.py password hashing.

Pure-Python — no DB. Verifies bcrypt round-trip and that hash_password
produces distinct hashes for the same input (salt is not deterministic).
"""

from __future__ import annotations

import pytest

from api.auth import hash_password, verify_password


def test_hash_password_produces_bcrypt_hash() -> None:
    h = hash_password("hunter2")
    # bcrypt prefix.
    assert h.startswith("$2b$") or h.startswith("$2a$") or h.startswith("$2y$")
    assert len(h) >= 50


def test_verify_password_roundtrip() -> None:
    h = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", h) is True
    assert verify_password("wrong password", h) is False


def test_hash_password_uses_salt() -> None:
    """Two calls with the same input yield different hashes."""
    h1 = hash_password("same-password")
    h2 = hash_password("same-password")
    assert h1 != h2
    # Both still verify.
    assert verify_password("same-password", h1)
    assert verify_password("same-password", h2)


def test_verify_password_rejects_empty() -> None:
    h = hash_password("x")
    assert verify_password("", h) is False


@pytest.mark.parametrize("bad_hash", ["", "not-a-hash", "$2b$fake"])
def test_verify_password_rejects_bad_hash(bad_hash: str) -> None:
    # passlib raises for malformed hashes; verify_password should return False.
    try:
        result = verify_password("whatever", bad_hash)
    except Exception:
        # Acceptable: passlib rejected outright.
        return
    assert result is False
