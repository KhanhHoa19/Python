"""Ready-made accounts for local testing (DEV_QUICK_LOGIN=true). Never enable this on a shared server."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from sqlalchemy import Engine, text

from src.core.auth.security import hash_password
from src.core.auth.users import SqlUserRepository
from src.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DemoAccount:
    username: str
    password: str
    full_name: str
    role: str


def _password(username: str) -> str:
    """From DEMO_PASSWORD_<USERNAME> in .env (never in the repository); a plainly fake default otherwise."""
    return os.getenv(f"DEMO_PASSWORD_{username.upper()}") or f"Demo@{username}1"


def demo_accounts() -> list[DemoAccount]:
    """The administrator (named by ADMIN_USERNAME) and two ordinary users."""
    admin = get_settings().admin_username
    return [
        DemoAccount(admin, _password(admin), "Quản trị viên", "admin"),
        DemoAccount("khanhhoa36", _password("khanhhoa36"), "Khánh Hòa", "user"),
        DemoAccount("xuanhai18", _password("xuanhai18"), "Xuân Hải", "user"),
    ]


def seed_demo_accounts(engine: Engine, overwrite_passwords: bool = False) -> list[str]:
    """Create the accounts that are missing. With `overwrite_passwords`, also (re)set the password of those that exist.
    Returns the usernames that were created or changed."""
    repo = SqlUserRepository(engine)
    touched: list[str] = []
    for account in demo_accounts():
        found = repo.get_with_hash(account.username)
        if found is None:
            repo.create_user(account.username, hash_password(account.password), account.full_name, account.role)
            touched.append(account.username)
        elif overwrite_passwords:
            with engine.begin() as conn:
                conn.execute(
                    text("UPDATE users SET password_hash = :h WHERE id = :id"),
                    {"h": hash_password(account.password), "id": found[0].id},
                )
            touched.append(account.username)
    if touched:
        logger.warning("DEV_QUICK_LOGIN: demo accounts ready: %s", ", ".join(touched))
    return touched
