import json

class TrieNode:
    def __init__(self, prefix: str, char: str):
        self.data = char
        self.prefix = prefix
        self.children = {}
        self.is_word = False

class Trie:
    def __init__(self):
        # root to a-z
        # uses dictionary/list
        # make methods to accept word list to propagate trie
        self.root = TrieNode(prefix="", char="")

    def store_dic_words(self, path: str):
        with open(path, 'r') as f:
            data = json.load(f)
            # Type safety check: ensure the root object parsed into a dictionary
            if isinstance(data, dict):
                # Iterating directly over a dict extracts its string keys
                for word in data:
                    self.insert(word)

    def insert(self, word: str):
        curr_node = self.root
        curr_prefix = self.root.prefix
        for char in word:
            if char not in curr_node.children:
                curr_node.children[char] = TrieNode(curr_prefix, char)

            curr_node = curr_node.children[char]
            curr_prefix += char

        curr_node.is_word = True

    # def check_if_word() -> bool:
    #     return True

if __name__ == '__main__':
    path = r"C:\Users\sathc\PycharmProjects\BoggleSolver\words_dictionary.json"
    trie = Trie()
    trie.store_dic_words(path)
    print(trie.root.children)