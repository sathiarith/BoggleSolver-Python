"""A Boggle-style word finder built on a Trie of valid dictionary words."""

from trie import Trie

class Solver:
    """Finds all dictionary words that can be traced on a letter grid.

    Words are formed by chaining adjacent tiles (horizontally, vertically,
    or diagonally). Each tile may be used at most once per word. Matching is
    case-insensitive, and results are returned in lowercase.

    Example:
      board = [["c", "a"],
               ["t", "s"]]
      Solver(board).find_words()
      ['act', 'cat', 'cats', 'scat']
    """

    def __init__(self, board: list[list[str]], trie: Trie) -> None:
        """Initialize the solver.

        Args:
            board: A rectangular grid of tiles. Each tile is a string,
                usually a single letter, but multi-letter tiles such as
                "qu" also work. Must be non-empty.

        """
        self.board = board
        self.row = len(board)
        self.col = len(board[0])
        self.used_tiles = [[False for _ in range(self.col)] for _ in range(self.row)]

        # Word list generation component
        self.trie = trie

    def find_words(self) -> list[str]:
        """Find every valid word on the board.

        Starts a depth-first search from each tile. Duplicates are removed
        and words shorter than 3 letters are dropped.

        Returns:
            An alphabetically sorted list of unique lowercase words, each
            at least 3 letters long.
        """
        valid_words = []
        for r in range(self.row):
            for c in range(self.col):
                valid_words += self.dfs("", r, c)

        # Clean the list: Convert to set for uniqueness, and drop anything under 3 letters!
        filtered_words = [word for word in set(valid_words) if len(word) >= 3]
        return sorted(filtered_words)

    def dfs(self, prefix: str, r: int, c: int) -> list[str]:
        """Recursively search for words, extending `prefix` with tile (r, c).

        Marks the current tile as used while exploring its 8 neighbors, then
        unmarks it (backtracking) so other paths can reuse it.

        Args:
            prefix: Letters collected so far, before this tile.
            r: Row index of the tile to visit.
            c: Column index of the tile to visit.

        Returns:
            All dictionary words found along paths that pass through this
            tile. May contain duplicates and words under 3 letters; callers
            should clean the result (see `find_words`). Returns an empty
            list if the tile is out of bounds, already used, or the
            search path can't lead to a word.
        """
        if self.is_out_of_bounds(r, c) or self.is_used(r, c):
            return []

        token = prefix + self.board[r][c].lower()

        if not self.trie.check_if_prefix(token):
            return []

        self.used_tiles[r][c] = True
        valid_word = []

        if self.trie.check_if_word(token):
            valid_word.append(token)

        # Possible directions
        n_words = self.dfs(token, r-1, c)
        ne_words = self.dfs(token, r-1, c+1)
        nw_words = self.dfs(token, r-1, c-1)
        e_words = self.dfs(token, r, c+1)
        w_words = self.dfs(token, r, c-1)
        s_words = self.dfs(token, r+1, c)
        se_words = self.dfs(token, r+1, c+1)
        sw_words = self.dfs(token, r+1, c-1)

        self.used_tiles[r][c] = False

        return (valid_word + n_words + ne_words + nw_words + e_words
                + w_words + s_words + se_words + sw_words)

    # Helper functions
    def is_out_of_bounds(self, row: int, col: int) -> bool:
        """Return True if (row, col) lies outside the board."""
        return not (0 <= row < self.row and 0 <= col < self.col)

    def is_used(self, row: int, col: int) -> bool:
        """Return True if the tile at (row, col) is on the current path.

        The caller must ensure the position is in bounds first.
        """
        return self.used_tiles[row][col]

