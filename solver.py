from trie import Trie

class Solver:
    def __init__(self, board: list[list[str]], trie: Trie) -> None:
        self.board = board
        self.row = len(board)
        self.col = len(board[0])
        self.trie = trie
        self.used_tiles = [[False] for _ in range(self.col) for _ in range(self.row)]

    def find_words(self) -> list[str]:
        valid_words = set(self.dfs("", 0, 0))

        return list(valid_words)

    def dfs(self, prefix: str, r: int, c: int) -> list[str]:
        if self.is_used(r, c) or self.is_out_of_bounds(r, c):
            return []

        self.used_tiles[r][c] = True

        valid_word = []

        token = prefix + self.board[r][c]

        if self.trie.check_if_word(token):
            valid_word.append(token)

        # Possible directions
        n_words = self.dfs(token, r, c)
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
        return 0 <= row < self.row and 0 <= col < self.col

    def is_used(self, row: int, col: int) -> bool:
        return self.used_tiles[row][col]
