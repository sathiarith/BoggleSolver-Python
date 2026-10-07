import json

class TrieNode:
    def __init__(self, prefix: str, char: str):
        self.data = char
        self.prefix = prefix
        self.children = {}
        self.is_word = False

class Trie:
    def __init__(self):
        self.root = TrieNode(prefix="", char="")

    def store_dic_words(self, path: str):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Expected a JSON object at top level in {path}, got {type(data).__name__}")

        for word in data:
            self.insert(word)

    def insert(self, word: str):
        curr_node = self.root
        curr_prefix = self.root.prefix
        for char in word.lower():
            if char not in curr_node.children:
                curr_node.children[char] = TrieNode(curr_prefix, char)

            curr_node = curr_node.children[char]
            curr_prefix += char
        curr_node.is_word = True


    def check_if_word(self, string: str) -> bool:
        curr_node = self.root
        for char in string.lower():
            if char in curr_node.children:
                curr_node = curr_node.children[char]
            else:
                return False
        return curr_node.is_word

    def check_if_prefix(self, prefix: str) -> bool:
        """Returns True if there is any word in the trie that starts with the given prefix."""
        curr_node = self.root
        for char in prefix:
            if char in curr_node.children:
                curr_node = curr_node.children[char]
            else:
                return False
        return True