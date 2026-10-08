"""A simple Trie (prefix tree) for fast word and prefix lookups."""

import json

class TrieNode:
    """A single node in a Trie.

    Attributes:
        data: The character this node represents ("" for the root).
        prefix: The characters on the path from the root to this node's
            parent. The full prefix for this node is `prefix + data`.
        children: Maps a character to the child `TrieNode` for it.
        is_word: True if the path to this node spells a complete word.
    """
    def __init__(self, prefix: str, char: str):
        """Initialize a node.

        Args:
            prefix: The path from the root to this node's parent.
            char: The character this node represents.
        """
        self.data = char
        self.prefix = prefix
        self.children = {}
        self.is_word = False

class Trie:
    """A case-insensitive Trie supporting word and prefix lookups.

    Example:
        >>> trie = Trie()
        >>> trie.insert("Apple")
        >>> trie.check_if_word("apple")
        True
        >>> trie.check_if_prefix("app")
        True
    """
    def __init__(self):
        self.root = TrieNode(prefix="", char="")

    def store_dic_words(self, path: str):
        """Load words from a JSON dictionary file into the Trie.

        Only the keys of the JSON object are inserted; values are ignored.

        Args:
            path: Path to a UTF-8 encoded JSON file whose top level is an
                object, e.g. `{"apple": "a fruit", "bat": "a mammal"}`.

        Raises:
            ValueError: If the top-level JSON value is not an object.
            FileNotFoundError: If `path` does not exist.
            json.JSONDecodeError: If the file is not valid JSON.
        """
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Expected a JSON object at top level in {path}, got {type(data).__name__}")

        for word in data:
            self.insert(word)

    def insert(self, word: str):
        """Insert a word into the Trie.

        The word is lowercased before insertion. Inserting a word that
        already exists has no effect.

        Args:
            word: The word to insert.
        """
        curr_node = self.root
        curr_prefix = self.root.prefix
        for char in word.lower():
            if char not in curr_node.children:
                curr_node.children[char] = TrieNode(curr_prefix, char)

            curr_node = curr_node.children[char]
            curr_prefix += char
        curr_node.is_word = True


    def check_if_word(self, string: str) -> bool:
        """Check whether a string is a complete word in the Trie.

        Args:
            string: The string to look up.

        Returns:
            True if `string` was inserted as a word, False otherwise.
            A string that is only a prefix of a stored word returns False.
        """
        curr_node = self.root
        for char in string.lower():
            if char in curr_node.children:
                curr_node = curr_node.children[char]
            else:
                return False
        return curr_node.is_word

    def check_if_prefix(self, prefix: str) -> bool:
        """Check whether any stored word starts with the given prefix.

        Args:
            prefix: The prefix to look for.

        Returns:
            True if at least one word begins with `prefix`, False otherwise.
            An empty prefix returns True.
        """
        curr_node = self.root
        for char in prefix.lower():
            if char in curr_node.children:
                curr_node = curr_node.children[char]
            else:
                return False
        return True