"""Signing in during tests: the API needs a token on every request."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from src.core.auth.security import create_access_token
from src.core.auth.users import SqlUserRepository, User, jwt_secret

ROUTE_MODULES = ["auth", "books", "categories", "player", "analytics", "voices", "notes", "settings", "export", "admin", "ambient"]
TESTER = "tester"


@contextmanager
def use_engine(engine: Engine, extra: tuple[str, ...] = ()) -> Iterator[None]:
    """Make every route module (and the auth dependency) use `engine`."""
    with ExitStack() as stack:
        for module in ROUTE_MODULES:
            stack.enter_context(patch(f"src.api.routes.{module}.get_db_engine", return_value=engine))
        stack.enter_context(patch("src.api.deps.get_db_engine", return_value=engine))
        for target in extra:
            stack.enter_context(patch(target, return_value=engine))
        yield


def user_by_name(engine: Engine, username: str) -> User:
    found = SqlUserRepository(engine).get_with_hash(username)
    assert found is not None, f"no user {username}"
    return found[0]


def make_user(engine: Engine, username: str, role: str = "user") -> User:
    """An account that can only be reached with a token (its password hash never matches)."""
    return SqlUserRepository(engine).create_user(username, "x", username.title(), role)


def token_for(engine: Engine, user: User) -> str:
    return create_access_token(user.id, user.role, jwt_secret(engine), 1)[0]


def sign_in(client: TestClient, engine: Engine, user: User) -> TestClient:
    """Send this user's token with every request of `client`."""
    client.headers["Authorization"] = f"Bearer {token_for(engine, user)}"
    return client


def tester(engine: Engine) -> User:
    return user_by_name(engine, TESTER)

TESTER_ID = 2  # test_engine creates the admin (id 1) first, then the tester
