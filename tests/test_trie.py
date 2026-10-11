"""
Tests for trie.py.  Run from the project root with:   pytest -v

If your module is not called trie.py, change the import below.
The expected answers come from the docstrings and from working the examples out
by hand, not from running the code and copying whatever it printed.
"""

import json

import pytest

from trie import Trie

WORDS = ["cat", "car", "card", "care", "dog", "do"]


@pytest.fixture
def trie():
    """A small trie. Note that 'car' and 'do' are words AND prefixes of other words."""
    t = Trie()
    for word in WORDS:
        t.insert(word)
    return t


def count_nodes(node):
    """Count a node plus everything beneath it (used to check structure sharing)."""
    return 1 + sum(count_nodes(child) for child in node.children.values())


# ----------------------------------------------------------------------
# insert + check_if_word
# ----------------------------------------------------------------------
class TestCheckIfWord:
    @pytest.mark.parametrize("word", WORDS)
    def test_inserted_words_are_found(self, trie, word):
        assert trie.check_if_word(word) is True

    @pytest.mark.parametrize("not_a_word", ["cow", "cats", "carde", "dogs", "x", ""])
    def test_unknown_strings_are_not_words(self, trie, not_a_word):
        assert trie.check_if_word(not_a_word) is False

    @pytest.mark.parametrize("prefix_only", ["c", "ca", "d"])
    def test_a_prefix_alone_is_not_a_word(self, trie, prefix_only):
        assert trie.check_if_word(prefix_only) is False

    def test_a_word_can_also_be_a_prefix_of_another_word(self, trie):
        # "car" -> "card" and "do" -> "dog": both the short and long forms must be words
        assert trie.check_if_word("car") and trie.check_if_word("card")
        assert trie.check_if_word("do") and trie.check_if_word("dog")

    @pytest.mark.parametrize("query", ["CAT", "Cat", "cAt"])
    def test_lookup_ignores_case(self, trie, query):
        assert trie.check_if_word(query) is True

    def test_insert_ignores_case(self):
        t = Trie()
        t.insert("Apple")
        assert t.check_if_word("apple") is True
        assert t.check_if_word("APPLE") is True

    def test_empty_trie_has_no_words(self):
        t = Trie()
        assert t.check_if_word("a") is False
        assert t.check_if_word("") is False


# ----------------------------------------------------------------------
# check_if_prefix
# ----------------------------------------------------------------------
class TestCheckIfPrefix:
    @pytest.mark.parametrize("prefix", ["c", "ca", "car", "card", "d", "do", "dog"])
    def test_prefixes_of_stored_words(self, trie, prefix):
        # A complete word counts as a prefix of itself
        assert trie.check_if_prefix(prefix) is True

    @pytest.mark.parametrize("prefix", ["x", "cb", "cars", "dogs", "cat s", "cart"])
    def test_non_prefixes(self, trie, prefix):
        assert trie.check_if_prefix(prefix) is False

    @pytest.mark.parametrize("query", ["CA", "Car", "DO"])
    def test_lookup_ignores_case(self, trie, query):
        assert trie.check_if_prefix(query) is True

    def test_empty_prefix_is_true_even_for_an_empty_trie(self):
        # Documented behavior: "An empty prefix returns True."
        assert Trie().check_if_prefix("") is True

    def test_prefix_and_word_checks_differ(self, trie):
        assert trie.check_if_prefix("ca") is True
        assert trie.check_if_word("ca") is False

    def test_qu_tile_text_matches_lowercase_words(self):
        # A Boggle "Qu" tile displays as "Qu"; the solver can pass that straight in
        t = Trie()
        t.insert("quit")
        assert t.check_if_prefix("Qu") is True
        assert t.check_if_prefix("Qui") is True
        assert t.check_if_word("Quit") is True
        assert t.check_if_prefix("Q") is True   # "q" alone is a prefix of "quit"
        assert t.check_if_prefix("Qa") is False


# ----------------------------------------------------------------------
# structure
# ----------------------------------------------------------------------
class TestStructure:
    def test_root_node(self):
        root = Trie().root
        assert (root.data, root.prefix, root.is_word) == ("", "", False)
        assert root.children == {}

    def test_node_data_prefix_and_is_word(self, trie):
        c = trie.root.children["c"]
        a = c.children["a"]
        t = a.children["t"]

        assert (c.data, c.prefix, c.is_word) == ("c", "", False)
        assert (a.data, a.prefix, a.is_word) == ("a", "c", False)
        assert (t.data, t.prefix, t.is_word) == ("t", "ca", True)
        assert t.prefix + t.data == "cat"   # documented: full prefix = prefix + data

    def test_shared_prefixes_share_nodes(self):
        t = Trie()
        t.insert("car")
        t.insert("card")
        # root + c + a + r + d
        assert count_nodes(t.root) == 5

    def test_inserting_a_duplicate_changes_nothing(self):
        t = Trie()
        t.insert("cat")
        before = count_nodes(t.root)
        t.insert("cat")
        t.insert("CAT")
        assert count_nodes(t.root) == before
        assert t.check_if_word("cat") is True

    def test_lookups_do_not_modify_the_trie(self, trie):
        before = count_nodes(trie.root)
        trie.check_if_word("zzzz")
        trie.check_if_prefix("qqqq")
        assert count_nodes(trie.root) == before


# ----------------------------------------------------------------------
# edge cases (these pin down CURRENT behavior; change them if you change the code)
# ----------------------------------------------------------------------
class TestEdgeCases:
    def test_inserting_empty_string_makes_the_empty_string_a_word(self):
        # insert("") marks the root as a word. Harmless for Boggle (the solver never
        # looks up ""), but you may prefer insert() to ignore empty strings.
        t = Trie()
        t.insert("")
        assert t.check_if_word("") is True

    @pytest.mark.parametrize("word", ["don't", "ice-cream", "ice cream"])
    def test_non_letter_characters_are_stored_as_is(self, word):
        # No filtering happens, so dictionary entries with punctuation or spaces are
        # stored too. They can never match a board path, but they do take up memory.
        t = Trie()
        t.insert(word)
        assert t.check_if_word(word) is True


# ----------------------------------------------------------------------
# store_dic_words
# ----------------------------------------------------------------------
def write_json(tmp_path, content, name="dictionary.json"):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


class TestStoreDicWords:
    def test_keys_become_words_and_values_are_ignored(self, tmp_path):
        path = write_json(tmp_path, json.dumps({"apple": "a fruit", "Bat": "a mammal"}))
        t = Trie()
        t.store_dic_words(path)

        assert t.check_if_word("apple") is True
        assert t.check_if_word("bat") is True          # keys are lowercased
        assert t.check_if_word("a fruit") is False     # values are not inserted
        assert t.check_if_prefix("a m") is False

    def test_values_may_be_any_json_type(self, tmp_path):
        path = write_json(tmp_path, '{"x": null, "y": 3, "z": ["a", "b"]}')
        t = Trie()
        t.store_dic_words(path)
        assert all(t.check_if_word(w) for w in "xyz")

    def test_empty_object_loads_nothing(self, tmp_path):
        t = Trie()
        t.store_dic_words(write_json(tmp_path, "{}"))
        assert t.check_if_prefix("a") is False

    def test_reads_utf8(self, tmp_path):
        path = tmp_path / "dictionary.json"
        path.write_text(json.dumps({"café": "x"}, ensure_ascii=False), encoding="utf-8")
        t = Trie()
        t.store_dic_words(str(path))
        assert t.check_if_word("café") is True

    def test_existing_words_are_kept(self, tmp_path):
        t = Trie()
        t.insert("cat")
        t.store_dic_words(write_json(tmp_path, '{"dog": "x"}'))
        assert t.check_if_word("cat") is True
        assert t.check_if_word("dog") is True

    @pytest.mark.parametrize("content", ['["apple", "bat"]', '"apple"', "42", "null"])
    def test_top_level_must_be_an_object(self, tmp_path, content):
        t = Trie()
        with pytest.raises(ValueError, match="Expected a JSON object"):
            t.store_dic_words(write_json(tmp_path, content))
        assert t.check_if_prefix("a") is False   # nothing was inserted

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            Trie().store_dic_words(str(tmp_path / "does_not_exist.json"))

    def test_invalid_json_raises_and_inserts_nothing(self, tmp_path):
        t = Trie()
        with pytest.raises(json.JSONDecodeError):
            t.store_dic_words(write_json(tmp_path, '{"apple": '))
        assert t.check_if_prefix("a") is False