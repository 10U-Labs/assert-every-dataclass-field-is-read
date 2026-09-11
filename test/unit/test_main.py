from __future__ import annotations

from test.runners import module_exit_code
from test.samples import PAIR
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

    from test.runners import WriteTree

MODULE_NAME = "assert_every_dataclass_field_is_read"


def test_module_entry_point_reports_a_finding(
    write_tree: WriteTree, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_tree({"src/w.py": PAIR})
    monkeypatch.setattr("sys.argv", [MODULE_NAME, "src", "--quiet"])
    assert module_exit_code(MODULE_NAME) == 1
