import random
from typing import List, Tuple
import copy

Board = List[List[int]]

def find_empty(board: Board) -> Tuple[int, int] | None:
    for r in range(9):
        for c in range(9):
            if board[r][c] == 0:
                return r, c
    return None

def valid(board: Board, num: int, pos: Tuple[int, int]) -> bool:
    r, c = pos
    if any(board[r][i] == num for i in range(9)):
        return False
    if any(board[i][c] == num for i in range(9)):
        return False
    br, bc = 3*(r//3), 3*(c//3)
    for i in range(br, br+3):
        for j in range(bc, bc+3):
            if board[i][j] == num:
                return False
    return True

def solve(board: Board) -> bool:
    empty = find_empty(board)
    if not empty:
        return True
    r, c = empty
    for n in range(1, 10):
        if valid(board, n, (r, c)):
            board[r][c] = n
            if solve(board):
                return True
            board[r][c] = 0
    return False

def solve_with_counter(board: Board, counter: list[int]) -> bool:
    empty = find_empty(board)
    if not empty:
        counter[0] += 1
        return counter[0] > 1
    r, c = empty
    for n in range(1, 10):
        if valid(board, n, (r, c)):
            board[r][c] = n
            if solve_with_counter(board, counter):
                return True
            board[r][c] = 0
    return False

def generate_full_board() -> Board:
    board = [[0]*9 for _ in range(9)]
    nums = list(range(1, 10))
    for box in range(0, 9, 3):
        random.shuffle(nums)
        idx = 0
        for r in range(box, box+3):
            for c in range(box, box+3):
                board[r][c] = nums[idx]; idx += 1
    solve(board)
    return board

def remove_cells_for_difficulty(board: Board, difficulty: str) -> Board:
    if difficulty == "easy":
        clues = random.randint(40, 45)
    elif difficulty == "medium":
        clues = random.randint(32, 36)
    else:
        clues = random.randint(26, 30)

    puzzle = copy.deepcopy(board)
    cells = [(r, c) for r in range(9) for c in range(9)]
    random.shuffle(cells)

    removed = 81 - clues
    count = 0
    for r, c in cells:
        if count >= removed:
            break
        backup = puzzle[r][c]
        puzzle[r][c] = 0

        test = copy.deepcopy(puzzle)
        counter = [0]
        solve_with_counter(test, counter)
        if counter[0] != 1:
            puzzle[r][c] = backup
        else:
            count += 1
    return puzzle

def generate_puzzle(difficulty: str = "easy") -> tuple[Board, Board]:
    solution = generate_full_board()
    puzzle = remove_cells_for_difficulty(solution, difficulty)
    return puzzle, solution
