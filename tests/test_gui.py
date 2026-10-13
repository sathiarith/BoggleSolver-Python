"""
Tests for gui.py.  Run from the project root with:   pytest -v

Layout of this file:

  * Pure tests of the two static helpers (_is_valid_tile_text and
    _get_board_validity_state). They need no window at all.
  * GUI tests, which build ONE real BoggleSolverApp for the whole run (with a tiny
    three-word dictionary written to a temporary folder, so enable_word_list.json is not
    needed) and reset it before every test. They need a display and are skipped
    automatically without one. A window will appear while they run. Skip them on
    purpose with:   pytest -m "not gui"

Design choices that keep these tests reliable:

  * Typing is tested by calling _on_tile_typed with small fake key events, not by
    simulating real keystrokes (synthetic key releases carry no character).
  * The file dialog, message boxes, crop dialog and image reader are replaced with
    stand-ins, so nothing opens and Tesseract is not needed.
  * Errors raised inside gui.py event handlers are turned into test failures
    (Tkinter would only print them).
"""

import json
import os
import time
import traceback
import tkinter as tk
from types import SimpleNamespace

import pytest
from PIL import Image

pytest.importorskip("customtkinter")
import customtkinter as ctk

import gui
from gui import BoggleSolverApp, COLOR_BORDER, COLOR_SELECTED, COLOR_SELECTED_TEXT, DICTIONARY_PATH
from gui import COLOR_UNSELECTED, COLOR_UNSELECTED_TEXT
from image_reader import BoardReadError

DICTIONARY = {"cat": "", "dog": "", "quit": ""}


# ----------------------------------------------------------------------
# Pure tests: no window needed
# ----------------------------------------------------------------------
class TestIsValidTileText:
    @pytest.mark.parametrize("text", ["", "a", "Z", "q", "Q", "QU", "Qu", "qu", "qU"])
    def test_accepted(self, text):
        assert BoggleSolverApp._is_valid_tile_text(text) is True

    @pytest.mark.parametrize("text", [
        "ab", "AB", "UQ", "QUU", "QA", "Q U", "qui",   # too long, or not "QU"
        "1", "12", "A1", " ", "!", "-",                 # digits, spaces, symbols
        "é", "ß", "Ａ",                                  # letters outside plain ASCII
    ])
    def test_rejected(self, text):
        assert BoggleSolverApp._is_valid_tile_text(text) is False


class TestGetBoardValidityState:
    def test_a_full_board_is_valid(self):
        assert BoggleSolverApp._get_board_validity_state([["a", "b"], ["c", "d"]]) == (True, [])

    def test_blank_tiles_are_listed_in_reading_order(self):
        board = [["a", "", ""],
                 ["", "b", ""]]
        assert BoggleSolverApp._get_board_validity_state(board) == (
            False, [(0, 1), (0, 2), (1, 0), (1, 2)])

    def test_an_entirely_blank_board(self):
        valid, blanks = BoggleSolverApp._get_board_validity_state([["", ""], ["", ""]])
        assert valid is False
        assert blanks == [(0, 0), (0, 1), (1, 0), (1, 1)]

    def test_a_qu_tile_counts_as_filled(self):
        assert BoggleSolverApp._get_board_validity_state([["QU", "A"]]) == (True, [])

    def test_an_empty_board_has_no_blanks(self):
        assert BoggleSolverApp._get_board_validity_state([]) == (True, [])


# ----------------------------------------------------------------------
# GUI plumbing
# ----------------------------------------------------------------------
def pump(window, seconds=0.07):
    """Let Tk run for a moment so delayed callbacks (like the 50 ms focus call) finish."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        window.update()
        time.sleep(0.005)


def wait_until_visible(window, timeout=3.0):
    """Windows can take a moment to appear; layout and focus checks need them on screen."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        window.update()
        if window.winfo_viewable():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture(scope="session")
def app(tmp_path_factory):
    """One real application window for the whole run."""
    folder = tmp_path_factory.mktemp("dictionary")
    (folder / DICTIONARY_PATH).write_text(json.dumps(DICTIONARY), encoding="utf-8")

    patcher = pytest.MonkeyPatch()
    patcher.chdir(folder)          # the app loads "enable_word_list.json"/DICTONARY_PATH from the working directory
    try:
        window = BoggleSolverApp()
    except tk.TclError as err:
        pytest.skip(f"no display available for GUI tests ({err})")
    finally:
        patcher.undo()

    # Remember how a freshly started app looks, before any test touches it
    window.initial = SimpleNamespace(
        board_size=window.board_size,
        prev_board_size=window.prev_board_size,
        entry_mode=window.entry_mode,
        rows=len(window.tile_entries),
        size_fills={s: b.cget("fg_color") for s, b in window.size_buttons.items()},
        manual_fill=window.manual_btn.cget("fg_color"),
        image_fill=window.image_btn.cget("fg_color"),
    )
    if not wait_until_visible(window):
        window.destroy()
        pytest.skip("the application window never became visible")
    yield window
    try:
        window.destroy()
    except tk.TclError:
        pass


@pytest.fixture(autouse=True)
def fresh_app(request):
    """Before each GUI test: back to an empty 4x4 manual board. Also catch handler errors."""
    if "app" not in request.fixturenames:
        yield
        return
    window = request.getfixturevalue("app")
    errors = []

    def record(exc_type, value, tb):
        if any(os.path.basename(f.filename) == "gui.py" for f in traceback.extract_tb(tb)):
            errors.append(value)

    original = window.report_callback_exception
    window.report_callback_exception = record
    if window.board_size == 4:
        window._on_manual_selected()      # one rebuild: empty board, Manual mode
    else:
        window._on_size_selected(4)
    window.set_valid_words([])
    pump(window, 0.06)                    # the focus call is scheduled 50 ms after a rebuild
    yield
    window.report_callback_exception = original
    assert not errors, f"error inside a gui.py event handler: {errors!r}"


def tile(app, r, c):
    return app.tile_entries[r][c]


def grid(*lines):
    """Build board rows from text: '.' is a blank tile, 'Q' is a QU tile."""
    return [["" if ch == "." else "QU" if ch == "Q" else ch for ch in line] for line in lines]


def put(app, rows):
    """Type letters straight into the tiles (blank entries are skipped)."""
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            if text:
                tile(app, r, c).insert(0, text)


def shown_words(app):
    """The words currently listed in the Valid Words panel, top to bottom."""
    text = app.words_box.get("1.0", "end-1c")       # "end-1c" leaves out Tk's extra final newline
    return text.split("\n") if text else []


def focused_tile(app):
    """(row, col) of the tile that has (or would get) keyboard focus, else None."""
    widget = app.focus_lastfor()
    for r, row in enumerate(app.tile_entries):
        for c, entry in enumerate(row):
            if widget is entry._entry:
                return (r, c)
    return None


def border(app, r, c):
    return tile(app, r, c).cget("border_color")


def is_selected(button):
    return button.cget("fg_color") == COLOR_SELECTED


def key(char="", keysym=""):
    """A stand-in for the Tk key event that _on_tile_typed receives."""
    return SimpleNamespace(char=char, keysym=keysym)


# ----------------------------------------------------------------------
# Start-up state
# ----------------------------------------------------------------------
@pytest.mark.gui
class TestStartup:
    def test_starts_with_an_empty_4x4_manual_board(self, app):
        start = app.initial
        assert (start.board_size, start.entry_mode, start.rows) == (4, "Manual", 4)
        assert start.prev_board_size == 4

    def test_manual_and_4x4_start_out_highlighted(self, app):
        start = app.initial
        assert start.manual_fill == COLOR_SELECTED
        assert start.image_fill == COLOR_UNSELECTED
        assert start.size_fills == {4: COLOR_SELECTED, 5: COLOR_UNSELECTED, 6: COLOR_UNSELECTED}

    def test_the_dictionary_is_loaded(self, app):
        assert app.trie.check_if_word("cat") is True
        assert app.trie.check_if_word("zebra") is False

    def test_the_first_tile_gets_focus_after_the_board_is_built(self, app):
        assert focused_tile(app) == (0, 0)


# ----------------------------------------------------------------------
# Building the board
# ----------------------------------------------------------------------
@pytest.mark.gui
class TestShowBoard:
    @pytest.mark.parametrize("size", [4, 5, 6])
    def test_builds_an_empty_square_grid(self, app, size):
        app._show_board(size)
        assert len(app.tile_entries) == size
        assert all(len(row) == size for row in app.tile_entries)
        assert app.get_board_letters() == [[""] * size for _ in range(size)]
        assert app.board_frame.grid_size() == (size, size)
        assert app.prev_board_size == size

    @pytest.mark.parametrize("size, font_size", [(4, 48), (5, 40), (6, 32)])
    def test_letters_get_smaller_on_bigger_boards(self, app, size, font_size):
        app._show_board(size)
        assert tile(app, 0, 0).cget("font").cget("size") == font_size

    def test_going_from_6x6_back_to_4x4_leaves_no_stale_rows_or_columns(self, app):
        # Regression: leftover weights from the 6x6 grid used to leave empty space
        app._show_board(6)
        app._show_board(4)
        assert app.board_frame.grid_size() == (4, 4)
        for index in (4, 5):
            row = app.board_frame.grid_rowconfigure(index)
            column = app.board_frame.grid_columnconfigure(index)
            assert row["weight"] == 0 and not row["uniform"]
            assert column["weight"] == 0 and not column["uniform"]
        for index in range(4):
            assert app.board_frame.grid_rowconfigure(index)["weight"] == 1
            assert app.board_frame.grid_columnconfigure(index)["weight"] == 1

    def test_rows_and_columns_are_sized_evenly(self, app):
        app._show_board(5)
        for index in range(5):
            assert app.board_frame.grid_rowconfigure(index)["uniform"] == "row"
            assert app.board_frame.grid_columnconfigure(index)["uniform"] == "col"

    def test_old_tiles_are_destroyed_when_the_board_is_rebuilt(self, app):
        old = tile(app, 0, 0)
        app._show_board(4)
        assert not old.winfo_exists()

    def test_rebuilding_discards_typed_letters(self, app):
        put(app, grid("ABCD"))
        app._show_board(4)
        assert app.get_board_letters() == [[""] * 4 for _ in range(4)]

    def test_tiles_reject_text_that_is_not_one_letter_or_qu(self, app):
        entry = tile(app, 0, 0)
        for rejected in ("12", "AB", "!", "é"):
            entry.delete(0, "end")
            entry.insert(0, rejected)
            assert entry.get() == "", f"{rejected!r} should have been refused"
        for accepted in ("A", "QU"):
            entry.delete(0, "end")
            entry.insert(0, accepted)
            assert entry.get() == accepted

    def test_each_tile_reacts_to_its_own_key_events(self, app):
        # A real (synthetic) key release, to prove each tile's binding knows its own row
        # and column. BackSpace is used because it works without a typed character.
        put(app, grid("Z"))
        targets = [(1, 2), (3, 3)]
        for r, c in targets:
            entry = tile(app, r, c)
            entry.insert(0, "A")
            entry._entry.focus_force()
            app.update()
            if app.focus_get() is not entry._entry:
                pytest.skip("this environment will not give the window keyboard focus")
            entry._entry.event_generate("<KeyRelease>", keysym="BackSpace")
            app.update()
            assert entry.get() == ""
        assert tile(app, 0, 0).get() == "Z"


# ----------------------------------------------------------------------
# Typing in a tile
# ----------------------------------------------------------------------
@pytest.mark.gui
class TestTileTyped:
    @pytest.mark.parametrize("char", ["a", "A"])
    def test_a_letter_is_shown_in_uppercase(self, app, char):
        app._on_tile_typed(key(char, char), 0, 0)
        assert tile(app, 0, 0).get() == "A"

    def test_a_new_letter_replaces_the_old_one(self, app):
        tile(app, 0, 0).insert(0, "X")
        app._on_tile_typed(key("b", "b"), 0, 0)
        assert tile(app, 0, 0).get() == "B"

    def test_focus_moves_to_the_next_tile(self, app):
        app._on_tile_typed(key("a", "a"), 0, 0)
        pump(app)
        assert focused_tile(app) == (0, 1)

    def test_focus_wraps_to_the_start_of_the_next_row(self, app):
        app._on_tile_typed(key("a", "a"), 0, 3)
        pump(app)
        assert focused_tile(app) == (1, 0)

    def test_wrapping_follows_the_board_size(self, app):
        app._on_size_selected(5)
        pump(app)
        app._on_tile_typed(key("a", "a"), 0, 4)
        pump(app)
        assert focused_tile(app) == (1, 0)

    def test_focus_stays_put_after_the_last_tile(self, app):
        tile(app, 3, 3).focus_set()
        app._on_tile_typed(key("a", "a"), 3, 3)
        pump(app)
        assert tile(app, 3, 3).get() == "A"
        assert focused_tile(app) == (3, 3)

    @pytest.mark.parametrize("char", ["q", "Q"])
    def test_q_becomes_qu_and_focus_moves_on(self, app, char):
        app._on_tile_typed(key(char, char), 1, 1)
        pump(app)
        assert tile(app, 1, 1).get() == "QU"
        assert focused_tile(app) == (1, 2)

    def test_a_letter_typed_over_qu_replaces_it(self, app):
        tile(app, 0, 0).insert(0, "QU")
        app._on_tile_typed(key("e", "e"), 0, 0)
        assert tile(app, 0, 0).get() == "E"

    @pytest.mark.parametrize("keysym", ["BackSpace", "Delete"])
    def test_backspace_and_delete_clear_the_whole_tile(self, app, keysym):
        tile(app, 2, 2).insert(0, "QU")
        tile(app, 2, 2).focus_set()
        app._on_tile_typed(key("", keysym), 2, 2)
        pump(app)
        assert tile(app, 2, 2).get() == ""
        assert focused_tile(app) == (2, 2)      # clearing does not move on

    @pytest.mark.parametrize("char, keysym", [
        ("", "Left"), ("", "Right"), ("", "Up"), ("", "Shift_L"),   # navigation / modifiers
        ("\t", "Tab"), ("\r", "Return"),
        ("1", "1"), ("!", "exclam"), (" ", "space"),                # not letters
        ("é", "eacute"),                                            # not plain ASCII
    ])
    def test_other_keys_leave_the_tile_alone(self, app, char, keysym):
        # Regression: arrow keys used to rewrite "QU" as "U" and jump to the next tile
        tile(app, 0, 1).insert(0, "QU")
        tile(app, 0, 1).focus_set()
        app._on_tile_typed(key(char, keysym), 0, 1)
        pump(app)
        assert tile(app, 0, 1).get() == "QU"
        assert focused_tile(app) == (0, 1)


# ----------------------------------------------------------------------
# Filling and reading the board
# ----------------------------------------------------------------------
@pytest.mark.gui
class TestFillAndRead:
    def test_fill_board_puts_each_letter_in_its_tile(self, app):
        app._fill_board(grid("CATZ", "QITZ", "....", "...."))
        assert app.get_board_letters() == grid("CATZ", "QITZ", "....", "....")

    def test_fill_board_replaces_what_was_there(self, app):
        put(app, grid("ABCD"))
        app._fill_board(grid("ZZ.Z"))
        assert app.get_board_letters()[0] == ["Z", "Z", "", "Z"]

    def test_text_the_tiles_refuse_is_dropped_silently(self, app):
        # Documents current behavior: validation also applies to programmatic inserts
        app._fill_board([["AB", "1", "A"]])
        assert app.get_board_letters()[0] == ["", "", "A", ""]

    def test_get_board_letters_returns_the_tile_text(self, app):
        put(app, grid("A.QZ"))
        assert app.get_board_letters()[0] == ["A", "", "QU", "Z"]


# ----------------------------------------------------------------------
# Valid Words panel
# ----------------------------------------------------------------------
@pytest.mark.gui
class TestValidWordsPanel:
    def test_words_are_listed_in_the_order_given(self, app):
        app.set_valid_words(["cat", "dog", "ant"])
        assert shown_words(app) == ["cat", "dog", "ant"]

    def test_new_words_replace_the_old_ones(self, app):
        app.set_valid_words(["cat", "dog"])
        app.set_valid_words(["owl"])
        assert shown_words(app) == ["owl"]

    def test_an_empty_list_clears_the_panel(self, app):
        app.set_valid_words(["cat"])
        app.set_valid_words([])
        assert shown_words(app) == []

    def test_any_iterable_works(self, app):
        app.set_valid_words(word for word in ("cat", "dog"))
        assert shown_words(app) == ["cat", "dog"]

    def test_each_word_is_on_its_own_line(self, app):
        app.set_valid_words(["cat", "dog", "ant"])
        assert app.words_box.get("1.0", "end-1c") == "cat\ndog\nant"

    def test_the_panel_is_read_only(self, app):
        app.set_valid_words(["cat"])
        assert app.words_box.cget("state") == "disabled"
        app.words_box._textbox.insert("end", "typed by the user")     # the widget refuses it
        assert shown_words(app) == ["cat"]

    def test_the_panel_stays_read_only_after_being_cleared(self, app):
        app.set_valid_words(["cat"])
        app.set_valid_words([])
        assert app.words_box.cget("state") == "disabled"

    def test_new_results_start_at_the_top(self, app):
        app.set_valid_words([f"word{i}" for i in range(300)])
        app.update()
        app.words_box.yview_moveto(1.0)                  # the user scrolled to the bottom
        app.set_valid_words([f"other{i}" for i in range(300)])
        app.update()
        assert app.words_box.yview()[0] == 0.0

    def test_a_big_list_appears_quickly(self, app):
        # Regression: one label per word took about 2 seconds for 1000 words; one text
        # box takes a few milliseconds. The limit is generous so a slow machine passes.
        words = [f"word{i}" for i in range(1000)]
        start = time.perf_counter()
        app.set_valid_words(words)
        app.update()
        assert time.perf_counter() - start < 1.0
        assert len(shown_words(app)) == 1000

    def test_a_long_list_is_shown_completely(self, app):
        words = [f"word{i}" for i in range(200)]
        app.set_valid_words(words)
        assert shown_words(app) == words


# ----------------------------------------------------------------------
# Entry method buttons
# ----------------------------------------------------------------------
@pytest.mark.gui
class TestEntryMethod:
    def test_set_button_selected_styles_a_button(self, app):
        button = ctk.CTkButton(app, text="demo")
        try:
            BoggleSolverApp._set_button_selected(button, True)
            assert (button.cget("fg_color"), button.cget("text_color")) == (
                COLOR_SELECTED, COLOR_SELECTED_TEXT)
            BoggleSolverApp._set_button_selected(button, False)
            assert (button.cget("fg_color"), button.cget("text_color")) == (
                COLOR_UNSELECTED, COLOR_UNSELECTED_TEXT)
        finally:
            button.destroy()

    def test_manual_mode_highlights_manual_and_empties_the_board(self, app):
        app.entry_mode = "Image"
        app._set_button_selected(app.manual_btn, False)
        app._set_button_selected(app.image_btn, True)
        put(app, grid("ABCD"))

        app._on_manual_selected()
        assert app.entry_mode == "Manual"
        assert is_selected(app.manual_btn) and not is_selected(app.image_btn)
        assert app.get_board_letters() == [[""] * 4 for _ in range(4)]

    def test_manual_mode_clears_the_old_words(self, app):
        app.set_valid_words(["stale"])
        app._on_manual_selected()
        assert shown_words(app) == []

    def test_the_manual_button_is_wired_up(self, app):
        app.entry_mode = "Image"
        app.manual_btn.invoke()
        assert app.entry_mode == "Manual"


# ----------------------------------------------------------------------
# Board size selector
# ----------------------------------------------------------------------
@pytest.mark.gui
class TestSizeSelection:
    @pytest.mark.parametrize("size", [5, 6, 4])
    def test_choosing_a_size_rebuilds_the_board(self, app, size):
        put(app, grid("ABCD"))
        app._on_size_selected(size)
        assert app.board_size == size
        assert app.board_frame.grid_size() == (size, size)
        assert app.get_board_letters() == [[""] * size for _ in range(size)]   # letters reset

    @pytest.mark.parametrize("size", [4, 5, 6])
    def test_only_the_chosen_size_button_is_highlighted(self, app, size):
        app._on_size_selected(size)
        assert {s: is_selected(b) for s, b in app.size_buttons.items()} == {
            s: s == size for s in (4, 5, 6)}

    def test_choosing_a_size_returns_to_manual_entry(self, app):
        app.entry_mode = "Image"
        app._set_button_selected(app.manual_btn, False)
        app._set_button_selected(app.image_btn, True)
        app._on_size_selected(5)
        assert app.entry_mode == "Manual"
        assert is_selected(app.manual_btn) and not is_selected(app.image_btn)

    def test_the_first_tile_gets_focus_after_a_size_change(self, app):
        app._on_size_selected(6)
        pump(app)
        assert focused_tile(app) == (0, 0)

    def test_choosing_a_size_clears_the_old_words(self, app):
        # The words belonged to the old board, so they must not stay on screen
        app.set_valid_words(["stale"])
        app._on_size_selected(5)
        assert shown_words(app) == []

    @pytest.mark.parametrize("size", [4, 5, 6])
    def test_choosing_a_size_builds_the_board_only_once(self, app, monkeypatch, size):
        # Regression: the grid used to be built twice, first at the old size and then at the new
        builds = []
        original = app._show_board
        monkeypatch.setattr(app, "_show_board", lambda s: (builds.append(s), original(s))[1])
        app._on_size_selected(size)
        assert builds == [size]

    @pytest.mark.parametrize("handler", ["_on_manual_selected", "_on_clear_board"])
    def test_other_handlers_also_build_the_board_only_once(self, app, monkeypatch, handler):
        builds = []
        original = app._show_board
        monkeypatch.setattr(app, "_show_board", lambda s: (builds.append(s), original(s))[1])
        getattr(app, handler)()
        assert builds == [app.board_size]

    @pytest.mark.parametrize("size", [5, 6])
    def test_size_buttons_are_wired_up(self, app, size):
        app.size_buttons[size].invoke()
        assert app.board_size == size


# ----------------------------------------------------------------------
# Submit
# ----------------------------------------------------------------------
@pytest.mark.gui
class TestSubmit:
    def test_valid_board_lists_the_words_on_it(self, app):
        put(app, grid("CATZ", "DOGZ", "ZZZZ", "ZZZZ"))
        app._on_submit_board()
        assert shown_words(app) == ["cat", "dog"]

    def test_a_qu_tile_spells_both_letters(self, app):
        put(app, grid("QITZ", "ZZZZ", "ZZZZ", "ZZZZ"))
        app._on_submit_board()
        assert shown_words(app) == ["quit"]

    def test_a_board_with_no_words_shows_an_empty_panel(self, app):
        put(app, grid("ZZZZ", "ZZZZ", "ZZZZ", "ZZZZ"))
        app._on_submit_board()
        assert shown_words(app) == []

    def test_blank_tiles_get_a_red_border_and_the_rest_do_not(self, app):
        put(app, grid("CATZ", "Z.ZZ", "ZZ.Z", "ZZZZ"))
        app._on_submit_board()
        red = {(r, c) for r in range(4) for c in range(4) if border(app, r, c) == "red"}
        assert red == {(1, 1), (2, 2)}
        assert border(app, 0, 0) == COLOR_BORDER

    def test_the_first_blank_tile_gets_focus(self, app):
        put(app, grid("CATZ", "Z.ZZ", "ZZ.Z", "ZZZZ"))
        app._on_submit_board()
        pump(app)
        assert focused_tile(app) == (1, 1)

    def test_a_board_with_blanks_is_not_solved(self, app, monkeypatch):
        def fail(*args):
            raise AssertionError("the solver must not run while tiles are blank")
        monkeypatch.setattr(gui, "Solver", fail)
        put(app, grid("CAT.", "ZZZZ", "ZZZZ", "ZZZZ"))
        app._on_submit_board()

    def test_old_words_are_cleared_when_the_board_has_blanks(self, app):
        app.set_valid_words(["stale"])
        put(app, grid("CAT.", "ZZZZ", "ZZZZ", "ZZZZ"))
        app._on_submit_board()
        assert shown_words(app) == []

    def test_fixing_a_blank_and_resubmitting_clears_the_red_border(self, app):
        put(app, grid("CAT.", "ZZZZ", "ZZZZ", "ZZZZ"))
        app._on_submit_board()
        assert border(app, 0, 3) == "red"

        tile(app, 0, 3).insert(0, "Z")
        app._on_submit_board()
        assert border(app, 0, 3) == COLOR_BORDER
        assert shown_words(app) == ["cat"]

    def test_resubmitting_a_changed_board_replaces_the_old_words(self, app):
        put(app, grid("CATZ", "ZZZZ", "ZZZZ", "ZZZZ"))
        app._on_submit_board()
        assert shown_words(app) == ["cat"]

        tile(app, 0, 0).delete(0, "end")
        tile(app, 0, 0).insert(0, "Z")
        app._on_submit_board()
        assert shown_words(app) == []

    def test_the_solver_gets_the_board_and_the_loaded_dictionary(self, app, monkeypatch):
        received = []

        class FakeSolver:
            def __init__(self, board, trie):
                received.append((board, trie))

            def find_words(self):
                return ["alpha", "beta"]

        monkeypatch.setattr(gui, "Solver", FakeSolver)
        put(app, grid("CATZ", "DOGZ", "ZZZZ", "ZZZZ"))
        app._on_submit_board()

        assert received == [(app.get_board_letters(), app.trie)]
        assert shown_words(app) == ["alpha", "beta"]

    def test_the_submit_button_is_wired_up(self, app):
        put(app, grid("CATZ", "ZZZZ", "ZZZZ", "ZZZZ"))
        app.submit_btn.invoke()
        assert shown_words(app) == ["cat"]


# ----------------------------------------------------------------------
# Clear Board
# ----------------------------------------------------------------------
@pytest.mark.gui
class TestClearBoard:
    def test_clear_empties_everything_and_returns_to_manual_entry(self, app):
        put(app, grid("CATZ", "DOGZ", ".ZZZ", "ZZZZ"))
        app._on_submit_board()                       # the blank tile gets a red border
        assert border(app, 2, 0) == "red"
        app.set_valid_words(["stale"])               # something in the panel to be cleared
        app.entry_mode = "Image"
        app._set_button_selected(app.manual_btn, False)
        app._set_button_selected(app.image_btn, True)

        app._on_clear_board()
        pump(app)

        assert app.get_board_letters() == [[""] * 4 for _ in range(4)]
        assert all(border(app, r, c) == COLOR_BORDER for r in range(4) for c in range(4))
        assert shown_words(app) == []
        assert app.entry_mode == "Manual"
        assert is_selected(app.manual_btn) and not is_selected(app.image_btn)
        assert focused_tile(app) == (0, 0)

    def test_clear_keeps_the_current_board_size(self, app):
        app._on_size_selected(5)
        app._on_clear_board()
        assert app.board_size == 5
        assert len(app.tile_entries) == 5

    def test_the_clear_button_is_wired_up(self, app):
        put(app, grid("ABCD"))
        app.clear_btn.invoke()
        assert app.get_board_letters() == [[""] * 4 for _ in range(4)]


# ----------------------------------------------------------------------
# Image entry (file dialog, crop dialog and reader are stand-ins)
# ----------------------------------------------------------------------
@pytest.fixture
def image_flow(app, monkeypatch, tmp_path):
    """Replace every interactive or slow step of the Image button and record what happens."""
    picture = tmp_path / "board.png"
    Image.new("RGBA", (60, 40), "white").save(picture)

    flow = SimpleNamespace(
        chosen_path=str(picture),                       # what the file dialog "returns"
        crop_result=Image.new("RGB", (30, 30), "white"),  # what the crop dialog "returns"
        letters=grid("CATZ", "DOGZ", "ZZZZ", "ZZZZ"),     # what the reader "returns"
        read_error=None,
        dialogs=[], crops=[], reads=[], errors=[], warnings=[],
    )

    def fake_dialog(**kwargs):
        flow.dialogs.append(kwargs)
        return flow.chosen_path

    def fake_crop(parent, image):
        flow.crops.append((parent, image))
        return flow.crop_result

    def fake_read(image, size, method="ocr"):
        flow.reads.append((image, size, method))
        if flow.read_error is not None:
            raise flow.read_error
        return flow.letters

    monkeypatch.setattr(gui.filedialog, "askopenfilename", fake_dialog)
    monkeypatch.setattr(gui, "ask_crop", fake_crop)
    monkeypatch.setattr(gui, "read_board", fake_read)
    monkeypatch.setattr(gui.messagebox, "showerror", lambda title, message: flow.errors.append((title, message)))
    monkeypatch.setattr(gui.messagebox, "showwarning", lambda title, message: flow.warnings.append((title, message)))
    return flow


@pytest.mark.gui
class TestImageEntry:
    def test_the_image_button_is_wired_up(self, app, image_flow):
        image_flow.chosen_path = ""
        app.image_btn.invoke()
        assert len(image_flow.dialogs) == 1

    def test_the_file_dialog_asks_for_image_files(self, app, image_flow):
        image_flow.chosen_path = ""
        app._on_image_selected()
        patterns = " ".join(pattern for _label, pattern in image_flow.dialogs[0]["filetypes"])
        assert "*.png" in patterns and "*.jpg" in patterns

    def test_cancelling_the_file_dialog_changes_nothing(self, app, image_flow):
        put(app, grid("A"))
        image_flow.chosen_path = ""
        app._on_image_selected()
        assert image_flow.crops == [] and image_flow.reads == []
        assert image_flow.errors == [] and image_flow.warnings == []    # no message box either
        assert app.entry_mode == "Manual"
        assert tile(app, 0, 0).get() == "A"

    def test_cancelling_the_file_dialog_keeps_the_words(self, app, image_flow):
        app.set_valid_words(["keep"])
        image_flow.chosen_path = ""
        app._on_image_selected()
        assert shown_words(app) == ["keep"]       # the board did not change, so neither do its words

    def test_cancelling_the_crop_keeps_the_words(self, app, image_flow):
        app.set_valid_words(["keep"])
        image_flow.crop_result = None
        app._on_image_selected()
        assert shown_words(app) == ["keep"]

    def test_reading_an_image_clears_the_old_words(self, app, image_flow):
        app.set_valid_words(["stale"])
        app._on_image_selected()
        assert shown_words(app) == []             # the board was replaced and not yet submitted

    def test_a_file_that_is_not_an_image_shows_an_error(self, app, image_flow, tmp_path):
        not_an_image = tmp_path / "notes.png"
        not_an_image.write_text("this is not a picture")
        put(app, grid("A"))
        image_flow.chosen_path = str(not_an_image)

        app._on_image_selected()
        assert [title for title, _message in image_flow.errors] == ["Image error"]
        assert image_flow.crops == []
        assert tile(app, 0, 0).get() == "A"

    def test_cancelling_the_crop_changes_nothing(self, app, image_flow):
        put(app, grid("A"))
        image_flow.crop_result = None
        app._on_image_selected()
        assert image_flow.reads == []
        assert image_flow.errors == [] and image_flow.warnings == []
        assert app.entry_mode == "Manual"
        assert tile(app, 0, 0).get() == "A"

    def test_a_reader_failure_shows_a_warning_and_changes_nothing(self, app, image_flow):
        put(app, grid("A"))
        image_flow.read_error = BoardReadError("Tesseract is missing")
        app._on_image_selected()
        assert image_flow.warnings == [("Couldn't read board", "Tesseract is missing")]
        assert app.entry_mode == "Manual"
        assert tile(app, 0, 0).get() == "A"

    def test_the_crop_dialog_gets_an_upright_rgb_picture(self, app, image_flow):
        app._on_image_selected()
        parent, picture = image_flow.crops[0]
        assert parent is app
        assert picture.mode == "RGB"              # the file was saved as RGBA
        assert picture.size == (60, 40)

    def test_the_reader_gets_the_cropped_picture_and_the_board_size(self, app, image_flow):
        app._on_size_selected(5)
        image_flow.letters = grid("CATZZ", "DOGZZ", "ZZZZZ", "ZZZZZ", "ZZZZZ")
        app._on_image_selected()
        image, size, method = image_flow.reads[0]
        assert image is image_flow.crop_result
        assert (size, method) == (5, "ocr")

    def test_a_complete_reading_fills_the_board_in_image_mode(self, app, image_flow):
        image_flow.letters = grid("QATZ", "DOGZ", "ZZZZ", "ZZZZ")
        app._on_image_selected()
        assert app.get_board_letters() == image_flow.letters
        assert app.entry_mode == "Image"
        assert is_selected(app.image_btn) and not is_selected(app.manual_btn)

    def test_an_incomplete_reading_falls_back_to_manual_entry(self, app, image_flow):
        image_flow.letters = grid("CAT.", "DOGZ", "ZZZZ", "ZZ.Z")
        app._on_image_selected()
        assert app.get_board_letters() == image_flow.letters      # blanks left for the user
        assert app.entry_mode == "Manual"
        assert is_selected(app.manual_btn) and not is_selected(app.image_btn)

    def test_a_board_read_from_an_image_can_be_submitted(self, app, image_flow):
        app._on_image_selected()
        app._on_submit_board()
        assert shown_words(app) == ["cat", "dog"]