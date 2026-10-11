"""
Tests for solver.py.  Run from the project root with:   pytest -v

Every expected answer below was worked out by hand (or comes from an independent
brute-force reference solver), not copied from whatever Solver happened to return.
Tests use tiny hand-made dictionaries so the results are easy to verify.
"""

import itertools
import random

import pytest

from solver import Solver
from trie import Trie


def make_trie(words):
    trie = Trie()
    for word in words:
        trie.insert(word)
    return trie


def solve(board, words):
    """Shortcut: build a Trie from `words` and return Solver(board).find_words()."""
    return Solver(board, make_trie(words)).find_words()


# Every (row change, column change) a move can make, with a readable name
DIRECTIONS = [
    ("N", -1, 0), ("NE", -1, 1), ("E", 0, 1), ("SE", 1, 1),
    ("S", 1, 0), ("SW", 1, -1), ("W", 0, -1), ("NW", -1, -1),
]


# ----------------------------------------------------------------------
# Construction
# ----------------------------------------------------------------------
class TestConstruction:
    def test_dimensions_come_from_the_board(self):
        solver = Solver([["a", "b", "c"], ["d", "e", "f"]], Trie())
        assert (solver.row, solver.col) == (2, 3)

    def test_no_tile_starts_out_used(self):
        solver = Solver([["a", "b", "c"], ["d", "e", "f"]], Trie())
        assert solver.used_tiles == [[False] * 3, [False] * 3]

    def test_empty_board_is_rejected(self):
        # The docstring says the board "must be non-empty"; today that shows up as an
        # IndexError from board[0]. Either error type is acceptable here.
        with pytest.raises((IndexError, ValueError)):
            Solver([], Trie())


# ----------------------------------------------------------------------
# Adjacency rules
# ----------------------------------------------------------------------
class TestAdjacency:
    @pytest.mark.parametrize("name, dr, dc", DIRECTIONS, ids=[d[0] for d in DIRECTIONS])
    def test_a_word_can_be_traced_in_every_direction(self, name, dr, dc):
        # c, a, t laid out in a straight line through the center, heading (dr, dc)
        board = [["z"] * 3 for _ in range(3)]
        board[1 - dr][1 - dc] = "c"
        board[1][1] = "a"
        board[1 + dr][1 + dc] = "t"
        assert solve(board, ["cat"]) == ["cat"]

    def test_letters_with_a_gap_between_them_are_not_adjacent(self):
        assert solve([["c", "z", "a", "z", "t"]], ["cat"]) == []

    def test_adjacency_does_not_wrap_around_the_edges(self):
        # c at the right edge of row 0, a at the left edge of row 1, t beside it.
        # They look adjacent if columns wrap, but they are really 2 columns apart.
        board = [["z", "z", "c"],
                 ["a", "t", "z"]]
        assert solve(board, ["cat"]) == []

    def test_a_word_can_run_backwards_along_a_row(self):
        assert solve([["t", "a", "c"]], ["cat"]) == ["cat"]

    def test_single_row_and_single_column_boards(self):
        assert solve([["c", "a", "t"]], ["cat"]) == ["cat"]
        assert solve([["c"], ["a"], ["t"]], ["cat"]) == ["cat"]

    def test_non_square_board(self):
        board = [["c", "a", "t"],
                 ["z", "z", "z"]]
        assert solve(board, ["cat"]) == ["cat"]

    def test_single_tile_board_has_no_words(self):
        assert solve([["a"]], ["a", "aa", "aaa"]) == []


# ----------------------------------------------------------------------
# Each tile at most once per word
# ----------------------------------------------------------------------
class TestTileReuse:
    def test_a_tile_cannot_be_used_twice_in_one_word(self):
        # "tat" would need the only t twice
        assert solve([["t", "a"]], ["tat"]) == []

    def test_the_same_word_works_with_two_separate_tiles(self):
        assert solve([["t", "a", "t"]], ["tat"]) == ["tat"]

    def test_longest_possible_word_is_limited_by_tile_count(self):
        # A 2x2 board has 4 tiles, so "aaaaa" is impossible but "aaa" and "aaaa" are
        board = [["a", "a"], ["a", "a"]]
        assert solve(board, ["aaa", "aaaa", "aaaaa"]) == ["aaa", "aaaa"]

    def test_tiles_are_released_after_each_path(self):
        # If a tile stayed marked after a failed path, "cab" could be missed because
        # an earlier attempt at "cat" through the same letters left them locked.
        board = [["c", "a"], ["t", "b"]]
        assert solve(board, ["cat", "cab"]) == ["cab", "cat"]


# ----------------------------------------------------------------------
# What gets returned
# ----------------------------------------------------------------------
class TestResults:
    def test_words_shorter_than_three_letters_are_dropped(self):
        assert solve([["a", "t"]], ["at"]) == []
        assert solve([["c", "a", "t"]], ["at", "ca", "cat"]) == ["cat"]

    def test_three_letter_words_are_kept(self):
        assert solve([["c", "a", "t"]], ["cat"]) == ["cat"]

    def test_a_word_with_several_paths_appears_once(self):
        # Two different a's lead from c to t: c-a(top)-t and c-a(left)-t
        board = [["c", "a"],
                 ["a", "t"]]
        assert solve(board, ["cat"]) == ["cat"]

    def test_results_are_sorted_alphabetically(self):
        # All four tiles of a 2x2 board touch each other, so any ordering is a path.
        board = [["c", "a"],
                 ["t", "s"]]
        assert solve(board, ["scat", "cat", "cats", "act", "dog"]) == [
            "act", "cat", "cats", "scat"]

    def test_finding_a_word_does_not_stop_the_search_for_longer_ones(self):
        board = [["c", "a", "r", "d", "s"]]
        assert solve(board, ["car", "card", "cards"]) == ["car", "card", "cards"]

    def test_words_that_are_not_on_the_board_are_not_returned(self):
        assert solve([["c", "a", "t"]], ["dog", "cow", "cab"]) == []

    def test_empty_dictionary_gives_no_words(self):
        assert solve([["c", "a", "t"]], []) == []

    def test_matching_ignores_case_and_results_are_lowercase(self):
        assert solve([["C", "A", "T"]], ["cat"]) == ["cat"]
        assert solve([["c", "a", "t"]], ["CAT"]) == ["cat"]


# ----------------------------------------------------------------------
# "Qu" tiles
# ----------------------------------------------------------------------
class TestQuTiles:
    def test_qu_tile_spells_both_letters(self):
        board = [["Qu", "i"],
                 ["t", "z"]]
        assert solve(board, ["quit"]) == ["quit"]

    def test_qu_in_the_middle_of_a_word(self):
        assert solve([["e", "Qu", "a", "l"]], ["equal"]) == ["equal"]

    def test_qu_counts_as_two_letters_for_the_minimum_length(self):
        # "qua" is only two tiles but three letters, so it is long enough
        assert solve([["Qu", "a"]], ["qua"]) == ["qua"]

    def test_separate_q_and_u_tiles_also_spell_qu(self):
        assert solve([["q", "u", "i", "t"]], ["quit"]) == ["quit"]


# ----------------------------------------------------------------------
# State handling
# ----------------------------------------------------------------------
class TestState:
    def test_no_tile_is_left_marked_after_solving(self):
        solver = Solver([["c", "a"], ["t", "s"]], make_trie(["cat", "cats"]))
        solver.find_words()
        assert solver.used_tiles == [[False, False], [False, False]]

    def test_solving_twice_gives_the_same_answer(self):
        solver = Solver([["c", "a"], ["t", "s"]], make_trie(["cat", "cats", "act"]))
        assert solver.find_words() == solver.find_words()

    def test_the_board_is_not_modified(self):
        board = [["C", "a"], ["t", "S"]]
        solve(board, ["cat"])
        assert board == [["C", "a"], ["t", "S"]]


# ----------------------------------------------------------------------
# dfs() on its own
# ----------------------------------------------------------------------
class TestDfs:
    def test_dfs_does_not_filter_short_words(self):
        # Cleaning up (length, duplicates, sorting) is find_words' job, not dfs'
        solver = Solver([["a", "t"]], make_trie(["at"]))
        assert solver.dfs("", 0, 0) == ["at"]

    def test_dfs_may_return_duplicates(self):
        board = [["c", "a"], ["a", "t"]]
        solver = Solver(board, make_trie(["cat"]))
        assert solver.dfs("", 0, 0).count("cat") == 2   # one per path

    def test_dfs_builds_on_the_prefix_it_is_given(self):
        solver = Solver([["t"]], make_trie(["cat"]))
        assert solver.dfs("ca", 0, 0) == ["cat"]

    def test_dfs_with_a_prefix_that_leads_nowhere_finds_nothing(self):
        solver = Solver([["t"]], make_trie(["cat"]))
        assert solver.dfs("zz", 0, 0) == []

    @pytest.mark.parametrize("r, c", [(-1, 0), (0, -1), (1, 0), (0, 2)])
    def test_dfs_outside_the_board_finds_nothing(self, r, c):
        solver = Solver([["c", "a"]], make_trie(["ca"]))
        assert solver.dfs("", r, c) == []

    def test_dfs_on_a_used_tile_finds_nothing(self):
        solver = Solver([["a", "t"]], make_trie(["at"]))
        solver.used_tiles[0][0] = True
        assert solver.dfs("", 0, 0) == []

    def test_dfs_leaves_every_tile_unmarked(self):
        solver = Solver([["c", "a"], ["t", "s"]], make_trie(["cat", "cats"]))
        solver.dfs("", 0, 0)
        assert solver.used_tiles == [[False, False], [False, False]]


# ----------------------------------------------------------------------
# Helper methods
# ----------------------------------------------------------------------
class TestHelpers:
    @pytest.fixture
    def solver(self):
        # 3 rows x 4 columns, so mixing up rows and columns would be caught
        return Solver([["a"] * 4 for _ in range(3)], Trie())

    @pytest.mark.parametrize("r, c", [(0, 0), (2, 3), (0, 3), (2, 0), (1, 2)])
    def test_inside_the_board(self, solver, r, c):
        assert solver.is_out_of_bounds(r, c) is False

    @pytest.mark.parametrize("r, c", [(-1, 0), (0, -1), (3, 0), (0, 4), (3, 4), (-1, -1), (2, 4)])
    def test_outside_the_board(self, solver, r, c):
        assert solver.is_out_of_bounds(r, c) is True

    def test_is_used_reflects_the_marks(self, solver):
        assert solver.is_used(1, 2) is False
        solver.used_tiles[1][2] = True
        assert solver.is_used(1, 2) is True
        assert solver.is_used(2, 1) is False


# ----------------------------------------------------------------------
# Pruning: the search should stop as soon as a path cannot become a word
# ----------------------------------------------------------------------
class SpyTrie(Trie):
    """A Trie that records every string it is asked to look up as a word."""

    def __init__(self):
        super().__init__()
        self.word_checks = []

    def check_if_word(self, string):
        self.word_checks.append(string)
        return super().check_if_word(string)


def test_search_never_tests_a_dead_end_path_as_a_word():
    # Results are correct either way; this checks the search gives up on "x", "xc",
    # and so on immediately instead of exploring one more step first.
    trie = SpyTrie()
    trie.insert("cat")
    solver = Solver([["c", "a", "t"], ["x", "x", "x"]], trie)

    assert solver.find_words() == ["cat"]
    assert trie.word_checks, "expected at least one word check"
    assert all(trie.check_if_prefix(s) for s in trie.word_checks), (
        "word-checked a string that cannot start any word: "
        f"{[s for s in trie.word_checks if not trie.check_if_prefix(s)]}"
    )


# ----------------------------------------------------------------------
# Cross-check against an independent brute-force solver
# ----------------------------------------------------------------------
DICTIONARY = [
    "cat", "cats", "act", "acts", "east", "eats", "seat", "sea", "tea", "teas",
    "sat", "bad", "bed", "bead", "beads", "dab", "cab", "cabs", "tab", "tabs",
    "abed", "case", "cased", "bet", "bets", "best", "beast", "abet", "abets",
    "baste", "bade", "cede", "base", "bases", "dates", "taste", "stead", "sated",
]


def brute_force(board, words):
    """
    Reference solver: walk EVERY self-avoiding path from every tile, no pruning, no
    trie. Slow but obviously correct, which is the point.
    """
    rows, cols = len(board), len(board[0])
    wanted = {w.lower() for w in words}
    found = set()

    def walk(r, c, seen, text):
        text += board[r][c].lower()
        if len(text) >= 3 and text in wanted:
            found.add(text)
        for dr, dc in itertools.product((-1, 0, 1), repeat=2):
            nr, nc = r + dr, c + dc
            if (dr or dc) and 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in seen:
                walk(nr, nc, seen | {(nr, nc)}, text)

    for r in range(rows):
        for c in range(cols):
            walk(r, c, {(r, c)}, "")
    return sorted(found)


@pytest.mark.parametrize("seed", range(10))
@pytest.mark.parametrize("shape", [(2, 2), (2, 3), (3, 3)], ids=["2x2", "2x3", "3x3"])
def test_matches_brute_force_on_random_boards(shape, seed):
    rng = random.Random(seed)
    rows, cols = shape
    board = [[rng.choice("abcdest") for _ in range(cols)] for _ in range(rows)]

    assert solve(board, DICTIONARY) == brute_force(board, DICTIONARY), f"board: {board}"


def test_the_random_boards_actually_contain_words():
    # Guards against the cross-check passing only because every answer is empty
    total = 0
    for seed in range(10):
        rng = random.Random(seed)
        board = [[rng.choice("abcdest") for _ in range(3)] for _ in range(3)]
        total += len(brute_force(board, DICTIONARY))
    assert total >= 10