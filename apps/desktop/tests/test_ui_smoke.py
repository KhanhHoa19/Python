"""Runs the real UI code against a real backend with *fake* Tk widgets.

Why: tkinter may be unavailable (headless CI, missing python3-tk). With stub widgets we still execute
every screen's own logic (callbacks, data flow, matplotlib drawing) and catch exceptions in it.
This does NOT verify how CustomTkinter lays widgets out; that needs a real display.
"""

from __future__ import annotations

import logging
import sys
import time
import types

import pytest
from conftest import FakeOutput, wait_for


class W:
    """Stub widget: accepts any construction/method call; remembers values set via set/insert."""

    def __init__(self, *args, **kwargs):
        self._value = ""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *a, **k: W()

    def get(self, *args):
        return self._value

    def set(self, value):
        self._value = value

    def insert(self, index, text, *tags):
        self._value = text

    def delete(self, *args):
        self._value = ""

    def tag_ranges(self, *args):
        return ()

    def tag_names(self, *args):
        return ()

    def winfo_exists(self):
        return True

    def winfo_reqwidth(self):
        return 80

    def winfo_children(self):
        return []

    def winfo_toplevel(self):
        return self

    def after(self, *args):
        return "job"

    def cget(self, key):
        return "disabled"

    def index(self, *args):
        return "1.0"

    def focus_get(self):
        return None


class _Var:
    def __init__(self, value=None):
        self._v = value

    def get(self):
        return self._v

    def set(self, value):
        self._v = value


def _nested_dict():
    """Stand-in for CustomTkinter's theme dictionary: any key path can be read and updated."""
    import collections

    return collections.defaultdict(_nested_dict)


def _module(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    return mod


@pytest.fixture
def fake_tk(monkeypatch):
    """Install stub tkinter/customtkinter/FigureCanvasTkAgg and import the UI fresh."""
    class TclError(Exception):
        pass

    filedialog = _module("tkinter.filedialog", askopenfilename=lambda **k: "", asksaveasfilename=lambda **k: "")
    messagebox = _module("tkinter.messagebox", askyesno=lambda *a, **k: True)
    tkinter = _module(
        "tkinter", Misc=W, Event=W, Entry=type("Entry", (W,), {}), Text=type("Text", (W,), {}),
        TclError=TclError, StringVar=_Var, BooleanVar=_Var, filedialog=filedialog, messagebox=messagebox,
    )
    ctk = _module("customtkinter")
    ctk.__getattr__ = lambda name: W  # every CTk* class and function is a stub widget
    ctk.ThemeManager = types.SimpleNamespace(theme=_nested_dict())
    canvas_mod = _module("matplotlib.backends.backend_tkagg", FigureCanvasTkAgg=W)
    stubs = {
        "tkinter": tkinter, "tkinter.filedialog": filedialog, "tkinter.messagebox": messagebox,
        "customtkinter": ctk, "matplotlib.backends.backend_tkagg": canvas_mod,
    }
    for name, module in stubs.items():
        monkeypatch.setitem(sys.modules, name, module)
    for name in [m for m in sys.modules if m == "ui" or (m.startswith("ui.") and m != "ui.viewmodels")]:
        monkeypatch.delitem(sys.modules, name)
    yield
    for name in [m for m in sys.modules if m.startswith("ui.") and m != "ui.viewmodels"]:
        del sys.modules[name]


def pump(app, seconds: float = 0.4) -> None:
    """Run queued UI callbacks the way Tk's main loop would."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.ui._drain()
        time.sleep(0.02)


class _ErrorCollector(logging.Handler):
    """Collects ERROR records for the whole test (caplog.records only covers the current phase)."""

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(f"{record.name}: {record.getMessage()}\n{self.format(record)}")


@pytest.fixture
def app(fake_tk, api, book):
    collector = _ErrorCollector()
    logging.getLogger().addHandler(collector)
    api.save_bookmark(book["book_id"], 1, 1, 66.7)  # an in-progress book, so startup resumes it
    api.create_note(book["book_id"], 0, 0, 8, "ghi nhớ")
    from ui.app import App

    application = App(api, FakeOutput(duration=0.02))
    pump(application)
    yield application
    application.ui.close()
    logging.getLogger().removeHandler(collector)
    assert not collector.messages, "\n".join(collector.messages)


def test_startup_loads_settings_voices_and_resumes_last_book(app, book) -> None:
    assert app.settings["prefetch_count"] == 2
    assert app.voices and app.current_voice_id
    reader = app.ctx.reader
    assert reader.book and reader.book.book_id == book["book_id"]
    assert reader.index == 1 and not reader.is_playing  # positioned, not auto-playing


def test_play_to_the_end_updates_reader_state(app) -> None:
    app.reader_tab._toggle()
    assert wait_for(lambda: (pump(app, 0.1), app.reader_tab._state == "finished")[1], timeout=8)
    assert app.ctx.reader.index == 2


def test_transport_controls_do_not_raise(app) -> None:
    reader = app.ctx.reader
    reader.next()
    reader.previous()
    reader.jump(0)
    app.reader_tab._speed_chosen("1.25x")
    app.reader_tab.jump_entry.insert(0, "3")
    app.reader_tab._jump_from_entry()
    pump(app, 0.2)
    assert reader.index == 2 and reader.speed == 1.25


def test_library_books_and_notes_views_render(app) -> None:
    library = app.library_tab
    library.refresh()
    pump(app)
    assert library.tab == "reading" and len(library.books) == 1  # the resumed book is being read
    assert library.counts["reading"] == 1
    library._switch("Chưa nghe (0)")
    pump(app)
    assert library.tab == "unread" and library.books == []  # empty tab message path
    library._switch("Đang nghe dở (1)")
    library.search.insert(0, "khong co")
    library.refresh()
    pump(app)
    assert library.books == []  # the backend found nothing for this search
    app._tab_changed()


def test_quotes_tab_lists_filters_and_plays(app, book) -> None:
    quotes = app.quotes_tab
    quotes.refresh()
    pump(app)
    assert len(quotes.notes) == 1 and quotes.notes[0]["note_text"] == "ghi nhớ"  # the note created by the fixture
    app.reader_tab._bookmark()  # the one-tap bookmark of the sentence being read
    pump(app)
    assert app.reader_tab._saved_quote is not None and app.reader_tab._saved_quote["has_audio"]
    app.reader_tab._tag_saved_quote("wise")
    pump(app)
    assert app.reader_tab._saved_quote["emotion_tag"] == "wise"
    quotes.refresh()
    pump(app)
    assert len(quotes.notes) == 2 and {n["emotion_tag"] for n in quotes.notes} == {None, "wise"}
    quotes.feeling.set("Triết lý hay")
    quotes.refresh()
    pump(app)
    assert [n["emotion_tag"] for n in quotes.notes] == ["wise"]
    quotes.search.insert(0, "khong co")
    quotes._render()
    assert quotes.shown == []  # the empty-result message path
    app.show_quotes_for(book["book_id"])
    assert quotes.book_id == book["book_id"]
    quotes.shutdown()


def test_explore_tab_lists_public_books_and_picks_categories(app) -> None:
    explore = app.explore_tab
    explore.refresh()
    pump(app)
    assert explore.books == []  # nobody published a system book
    assert app.categories and app.categories[0]["slug"] == "tieu-thuyet"
    assert len(app.categories) == 15 and app.categories[-1]["slug"] == "khac"
    assert len(app.explore_tab.chips._buttons) == 16 == len(app.library_tab.chips._buttons)  # "Tất cả" + 15 tags
    app.pick_category("cong-nghe")
    pump(app)
    assert app.category == "cong-nghe"
    app.pick_category("cong-nghe")  # clicking again clears the filter
    assert app.category is None


def test_stats_tab_draws_real_matplotlib_charts(app, api) -> None:
    app.stats_tab.refresh()
    pump(app)
    assert len(app.stats_tab.figure.axes) == 3
    app.stats_tab.range_buttons.set("Tất cả")
    app.stats_tab.refresh()
    pump(app)
    assert len(app.stats_tab.figure.axes) == 3


def test_all_dialogs_open_and_load(app, book) -> None:
    from ui.dialogs import (
        BookPickerDialog,
        CloneVoiceDialog,
        EditNoteDialog,
        ExportDialog,
        NoteDialog,
        SettingsDialog,
        UploadDialog,
    )

    ctx = app.ctx
    book_row = ctx.api.list_books()[0]
    note = ctx.api.list_notes()[0]
    dialogs = [
        UploadDialog(app, ctx, lambda r: None),
        CloneVoiceDialog(app, ctx, lambda v: None),
        SettingsDialog(app, ctx),
        BookPickerDialog(app, ctx, lambda b: None),
        NoteDialog(app, ctx, book["book_id"], 0, 0, 8, "Xin chào", lambda: None),
        EditNoteDialog(app, ctx, note, lambda: None),
        ExportDialog(app, ctx, book_row),
    ]
    pump(app)
    settings_dialog = dialogs[2]
    settings_dialog._run_checks()
    settings_dialog._save()
    pump(app)
    assert ctx.api.get_settings()["prefetch_count"] >= 1
    export_dialog = dialogs[-1]
    export_dialog._start()
    pump(app, 1.5)
    assert getattr(export_dialog, "file_name", "").endswith(".wav")


def test_save_note_and_delete_book_via_dialog_logic(app, book) -> None:
    from ui.dialogs import NoteDialog

    dialog = NoteDialog(app, app.ctx, book["book_id"], 1, 0, 4, "Đây", lambda: None)
    dialog.box._value = "ghi chú mới"
    dialog._save()
    pump(app)
    assert len(app.ctx.api.list_notes()) == 2
    app.library_tab.refresh()
    pump(app)
    app.library_tab._remove_book(app.library_tab.books[0])
    pump(app)
    assert app.ctx.api.list_books() == [] and app.ctx.reader.book is None


def test_edit_dialog_renames_the_book_and_updates_the_open_reader(app, book) -> None:
    from ui.dialogs import EditBookDialog

    api = app.ctx.api
    book_row = api.list_books()[0]
    assert app.ctx.reader.book is not None  # the in-progress book was resumed at startup

    results: list[dict] = []
    dialog = EditBookDialog(app, app.ctx, book_row, results.append)
    dialog.entry._value = "  Tên   mới của sách "
    dialog._save()
    pump(app)
    assert results and results[0]["title"] == "Tên mới của sách"
    assert api.list_books()[0]["title"] == "Tên mới của sách"

    app.on_book_renamed(book_row["id"], "Tên mới của sách")
    assert app.ctx.reader.book.title == "Tên mới của sách"

    empty = EditBookDialog(app, app.ctx, api.list_books()[0], results.append)
    empty.entry._value = "   "
    empty._save()
    pump(app, 0.3)
    assert len(results) == 1 and api.list_books()[0]["title"] == "Tên mới của sách"  # rejected, unchanged


def test_voices_tab_lists_sets_default_and_renames(app, tmp_path) -> None:
    from conftest import make_wav

    voices = app.voices_tab
    voices.refresh()
    pump(app)
    assert voices.shown and not any(v.get("is_custom") for v in voices.shown)  # provider voices only so far
    sample = tmp_path / "mau.wav"
    sample.write_bytes(make_wav(6))
    created = app.ctx.api.clone_voice(sample, "Giọng của Hoa", "vi", "female", consent=True)
    voices.group.set("Giọng của tôi")
    voices.refresh()
    pump(app)
    assert [v["voice_id"] for v in voices.shown] == [created["voice_id"]]
    voices._make_default(voices.shown[0])
    pump(app)
    assert app.settings["default_voice"] == created["voice_id"] and app.current_voice_id == created["voice_id"]
    voices._delete(voices.shown[0])  # the stub messagebox answers "yes"
    pump(app)
    assert voices.shown == []


def test_admin_tab_only_exists_for_admins(app) -> None:
    assert app.admin_tab is None  # the fixture signs in as a normal member


def test_admin_tab_manages_books_categories_voices_and_users(fake_tk, admin_api, book, tmp_path) -> None:
    from ui.app import App

    collector = _ErrorCollector()
    logging.getLogger().addHandler(collector)
    try:
        sample = tmp_path / "txt.txt"
        sample.write_text("Câu một. Câu hai.", encoding="utf-8")
        uploaded = admin_api.ingest_book(sample, title="Sách của admin")
        application = App(admin_api, FakeOutput(duration=0.02), user={"id": 1, "username": "admin", "role": "admin", "full_name": "Admin"})
        pump(application)
        admin = application.admin_tab
        assert admin is not None
        for section in ("Sách hệ thống", "Thể loại", "Giọng hệ thống", "Người dùng"):
            admin.section.set(section)
            admin.refresh()
            pump(application, 0.3)
        admin._act(lambda: admin_api.set_book_public(uploaded["book_id"], True), "ok")
        pump(application)
        assert next(b for b in admin_api.admin_books() if b["id"] == uploaded["book_id"])["is_public"]
        admin.section.set("Sách hệ thống")
        admin.refresh()
        pump(application)
        admin._add_book()  # opens the stub dialog
        admin._edit_book(next(b for b in admin_api.admin_books() if b["id"] == uploaded["book_id"]))  # opens the stub dialog
        admin_api.update_book(uploaded["book_id"], title="Tên đã sửa", author="Tác giả mới")
        assert admin_api.admin_books()[0]["author"] == "Tác giả mới"
        admin._delete_book(next(b for b in admin_api.admin_books() if b["id"] == uploaded["book_id"]))  # the stub answers "yes"
        pump(application)
        assert uploaded["book_id"] not in {b["id"] for b in admin_api.admin_books()}
        admin._act(lambda: admin_api.create_category("Thử", "book-open", "#336699"), "ok")
        pump(application)
        assert any(c["slug"] == "thu" for c in application.categories)  # the sidebar list was reloaded
    finally:
        application.ui.close()
        logging.getLogger().removeHandler(collector)
    assert not collector.messages, "\n".join(collector.messages)


def test_ambient_dialog_saves_choices_and_the_reader_follows(app, admin_api, tmp_path) -> None:
    from ui.dialogs import AmbientDialog

    sound = tmp_path / "mua.mp3"
    sound.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 500)
    track = admin_api.add_ambient(sound, "Mưa rơi")  # an administrator adds it to the library ...

    changed: list[int] = []
    dialog = AmbientDialog(app.reader_tab, app.ctx, on_changed=lambda: changed.append(1))
    pump(app)  # ... and a reader's dialog lists it
    dialog.choice.set(str(track["id"]))
    dialog.slider.set(60)
    dialog.chime.set(False)
    dialog._track_changed()
    pump(app)
    saved = app.ctx.api.get_settings()
    assert (saved["ambient_track"], saved["ambient_volume"], saved["chapter_chime"]) == (track["id"], 0.6, False)
    assert app.ctx.reader.ambient.track_id == track["id"] and app.ctx.reader.chapter_chime is False
    assert changed  # the button on the reader refreshed itself
    app.reader_tab.refresh_ambient()


def test_admin_tab_manages_the_ambient_library(fake_tk, admin_api, tmp_path) -> None:
    from ui.app import App

    collector = _ErrorCollector()
    logging.getLogger().addHandler(collector)
    try:
        sound = tmp_path / "lo_suoi.ogg"
        sound.write_bytes(b"OggS" + b"\x00" * 500)
        application = App(admin_api, FakeOutput(duration=0.02), user={"id": 1, "username": "admin", "role": "admin", "full_name": "Admin"})
        pump(application)
        admin = application.admin_tab
        assert admin is not None
        admin.section.set("Âm thanh nền")
        admin.refresh()
        pump(application)
        track = admin_api.add_ambient(sound, "Lò sưởi")
        admin.refresh()
        pump(application)
        admin._preview_ambient(track)
        admin._rename_ambient(track)  # opens the stub dialog
        admin_api.rename_ambient(track["id"], "Lò sưởi ấm")
        assert admin_api.list_ambient()[0]["name"] == "Lò sưởi ấm"
        admin._delete_ambient(track)  # the stub messagebox answers "yes"
        pump(application)
        assert admin_api.list_ambient() == []
    finally:
        application.ui.close()
        logging.getLogger().removeHandler(collector)
    assert not collector.messages, "\n".join(collector.messages)


def test_recommend_tab_asks_first_then_filters_and_shelves(app, admin_api, tmp_path) -> None:
    text = tmp_path / "khoa_hoc.txt"
    text.write_text("Chương 1\n\nBầu trời có màu xanh vì ánh sáng bị tán xạ. Đó là một hiện tượng thú vị.", encoding="utf-8")
    cats = {c["slug"]: c["id"] for c in admin_api.list_categories()}
    admin_api.ingest_book(text, title="Vì sao trời xanh", category_id=cats["khoa-hoc"], is_public=True)

    tab = app.recommend_tab
    tab.refresh()
    pump(app)
    assert tab.data["onboarded"] is False and [b["title"] for b in tab.books] == ["Vì sao trời xanh"]  # the question is on screen
    tab._toggle("khoa-hoc")
    assert tab.picked == ["khoa-hoc"]
    tab._save(skip=False)
    pump(app)
    assert tab.data["onboarded"] and tab.data["favorite_categories"] == ["khoa-hoc"] and not tab.editing
    assert tab.books[0]["reasons"] and tab.books[0]["estimated_minutes"] >= 1

    tab._edit()  # change the favourites later
    assert tab.editing and tab.picked == ["khoa-hoc"]
    tab._cancel_edit()
    tab.mood_box.set("Hồi hộp")  # a mood with no matching book: empty list, not an error
    tab._mood_chosen("Hồi hộp")
    pump(app)
    assert tab.mood == "hoi-hop" and tab.books == []
    tab._mood_chosen("Hồi hộp")  # clicking it again clears the mood
    pump(app)
    assert tab.mood is None and len(tab.books) == 1
    tab.duration_box.set("≤ 15 phút")
    tab.refresh()
    pump(app)
    assert len(tab.books) == 1  # a two-sentence book fits any limit
    tab._add(tab.books[0])
    pump(app)
    assert tab.books == []  # shelved: nothing left to suggest


def test_logging_out_keeps_the_api_client_open_for_the_sign_in_window(app) -> None:
    """After "Đăng xuất" the sign-in window reuses the same client (it loads the quick-login boxes with it)."""
    app.logout()
    assert app.logout_requested
    assert app.ctx.api.me()["username"] == "tester"  # not closed: the window can still talk to the backend


def test_dialogs_claim_the_keyboard_and_pick_files_through_one_helper(app, book, monkeypatch) -> None:
    import tkinter

    from ui.dialogs import UploadDialog

    dialog = UploadDialog(app, app.ctx, lambda r: None)
    calls: list[str] = []
    monkeypatch.setattr(dialog, "lift", lambda: calls.append("lift"), raising=False)
    monkeypatch.setattr(dialog, "focus_force", lambda: calls.append("focus_force"), raising=False)
    dialog._claim_keyboard()  # nothing in this dialog has the keyboard (the stub reports no focus): take it
    assert calls == ["lift", "focus_force"]
    monkeypatch.setattr(tkinter.filedialog, "askopenfilename", lambda **kw: "/tmp/x.txt")
    assert dialog.pick_file(title="t") == "/tmp/x.txt"
    dialog._choose()  # the real handler goes through the same helper and fills the title from the file name
    assert dialog.title_entry.get() == "X"
