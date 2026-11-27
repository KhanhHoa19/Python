"""Account maintenance from a terminal (there is no "forgot password" screen).

    python -m src.core.auth.admin_cli list
    python -m src.core.auth.admin_cli seed-demo                       # development only: 3 ready-made accounts
    python -m src.core.auth.admin_cli reset-password <username>      # asks for the new password, nothing is echoed
    docker exec -it studylab-backend python -m src.core.auth.admin_cli reset-password admin
"""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import text

from src.core.auth.security import MIN_PASSWORD_LENGTH, hash_password
from src.core.storage.db import get_db_engine


def list_users() -> int:
    with get_db_engine().connect() as conn:
        rows = conn.execute(text("SELECT id, username, role, full_name FROM users ORDER BY id")).fetchall()
    for user_id, username, role, full_name in rows:
        print(f"{user_id:>4}  {username:<24} {role:<6} {full_name}")
    return 0


def reset_password(username: str, new_password: str | None = None) -> int:
    password = new_password
    if password is None:
        password = getpass.getpass("New password: ")
        if password != getpass.getpass("Repeat it: "):
            print("The two passwords differ.", file=sys.stderr)
            return 1
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"The password needs at least {MIN_PASSWORD_LENGTH} characters.", file=sys.stderr)
        return 1
    with get_db_engine().begin() as conn:
        changed = conn.execute(
            text("UPDATE users SET password_hash = :h WHERE username = :u"),
            {"h": hash_password(password), "u": username.strip().lower()},
        ).rowcount
    if not changed:
        print(f"No user named '{username}'.", file=sys.stderr)
        return 1
    print(f"Password of '{username}' changed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="show every account")
    commands.add_parser("seed-demo", help="create the 3 demo accounts and set their passwords (development only)")
    reset = commands.add_parser("reset-password", help="set a new password for an account")
    reset.add_argument("username")
    args = parser.parse_args(argv)
    if args.command == "seed-demo":
        from src.core.auth.demo_accounts import seed_demo_accounts

        print("Set up:", ", ".join(seed_demo_accounts(get_db_engine(), overwrite_passwords=True)) or "nothing")
        return 0
    return list_users() if args.command == "list" else reset_password(args.username)


if __name__ == "__main__":
    sys.exit(main())
