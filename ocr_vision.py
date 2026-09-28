"""
ocr_vision.py

Extracts a Boggle board by reading each ROW as a single line of text,
rather than isolating and reading one letter at a time.

Why this approach:
    Earlier attempts at reading individual, isolated letters worked well
    once cell boundaries were found correctly, but finding those cell
    boundaries (especially column boundaries) was the fragile part across
    different image styles. Treating a whole row as one "word" sidesteps
    needing column boundaries at all: OCR is naturally built to read a
    line of text, and the number of columns can be inferred afterward from
    how many characters it read -- with one exception, since physical
    Boggle dice have a combined "Qu" face that must be treated as a single
    tile rather than two separate letters.

How it works (two-pass):
    1. Run EasyOCR once over the whole image to find roughly where each
       row of text sits (its top/bottom y-range), by grouping individual
       detections by vertical position.
    2. Crop each row as its own horizontal strip and run OCR on that strip
       alone. Reading a single isolated line tends to be more reliable
       than reading a whole cluttered image at once, since there's no
       other row's text nearby to interfere.
    3. Split each row's resulting text into tiles, treating "QU" as one
       tile, and use the resulting tile count as the number of columns.

Usage:
    python ocr_vision.py path\\to\\image.png [--debug]

Requires:
    pip install opencv-python easyocr numpy
"""

import sys
import os

import cv2
import numpy as np
import easyocr

ALLOWED_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

_reader = None


def _get_reader() -> easyocr.Reader:
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


def find_row_bands(image_path: str, debug: bool = False) -> list[tuple[int, int, int, int]]:
    """First pass: find each row's approximate (top, bottom, left, right) box.

    Runs OCR once over the whole image, then groups the individual
    detections by vertical position. This does not need to read the text
    correctly -- it only needs the detections' positions to be roughly
    right, since the actual reading happens per-row in the second pass.

    The (left, right) horizontal extent matters just as much as the row's
    vertical range: a photographed board often has background/margin on
    either side of the actual grid, so a later step that divides the row
    into columns must divide the row's OWN detected width, not the full
    image width, or the edge columns end up slicing background instead of
    the outermost letters.
    """
    reader = _get_reader()
    results = reader.readtext(image_path, allowlist=ALLOWED_CHARS)

    if not results:
        raise ValueError("No text detected in the image at all.")

    boxes = []
    for bbox, text, conf in results:
        if not text.strip():
            continue
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        boxes.append((min(ys), max(ys), min(xs), max(xs)))

    # Drop detections that are much shorter than the rest -- board letters
    # are all roughly the same height, so a detection far smaller than the
    # median height (e.g. a caption or watermark elsewhere in the photo)
    # is very unlikely to be a real row of letters.
    heights = np.array([bottom - top for top, bottom, _, _ in boxes])
    median_h = float(np.median(heights))
    boxes = [b for b in boxes if (b[1] - b[0]) > median_h * 0.4]

    if debug:
        print(f"First pass: {len(boxes)} detections kept after removing undersized ones "
              f"(median height {median_h:.0f})")

    avg_h = float(np.mean([b[1] - b[0] for b in boxes]))
    boxes.sort(key=lambda b: b[0])

    rows = [[boxes[0]]]
    for box in boxes[1:]:
        if abs(box[0] - rows[-1][-1][0]) < avg_h * 0.6:
            rows[-1].append(box)
        else:
            rows.append([box])

    # Build RAW (unpadded) row extents first. Merging decisions happen on
    # these, before any padding is added -- padding can otherwise shrink or
    # even eliminate the real gap between two genuinely separate rows,
    # causing them to be wrongly merged together.
    raw_bands = []
    for row in rows:
        row_top = min(b[0] for b in row)
        row_bottom = max(b[1] for b in row)
        row_left = min(b[2] for b in row)
        row_right = max(b[3] for b in row)
        raw_bands.append((row_top, row_bottom, row_left, row_right))

    if len(raw_bands) > 1:
        gaps = [raw_bands[i + 1][0] - raw_bands[i][1] for i in range(len(raw_bands) - 1)]
        positive_gaps = [g for g in gaps if g > 0]
        typical_gap = float(np.median(positive_gaps)) if positive_gaps else 0
        merged_raw = [raw_bands[0]]
        for top, bottom, left, right in raw_bands[1:]:
            prev_top, prev_bottom, prev_left, prev_right = merged_raw[-1]
            gap = top - prev_bottom
            # Only merge when there's a genuine (positive) small gap -- if
            # the raw bands already overlap or the gap looks like a normal
            # inter-row spacing, leave them as separate rows.
            if typical_gap > 0 and 0 <= gap < typical_gap * 0.4:
                merged_raw[-1] = (prev_top, max(prev_bottom, bottom),
                                   min(prev_left, left), max(prev_right, right))
            else:
                merged_raw.append((top, bottom, left, right))
        raw_bands = merged_raw

    # Pad each final band (vertically AND horizontally), and explicitly
    # cast to int -- EasyOCR's box coordinates can come back as floats
    # (e.g. for rotated/quad boxes), and a float slice index raises a
    # TypeError on a numpy array.
    row_bands = []
    for top, bottom, left, right in raw_bands:
        pad_y = int((bottom - top) * 0.15)
        pad_x = int((right - left) * 0.08)
        row_bands.append((
            int(max(0, top - pad_y)), int(bottom + pad_y),
            int(max(0, left - pad_x)), int(right + pad_x),
        ))

    if debug:
        print(f"Grouped into {len(row_bands)} row bands (top, bottom, left, right): {row_bands}")

    return row_bands


def infer_row_tiles(raw_text: str) -> list[str]:
    """Split a row's raw OCR text into tile contents.

    "QU" is treated as a single tile, matching physical Boggle dice that
    have a combined Qu face, rather than two separate letters.
    """
    raw_text = raw_text.upper().replace(" ", "")
    tiles = []
    i = 0
    while i < len(raw_text):
        if raw_text[i:i + 2] == "QU":
            tiles.append("QU")
            i += 2
        else:
            if raw_text[i].isalpha():
                tiles.append(raw_text[i])
            i += 1
    return tiles


def ocr_row_band(gray_img: np.ndarray, top: int, bottom: int, left: int, right: int,
                  reader: easyocr.Reader, debug: bool = False,
                  save_debug_strip: str | None = None) -> str:
    """Second pass: OCR one row's horizontal strip on its own, as a line of text."""
    strip = gray_img[int(top):int(bottom), int(left):int(right)]
    if strip.size == 0:
        return ""

    # Upscale -- a horizontal strip is often not very tall, and OCR tends
    # to read small text more reliably at a larger effective size.
    scale = max(1, 250 // max(strip.shape[0], 1))
    if scale > 1:
        strip = cv2.resize(strip, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # Add a border -- a character sitting flush against the crop's edge can
    # be harder for the detector to isolate than one with margin around it.
    strip = cv2.copyMakeBorder(strip, 20, 20, 20, 20, cv2.BORDER_CONSTANT,
                                value=int(np.median(strip)))

    if save_debug_strip:
        cv2.imwrite(save_debug_strip, strip)

    # Lower the detector's sensitivity thresholds from EasyOCR's defaults
    # (text_threshold=0.7, low_text=0.4) so that narrow characters like
    # "I" -- which have much less ink than a wide letter and can otherwise
    # fall under the detector's confidence bar entirely -- are still found.
    results = reader.readtext(
        strip, allowlist=ALLOWED_CHARS, detail=1, paragraph=False,
        text_threshold=0.5, low_text=0.3,
    )
    results.sort(key=lambda r: r[0][0][0])
    raw_text = "".join(text for _, text, _ in results)

    if debug:
        print(f"  row band y=({top},{bottom}) -> raw OCR text: {raw_text!r}")
        if len(results) > 1:
            widths = [r[0][2][0] - r[0][0][0] for r in results]
            print(f"    detected piece widths: {widths} (a very narrow width relative "
                  f"to the others may indicate a thin letter like 'I')")

    return raw_text


def select_most_evenly_spaced_run(
    row_bands: list[tuple[int, int]], count: int
) -> list[int]:
    """Pick the `count` consecutive bands whose spacing is most uniform.

    A real grid's rows are evenly spaced, since they're a stack of
    identically-sized tiles. The transition into or out of the grid from
    surrounding UI text (a timer, a word display, branding) is typically a
    different, often larger, gap than the consistent tile-to-tile spacing
    within the grid itself. Scanning for the most uniform run of gaps is a
    more reliable way to locate the real rows than tile count, which can be
    thrown off by an unrelated OCR miss on a real row.
    """
    if count >= len(row_bands):
        return list(range(len(row_bands)))

    gaps = [row_bands[i + 1][0] - row_bands[i][1] for i in range(len(row_bands) - 1)]

    best_start = 0
    best_spread = None
    for start in range(len(row_bands) - count + 1):
        internal_gaps = gaps[start:start + count - 1]
        spread = max(internal_gaps) - min(internal_gaps) if internal_gaps else 0
        if best_spread is None or spread < best_spread:
            best_spread = spread
            best_start = start

    return list(range(best_start, best_start + count))


def looks_like_letter_i(cell_gray: np.ndarray, debug: bool = False) -> bool:
    """Check whether a cell's foreground is a single tall, narrow blob.

    "I" is the one letter that's essentially just a solid rectangle, with
    none of the curves or distinct strokes a generic text detector is
    trained to look for. In testing, EasyOCR's detector found ZERO text
    regions at all in cells containing a large, clear, high-contrast "I" --
    not a low-confidence miss, but no detection whatsoever. Since no other
    letter has this simple a shape, a tall/narrow aspect ratio check on the
    cell's own foreground blob is a safe, unambiguous way to identify "I"
    directly, without relying on OCR to recognize it as text at all.
    """
    _, thresh = cv2.threshold(cell_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if np.mean(thresh) > 127:
        thresh = cv2.bitwise_not(thresh)  # ensure the letter itself is the white foreground

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        if debug:
            print(f"      [I-shape check] no contours found at all in this cell")
        return False

    largest = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest)
    if w == 0:
        return False

    aspect = h / w
    area_ratio = (w * h) / (cell_gray.shape[0] * cell_gray.shape[1])
    matches = aspect > 2.0 and 0.03 < area_ratio < 0.6

    if debug:
        print(f"      [I-shape check] cell size={cell_gray.shape}, blob w={w} h={h}, "
              f"aspect={aspect:.2f} (need >2.0), area_ratio={area_ratio:.3f} "
              f"(need 0.05-0.6) -> {'MATCH' if matches else 'no match'}")

    return matches


def ocr_row_by_columns(gray_img: np.ndarray, top: int, bottom: int, left: int, right: int,
                        columns: int, reader: easyocr.Reader, debug: bool = False,
                        save_debug_dir: str | None = None, row_index: int = 0) -> list[str]:
    """Alternative second pass: split a row into `columns` EQUAL-WIDTH slices
    by geometry alone, and OCR each slice as one isolated tile.

    This is for evenly-spaced grids (like a clean screenshot) where the
    column count is already known. Reading the whole row as one line can
    fail when a UI element between tiles (e.g. a connector graphic) causes
    the detector to merge two neighboring letters into one region and only
    read one of them out. Dividing by known geometry instead guarantees
    each slice contains exactly one tile, regardless of what sits between
    tiles visually.

    (left, right) is the row's OWN detected horizontal extent, not
    necessarily the full image width -- a photographed board often has
    background/margin on either side of the grid, so dividing the full
    image width would slice background into the edge columns instead of
    the outermost letters.
    """
    strip = gray_img[int(top):int(bottom), int(left):int(right)]
    if strip.size == 0:
        return ["?"] * columns

    width = strip.shape[1]
    col_width = width / columns
    margin = int(col_width * 0.12)  # trim inward to avoid tile borders/connectors

    letters = []
    for c in range(columns):
        left = max(0, int(c * col_width) + margin)
        right = min(width, int((c + 1) * col_width) - margin)
        original_cell = strip[:, left:right]
        if original_cell.size == 0:
            letters.append("?")
            continue

        cell = cv2.resize(original_cell, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        cell = cv2.copyMakeBorder(cell, 20, 20, 20, 20, cv2.BORDER_CONSTANT,
                                   value=int(np.median(cell)))

        if save_debug_dir:
            path = os.path.join(save_debug_dir, f"row_{row_index}_col_{c}.png")
            cv2.imwrite(path, cell)

        results = reader.readtext(cell, allowlist=ALLOWED_CHARS, detail=1, paragraph=False)

        if not results:
            if looks_like_letter_i(original_cell, debug=debug):
                letters.append("I")
                if debug:
                    print(f"    col {c}: no OCR detection, but shape matches 'I' -> using 'I'")
            else:
                letters.append("?")
                if debug:
                    print(f"    col {c}: no OCR detection and shape doesn't match 'I' -> '?'")
            continue

        best = max(results, key=lambda r: r[2])
        text = best[1].strip().upper()
        letters.append(text if text.isalpha() else "?")

        if debug:
            print(f"    col {c}: {[(r[1], round(r[2], 2)) for r in results]}")

    return letters


def extract_board_by_rows(image_path: str, debug: bool = False, save_crops: bool = False,
                           expected_rows: int | None = None, columns: int | None = None) -> list[list[str]]:
    """Detect a Boggle board by reading each row as one line of text.

    expected_rows:
        If given and MORE row bands are found than this, the extra bands
        are dropped -- specifically whichever ones fall outside the most
        evenly-spaced run of `expected_rows` consecutive bands, on the
        assumption that the real grid rows are the ones with consistent
        spacing between them (see select_most_evenly_spaced_run). If the
        number of bands already matches expected_rows, nothing is dropped:
        a row with an unusual tile count in that case is far more likely to
        be a real row that was misread (e.g. a thin letter like "I" going
        undetected) than an extra row, and dropping it would destroy real
        data rather than fix anything.
    columns:
        If given, each row is read by dividing it into this many EQUAL-WIDTH
        slices and OCR-ing each in isolation (see ocr_row_by_columns),
        instead of reading the whole row as one line of text. Use this for
        evenly-spaced grids (clean screenshots) where whole-row reading
        merges a letter into its neighbor. Leave unset for photographed or
        hand-drawn boards, where tile spacing isn't perfectly uniform.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not read image at: {image_path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    row_bands = find_row_bands(image_path, debug=debug)
    reader = _get_reader()

    if save_crops:
        os.makedirs("debug_row_crops", exist_ok=True)
        for i, (top, bottom, left, right) in enumerate(row_bands):
            crop_path = os.path.join("debug_row_crops", f"row_{i}_y{top}-{bottom}.png")
            cv2.imwrite(crop_path, gray[int(top):int(bottom), int(left):int(right)])
        print(f"Saved {len(row_bands)} row crops to debug_row_crops/ -- open them to see "
              f"exactly what each detected band contains.")

    if expected_rows is not None and len(row_bands) > expected_rows:
        keep_indices = select_most_evenly_spaced_run(row_bands, expected_rows)
        if debug:
            dropped_indices = [i for i in range(len(row_bands)) if i not in keep_indices]
            print(f"Found {len(row_bands)} bands but expected {expected_rows} rows -- "
                  f"keeping the most evenly-spaced run at indices {keep_indices}, "
                  f"dropping indices {dropped_indices}")
        row_bands = [row_bands[i] for i in keep_indices]
    elif expected_rows is not None and len(row_bands) < expected_rows:
        if debug:
            print(f"Warning: only found {len(row_bands)} row bands but expected {expected_rows}. "
                  f"At least one row may not have been detected at all.")

    # All rows of a real grid share essentially the same left/right edge,
    # since tiles line up in columns. A single row's own first-pass
    # detection can sometimes undershoot (miss a letter at one end), which
    # would otherwise shift that row's column boundaries away from the
    # real tile positions. Using the WIDEST span found across all kept
    # rows, applied uniformly to every row, means one row's partial miss
    # doesn't corrupt its own column alignment as long as some other row
    # was detected across the full width.
    if columns is not None and row_bands:
        shared_left = min(b[2] for b in row_bands)
        shared_right = max(b[3] for b in row_bands)
        if debug:
            print(f"Using shared horizontal extent ({shared_left},{shared_right}) for all "
                  f"rows' column splitting, instead of each row's own detected extent")
        row_bands = [(top, bottom, shared_left, shared_right) for top, bottom, _, _ in row_bands]

    board = []
    for i, (top, bottom, left, right) in enumerate(row_bands):
        if columns is not None:
            tiles = ocr_row_by_columns(
                gray, top, bottom, left, right, columns, reader, debug=debug,
                save_debug_dir="debug_row_crops" if save_crops else None, row_index=i,
            )
            if debug:
                print(f"  row band y=({top},{bottom}) x=({left},{right}) -> columns: {tiles}")
        else:
            debug_strip_path = None
            if save_crops:
                debug_strip_path = os.path.join("debug_row_crops", f"row_{i}_ocr_input.png")
            raw_text = ocr_row_band(gray, top, bottom, left, right, reader, debug=debug,
                                     save_debug_strip=debug_strip_path)
            tiles = infer_row_tiles(raw_text)
        board.append(tiles)

    columns_per_row = [len(row) for row in board]
    if debug:
        print(f"Tiles per row: {columns_per_row}")

    row_lengths = [len(row) for row in board]
    if len(set(row_lengths)) != 1:
        raise ValueError(
            f"Rows are inconsistent: {row_lengths}. Rows read as: {board}\n"
            f"This is more likely a real row missing a letter (e.g. a thin "
            f"character like 'I' going undetected) than an extra row -- "
            f"check debug_row_crops/ (--save-crops) for the mismatched row."
        )

    return board


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit("Usage: python ocr_vision.py <path_to_image> [--debug] [--save-crops] "
                  "[--rows=N] [--columns=N]")

    path = args[0]
    debug_flag = "--debug" in args
    save_crops_flag = "--save-crops" in args
    expected_rows = None
    columns = None
    for arg in args:
        if arg.startswith("--rows="):
            expected_rows = int(arg.split("=", 1)[1])
        if arg.startswith("--columns="):
            columns = int(arg.split("=", 1)[1])

    if not os.path.exists(path):
        sys.exit(f"File not found: {path}")

    result = extract_board_by_rows(
        path, debug=debug_flag, save_crops=save_crops_flag,
        expected_rows=expected_rows, columns=columns,
    )
    print(result)