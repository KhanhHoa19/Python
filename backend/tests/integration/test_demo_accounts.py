"""One-click demo accounts: off by default, and when on they exist and really log in."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from src.api.app import create_app
from src.core.auth.demo_accounts import demo_accounts, seed_demo_accounts
from src.core.config import get_settings
from src.core.storage.migrations import run_migrations
from tests.auth_helpers import use_engine


@pytest.fixture
def anonymous(test_engine: Engine) -> Generator[TestClient, None, None]:
    with use_engine(test_engine), TestClient(create_app()) as client:
        yield client


@pytest.fixture
def dev_mode(monkeypatch):
    monkeypatch.setenv("DEV_QUICK_LOGIN", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_the_list_is_empty_unless_dev_mode_is_on(anonymous: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("DEV_QUICK_LOGIN", "false")  # the developer's own .env may switch it on
    get_settings.cache_clear()
    assert anonymous.get("/api/auth/demo-accounts").json() == []


def test_dev_mode_lists_three_accounts_and_each_one_logs_in(anonymous: TestClient, test_engine: Engine, dev_mode) -> None:
    run_migrations(test_engine)  # a start with the flag on creates the accounts
    listed = anonymous.get("/api/auth/demo-accounts").json()
    assert [(a["username"], a["role"]) for a in listed] == [("admin", "admin"), ("khanhhoa36", "user"), ("xuanhai18", "user")]
    seed_demo_accounts(test_engine, overwrite_passwords=True)  # the existing admin gets the demo password too
    for account in listed:
        response = anonymous.post("/api/auth/login", json={"username": account["username"], "password": account["password"]})
        assert response.status_code == 200, account["username"]
        assert response.json()["user"]["role"] == account["role"]


def test_seeding_creates_only_what_is_missing_and_keeps_passwords(test_engine: Engine, dev_mode) -> None:
    created = seed_demo_accounts(test_engine)
    assert set(created) == {"khanhhoa36", "xuanhai18"}  # `admin` already exists
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE users SET password_hash = 'changed' WHERE username = 'khanhhoa36'"))
    assert seed_demo_accounts(test_engine) == []
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT password_hash FROM users WHERE username = 'khanhhoa36'")).scalar() == "changed"
    assert seed_demo_accounts(test_engine, overwrite_passwords=True)  # explicit command resets them


def test_demo_passwords_are_long_enough_for_registration_rules() -> None:
    assert all(len(a.password) >= 8 for a in demo_accounts())
