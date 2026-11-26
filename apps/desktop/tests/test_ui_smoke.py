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
    assert len(library.books) == 1 and len(library.notes) == 1
    library._switch("Ghi chú")
    library._render()
    library._switch("Tài liệu")
    library.search.insert(0, "khong co")
    library._render()  # empty-result message path
    app._tab_changed()


def test_stats_tab_draws_real_matplotlib_charts(app, api) -> None:
    app.stats_tab.refresh()
    pump(app)
    assert len(app.stats_tab.figure.axes) == 2
    app.stats_tab.range_buttons.set("Tất cả")
    app.stats_tab.refresh()
    pump(app)
    assert len(app.stats_tab.figure.axes) == 2


def test_all_dialogs_open_and_load(app, book) -> None:
    from ui.dialogs import (
        BookPickerDialog,
        CloneVoiceDialog,
        EditNoteDialog,
        ExportDialog,
        NoteDialog,
        SettingsDialog,
        UploadDialog,
        VoicesDialog,
    )

    ctx = app.ctx
    book_row = ctx.api.list_books()[0]
    note = ctx.api.list_notes()[0]
    dialogs = [
        UploadDialog(app, ctx, lambda r: None),
        VoicesDialog(app, ctx, lambda v: None),
        CloneVoiceDialog(app, ctx, lambda v: None),
        SettingsDialog(app, ctx),
        BookPickerDialog(app, ctx, lambda b: None),
        NoteDialog(app, ctx, book["book_id"], 0, 0, 8, "Xin chào", lambda: None),
        EditNoteDialog(app, ctx, note, lambda: None),
        ExportDialog(app, ctx, book_row),
    ]
    pump(app)
    settings_dialog = dialogs[3]
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
    app.library_tab._delete_book(app.library_tab.books[0])
    pump(app)
    assert app.ctx.api.list_books() == [] and app.ctx.reader.book is None
