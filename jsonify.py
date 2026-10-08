import json


def convert_txt_to_boggle_json(txt_path: str, json_output_path: str):
    """
    Reads a newline-separated text wordlist, cleans it, 
    and saves it as a structural key-value JSON file.
    """
    word_map = {}

    print("Reading text file and parsing words...")
    with open(txt_path, 'r', encoding='utf-8') as f:
        for line in f:
            # Strip spaces, newlines, and convert to lowercase
            word = line.strip().lower()

            # Ensure it's a valid word (removes numbers, punctuation, empty lines)
            if word.isalpha():
                word_map[word] = 1

    print(f"Successfully processed {len(word_map)} unique words.")

    # Save as formatted JSON
    print(f"Writing data to {json_output_path}...")
    with open(json_output_path, 'w', encoding='utf-8') as f:
        # indent=2 adds clean line breaks so it's easy to look at manually
        json.dump(word_map, f, indent=2)

    print("Conversion complete!")

# --- Local Execution Example ---
# convert_txt_to_boggle_json("CSW21.txt", "words_dictionary.json")
if __name__ == "__main__":
    convert_txt_to_boggle_json("CSW24.txt", "CSW24_words.json")