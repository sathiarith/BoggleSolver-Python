import pytest
from old_files.input_handling import read_positive_int, get_dimensions, get_board_info

@pytest.mark.parametrize("value", [1, 2, 10, 999])
def test_returns_valid_integer(monkeypatch, value):
    monkeypatch.setattr("builtins.input", lambda _: str(value))
    assert read_positive_int("Rows: ") == value


@pytest.mark.parametrize("bad", ["abc", "4.2", "", " ", "0", "-1"])
def test_rejects_bad_input_then_accepts(monkeypatch, bad):
    answers = iter([bad, "3"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert read_positive_int("Rows: ") == 3


def test_error_messages(monkeypatch, capsys):
    answers = iter(["abc", "0", "5"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert read_positive_int("Rows: ") == 5
    lines = capsys.readouterr().out.splitlines()
    assert lines == ["Input must be an integer.", "Input must be at least 1."]


# main.py may be changed in terms of sys.argv pertaining to get_dimensions
def test_get_dimensions_user_inputs(monkeypatch):
    monkeypatch.setattr("sys.argv", ["main.py"])
    resp = iter(["3","4"])
    monkeypatch.setattr("builtins.input", lambda _: next(resp))
    assert get_dimensions() == (3,4)

def test_dimensions_from_valid_argv(monkeypatch):
    monkeypatch.setattr("sys.argv", ["main.py", "3", "4"])
    assert get_dimensions() == (3,4)

@pytest.mark.parametrize("argv_err_inputs", [
    ["a", "1"],   # bad rows
    ["2", "b"],   # bad columns
    ["a", "b"]   # both bad
])
def test_non_int_argv_exits(monkeypatch, argv_err_inputs):
    monkeypatch.setattr("sys.argv", ["main.py", *argv_err_inputs])
    with pytest.raises(SystemExit) as err_msg:
        get_dimensions()
    assert str(err_msg.value.code) == "Usage: python main.py rows columns (integers)"

@pytest.mark.parametrize("argv_incorrect_amount_provided", [
    ["1", "2", "3"],
    ["4"]
])
def test_incorrect_num_of_argv_exits(monkeypatch, argv_incorrect_amount_provided):
    monkeypatch.setattr("sys.argv", ["main.py", *argv_incorrect_amount_provided])
    with pytest.raises(SystemExit) as err_msg:
        get_dimensions()
    assert str(err_msg.value.code) == ("Incorrect number of arguments, "
                                       "two arguments are required: row and column (integers).")

@pytest.mark.parametrize("argv_below_threshold_provided", [
    ["0", "2"],
    ["4", "-1"]
])
def test_int_value_below_threshold_exits(monkeypatch, argv_below_threshold_provided):
    monkeypatch.setattr("sys.argv", ["main.py", *argv_below_threshold_provided])
    with pytest.raises(SystemExit) as err_msg:
        get_dimensions()
    assert str(err_msg.value.code) == "Rows and columns must be at least 1."


def test_valid_arg_get_board_info(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["main.py"])
    input_info = iter(["3","3", "abc", "def", "ghi"])
    monkeypatch.setattr("builtins.input", lambda _: next(input_info))
    assert get_board_info("AI_VISION") == [["Z"]]
    assert get_board_info("USER_ENTRY") == [["A", "B", "C"],
                                            ["D", "E", "F"],
                                            ["G", "H", "I"]]

def test_invalid_arg_get_board_info(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["main.py"])
    with pytest.raises(SystemExit) as err_msg:
        get_board_info("USER_VISION")
    assert str(err_msg.value.code) == "Input method must be 'AI_VISION' or 'USER_ENTRY'."
    with pytest.raises(SystemExit) as err_msg:
        get_board_info("")
    assert str(err_msg.value.code) == "Input method must be 'AI_VISION' or 'USER_ENTRY'."
    with pytest.raises(SystemExit) as err_msg:
        get_board_info(1234)
    assert str(err_msg.value.code) == "Input method must be 'AI_VISION' or 'USER_ENTRY'."

def test_read_letters_by_input(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["main.py"])