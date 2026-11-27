"""Request dependencies: who is calling, and what they may touch."""

from __future__ import annotations

from weakref import WeakKeyDictionary

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Engine

from src.core.auth.security import decode_access_token
from src.core.auth.users import SqlUserRepository, User, jwt_secret
from src.core.models.book import Book
from src.core.storage.db import get_db_engine
from src.core.storage.repositories import SqlBookRepository, SqlVoiceRepository

_bearer = HTTPBearer(auto_error=False)
_SECRETS: WeakKeyDictionary[Engine, str] = WeakKeyDictionary()  # keyed by the engine itself: an id() can be reused


def _secret(engine: Engine) -> str:
    """The signing secret, read from the database once per engine."""
    if engine not in _SECRETS:
        _SECRETS[engine] = jwt_secret(engine)
    return _SECRETS[engine]


def token_secret() -> str:
    return _secret(get_db_engine())


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(401, message, headers={"WWW-Authenticate": "Bearer"})


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> User:
    """The signed-in user, from `Authorization: Bearer <token>`. 401 if missing, invalid, expired or the account is gone."""
    if credentials is None:
        raise _unauthorized("Not signed in.")
    engine = get_db_engine()
    claims = decode_access_token(credentials.credentials, _secret(engine))
    if claims is None:
        raise _unauthorized("Your session has expired. Please sign in again.")
    try:
        user = SqlUserRepository(engine).get_by_id(int(claims["sub"]))
    except (ValueError, TypeError):
        user = None
    if user is None:
        raise _unauthorized("This account no longer exists.")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Administrator access is required.")
    return user


def visible_book(engine: Engine, book_id: int, user: User) -> Book:
    """The book if the user may see it. A book that is someone else's looks exactly like a missing one."""
    book = SqlBookRepository(engine).get_visible(book_id, user.id)
    if book is None:
        raise HTTPException(404, f"Book {book_id} not found")
    return book


def editable_book(engine: Engine, book_id: int, user: User) -> Book:
    """The book if the user may rename or delete it: their own, or a public one for an admin."""
    book = visible_book(engine, book_id, user)
    if book.owner_id != user.id and not (book.is_public and user.is_admin):
        raise HTTPException(403, "You cannot change this book.")
    return book


def check_voice_access(engine: Engine, voice_id: str | None, user: User) -> None:
    """A cloned voice may only be used by its owner (or by everyone if public). Provider voices are open."""
    if not voice_id:
        return
    voice = SqlVoiceRepository(engine).get_voice(voice_id)
    if voice is not None and not (voice["is_public"] or voice["owner_id"] == user.id):
        raise HTTPException(404, f"Voice '{voice_id}' not found")
