# Outdated 9/27/2026

import pytest

from old_files.input_handling import get_dimensions

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