"""
crop_dialog.py - a modal window where the user drags a rectangle over a picture
to select just the Boggle board. Anything outside the rectangle (titles, margins,
page footers) is thrown away before the picture reaches the recognizer.

Usage:
    cropped = ask_crop(parent_window, pil_image)   # PIL image, or None if cancelled

Requires: pip install pillow customtkinter
"""

import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageTk


def canvas_box_to_image_box(x0, y0, x1, y1, scale, img_w, img_h):
    """
    Convert a rectangle dragged on the (scaled-down) canvas into pixel coordinates
    of the original image. Works for drags in any direction and clamps the result
    to the image edges. Returns (left, top, right, bottom).
    """
    left, right = sorted((x0, x1))
    top, bottom = sorted((y0, y1))

    def to_image(value, upper):
        return max(0, min(upper, round(value / scale)))

    return (to_image(left, img_w), to_image(top, img_h),
            to_image(right, img_w), to_image(bottom, img_h))


class CropDialog(ctk.CTkToplevel):
    MAX_W, MAX_H = 820, 620   # largest on-screen size of the picture
    MIN_SIZE = 20             # smallest allowed selection, in original-image pixels

    def __init__(self, parent, pil_image):
        super().__init__(parent)
        self.title("Crop to the board")
        self.resizable(False, False)
        self.result = None  # set to the cropped PIL image on confirm

        self._image = pil_image.convert("RGB")
        img_w, img_h = self._image.size

        # Shrink big pictures to fit the screen (never enlarge small ones)
        self._scale = min(self.MAX_W / img_w, self.MAX_H / img_h, 1.0)
        self._disp_w = max(1, round(img_w * self._scale))
        self._disp_h = max(1, round(img_h * self._scale))
        # Keep a reference on self, otherwise Tk garbage-collects the picture
        self._photo = ImageTk.PhotoImage(
            self._image.resize((self._disp_w, self._disp_h), Image.LANCZOS)
        )

        self._start = None      # where the current drag began (canvas coords)
        self._box = None        # finished selection (canvas coords)
        self._rect_id = None    # the rectangle drawn on the canvas

        self._hint = ctk.CTkLabel(
            self, text="Drag a box around the letter grid only "
                       "(outer corner to outer corner)."
        )
        self._hint.pack(padx=10, pady=(10, 5))

        self._canvas = tk.Canvas(
            self, width=self._disp_w, height=self._disp_h,
            highlightthickness=0, cursor="crosshair",
        )
        self._canvas.pack(padx=10, pady=5)
        self._canvas.create_image(0, 0, anchor="nw", image=self._photo)
        self._canvas.bind("<ButtonPress-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(pady=(5, 10))
        ctk.CTkButton(buttons, text="Cancel", width=100, command=self._cancel).grid(row=0, column=0, padx=5)
        ctk.CTkButton(buttons, text="Reset", width=100, command=self._reset).grid(row=0, column=1, padx=5)
        self._confirm_btn = ctk.CTkButton(
            buttons, text="Crop & Read Board", width=160,
            state="disabled", command=self._confirm,
        )
        self._confirm_btn.grid(row=0, column=2, padx=5)

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _event: self._cancel())

        # Make the dialog modal. Grabbing immediately can fail before the window
        # is visible, so wait a moment first.
        self.transient(parent)
        self.after(100, self._make_modal)

    # ------------------------------------------------------------------
    def _make_modal(self):
        if self.winfo_exists():
            self.grab_set()
            self.focus_set()

    def _clamp(self, event):
        return (max(0, min(self._disp_w, event.x)),
                max(0, min(self._disp_h, event.y)))

    def _on_press(self, event):
        self._reset()
        self._start = self._clamp(event)
        x, y = self._start
        self._rect_id = self._canvas.create_rectangle(
            x, y, x, y, outline="red", width=2, dash=(4, 2)
        )

    def _on_drag(self, event):
        if self._start is None:
            return
        x, y = self._clamp(event)
        self._canvas.coords(self._rect_id, self._start[0], self._start[1], x, y)

    def _on_release(self, event):
        if self._start is None:
            return
        x, y = self._clamp(event)
        self._box = (self._start[0], self._start[1], x, y)
        self._start = None

        if self._selection_in_image_coords() is None:
            self._hint.configure(text="That selection is too small - drag a larger box.")
            self._confirm_btn.configure(state="disabled")
        else:
            self._hint.configure(text="Happy with it? Click 'Crop & Read Board' "
                                      "(or drag again to redo).")
            self._confirm_btn.configure(state="normal")

    def _selection_in_image_coords(self):
        if self._box is None:
            return None
        img_w, img_h = self._image.size
        left, top, right, bottom = canvas_box_to_image_box(
            *self._box, self._scale, img_w, img_h
        )
        if right - left < self.MIN_SIZE or bottom - top < self.MIN_SIZE:
            return None
        return left, top, right, bottom

    def _reset(self):
        if self._rect_id is not None:
            self._canvas.delete(self._rect_id)
        self._rect_id = None
        self._start = None
        self._box = None
        self._confirm_btn.configure(state="disabled")

    def _confirm(self):
        box = self._selection_in_image_coords()
        if box is None:
            return
        self.result = self._image.crop(box)
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


def ask_crop(parent, pil_image):
    """Show the crop dialog and wait. Returns the cropped PIL image, or None."""
    dialog = CropDialog(parent, pil_image)
    parent.wait_window(dialog)
    return dialog.result