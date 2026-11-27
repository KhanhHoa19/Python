"""Password hashing (scrypt, standard library) and JWT access tokens (PyJWT, HS256)."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
from collections import defaultdict, deque
from typing import Any

import jwt

logger = logging.getLogger(__name__)

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1
ALGORITHM = "HS256"
MIN_PASSWORD_LENGTH = 8


def hash_password(password: str) -> str:
    """'scrypt$n$r$p$salt$hash' (hex). A new random salt every time."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check. Any malformed stored hash simply fails."""
    try:
        scheme, n, r, p, salt_hex, hash_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = bytes.fromhex(hash_hex)
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
    except (ValueError, TypeError, MemoryError):
        return False
    return hmac.compare_digest(digest, expected)


def create_access_token(user_id: int, role: str, secret: str, expires_hours: float) -> tuple[str, int]:
    """Returns (token, seconds until it expires)."""
    now = int(time.time())
    lifetime = int(expires_hours * 3600)
    payload = {"sub": str(user_id), "role": role, "iat": now, "exp": now + lifetime}
    return jwt.encode(payload, secret, algorithm=ALGORITHM), lifetime


def decode_access_token(token: str, secret: str) -> dict[str, Any] | None:
    """The token's claims, or None if it is malformed, expired or signed with another secret."""
    try:
        claims = jwt.decode(token, secret, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        return None
    return claims if isinstance(claims, dict) else None


class LoginThrottle:
    """Allows `max_failures` wrong logins per key in `window_seconds`; success clears the count."""

    def __init__(self, max_failures: int = 5, window_seconds: float = 300.0, clock: Any = time.monotonic):
        self.max_failures, self.window, self._clock = max_failures, window_seconds, clock
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _recent(self, key: str) -> deque[float]:
        failures = self._failures[key]
        while failures and self._clock() - failures[0] > self.window:
            failures.popleft()
        return failures

    def is_blocked(self, key: str) -> bool:
        return len(self._recent(key)) >= self.max_failures

    def retry_after(self, key: str) -> int:
        failures = self._recent(key)
        return max(1, int(self.window - (self._clock() - failures[0]))) if failures else 0

    def record_failure(self, key: str) -> None:
        self._recent(key).append(self._clock())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)
