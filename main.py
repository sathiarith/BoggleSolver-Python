from input_handling import get_board_info
from board import Board


def main():
    board = Board(get_board_info("USER_ENTRY"))
    board.print_board()

if __name__ == '__main__':
    main()
