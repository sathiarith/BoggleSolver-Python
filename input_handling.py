import sys
import re

def read_positive_int(prompt: str) -> int:
    while True:
        text = input(prompt)
        try:
            value = int(text)
        except ValueError:
            print("Input must be an integer.")
            continue
        if value < 1:
            print("Input must be at least 1.")
            continue
        return value

def read_letters_by_input(row: int, col: int) -> list[list[str]]:
    board = []
    for i in range(row):
        r_letters = []
        while len(r_letters) < col:
            remaining = col - len(r_letters)
            string = input(
                f"For row {i + 1}, provide letter(s) "
                f"(need {remaining} more): "
            )
            string = string.strip()

            if re.fullmatch(r"[A-Za-z]+", string):
                string = string.upper()

                # "QU" special case (always together as a single piece)
                # Later convert back to "QU" after broken into individual letter pieces
                if re.search(r"Q(?!U)", string):
                    print("In Boggle, Q is always followed by u. Please re-enter as 'qu'.")
                    continue
                elif "QU" in string:
                    string = string.replace("QU", "Q")

                # Break the input into individual letters
                new_letters = list(string)

                # Don't allow overflow past the needed column count
                if len(new_letters) > remaining:
                    print(f"Too many letters, only {remaining} more needed. Try again.")
                    continue

                # Make "Q" tile into "Qu" again
                new_letters = [i.replace("Q", "QU") if i == "Q" else i for i in new_letters]

                r_letters.extend(new_letters)
            else:
                print("Input must contain only alphabet letters (no numbers, spaces, or symbols).")

        board.append(r_letters)
    return board

def dummy_func() -> list[list[str]]:
    return [["Z"]]

def get_dimensions() -> tuple[int,int]:
    if len(sys.argv) == 1:
        rows = read_positive_int("Input number of rows: ")
        columns = read_positive_int("Input number of columns: ")
        return rows, columns
    elif len(sys.argv) == 3:
        try:
            rows, columns = int(sys.argv[1]), int(sys.argv[2])
        except ValueError:
            sys.exit("Usage: python main.py rows columns (integers)")
        if rows < 1 or columns < 1:
            sys.exit("Rows and columns must be at least 1.")
        return rows, columns
    else:
        sys.exit("Incorrect number of arguments, "
                 "two arguments are required: row and column (integers).")

def get_board_info(input_method: str) -> list[list[str]]:
    board = None
    # Obtain letters of row x col board
    if input_method == "AI_VISION":
        # need to implement module that identifies number of row and col by image
        # ocr_vision.py responsibility, temporarily assign to dummy function
        board = dummy_func()
    elif input_method == "USER_ENTRY":
        row, col = get_dimensions()
        board = read_letters_by_input(row, col)
    else:
        sys.exit("Input method must be 'AI_VISION' or 'USER_ENTRY'.")

    return board