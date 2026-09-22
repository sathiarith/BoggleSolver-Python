import sys

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

def create_board() -> list:
    board = []
    r, c = get_dimensions()



    return board
if __name__ == '__main__':
    read_positive_int("Rows: ")
