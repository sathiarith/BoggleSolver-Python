# Outdated 9/27/2026

import pytest

from input_handling import read_positive_int


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
