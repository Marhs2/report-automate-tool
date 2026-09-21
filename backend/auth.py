"""이름+비밀번호 로그인. 세션 토큰으로 현재 사용자를 고정한다."""

from __future__ import annotations

import hashlib
import hmac
import secrets

PBKDF2_ITERATIONS = 210_000
PASSWORD_MIN_LENGTH = 4


def hash_password(password: str) -> str:
    text = str(password or "")
    if len(text) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"비밀번호는 {PASSWORD_MIN_LENGTH}자 이상이어야 합니다.")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        text.encode("utf-8"),
        bytes.fromhex(salt),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"{PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    parts = str(stored or "").split("$")
    if len(parts) != 3:
        return False
    try:
        iterations = int(parts[0])
        salt = bytes.fromhex(parts[1])
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        str(password or "").encode("utf-8"),
        salt,
        iterations,
    ).hex()
    return hmac.compare_digest(digest, parts[2])


def new_session_token() -> str:
    return secrets.token_urlsafe(32)
