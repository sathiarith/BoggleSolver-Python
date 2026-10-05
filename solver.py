from board import Board
from trie import Trie

class Solver:
    def __init__(self, board: list[list[str]], trie: Trie) -> None:
        self.board = board
        self.trie = trie
        #self.visited = board.get_row() board.get_col
    # def DFS(trie: Trie):
        # word storage in set.
