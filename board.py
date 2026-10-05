class Board:
    def __init__(self, grid: list[list[str]]):
        self.row = len(grid)
        self.column = len(grid[0])
        self.board = grid

    def print_board(self,):
        for row in self.board:
            print(row)

    def get_row(self) -> int:
        return self.row

    def get_col(self) -> int:
        return self.column
