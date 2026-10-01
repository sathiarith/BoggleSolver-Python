"""
Boggle Solver GUI
Built with CustomTkinter, matching the provided wireframe layout.

Layout:
    - Top-left:    "Entry Method" panel with Manual / Image buttons
    - Bottom-left: "Clear Board" button
    - Center:      "Boggle Solver" title + letter grid (4x4 / 5x5 / 6x6)
    - Right:       "Valid words" scrollable results panel

Notes:
    - Manual mode shows an empty board of single-letter entry boxes.
      The first tile is autofocused with a blinking cursor, just like
      a normal text entry.
    - Image mode is a stub for now (prompts for an image file, but the
      OCR/parsing logic is not implemented yet).
    - The "Valid words" list is currently populated with placeholder
      text (lorem/ipsum/dolor) until the word-solving backend exists.
      See `find_valid_words()` below for where that logic should go.
"""

import customtkinter as ctk
from tkinter import filedialog

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
    def __init__(self):
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

    # ------------------------------------------------------------------
    # Layout construction
    # ------------------------------------------------------------------
    def _build_layout(self):
        # 3-column, 2-row outer grid: left | center | right
        self.grid_columnconfigure(0, weight=0, minsize=250)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0, minsize=280)
        self.grid_rowconfigure(1, weight=1)

        self._build_entry_method_panel()
        self._build_clear_board_button()
        self._build_center_panel()
        self._build_valid_words_panel()

    # -- Left column: Entry Method -------------------------------------
    def _build_entry_method_panel(self):
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

    def _build_clear_board_button(self):
        self.clear_btn = ctk.CTkButton(
            self, text="Clear Board", font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLOR_UNSELECTED, text_color=COLOR_UNSELECTED_TEXT,
            hover_color="#e0e0e0", border_width=2, border_color=COLOR_BORDER,
            corner_radius=4, height=45, command=self._on_clear_board,
        )
        self.clear_btn.grid(row=2, column=0, sticky="sew", padx=10, pady=(20, 10))

    # -- Center column: title, board, size selector ----------------------
    def _build_center_panel(self):
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

        # Placeholder content until the solving backend is wired up
        self.set_valid_words(["lorem", "ipsum", "dolor"])

    def set_valid_words(self, words):
        """Replace the contents of the Valid words panel with `words`."""
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
        self.entry_mode = "Manual"
        self._set_button_selected(self.manual_btn, True)
        self._set_button_selected(self.image_btn, False)
        self._show_manual_board(self.board_size)

    def _on_image_clicked(self):
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

    def _set_button_selected(self, button, selected):
        if selected:
            button.configure(fg_color=COLOR_SELECTED, text_color=COLOR_SELECTED_TEXT)
        else:
            button.configure(fg_color=COLOR_UNSELECTED, text_color=COLOR_UNSELECTED_TEXT)

    # ------------------------------------------------------------------
    # Board building
    # ------------------------------------------------------------------
    def _clear_board_frame(self):
        for widget in self.board_frame.winfo_children():
            widget.destroy()
        self.tile_entries = []

    def _show_manual_board(self, size):
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

    def _on_tile_typed(self, event, r, c):
        entry = self.tile_entries[r][c]

        if event.keysym in ("BackSpace", "Delete"):
            entry.delete(0, "end")
            return

        # Only react to an actual letter key being pressed —
        # ignore arrows, Tab, Home/End, Shift, etc.
        if not event.char.isalpha():
            return

        letter = event.char.upper()

        entry.delete(0, "end")
        if letter == "Q":
            entry.insert(0, "Qu")
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
    # Clear Board / Size selection
    # ------------------------------------------------------------------
    def _on_clear_board(self):
        for row in self.tile_entries:
            for entry in row:
                entry.delete(0, "end")
        if self.tile_entries:
            self.tile_entries[0][0].focus_set()

    def _on_size_selected(self, size):
        self.board_size = size
        self._highlight_size_button(size)
        # Letters reset whenever the board size changes
        if self.entry_mode == "Manual":
            self._show_manual_board(size)
        else:
            self._show_image_placeholder()

    def _highlight_size_button(self, selected_size):
        for size, btn in self.size_buttons.items():
            self._set_button_selected(btn, size == selected_size)

    # ------------------------------------------------------------------
    # Backend hook (placeholder)
    # ------------------------------------------------------------------
    def get_board_letters(self):
        """Return the current board as a 2D list of letters (may contain '')."""
        return [[entry.get() for entry in row] for row in self.tile_entries]

    def find_valid_words(self):
        """
        Placeholder for the Boggle-solving backend.

        A typical approach:
          1. Load a dictionary (e.g. a word list / trie) at startup.
          2. Read the board with `get_board_letters()`.
          3. DFS/backtrack from each tile, following adjacent tiles
             (including diagonals) without reusing a tile, pruning
             paths that aren't a prefix of any dictionary word (a
             trie makes this efficient).
          4. Collect all words found that meet Boggle's minimum length.
          5. Call `self.set_valid_words(sorted(words))` to display them.
        """
        board = self.get_board_letters()
        print("Current board:", board)
        # TODO: implement solving logic, then:
        # self.set_valid_words(found_words)


if __name__ == "__main__":
    app = BoggleSolverApp()
    app.mainloop()