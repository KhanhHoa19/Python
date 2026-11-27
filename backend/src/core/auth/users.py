"""User accounts: repository, first-run admin and the one-time move of single-user data to the admin."""

from __future__ import annotations

import logging
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from src.core.auth.security import hash_password
from src.core.config import get_settings

logger = logging.getLogger(__name__)

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
ROLES = ("admin", "user")


@dataclass(frozen=True)
class User:
    id: int
    username: str
    full_name: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


class UsernameTakenError(ValueError):
    """Another account already has this username (case-insensitive)."""


class SqlUserRepository:
    def __init__(self, engine: Engine):
        self.engine = engine

    @staticmethod
    def _user(row: object) -> User:
        return User(id=int(row[0]), username=row[1], full_name=row[2], role=row[3])  # type: ignore[index]

    def create_user(self, username: str, password_hash: str, full_name: str, role: str = "user") -> User:
        if role not in ROLES:
            raise ValueError(f"Unknown role '{role}'")
        key = username.strip().lower()
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    text("INSERT INTO users (username, password_hash, full_name, role, created_at) "
                         "VALUES (:u, :h, :n, :r, :now)"),
                    {"u": key, "h": password_hash, "n": full_name.strip() or username.strip(), "r": role,
                     "now": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")},
                )
                user_id = result.lastrowid or conn.execute(text("SELECT last_insert_rowid()")).scalar()
        except IntegrityError as exc:
            raise UsernameTakenError(f"Username '{username}' is already taken.") from exc
        return User(id=int(user_id or 0), username=key, full_name=full_name.strip() or username.strip(), role=role)

    def get_by_id(self, user_id: int) -> User | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT id, username, full_name, role FROM users WHERE id = :id"), {"id": user_id}
            ).fetchone()
        return self._user(row) if row else None

    def get_with_hash(self, username: str) -> tuple[User, str] | None:
        """(user, password_hash) for a login attempt, or None if there is no such account."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT id, username, full_name, role, password_hash FROM users WHERE username = :u"),
                {"u": username.strip().lower()},
            ).fetchone()
        return (self._user(row), row[4]) if row else None

    def list_all(self) -> list[tuple[User, str | None]]:
        """Every account with its creation time (admin overview; never any private content)."""
        with self.engine.connect() as conn:
            rows = conn.execute(text("SELECT id, username, full_name, role, created_at FROM users ORDER BY id")).fetchall()
        return [(self._user(r), str(r[4]) if r[4] else None) for r in rows]

    def count(self) -> int:
        with self.engine.connect() as conn:
            return int(conn.execute(text("SELECT COUNT(*) FROM users")).scalar() or 0)

    def first_admin_id(self) -> int | None:
        with self.engine.connect() as conn:
            value = conn.execute(text("SELECT MIN(id) FROM users WHERE role = 'admin'")).scalar()
        return int(value) if value is not None else None


def ensure_admin(engine: Engine) -> int:
    """The id of the first admin; creates the account on a fresh database.

    Name and password come from ADMIN_USERNAME / ADMIN_PASSWORD. Without a password a random one is
    generated and written to the log once, so a forgotten setting never leaves the system open."""
    repo = SqlUserRepository(engine)
    existing = repo.first_admin_id()
    if existing is not None:
        return existing
    cfg = get_settings()
    password = cfg.admin_password
    generated = not password
    if generated:
        password = secrets.token_urlsafe(12)
    admin = repo.create_user(cfg.admin_username, hash_password(password), "Quản trị viên", "admin")
    if generated:
        logger.warning(
            "Created the administrator account '%s' with the one-time password: %s "
            "(set ADMIN_PASSWORD in .env to choose your own).", admin.username, password,
        )
    else:
        logger.info("Created the administrator account '%s'.", admin.username)
    return admin.id


def cli_user_id(engine: Engine) -> int:
    """The terminal tool (`studylab`) has no login: it works as the first admin, whose library it shows."""
    admin_id = SqlUserRepository(engine).first_admin_id()
    if admin_id is None:
        raise LookupError("No administrator account yet. Start the backend once to create it.")
    return admin_id


def assign_legacy_data(engine: Engine, admin_id: int) -> None:
    """Data created before accounts existed belongs to the admin, as private data. Safe to run on every start."""
    params = {"admin": admin_id}
    with engine.begin() as conn:
        conn.execute(text("UPDATE books SET owner_id = :admin WHERE owner_id IS NULL AND is_public = 0"), params)
        conn.execute(text("UPDATE voice_profiles SET owner_id = :admin WHERE owner_id IS NULL AND is_public = 0"), params)
        conn.execute(text("UPDATE audio_notes SET user_id = :admin WHERE user_id IS NULL"), params)
        conn.execute(text("UPDATE reading_sessions SET user_id = :admin WHERE user_id IS NULL"), params)
        done = conn.execute(text("SELECT 1 FROM app_settings WHERE setting_key = 'migrated_bookmarks_v1'")).fetchone()
        if done is None:
            # One position per book (the old, single-user bookmarks) becomes the admin's progress.
            conn.execute(
                text("""
                    INSERT INTO user_book_progress
                        (user_id, book_id, status, current_chapter, current_sentence_index, completion_percentage, voice, last_read_at)
                    SELECT :admin, b.book_id,
                           CASE WHEN b.completion_percentage >= 100 THEN 'completed'
                                WHEN b.completion_percentage > 0 OR b.current_sentence_index > 0 THEN 'reading'
                                ELSE 'unread' END,
                           b.current_chapter, b.current_sentence_index, b.completion_percentage, b.voice, b.last_read_at
                    FROM bookmarks b WHERE EXISTS (SELECT 1 FROM books k WHERE k.id = b.book_id)
                      AND NOT EXISTS (SELECT 1 FROM user_book_progress p WHERE p.user_id = :admin AND p.book_id = b.book_id)
                """),
                params,
            )
            conn.execute(text("INSERT INTO app_settings (setting_key, setting_value) VALUES ('migrated_bookmarks_v1', '1')"))


def jwt_secret(engine: Engine) -> str:
    """JWT_SECRET from the environment, else a random secret kept in the database (created on first use)."""
    configured = get_settings().jwt_secret
    if configured:
        return configured
    with engine.begin() as conn:
        row = conn.execute(text("SELECT setting_value FROM app_settings WHERE setting_key = 'jwt_secret'")).fetchone()
        if row:
            return str(row[0])
        secret = secrets.token_urlsafe(48)
        try:
            conn.execute(text("INSERT INTO app_settings (setting_key, setting_value) VALUES ('jwt_secret', :v)"), {"v": secret})
        except IntegrityError:  # another worker created it first
            row = conn.execute(text("SELECT setting_value FROM app_settings WHERE setting_key = 'jwt_secret'")).fetchone()
            return str(row[0]) if row else secret
        return secret
