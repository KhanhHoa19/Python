"""Fill a running system with a varied demo catalogue and two different reading histories.

    python -m scripts.seed_demo_data --base http://localhost:5000 \\
        --admin-password ... --demo khanhhoa36=... --demo xuanhai18=...

Works through the public API (so every rule applies) and is safe to run twice: a book that already exists is skipped."""

from __future__ import annotations

import argparse
import io
from datetime import UTC, datetime, timedelta

import httpx

from scripts.demo_books import BOOKS, HISTORY, book_text


def login(client: httpx.Client, username: str, password: str) -> httpx.Client:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    response.raise_for_status()
    return httpx.Client(base_url=client.base_url, headers={"Authorization": f"Bearer {response.json()['access_token']}"}, timeout=120)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://localhost:5000")
    parser.add_argument("--admin", default="admin")
    parser.add_argument("--admin-password", required=True)
    parser.add_argument("--demo", action="append", default=[], metavar="USER=PASSWORD", help="a demo reader to give a history to")
    args = parser.parse_args()

    anon = httpx.Client(base_url=args.base, timeout=60)
    admin = login(anon, args.admin, args.admin_password)
    categories = {c["slug"]: c["id"] for c in admin.get("/api/categories").json()}
    existing = {b["title"]: b["id"] for b in admin.get("/api/books?source=system&limit=500").json()}
    existing.update({b["title"]: b["id"] for b in admin.get("/api/admin/books").json()})

    created = 0
    for book in BOOKS:
        if book.title in existing:
            continue
        response = admin.post(
            "/api/books/ingest",
            files={"file": (f"{book.title}.txt", io.BytesIO(book_text(book).encode("utf-8")))},
            data={"title": book.title, "author": book.author, "category_id": str(categories[book.category]), "is_public": "true"},
        )
        response.raise_for_status()
        existing[book.title] = response.json()["book_id"]
        created += 1
    print(f"catalogue: {created} new book(s), {len(BOOKS)} in total")

    for credential in args.demo:
        username, _, password = credential.partition("=")
        reader = login(anon, username, password)
        now = datetime.now(UTC)
        for number, (title, status, completion, minutes, favorite) in enumerate(HISTORY.get(username, [])):
            book_id = existing[title]
            reader.post(f"/api/books/{book_id}/shelf")
            detail = reader.get(f"/api/books/{book_id}").json()
            total = max(detail["total_sentences"], 1)
            index = min(int(total * completion / 100), total - 1)
            reader.post("/api/bookmarks", json={"book_id": book_id, "current_chapter": 1, "current_sentence_index": index, "completion_percentage": completion})
            if status == "completed":
                reader.put(f"/api/books/{book_id}/status", json={"status": "completed"})
            if favorite:
                reader.put(f"/api/books/{book_id}/favorite", json={"is_favorite": True})
            start = now - timedelta(days=2 + number * 3, minutes=minutes)
            reader.post("/api/sessions", json={
                "book_id": book_id, "duration_seconds": minutes * 60, "sentences_read": int(total * completion / 100),
                "words_read": int(detail["total_words"] * completion / 100),
                "start_time": start.isoformat(), "end_time": (start + timedelta(minutes=minutes)).isoformat(),
            }).raise_for_status()
        print(f"history: {username} now has {len(HISTORY.get(username, []))} book(s) on the shelf")


if __name__ == "__main__":
    main()
