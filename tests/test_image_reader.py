"""
Tests for image_reader.py.  Run from the project root with:   pytest -v

Three kinds of test live here:

  1. Pure-Python tests (normalize_label, image loading, tile slicing). They need
     only Pillow.
  2. Logic tests for read_board_ocr that replace Tesseract with a stand-in, so they
     are fast, deterministic and independent of your Tesseract version. They need
     opencv-python, numpy and pytesseract to be installed (the stand-in replaces the
     Tesseract program, not the Python package).
  3. A few end-to-end tests that run the real Tesseract on boards drawn with Pillow.
     They are marked "ocr" and skipped when Tesseract is missing. Skip them on
     purpose with:   pytest -m "not ocr"
"""

import os
import shutil

import pytest
from PIL import Image, ImageDraw, ImageFont

import image_reader
from image_reader import BoardReadError, normalize_label, read_board, read_board_ocr, split_into_tiles


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def colored_grid(width, height, n):
    """An image split into n x n blocks; block (r, c) is filled with (r*40, c*40, 200)."""
    img = Image.new("RGB", (width, height))
    pixels = img.load()
    for y in range(height):
        for x in range(width):
            r = min(n - 1, y * n // height)
            c = min(n - 1, x * n // width)
            pixels[x, y] = (r * 40, c * 40, 200)
    return img


def bar_board(n, cell=90, fg="black", bg="white"):
    """
    An n x n board where tile k (counting 1, 2, 3... in reading order) holds a bar
    10 pixels wide and 6*k pixels tall. The bar's size says which tile it came from.
    """
    img = Image.new("RGB", (n * cell, n * cell), bg)
    draw = ImageDraw.Draw(img)
    for r in range(n):
        for c in range(n):
            k = r * n + c + 1
            cx, cy = c * cell + cell // 2, r * cell + cell // 2
            draw.rectangle([cx - 5, cy - 3 * k, cx + 4, cy + 3 * k - 1], fill=fg)
    return img


def draw_board(letters, cell=120, fg="black", bg="white", grid_line="gray"):
    """Draw a board of real letters ('' leaves a tile blank) for the end-to-end tests."""
    n = len(letters)
    img = Image.new("RGB", (n * cell, n * cell), bg)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=int(cell * 0.6))
    except TypeError:
        pytest.skip("this Pillow version has no scalable default font")
    for r, row in enumerate(letters):
        for c, ch in enumerate(row):
            x0, y0 = c * cell, r * cell
            draw.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1], outline=grid_line, width=2)
            if ch:
                draw.text((x0 + cell / 2, y0 + cell / 2), ch, font=font, fill=fg, anchor="mm")
    return img


def tesseract_available():
    return shutil.which("tesseract") is not None or os.path.exists(image_reader._WINDOWS_TESSERACT)


# ----------------------------------------------------------------------
# normalize_label
# ----------------------------------------------------------------------
class TestNormalizeLabel:
    @pytest.mark.parametrize("raw, expected", [
        ("A", "A"),
        ("e", "E"),                  # always uppercase
        ("  e \n", "E"),             # surrounding whitespace is ignored
        ("A\n\x0c", "A"),            # Tesseract output typically ends with a form feed
        ("AB", "A"),                 # only the first character is kept
        ("", ""),
        ("   \n", ""),
    ])
    def test_ordinary_text(self, raw, expected):
        assert normalize_label(raw) == expected

    @pytest.mark.parametrize("raw", ["Q", "q", "QU", "qu", " q\n"])
    def test_q_always_becomes_qu(self, raw):
        # A Boggle Q tile always shows QU
        assert normalize_label(raw) == "QU"

    def test_a_q_that_is_not_first_does_not_count(self):
        assert normalize_label("AQ") == "A"


# ----------------------------------------------------------------------
# _as_pil: loading and cleaning up the input picture
# ----------------------------------------------------------------------
class TestAsPil:
    def test_opens_a_file_path(self, tmp_path):
        path = tmp_path / "board.png"
        Image.new("RGB", (40, 20), "white").save(path)
        img = image_reader._as_pil(str(path))
        assert img.size == (40, 20)
        assert img.mode == "RGB"

    def test_pathlib_path_is_accepted(self, tmp_path):
        path = tmp_path / "board.png"
        Image.new("RGB", (40, 20), "white").save(path)
        assert image_reader._as_pil(path).size == (40, 20)

    def test_truncated_image_file_raises_board_read_error(self, tmp_path):
        good = tmp_path / "good.png"
        Image.effect_noise((200, 200), 80).convert("RGB").save(good)
        data = good.read_bytes()
        cut = tmp_path / "cut.png"
        cut.write_bytes(data[: len(data) // 2])
        with pytest.raises(BoardReadError):
            image_reader._as_pil(str(cut))

    @pytest.mark.parametrize("mode", ["RGB", "RGBA", "L", "P"])
    def test_every_input_comes_out_as_rgb(self, mode):
        assert image_reader._as_pil(Image.new(mode, (8, 8))).mode == "RGB"

    def test_the_original_image_is_left_alone(self):
        original = Image.new("RGBA", (8, 8))
        image_reader._as_pil(original)
        assert original.mode == "RGBA"

    def test_missing_file_raises_board_read_error(self, tmp_path):
        missing = str(tmp_path / "nope.png")
        with pytest.raises(BoardReadError, match="Could not open image"):
            image_reader._as_pil(missing)

    def test_file_that_is_not_an_image_raises_board_read_error(self, tmp_path):
        path = tmp_path / "notes.png"
        path.write_text("this is not a picture")
        with pytest.raises(BoardReadError, match="Could not open image"):
            image_reader._as_pil(str(path))

    def test_exif_rotation_is_applied(self, tmp_path):
        # Phone photos are often stored sideways with an EXIF tag saying how to turn them
        path = tmp_path / "sideways.jpg"
        exif = Image.Exif()
        exif[0x0112] = 6   # "rotate to display"
        Image.new("RGB", (40, 20), "white").save(path, exif=exif)
        assert image_reader._as_pil(str(path)).size == (20, 40)


# ----------------------------------------------------------------------
# split_into_tiles
# ----------------------------------------------------------------------
class TestSplitIntoTiles:
    @pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 6])
    def test_produces_an_n_by_n_grid(self, n):
        tiles = split_into_tiles(Image.new("RGB", (120, 120)), n)
        assert len(tiles) == n
        assert all(len(row) == n for row in tiles)

    @pytest.mark.parametrize("width, height, n", [(400, 400, 4), (403, 302, 4), (97, 61, 6)])
    def test_tiles_cover_the_whole_image_with_no_gaps_or_overlap(self, width, height, n):
        tiles = split_into_tiles(Image.new("RGB", (width, height)), n)
        for row in tiles:
            assert sum(t.width for t in row) == width
        for c in range(n):
            assert sum(tiles[r][c].height for r in range(n)) == height

    def test_tile_sizes_differ_by_at_most_one_pixel(self):
        tiles = split_into_tiles(Image.new("RGB", (403, 302)), 4)
        widths = {t.width for row in tiles for t in row}
        heights = {t.height for row in tiles for t in row}
        assert max(widths) - min(widths) <= 1
        assert max(heights) - min(heights) <= 1

    @pytest.mark.parametrize("width, height, n", [(400, 400, 4), (403, 302, 4), (90, 60, 3)])
    def test_tiles_come_back_in_reading_order(self, width, height, n):
        tiles = split_into_tiles(colored_grid(width, height, n), n)
        for r in range(n):
            for c in range(n):
                tile = tiles[r][c]
                center = tile.getpixel((tile.width // 2, tile.height // 2))
                assert center == (r * 40, c * 40, 200), f"tile ({r}, {c}) holds the wrong block"

    def test_one_tile_is_the_whole_image(self):
        img = colored_grid(50, 30, 2)
        (only,) = split_into_tiles(img, 1)[0]
        assert only.size == img.size


# ----------------------------------------------------------------------
# read_board_ocr logic, with Tesseract replaced by a stand-in
# ----------------------------------------------------------------------
class FakeOcr:
    """Stands in for pytesseract.image_to_string: records calls, returns scripted text."""

    def __init__(self):
        self.calls = []     # (image array, config string) per call
        self.replies = []   # text to return for the 1st, 2nd, ... call

    def __call__(self, image, config=""):
        self.calls.append((image, config))
        index = len(self.calls) - 1
        return self.replies[index] if index < len(self.replies) else ""


@pytest.fixture
def pytesseract_module():
    pytest.importorskip("cv2")
    pytest.importorskip("numpy")
    return pytest.importorskip("pytesseract")


@pytest.fixture
def fake_ocr(pytesseract_module, monkeypatch):
    fake = FakeOcr()
    monkeypatch.setattr(pytesseract_module, "image_to_string", fake)
    # Make sure any change the code makes to the Tesseract location is undone afterwards
    monkeypatch.setattr(pytesseract_module.pytesseract, "tesseract_cmd",
                        pytesseract_module.pytesseract.tesseract_cmd)
    return fake


class TestReadBoardOcrLogic:
    def test_replies_fill_the_grid_in_reading_order(self, fake_ocr):
        fake_ocr.replies = list("ABCDEFGHI")
        grid = read_board_ocr(Image.new("RGB", (270, 270), "white"), 3)
        assert grid == [["A", "B", "C"], ["D", "E", "F"], ["G", "H", "I"]]

    def test_each_reply_is_normalized(self, fake_ocr):
        fake_ocr.replies = ["a\n", "q", "", "xyz"]
        grid = read_board_ocr(Image.new("RGB", (100, 100), "white"), 2)
        assert grid == [["A", "QU"], ["", "X"]]

    @pytest.mark.parametrize("n", [2, 4, 6])
    def test_ocr_runs_once_per_tile(self, fake_ocr, n):
        read_board_ocr(Image.new("RGB", (n * 30, n * 30), "white"), n)
        assert len(fake_ocr.calls) == n * n

    def test_each_tile_is_sent_to_ocr_on_its_own_and_in_order(self, fake_ocr):
        # Tile k contains a bar with exactly 60*k black pixels, so the k-th OCR call
        # should receive an image with that many black pixels.
        read_board_ocr(bar_board(3), 3)
        black_pixels = [int((array == 0).sum()) for array, _config in fake_ocr.calls]
        assert black_pixels == [60 * k for k in range(1, 10)]

    def test_text_reaches_ocr_as_black_on_white_whatever_the_original_colors(self, fake_ocr):
        # Mixed board: dark-on-light and light-on-dark tiles, side by side
        img = Image.new("RGB", (200, 200), "white")
        draw = ImageDraw.Draw(img)
        for r in range(2):
            for c in range(2):
                dark_background = (r + c) % 2 == 1
                x0, y0 = c * 100, r * 100
                if dark_background:
                    draw.rectangle([x0, y0, x0 + 99, y0 + 99], fill="black")
                draw.rectangle([x0 + 40, y0 + 40, x0 + 59, y0 + 59],
                               fill="white" if dark_background else "black")
        read_board_ocr(img, 2)

        assert len(fake_ocr.calls) == 4
        for array, _config in fake_ocr.calls:
            height, width = array.shape
            assert array[0, 0] == 255                       # background is white
            assert array[height // 2, width // 2] == 0      # the letter is black

    def test_tiles_are_trimmed_so_grid_lines_are_not_read(self, fake_ocr):
        read_board_ocr(Image.new("RGB", (400, 400), "white"), 4)   # 100 x 100 tiles
        for array, _config in fake_ocr.calls:
            height, width = array.shape
            assert 50 < height < 100
            assert 50 < width < 100

    def test_ocr_is_asked_for_a_single_uppercase_letter(self, fake_ocr):
        read_board_ocr(Image.new("RGB", (60, 60), "white"), 2)
        for _array, config in fake_ocr.calls:
            assert "--psm 10" in config                                   # one character
            assert "tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ" in config

    def test_a_file_path_and_a_picture_give_the_same_result(self, fake_ocr, tmp_path):
        img = Image.new("RGB", (80, 80), "white")
        path = tmp_path / "board.png"
        img.save(path)

        fake_ocr.replies = ["a", "b", "c", "d"]
        from_picture = read_board_ocr(img, 2)
        fake_ocr.calls.clear()
        from_path = read_board_ocr(str(path), 2)
        assert from_picture == from_path == [["A", "B"], ["C", "D"]]


class TestTesseractLocation:
    def test_missing_tesseract_becomes_board_read_error(self, pytesseract_module, monkeypatch):
        monkeypatch.setattr(image_reader.shutil, "which", lambda _name: "somewhere")  # skip fallback
        monkeypatch.setattr(pytesseract_module.pytesseract, "tesseract_cmd", "no_such_tesseract_program")
        with pytest.raises(BoardReadError, match="Tesseract"):
            read_board_ocr(Image.new("RGB", (80, 80), "white"), 2)

    def test_falls_back_to_the_windows_install_when_not_on_path(
            self, fake_ocr, pytesseract_module, monkeypatch, tmp_path):
        fake_exe = tmp_path / "tesseract.exe"
        fake_exe.write_text("")
        monkeypatch.setattr(image_reader, "_WINDOWS_TESSERACT", str(fake_exe))
        monkeypatch.setattr(image_reader.shutil, "which", lambda _name: None)

        read_board_ocr(Image.new("RGB", (40, 40), "white"), 1)
        assert pytesseract_module.pytesseract.tesseract_cmd == str(fake_exe)

    def test_a_tesseract_on_the_path_is_left_alone(
            self, fake_ocr, pytesseract_module, monkeypatch, tmp_path):
        fake_exe = tmp_path / "tesseract.exe"
        fake_exe.write_text("")
        monkeypatch.setattr(image_reader, "_WINDOWS_TESSERACT", str(fake_exe))
        monkeypatch.setattr(image_reader.shutil, "which", lambda _name: "on-the-path")
        monkeypatch.setattr(pytesseract_module.pytesseract, "tesseract_cmd", "my_own_setting")

        read_board_ocr(Image.new("RGB", (40, 40), "white"), 1)
        assert pytesseract_module.pytesseract.tesseract_cmd == "my_own_setting"

    def test_no_fallback_when_the_windows_install_does_not_exist(
            self, fake_ocr, pytesseract_module, monkeypatch, tmp_path):
        monkeypatch.setattr(image_reader, "_WINDOWS_TESSERACT", str(tmp_path / "not_there.exe"))
        monkeypatch.setattr(image_reader.shutil, "which", lambda _name: None)
        monkeypatch.setattr(pytesseract_module.pytesseract, "tesseract_cmd", "my_own_setting")

        read_board_ocr(Image.new("RGB", (40, 40), "white"), 1)
        assert pytesseract_module.pytesseract.tesseract_cmd == "my_own_setting"


# ----------------------------------------------------------------------
# read_board: the entry point the GUI calls
# ----------------------------------------------------------------------
class TestReadBoard:
    def test_defaults_to_ocr(self, monkeypatch):
        calls = []

        def fake_read(image, size):
            calls.append((image, size))
            return [["sentinel"]]

        monkeypatch.setattr(image_reader, "read_board_ocr", fake_read)
        assert read_board("picture", 4) == [["sentinel"]]
        assert calls == [("picture", 4)]

    def test_unknown_method_is_rejected(self):
        with pytest.raises(ValueError, match="Unknown method"):
            read_board("picture", 4, method="telepathy")


# ----------------------------------------------------------------------
# End to end with the real Tesseract (skipped when it is not installed)
# ----------------------------------------------------------------------
@pytest.mark.ocr
@pytest.mark.skipif(not tesseract_available(), reason="Tesseract is not installed")
class TestRealOcr:
    """
    Boards are drawn with Pillow in Pillow's built-in font, using letters that read
    reliably. If a different Tesseract version misreads one, swap that letter out; a
    failure here is about OCR quality, not about the logic tested above.
    """

    @pytest.fixture(autouse=True)
    def _need_packages(self):
        pytest.importorskip("cv2")
        pytest.importorskip("pytesseract")

    @pytest.mark.parametrize("colors", [
        {},                                            # dark letters on light tiles
        {"fg": "white", "bg": "black"},                # light letters on dark tiles
    ], ids=["dark-on-light", "light-on-dark"])
    def test_reads_a_3x3_board(self, colors):
        letters = [list("CAT"), list("DOG"), list("SUN")]
        assert read_board(draw_board(letters, **colors), 3) == letters

    def test_reads_a_4x4_board(self):
        letters = [list("KMRD"), list("FHJB"), list("AVXU"), list("CETN")]
        assert read_board(draw_board(letters), 4) == letters

    def test_a_blank_tile_comes_back_empty_and_q_becomes_qu(self):
        letters = [["C", "", "T"], ["Q", "A", "R"], ["E", "N", "D"]]
        expected = [["C", "", "T"], ["QU", "A", "R"], ["E", "N", "D"]]
        assert read_board(draw_board(letters), 3) == expected

    def test_reads_from_a_file_on_disk(self, tmp_path):
        letters = [list("CAT"), list("DOG"), list("SUN")]
        path = tmp_path / "board.png"
        draw_board(letters).save(path)
        assert read_board(str(path), 3) == letters