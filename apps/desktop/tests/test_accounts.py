"""Accounts on the desktop side: sign-in calls, the saved session file, form checks, expiry handling."""

from __future__ import annotations

import os
import stat

import httpx
import pytest

import auth_store
from api_client import ApiClient, ApiError
from ui.viewmodels import avatar_letter, check_credentials


def make_client(handler) -> ApiClient:
    return ApiClient(base_url="http://test", transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------- ApiClient

def test_token_is_sent_with_every_request_once_set() -> None:
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("Authorization"))
        return httpx.Response(200, json=[])

    client = make_client(handler)
    client.list_books()
    client.set_token("abc.def")
    client.list_books()
    client.set_token(None)
    client.list_books()
    assert seen == [None, "Bearer abc.def", None]


def test_an_expired_session_calls_the_hook_but_a_wrong_password_does_not() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "nope"})

    client = make_client(handler)
    calls: list[int] = []
    client.on_unauthorized = lambda: calls.append(1)
    client.set_token("old-token")
    with pytest.raises(ApiError):
        client.list_books()
    assert calls == [1]
    with pytest.raises(ApiError) as info:
        client.login("lan", "wrong")  # a failed sign-in is not an expired session
    assert info.value.status == 401 and calls == [1]


def test_no_hook_call_when_nobody_was_signed_in() -> None:
    client = make_client(lambda request: httpx.Response(401, json={"error": "Not signed in."}))
    calls: list[int] = []
    client.on_unauthorized = lambda: calls.append(1)
    with pytest.raises(ApiError):
        client.list_books()
    assert calls == []


def test_register_login_me_against_the_real_backend(backend) -> None:
    from fastapi.testclient import TestClient

    client = ApiClient(base_url="http://backend")
    client._http = TestClient(backend, base_url="http://backend")
    created = client.register("lan.nguyen", "correct horse", "Lan Nguyễn")
    assert created["user"]["role"] == "user" and created["user"]["full_name"] == "Lan Nguyễn"
    with pytest.raises(ApiError) as taken:
        client.register("LAN.NGUYEN", "another pass", "")
    assert taken.value.status == 409
    with pytest.raises(ApiError) as bad:
        client.login("lan.nguyen", "wrong password")
    assert bad.value.status == 401
    client.set_token(client.login("lan.nguyen", "correct horse")["access_token"])
    assert client.me()["username"] == "lan.nguyen"
    with pytest.raises(ApiError) as short:
        client.register("another", "short", "")
    assert short.value.status == 400


def test_the_backend_rejects_requests_without_a_token(backend) -> None:
    from fastapi.testclient import TestClient

    anonymous = ApiClient(base_url="http://backend")
    anonymous._http = TestClient(backend, base_url="http://backend")
    with pytest.raises(ApiError) as info:
        anonymous.list_books()
    assert info.value.status == 401
    assert anonymous.health()["status"] == "ok"  # the health check stays open


# ---------------------------------------------------------------- saved session

def test_session_file_roundtrip_with_private_permissions() -> None:
    assert auth_store.load() is None
    auth_store.save("tok.en", {"id": 3, "username": "lan", "role": "user"})
    assert auth_store.load() == {"token": "tok.en", "user": {"id": 3, "username": "lan", "role": "user"}}
    if os.name == "posix":
        mode = stat.S_IMODE(os.stat(auth_store._file()).st_mode)
        assert mode == 0o600, oct(mode)
    auth_store.clear()
    assert auth_store.load() is None
    auth_store.clear()  # clearing twice is fine


def test_a_damaged_session_file_is_ignored() -> None:
    path = auth_store._file()
    path.parent.mkdir(parents=True, exist_ok=True)
    for text in ("not json", "[]", "{}", '{"token": "", "user": {}}', '{"token": "t", "user": "x"}'):
        path.write_text(text, encoding="utf-8")
        assert auth_store.load() is None, text


def test_saving_over_a_wider_file_tightens_it() -> None:
    path = auth_store._file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    if os.name == "posix":
        os.chmod(path, 0o644)
        auth_store.save("t", {"id": 1})
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


# ---------------------------------------------------------------- form checks

def test_login_form_checks() -> None:
    assert check_credentials("login", " lan ", "x") is None
    assert check_credentials("login", "", "x") and check_credentials("login", "lan", "")


def test_register_form_checks() -> None:
    assert check_credentials("register", "lan.nguyen", "correct horse", "correct horse") is None
    assert "3–32" in (check_credentials("register", "ab", "correct horse", "correct horse") or "")
    assert "3–32" in (check_credentials("register", "có dấu", "correct horse", "correct horse") or "")
    assert "8 ký tự" in (check_credentials("register", "lan", "short", "short") or "")
    assert "không khớp" in (check_credentials("register", "lan", "correct horse", "different one") or "")


def test_avatar_letter() -> None:
    assert avatar_letter({"full_name": "đức anh", "username": "x"}) == "Đ"
    assert avatar_letter({"full_name": "", "username": "minh"}) == "M"
    assert avatar_letter({}) == "?"


def test_demo_accounts_are_empty_on_a_normal_backend_and_listed_in_dev_mode(backend, monkeypatch) -> None:
    from fastapi.testclient import TestClient
    from src.core.config import get_settings

    client = ApiClient(base_url="http://backend")
    client._http = TestClient(backend, base_url="http://backend")
    monkeypatch.setenv("DEV_QUICK_LOGIN", "false")  # the developer's own .env may switch it on
    get_settings.cache_clear()
    assert client.demo_accounts() == []
    monkeypatch.setenv("DEV_QUICK_LOGIN", "true")
    get_settings.cache_clear()
    listed = client.demo_accounts()
    assert [a["username"] for a in listed] == ["admin", "khanhhoa36", "xuanhai18"]
    from src.core.auth.demo_accounts import seed_demo_accounts
    from src.core.storage import db

    seed_demo_accounts(db.get_db_engine(), overwrite_passwords=True)
    for account in listed:  # the box really signs in
        assert client.login(account["username"], account["password"])["user"]["role"] == account["role"]
