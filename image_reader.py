"""
image_reader.py - read a Boggle board from a picture using Tesseract OCR.

Pass a file path or a PIL image (such as the cropped board from
crop_dialog.ask_crop). The picture must be cropped tightly to the letter grid,
because it is divided into equal N x N tiles. Returns an N x N list of lists of
strings, for example [["A", "B"], ["QU", "E"]], with "" for any tile that could
not be read.

Requires:
    pip install pillow opencv-python pytesseract
    plus the Tesseract program itself (https://github.com/UB-Mannheim/tesseract/wiki
    for Windows builds).
"""

from __future__ import annotations

import os
import shutil

from PIL import Image, ImageOps

# Default install location of Tesseract on Windows
_WINDOWS_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


class BoardReadError(Exception):
    """Raised when the picture cannot be read as a board."""


def normalize_label(text: str) -> str:
    """Turn OCR output into the text a tile should display."""
    text = text.strip().upper()
    if not text:
        return ""
    return "QU" if text[0] == "Q" else text[0]  # a Boggle Q tile always shows QU


def _as_pil(image) -> Image.Image:
    """Accept a path or a PIL image; always return an upright RGB PIL image."""
    if isinstance(image, (str, os.PathLike)):
        path = image
        try:
            image = Image.open(path)
            image.load()  # read the pixels now, so a truncated file fails here
        except OSError as err:
            raise BoardReadError(f"Could not open image: {path}") from err
    return ImageOps.exif_transpose(image).convert("RGB")



def split_into_tiles(image: Image.Image, size: int) -> list[list[Image.Image]]:
    """Cut an image into size x size equal tiles."""
    w, h = image.size
    return [
        [image.crop((round(c * w / size), round(r * h / size),
                     round((c + 1) * w / size), round((r + 1) * h / size)))
         for c in range(size)]
        for r in range(size)
    ]


def read_board_ocr(image, size: int) -> list[list[str]]:
    import cv2
    import numpy as np
    import pytesseract

    # If Tesseract is not on PATH, fall back to its default Windows location
    if shutil.which("tesseract") is None and os.path.exists(_WINDOWS_TESSERACT):
        pytesseract.pytesseract.tesseract_cmd = _WINDOWS_TESSERACT

    config = "--psm 10 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    grid = []
    try:
        for tile_row in split_into_tiles(_as_pil(image), size):
            row = []
            for tile in tile_row:
                mx, my = tile.width // 8, tile.height // 8  # trim borders and grid lines
                tile = tile.crop((mx, my, tile.width - mx, tile.height - my))
                gray = np.array(tile.convert("L"))
                _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                if bw.mean() < 127:  # Tesseract prefers dark text on a light background
                    bw = cv2.bitwise_not(bw)
                row.append(normalize_label(pytesseract.image_to_string(bw, config=config)))
            grid.append(row)
    except pytesseract.TesseractNotFoundError as err:
        raise BoardReadError(
            "Tesseract OCR is not installed or could not be found. "
            "Install it and make sure it is on your PATH."
        ) from err
    return grid


def read_board(image, size: int, method: str = "ocr") -> list[list[str]]:
    """Entry point for the GUI. OCR is the only method right now."""
    if method == "ocr":
        return read_board_ocr(image, size)
    raise ValueError(f"Unknown method: {method}")