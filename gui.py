"""
Boggle Solver GUI
Built with CustomTkinter, matching the provided wireframe layout.

Layout:
    - Top-left:    "Entry Method" panel with Manual / Image buttons
    - Bottom-left: "Submit" and "Clear Board" button
    - Center:      "Boggle Solver" title + letter grid (4x4 / 5x5 / 6x6)
    - Right:       "Valid Words" scrollable results panel

Notes:
    - Manual mode shows an empty board of single-letter entry boxes.
      The first tile is autofocused with a blinking cursor, just like
      a normal text entry.
    - Image mode is a stub for now (prompts for an image file, but the
      OCR/parsing logic is not implemented yet).
    - The "Valid words" list is populated with a trie data structure using
      the Solver class for backend processing.
"""

import customtkinter as ctk
from tkinter import filedialog
from trie import Trie
from solver import Solver

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# ---- Colors to roughly match the wireframe -------------------------------
COLOR_SELECTED = "#808080"   # gray fill for the selected/active button
COLOR_SELECTED_TEXT = "white"
COLOR_UNSELECTED = "white"
COLOR_UNSELECTED_TEXT = "black"
COLOR_BORDER = "black"
COLOR_HEADER = "orange"
COLOR_HEADER_FONT = "white"

class BoggleSolverApp(ctk.CTk):
    """Main window of the Boggle Solver application.

    Builds the three-column layout (entry method, board, results) and wires
    the buttons to the board-entry and solving logic. Words are found by
    handing the board to `solver.Solver`.

    Attributes:
        board_size: Current board dimension (4, 5, or 6).
        prev_board_size: Board dimension before the last rebuild. Used to
            reset grid weights on `board_frame`.
        entry_mode: Either "Manual" or "Image".
        tile_entries: 2D list of `CTkEntry` widgets indexed `[row][col]`.
            Empty while the image placeholder is shown.
        manual_btn: Button that selects manual entry.
        image_btn: Button that selects image entry.
        submit_btn: Button that validates the board and runs the solver.
        clear_btn: Button that empties all tiles.
        size_buttons: Maps a board size to its selector button.
        board_frame: Frame holding the tile grid; rebuilt on demand.
        words_frame: Scrollable frame listing the valid words.
    """
    def __init__(self):
        """Create the window, build the layout, and show a 4x4 manual board."""
        super().__init__()

        self.title("Boggle Solver")
        self.geometry("1024x576")
        self.minsize(825, 425)
        self.configure(fg_color="lightblue")

        # State
        self.board_size = 4
        self.prev_board_size = 0
        self.entry_mode = "Manual"
        self.tile_entries = []  # list of CTkEntry, [row][col]

        self._build_layout()
        self._show_manual_board(self.board_size)  # default: 4x4 manual board

        # load dictionary word list once
        self.trie = Trie()
        self.trie.store_dic_words(path="CSW24_words.json")

    # ------------------------------------------------------------------
    # Layout construction
    # ------------------------------------------------------------------
    def _build_layout(self):
        """Configure the 3-column outer grid and build each panel."""
        # 3-column, 2-row outer grid: left | center | right
        self.grid_columnconfigure(0, weight=0, minsize=250)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0, minsize=280)
        self.grid_rowconfigure(1, weight=1)

        self._build_entry_method_panel()
        self._build_submit_board_button()
        self._build_clear_board_button()
        self._build_center_panel()
        self._build_valid_words_panel()

    # -- Left column: Entry Method -------------------------------------
    def _build_entry_method_panel(self):
        """Build the "Entry Method" header and the Manual/Image buttons."""
        header = ctk.CTkLabel(
            self, text="Entry Method", font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=COLOR_HEADER, text_color=COLOR_HEADER_FONT,
            corner_radius=50, height=40,
        )
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))

        box = ctk.CTkFrame(self, border_width=2, border_color=COLOR_BORDER, fg_color="white")
        box.grid(row=1, column=0, sticky="new", padx=10, pady=5)
        box.grid_columnconfigure(0, weight=1)

        self.manual_btn = ctk.CTkButton(
            box, text="Manual", font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLOR_SELECTED, text_color=COLOR_SELECTED_TEXT,
            hover_color="#6e6e6e", border_width=2, border_color=COLOR_BORDER,
            corner_radius=4, command=self._on_manual_clicked,
        )
        self.manual_btn.grid(row=0, column=0, sticky="ew", padx=15, pady=(20, 10))

        self.image_btn = ctk.CTkButton(
            box, text="Image", font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLOR_UNSELECTED, text_color=COLOR_UNSELECTED_TEXT,
            hover_color="#e0e0e0", border_width=2, border_color=COLOR_BORDER,
            corner_radius=4, command=self._on_image_clicked,
        )
        self.image_btn.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 20))

    def _build_submit_board_button(self):
        """Build the "Submit" button in the bottom-left area."""
        self.submit_btn = ctk.CTkButton(
            self, text="Submit", font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLOR_UNSELECTED, text_color=COLOR_UNSELECTED_TEXT,
            hover_color="#e0e0e0", border_width=2, border_color=COLOR_BORDER,
            corner_radius=4, height=45, command=self._on_submit_board,
        )
        self.submit_btn.grid(row=1, column=0, sticky="sew", padx=10, pady=(20, 0))

    def _build_clear_board_button(self):
        """Build the "Clear Board" button below the Submit button."""
        self.clear_btn = ctk.CTkButton(
            self, text="Clear Board", font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLOR_UNSELECTED, text_color=COLOR_UNSELECTED_TEXT,
            hover_color="#e0e0e0", border_width=2, border_color=COLOR_BORDER,
            corner_radius=4, height=45, command=self._on_clear_board,
        )
        self.clear_btn.grid(row=2, column=0, sticky="sew", padx=10, pady=(20, 10))

    # -- Center column: title, board, size selector ----------------------
    def _build_center_panel(self):
        """Build the title, the board frame, and the 4x4/5x5/6x6 selector."""
        title = ctk.CTkLabel(
            self, text="Boggle Solver", font=ctk.CTkFont(size=30, weight="bold"),
            fg_color=COLOR_HEADER, text_color=COLOR_HEADER_FONT, corner_radius=50, height=60,
        )
        title.grid(row=0, column=1, sticky="new", padx=10, pady=(10, 5))

        # Frame that holds the letter grid; contents are rebuilt on demand
        self.board_frame = ctk.CTkFrame(
            self, border_width=2, border_color=COLOR_BORDER, fg_color="gray88"
        )
        self.board_frame.grid(row=1, column=1, sticky="nsew", padx=10, pady=5)

        # Size selector row (4x4 / 5x5 / 6x6)
        size_row = ctk.CTkFrame(self, fg_color="transparent")
        size_row.grid(row=2, column=1, sticky="sew", padx=10, pady=(20, 10))
        size_row.grid_columnconfigure((0, 1, 2), weight=1)

        self.size_buttons = {}
        for i, size in enumerate((4, 5, 6)):
            btn = ctk.CTkButton(
                size_row, text=f"{size}x{size}", font=ctk.CTkFont(size=14, weight="bold"),
                fg_color=COLOR_UNSELECTED, text_color=COLOR_UNSELECTED_TEXT,
                hover_color="#e0e0e0", border_width=2, border_color=COLOR_BORDER,
                corner_radius=4, height=45,
                command=lambda s=size: self._on_size_selected(s),
            )
            btn.grid(row=0, column=i, sticky="ew", padx=5)
            self.size_buttons[size] = btn

        self._highlight_size_button(self.board_size)

    # -- Right column: Valid words ---------------------------------------
    def _build_valid_words_panel(self):
        """Build the "Valid Words" header and its scrollable results frame."""
        header = ctk.CTkLabel(
            self, text="Valid Words", font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=COLOR_HEADER, text_color=COLOR_HEADER_FONT, corner_radius=50, height=40,
        )
        header.grid(row=0, column=2, sticky="ew", padx=10, pady=(10, 5))

        self.words_frame = ctk.CTkScrollableFrame(
            self, border_width=2, border_color=COLOR_BORDER, fg_color="white"
        )
        self.words_frame.grid(row=1, column=2, rowspan=2, sticky="nsew", padx=10, pady=5)
        self.words_frame.grid_columnconfigure(0, weight=1)

    def set_valid_words(self, words):
        """Replace the contents of the Valid Words panel.

        Args:
            words: Iterable of strings to display, one label per word,
                in the order given.
        """
        for widget in self.words_frame.winfo_children():
            widget.destroy()
        for i, word in enumerate(words):
            label = ctk.CTkLabel(
                self.words_frame, text=word, font=ctk.CTkFont(size=14),
                text_color="black", anchor="w",
            )
            label.grid(row=i, column=0, sticky="w", padx=8, pady=2)

    # ------------------------------------------------------------------
    # Entry Method behavior
    # ------------------------------------------------------------------
    def _on_manual_clicked(self):
        """Switch to manual entry and rebuild an empty board."""
        self.entry_mode = "Manual"
        self._set_button_selected(self.manual_btn, True)
        self._set_button_selected(self.image_btn, False)
        self._show_manual_board(self.board_size)

    def _on_image_clicked(self):
        """Switch to image entry and prompt for an image file.

        Stub: the chosen path is only printed. OCR/parsing is not
        implemented, so a placeholder message replaces the board.
        """
        self.entry_mode = "Image"
        self._set_button_selected(self.image_btn, True)
        self._set_button_selected(self.manual_btn, False)

        # Stub: prompt for an image file. OCR/parsing not implemented yet.
        file_path = filedialog.askopenfilename(
            title="Select a Boggle board image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")],
        )
        if file_path:
            print(f"[Image mode] Selected file (not yet processed): {file_path}")
        self._show_image_placeholder()

    @staticmethod
    def _set_button_selected(button, selected):
        """Style a button as selected (gray) or unselected (white).

        Args:
            button: The `CTkButton` to restyle.
            selected: True for the selected look, False otherwise.
        """
        if selected:
            button.configure(fg_color=COLOR_SELECTED, text_color=COLOR_SELECTED_TEXT)
        else:
            button.configure(fg_color=COLOR_UNSELECTED, text_color=COLOR_UNSELECTED_TEXT)

    # ------------------------------------------------------------------
    # Board building
    # ------------------------------------------------------------------
    def _clear_board_frame(self):
        """Destroy everything in the board frame and forget the tile entries."""
        for widget in self.board_frame.winfo_children():
            widget.destroy()
        self.tile_entries = []

    def _show_manual_board(self, size):
        """Rebuild the board as an empty `size` x `size` grid of entry boxes.

        Resets grid weights left over from the previous board, scales the
        font down for larger boards, and focuses the first tile.

        Args:
            size: Number of rows and columns.
        """
        self._clear_board_frame()

        # reset previous resize configuration weights
        for r in range(self.prev_board_size):
            self.board_frame.grid_rowconfigure(r, weight=0, uniform="")
        for c in range(self.prev_board_size):
            self.board_frame.grid_columnconfigure(c, weight=0, uniform="")

        # Update previous size
        self.prev_board_size = size

        for r in range(size):
            self.board_frame.grid_rowconfigure(r, weight=1, uniform="row")
        for c in range(size):
            self.board_frame.grid_columnconfigure(c, weight=1, uniform="col")

        font_size = max(14, int(48 - (size - 4) * 8))
        # Register once; "%P" passes the text the entry would contain after the edit
        vcmd = (self.register(self._is_valid_tile_text), "%P")

        entries_grid = []
        for r in range(size):
            row_entries = []
            for c in range(size):
                var = ctk.StringVar()
                entry = ctk.CTkEntry(
                    self.board_frame,
                    textvariable=var,
                    justify="center",
                    font=ctk.CTkFont(size=font_size, weight="bold"),
                    border_width=2,
                    border_color=COLOR_BORDER,
                    corner_radius=8,
                    fg_color="white",
                    text_color="black",
                    validate="key",
                    validatecommand=vcmd,
                )
                entry.grid(row=r, column=c, sticky="nsew", padx=4, pady=4)

                # Restrict to a single letter, auto-uppercase, auto-advance
                entry.bind("<KeyRelease>", lambda e, rr=r, cc=c: self._on_tile_typed(e, rr, cc))
                row_entries.append(entry)
            entries_grid.append(row_entries)

        self.tile_entries = entries_grid

        # Focus the first tile so its cursor blinks, like the sketch shows
        self.after(50, lambda: self.tile_entries[0][0].focus_set())

    def _show_image_placeholder(self):
        """Replace the board with a "still in development" message."""
        self._clear_board_frame()
        self.board_frame.grid_rowconfigure(0, weight=1)
        self.board_frame.grid_columnconfigure(0, weight=1)

        label = ctk.CTkLabel(
            self.board_frame,
            text="Image entry is still in development.\nSelect an image file, then check back soon!",
            font=ctk.CTkFont(size=18),
            text_color="gray30",
            justify="center",
        )
        label.grid(row=0, column=0, sticky="nsew")

    @staticmethod
    def _is_valid_tile_text(proposed: str) -> bool:
        """Tk validation callback for a tile's contents.

        Args:
            proposed: The text the entry would contain if the edit is allowed.

        Returns:
            True for an empty tile, a single ASCII letter, or "QU".
            False for anything else (digits, symbols, spaces, non-ASCII
            letters, or longer strings).
        """
        if proposed == "":
            return True
        if proposed.isascii() and proposed.isalpha():
            return len(proposed) == 1 or proposed.upper() == "QU"
        return False

    def _on_tile_typed(self, event, r, c):
        """Handle a key release in a tile.

        Backspace/Delete clears the tile. A letter key replaces the tile's
        contents with the uppercase letter ("Q" becomes "QU") and moves
        focus to the next tile, left to right, then top to bottom. All
        other keys (arrows, Tab, Shift, ...) are ignored.

        Args:
            event: The Tk key event.
            r: Row index of the tile that received the key.
            c: Column index of the tile that received the key.
        """
        entry = self.tile_entries[r][c]

        if event.keysym in ("BackSpace", "Delete"):
            entry.delete(0, "end")
            return

        # Only accepts a letter per tile
        if not (event.char.isascii() and event.char.isalpha()):
            return

        letter = event.char.upper()

        entry.delete(0, "end")
        if letter == "Q":
            entry.insert(0, "QU")
        else:
            entry.insert(0, letter)
        entry.icursor("end")

        size = self.board_size
        next_r, next_c = r, c + 1
        if next_c >= size:
            next_c = 0
            next_r += 1
        if next_r < size:
            self.tile_entries[next_r][next_c].focus_set()

    # ------------------------------------------------------------------
    # Submit Board / Clear Board / Size selection
    # ------------------------------------------------------------------
    def _on_submit_board(self):
        """Validate the board, flag blank tiles, and show the valid words.

        Blank tiles get a red border (all others reset to the normal
        border color) and the first blank tile is focused. If no tiles are
        blank, a `Solver` is created and its results are shown in the
        Valid Words panel.
        """
        # Clear previous word list
        self.set_valid_words([])

        board = self.get_board_letters()
        valid_check, blanks_coords = self._get_board_validity_state(board)
        # Using set for look-up purposes
        blanks_set = set(blanks_coords)

        # Updates all blank tiles to have red border and the rest defined by COLOR_BORDER
        for r, row in enumerate(self.tile_entries):
            for c, entry in enumerate(row):
                entry.configure(border_color="red" if (r, c) in blanks_set else COLOR_BORDER)

        # Focus the first blank tile so the user can fix it immediately
        if blanks_coords:
            first_row, first_col = blanks_coords[0]
            self.tile_entries[first_row][first_col].focus_set()

        # call solver.py and provide valid board info
        if valid_check:
            solver = Solver(board, self.trie)
            valid_words = solver.find_words()
            self.set_valid_words(valid_words)

    def reset_missing_tiles(self):
        """Return all tile borders to COLOR_BORDER"""
        for r, row in enumerate(self.tile_entries):
            for c, entry in enumerate(row):
                entry.configure(border_color=COLOR_BORDER)

    def _on_clear_board(self):
        """Empty every tile and return focus to the first one."""
        for row in self.tile_entries:
            for entry in row:
                entry.delete(0, "end")
        if self.tile_entries:
            self.tile_entries[0][0].focus_set()

        self.reset_missing_tiles()
        self.set_valid_words([])

    def _on_size_selected(self, size):
        """Change the board size and reset the board.

        Args:
            size: The new board dimension (4, 5, or 6). Any letters
                already entered are discarded.
        """
        self.board_size = size
        self._highlight_size_button(size)
        # Letters reset whenever the board size changes
        if self.entry_mode == "Manual":
            self._show_manual_board(size)
        else:
            self._show_image_placeholder()

    def _highlight_size_button(self, selected_size):
        """Mark one size button as selected and the others as unselected.

        Args:
            selected_size: The size whose button should be highlighted.
        """
        for size, btn in self.size_buttons.items():
            self._set_button_selected(btn, size == selected_size)

    # ------------------------------------------------------------------
    # Backend Processing
    # ------------------------------------------------------------------
    def get_board_letters(self):
        """Return the current board as a 2D list of letters.

        Returns:
            A list of rows, each a list of the tile strings. Blank tiles
            are empty strings, and a "Q" tile reads as "QU". The list is
            empty if no tiles exist (e.g. in Image mode).
        """
        return [[entry.get() for entry in row] for row in self.tile_entries]

    @staticmethod
    def _get_board_validity_state(board: list[list[str]]) -> tuple[bool, list[tuple[int,int]]]:
        """Check a board for blank tiles.

        Args:
            board: 2D list of tile strings, as from `get_board_letters`.

        Returns:
            A tuple `(is_valid, blank_coords)`. `is_valid` is True when no
            tile is blank. `blank_coords` lists the `(row, col)` of each
            blank tile in row-major order.
        """
        # Check for all blank entry(s) and store their coordinate(s)
        invalid_coordinates = []
        for i, row in enumerate(board):
            for j, tile in enumerate(row):
                if tile == "":
                    invalid_coordinates.append((i, j))

        is_valid = not invalid_coordinates
        return is_valid, invalid_coordinates
