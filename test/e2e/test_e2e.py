from __future__ import annotations

from test.samples import ALL_READ, PAIR
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from test.runners import RunOver

TREE = ["src"]


def test_names_the_unread_field(run_over: RunOver) -> None:
    assert "Widget.color" in run_over({"src/w.py": PAIR}, TREE)[1]


def test_exits_on_a_finding(run_over: RunOver) -> None:
    assert run_over({"src/w.py": PAIR}, TREE)[0] == 1


def test_exits_clean_when_every_field_is_read(run_over: RunOver) -> None:
    assert run_over({"src/w.py": ALL_READ}, TREE)[0] == 0


def test_prints_nothing_when_quiet(run_over: RunOver) -> None:
    assert run_over({"src/w.py": PAIR}, ["src", "--quiet"])[1] == ""


def test_offers_help(run_over: RunOver) -> None:
    assert "--dont-search-in" in run_over({"src/w.py": PAIR}, ["--help"])[1]
