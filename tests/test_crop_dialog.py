"""
Tests for crop_dialog.py.  Run from the project root with:   pytest -v

Two kinds of test live here:

  1. Pure tests of canvas_box_to_image_box (the coordinate math). They need only
     tkinter and customtkinter to be importable.
  2. GUI tests that open the real dialog and drive it with simulated mouse and key
     events. They need a display, and are skipped automatically when there is none.
     Expect a window or two to flash on screen while they run. A single hidden
     "root" window is shared by all of them.

The GUI tests reach into the dialog's private attributes (_canvas, _box, _hint,
_confirm_btn), so they will need updating if you rename those.
"""

import random
import time
import traceback
import tkinter as tk

import pytest
from PIL import Image

pytest.importorskip("customtkinter")
import customtkinter as ctk

from crop_dialog import CropDialog, ask_crop, canvas_box_to_image_box


# ----------------------------------------------------------------------
# Pure coordinate math
# ----------------------------------------------------------------------
class TestCanvasBoxToImageBox:
    def test_no_scaling(self):
        assert canvas_box_to_image_box(10, 20, 110, 220, 1.0, 400, 300) == (10, 20, 110, 220)

    @pytest.mark.parametrize("scale, box, expected", [
        (0.5,  (10, 20, 60, 70),  (20, 40, 120, 140)),    # picture shown at half size
        (0.25, (5, 5, 50, 25),    (20, 20, 200, 100)),    # shown at a quarter
        (0.3,  (10, 10, 20, 20),  (33, 33, 67, 67)),      # rounds to the nearest pixel
    ])
    def test_canvas_pixels_are_scaled_back_up(self, scale, box, expected):
        assert canvas_box_to_image_box(*box, scale, 1000, 1000) == expected

    @pytest.mark.parametrize("x0, y0, x1, y1", [
        (50, 40, 250, 160),   # top-left to bottom-right
        (250, 160, 50, 40),   # bottom-right to top-left
        (250, 40, 50, 160),   # top-right to bottom-left
        (50, 160, 250, 40),   # bottom-left to top-right
    ])
    def test_drag_direction_does_not_matter(self, x0, y0, x1, y1):
        assert canvas_box_to_image_box(x0, y0, x1, y1, 1.0, 400, 300) == (50, 40, 250, 160)

    def test_x_and_y_are_ordered_independently(self):
        assert canvas_box_to_image_box(100, 20, 50, 80, 1.0, 400, 300) == (50, 20, 100, 80)

    def test_result_is_clamped_to_the_image(self):
        assert canvas_box_to_image_box(-50, -50, 5000, 5000, 1.0, 400, 300) == (0, 0, 400, 300)

    def test_clamping_happens_in_image_pixels_after_scaling(self):
        # 900 canvas pixels at half scale is 1800 image pixels, beyond a 400 x 300 image
        assert canvas_box_to_image_box(0, 0, 900, 900, 0.5, 400, 300) == (0, 0, 400, 300)

    def test_zero_area_box(self):
        assert canvas_box_to_image_box(30, 30, 30, 30, 1.0, 400, 300) == (30, 30, 30, 30)

    def test_result_is_always_ordered_and_inside_the_image(self):
        rng = random.Random(0)
        for _ in range(300):
            x0, y0, x1, y1 = (rng.uniform(-100, 600) for _ in range(4))
            scale = rng.uniform(0.1, 1.0)
            left, top, right, bottom = canvas_box_to_image_box(x0, y0, x1, y1, scale, 500, 400)
            assert 0 <= left <= right <= 500
            assert 0 <= top <= bottom <= 400


# ----------------------------------------------------------------------
# GUI test plumbing
# ----------------------------------------------------------------------
@pytest.fixture(scope="session")
def root():
    """One shared main window for every GUI test; skips them all if there is no display."""
    try:
        window = ctk.CTk()
    except tk.TclError as err:
        pytest.skip(f"no display available for GUI tests ({err})")
    yield window
    try:
        window.destroy()
    except tk.TclError:
        pass


@pytest.fixture(autouse=True)
def fail_on_errors_inside_crop_dialog(request):
    """
    Tkinter only prints exceptions raised inside event handlers, so a broken handler
    would not fail a test. Catch the ones that come from crop_dialog.py and fail.
    """
    if "root" not in request.fixturenames:
        yield
        return
    window = request.getfixturevalue("root")
    errors = []

    def record(exc_type, value, tb):
        if any("crop_dialog" in frame.filename for frame in traceback.extract_tb(tb)):
            errors.append(value)

    original = window.report_callback_exception
    window.report_callback_exception = record
    yield
    window.report_callback_exception = original
    assert not errors, f"error inside a crop_dialog event handler: {errors!r}"


def wait_until_visible(window, timeout=3.0):
    """
    Wait until the window is really on screen; True if it got there in time.

    On some systems (notably Windows with CustomTkinter) a new window appears a moment
    after it is created. Until then, simulated mouse and key events are silently dropped
    and the widgets report no size or position, so every GUI test must wait first.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        window.update()
        if window.winfo_viewable():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def make_dialog(root):
    """Open dialogs for a test and always close them afterwards (a leftover dialog can hold the input grab)."""
    created = []

    def make(image=None, size=(400, 200)):
        dialog = CropDialog(root, image if image is not None else Image.new("RGB", size, "white"))
        created.append(dialog)
        if not wait_until_visible(dialog):
            pytest.skip("the dialog window never became visible, so events cannot be sent to it")
        return dialog

    yield make
    for dialog in created:
        try:
            dialog.destroy()
        except tk.TclError:
            pass
    root.update()


def is_open(widget):
    try:
        return bool(widget.winfo_exists())
    except tk.TclError:
        return False


def press(dialog, x, y):
    dialog._canvas.event_generate("<ButtonPress-1>", x=x, y=y)
    dialog.update()


def move(dialog, x, y):
    dialog._canvas.event_generate("<B1-Motion>", x=x, y=y)
    dialog.update()


def release(dialog, x, y):
    dialog._canvas.event_generate("<ButtonRelease-1>", x=x, y=y)
    dialog.update()


def drag(dialog, start, end):
    press(dialog, *start)
    move(dialog, *end)
    release(dialog, *end)


def confirm_enabled(dialog):
    return dialog._confirm_btn.cget("state") == "normal"


def hint(dialog):
    return dialog._hint.cget("text")


def find_button(widget, text):
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkButton) and child.cget("text") == text:
            return child
        found = find_button(child, text)
        if found is not None:
            return found
    return None


def canvas_items(dialog):
    return len(dialog._canvas.find_all())


def two_color_image(width, height, left_color=(255, 0, 0), right_color=(0, 0, 255)):
    """Left half one color, right half another, so a crop's content shows where it came from."""
    img = Image.new("RGB", (width, height), left_color)
    img.paste(right_color, (width // 2, 0, width, height))
    return img


# ----------------------------------------------------------------------
# Opening the dialog
# ----------------------------------------------------------------------
class TestOpening:
    def test_starts_with_nothing_selected(self, make_dialog):
        dialog = make_dialog()
        assert dialog.result is None
        assert dialog._box is None
        assert dialog._rect_id is None
        assert not confirm_enabled(dialog)
        assert canvas_items(dialog) == 1   # just the picture

    def test_small_picture_is_shown_at_full_size(self, make_dialog):
        dialog = make_dialog(size=(400, 200))
        assert dialog._scale == 1.0
        assert (int(dialog._canvas.cget("width")), int(dialog._canvas.cget("height"))) == (400, 200)

    @pytest.mark.parametrize("size, scale, shown", [
        ((1640, 1240), 0.5,  (820, 620)),
        ((2000, 500),  0.41, (820, 205)),   # width is the limit
        ((500, 2000),  0.31, (155, 620)),   # height is the limit
    ])
    def test_big_pictures_are_shrunk_to_fit(self, make_dialog, size, scale, shown):
        dialog = make_dialog(size=size)
        assert dialog._scale == pytest.approx(scale)
        assert (int(dialog._canvas.cget("width")), int(dialog._canvas.cget("height"))) == shown

    @pytest.mark.parametrize("size", [(100, 50), (30, 30)])
    def test_tiny_pictures_are_never_enlarged(self, make_dialog, size):
        assert make_dialog(size=size)._scale == 1.0

    @pytest.mark.parametrize("mode", ["RGBA", "L", "P"])
    def test_picture_is_converted_to_rgb(self, make_dialog, mode):
        assert make_dialog(Image.new(mode, (100, 80)))._image.mode == "RGB"

    def test_the_callers_picture_is_not_modified(self, make_dialog):
        original = Image.new("RGBA", (100, 80))
        make_dialog(original)
        assert original.mode == "RGBA"

    def test_shows_instructions(self, make_dialog):
        assert "Drag a box" in hint(make_dialog())

    def test_every_part_is_actually_on_screen_and_not_cut_off(self, make_dialog):
        # Having text in the label is not enough: it has to be placed in the window too
        dialog = make_dialog()
        parts = {
            "instructions": dialog._hint,
            "picture": dialog._canvas,
            "Cancel button": find_button(dialog, "Cancel"),
            "Reset button": find_button(dialog, "Reset"),
            "Crop button": dialog._confirm_btn,
        }
        window_top = dialog.winfo_rooty()
        window_bottom = window_top + dialog.winfo_height()
        for name, widget in parts.items():
            assert widget.winfo_ismapped(), f"{name} is not shown"
            assert widget.winfo_height() > 1, f"{name} has no height"
            top = widget.winfo_rooty()
            assert window_top <= top and top + widget.winfo_height() <= window_bottom, \
                f"{name} is cut off by the window edge"

    def test_instructions_sit_above_the_picture_and_buttons_below_it(self, make_dialog):
        dialog = make_dialog()
        hint_bottom = dialog._hint.winfo_rooty() + dialog._hint.winfo_height()
        canvas_top = dialog._canvas.winfo_rooty()
        canvas_bottom = canvas_top + dialog._canvas.winfo_height()
        assert hint_bottom <= canvas_top
        assert canvas_bottom <= dialog._confirm_btn.winfo_rooty()


# ----------------------------------------------------------------------
# Selecting a region with the mouse
# ----------------------------------------------------------------------
class TestSelecting:
    def test_dragging_a_box_selects_it_and_enables_the_button(self, make_dialog):
        dialog = make_dialog()
        drag(dialog, (50, 40), (250, 160))
        assert dialog._selection_in_image_coords() == (50, 40, 250, 160)
        assert confirm_enabled(dialog)

    @pytest.mark.parametrize("start, end", [
        ((50, 40), (250, 160)),
        ((250, 160), (50, 40)),
        ((250, 40), (50, 160)),
        ((50, 160), (250, 40)),
    ])
    def test_drag_direction_does_not_matter(self, make_dialog, start, end):
        dialog = make_dialog()
        drag(dialog, start, end)
        assert dialog._selection_in_image_coords() == (50, 40, 250, 160)

    def test_selection_is_in_original_pixels_when_the_picture_is_shrunk(self, make_dialog):
        dialog = make_dialog(size=(1640, 1240))   # shown at half size
        drag(dialog, (100, 100), (300, 200))
        assert dialog._selection_in_image_coords() == (200, 200, 600, 400)

    def test_dragging_past_the_picture_is_clamped_to_its_edge(self, make_dialog):
        dialog = make_dialog(size=(400, 200))
        drag(dialog, (10, 10), (5000, 5000))
        assert dialog._selection_in_image_coords() == (10, 10, 400, 200)

    def test_dragging_over_the_whole_shrunk_picture_selects_all_of_it(self, make_dialog):
        dialog = make_dialog(size=(1234, 987))
        drag(dialog, (0, 0), (dialog._disp_w, dialog._disp_h))
        left, top, right, bottom = dialog._selection_in_image_coords()
        assert (left, top) == (0, 0)
        assert abs(right - 1234) <= 1 and abs(bottom - 987) <= 1

    def test_rectangle_follows_the_mouse_while_dragging(self, make_dialog):
        dialog = make_dialog(size=(400, 200))
        press(dialog, 50, 40)
        move(dialog, 200, 120)
        assert dialog._canvas.coords(dialog._rect_id) == [50.0, 40.0, 200.0, 120.0]
        move(dialog, 9999, 9999)   # past the edge: the rectangle stops at the picture
        assert dialog._canvas.coords(dialog._rect_id) == [50.0, 40.0, 400.0, 200.0]

    def test_starting_a_new_drag_replaces_the_old_rectangle(self, make_dialog):
        dialog = make_dialog()
        drag(dialog, (50, 40), (250, 160))
        drag(dialog, (100, 50), (300, 150))
        assert canvas_items(dialog) == 2   # picture + one rectangle
        assert dialog._selection_in_image_coords() == (100, 50, 300, 150)

    def test_button_is_disabled_again_while_a_new_drag_is_in_progress(self, make_dialog):
        dialog = make_dialog()
        drag(dialog, (50, 40), (250, 160))
        assert confirm_enabled(dialog)
        press(dialog, 100, 100)
        assert not confirm_enabled(dialog)
        move(dialog, 300, 180)
        release(dialog, 300, 180)
        assert confirm_enabled(dialog)

    def test_mouse_movement_without_a_press_does_nothing(self, make_dialog):
        dialog = make_dialog()
        move(dialog, 100, 100)
        release(dialog, 100, 100)
        assert dialog._rect_id is None
        assert dialog._box is None
        assert not confirm_enabled(dialog)


class TestMinimumSize:
    @pytest.mark.parametrize("width, height, accepted", [
        (20, 20, True),     # exactly the minimum
        (19, 20, False),
        (20, 19, False),
        (5, 5, False),
        (0, 0, False),
    ])
    def test_boundary_in_image_pixels(self, make_dialog, width, height, accepted):
        dialog = make_dialog(size=(400, 200))
        drag(dialog, (100, 100), (100 + width, 100 + height))
        assert confirm_enabled(dialog) is accepted
        assert ("too small" in hint(dialog)) is (not accepted)

    @pytest.mark.parametrize("canvas_px, accepted", [(10, True), (9, False)])
    def test_minimum_applies_to_the_original_picture_not_the_screen(
            self, make_dialog, canvas_px, accepted):
        dialog = make_dialog(size=(1640, 1240))   # shown at half size: 10 px on screen = 20 real
        drag(dialog, (100, 100), (100 + canvas_px, 100 + canvas_px))
        assert confirm_enabled(dialog) is accepted

    def test_a_plain_click_is_too_small(self, make_dialog):
        dialog = make_dialog()
        press(dialog, 100, 100)
        release(dialog, 100, 100)
        assert not confirm_enabled(dialog)
        assert "too small" in hint(dialog)


# ----------------------------------------------------------------------
# Reset
# ----------------------------------------------------------------------
class TestReset:
    def test_reset_clears_the_selection(self, make_dialog):
        dialog = make_dialog()
        drag(dialog, (50, 40), (250, 160))
        dialog._reset()
        assert dialog._box is None
        assert dialog._rect_id is None
        assert not confirm_enabled(dialog)
        assert canvas_items(dialog) == 1

    def test_reset_button_is_wired_up(self, make_dialog):
        dialog = make_dialog()
        drag(dialog, (50, 40), (250, 160))
        find_button(dialog, "Reset").invoke()
        assert dialog._box is None
        assert not confirm_enabled(dialog)

    def test_reset_brings_back_the_instructions(self, make_dialog):
        # After a selection the hint says "Happy with it? ..." or "too small ...".
        # Once the selection is gone, that message no longer makes sense.
        dialog = make_dialog()
        original = hint(dialog)
        drag(dialog, (50, 40), (250, 160))
        assert hint(dialog) != original
        dialog._reset()
        assert hint(dialog) == original


# ----------------------------------------------------------------------
# Confirming and cancelling
# ----------------------------------------------------------------------
class TestConfirm:
    def test_confirm_returns_the_selected_region_and_closes(self, make_dialog):
        dialog = make_dialog()
        drag(dialog, (50, 40), (250, 160))
        dialog._confirm()
        assert dialog.result.size == (200, 120)
        assert not is_open(dialog)

    def test_confirm_crops_the_pixels_that_were_selected(self, make_dialog):
        image = two_color_image(400, 200)       # red on the left, blue on the right
        blue = make_dialog(image)
        drag(blue, (250, 40), (350, 160))
        blue._confirm()
        assert blue.result.getpixel((0, 0)) == (0, 0, 255)
        assert blue.result.getpixel((99, 119)) == (0, 0, 255)

        red = make_dialog(image)
        drag(red, (50, 40), (150, 160))
        red._confirm()
        assert red.result.getpixel((0, 0)) == (255, 0, 0)
        assert red.result.getpixel((99, 119)) == (255, 0, 0)

    def test_confirm_crops_the_original_picture_when_it_is_shrunk(self, make_dialog):
        dialog = make_dialog(two_color_image(1640, 1240))     # blue starts at x = 820
        drag(dialog, (450, 100), (750, 400))                  # = x 900..1500 in the original
        dialog._confirm()
        assert dialog.result.size == (600, 600)
        assert dialog.result.getpixel((0, 0)) == (0, 0, 255)
        assert dialog.result.getpixel((599, 599)) == (0, 0, 255)

    def test_result_is_rgb_even_for_other_picture_modes(self, make_dialog):
        dialog = make_dialog(Image.new("RGBA", (400, 200)))
        drag(dialog, (50, 40), (250, 160))
        dialog._confirm()
        assert dialog.result.mode == "RGB"

    def test_confirm_without_a_selection_does_nothing(self, make_dialog):
        dialog = make_dialog()
        dialog._confirm()
        assert dialog.result is None
        assert is_open(dialog)

    def test_confirm_with_a_too_small_selection_does_nothing(self, make_dialog):
        dialog = make_dialog()
        drag(dialog, (100, 100), (105, 105))
        dialog._confirm()
        assert dialog.result is None
        assert is_open(dialog)

    def test_crop_button_is_wired_up(self, make_dialog):
        dialog = make_dialog()
        drag(dialog, (50, 40), (250, 160))
        find_button(dialog, "Crop & Read Board").invoke()
        assert dialog.result.size == (200, 120)
        assert not is_open(dialog)

    def test_crop_button_does_nothing_without_a_selection(self, make_dialog):
        dialog = make_dialog()
        find_button(dialog, "Crop & Read Board").invoke()
        assert dialog.result is None
        assert is_open(dialog)


class TestCancel:
    def test_cancel_closes_and_returns_nothing(self, make_dialog):
        dialog = make_dialog()
        dialog._cancel()
        assert dialog.result is None
        assert not is_open(dialog)

    def test_cancel_after_selecting_still_returns_nothing(self, make_dialog):
        dialog = make_dialog()
        drag(dialog, (50, 40), (250, 160))
        dialog._cancel()
        assert dialog.result is None
        assert not is_open(dialog)

    def test_cancel_button_is_wired_up(self, make_dialog):
        dialog = make_dialog()
        find_button(dialog, "Cancel").invoke()
        assert not is_open(dialog)

    def test_escape_key_cancels(self, make_dialog):
        dialog = make_dialog()
        dialog.focus_force()
        dialog.update()
        dialog.event_generate("<Escape>")
        dialog.update()
        assert not is_open(dialog)
        assert dialog.result is None

    def test_closing_the_window_cancels(self, make_dialog):
        dialog = make_dialog()
        dialog.tk.call(dialog.protocol("WM_DELETE_WINDOW"))   # what the window's X button triggers
        dialog.update()
        assert not is_open(dialog)
        assert dialog.result is None


# ----------------------------------------------------------------------
# Modal behavior
# ----------------------------------------------------------------------
class TestModal:
    def test_dialog_takes_the_input_grab_shortly_after_opening(self, make_dialog):
        dialog = make_dialog()
        for _ in range(40):                     # the grab is requested 100 ms after opening
            dialog.update()
            if dialog.grab_current() is not None:
                break
            time.sleep(0.05)
        assert dialog.grab_current() is dialog

    def test_a_dialog_closed_before_the_grab_fires_does_not_error(self, make_dialog):
        dialog = make_dialog()
        dialog.destroy()
        dialog._make_modal()    # the delayed call that still runs after the dialog is gone


# ----------------------------------------------------------------------
# ask_crop: the function the GUI calls
# ----------------------------------------------------------------------
def run_ask_crop(root, image, action):
    """
    Call ask_crop (which blocks) and run action(dialog) once the dialog is on screen.
    A watchdog closes a dialog that is still open after 4 seconds, so a failing test
    cannot hang the whole test run.
    """
    problems = []

    def act():
        dialog = next(w for w in root.winfo_children() if isinstance(w, CropDialog))
        try:
            if not wait_until_visible(dialog):
                raise AssertionError("dialog never became visible")
            action(dialog)
        except Exception as err:        # report it from the test, not from inside Tk
            problems.append(err)

    def watchdog():
        for widget in root.winfo_children():
            if isinstance(widget, CropDialog):
                problems.append(AssertionError("dialog was still open after 4 seconds"))
                widget.destroy()

    ids = [root.after(200, act), root.after(4000, watchdog)]
    try:
        result = ask_crop(root, image)
    finally:
        for after_id in ids:
            root.after_cancel(after_id)
    if problems:
        raise problems[0]
    return result


class TestAskCrop:
    def test_returns_the_cropped_picture_after_confirming(self, root):
        def confirm(dialog):
            drag(dialog, (50, 40), (250, 160))
            find_button(dialog, "Crop & Read Board").invoke()

        result = run_ask_crop(root, Image.new("RGB", (400, 200), "white"), confirm)
        assert result.size == (200, 120)

    def test_returns_none_after_cancelling(self, root):
        result = run_ask_crop(root, Image.new("RGB", (400, 200), "white"),
                              lambda dialog: find_button(dialog, "Cancel").invoke())
        assert result is None

    def test_returns_none_when_the_window_is_closed(self, root):
        def close_window(dialog):
            dialog.tk.call(dialog.protocol("WM_DELETE_WINDOW"))

        assert run_ask_crop(root, Image.new("RGB", (400, 200), "white"), close_window) is None

    def test_leaves_no_dialog_behind(self, root):
        run_ask_crop(root, Image.new("RGB", (400, 200), "white"),
                     lambda dialog: find_button(dialog, "Cancel").invoke())
        assert not [w for w in root.winfo_children() if isinstance(w, CropDialog)]