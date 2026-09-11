from __future__ import annotations

from test.runners import module_exit_code
from test.samples import ALL_READ, PAIR, READS_NAME_ONLY, SHAPES, searching_both
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from test.runners import ExitCodeOf, RunOver, StderrOf, StdoutOf, WriteTree

OVER_SRC = ["src"]
ENTRY_POINT = "assert_every_dataclass_field_is_read"


@pytest.fixture(name="shapes_report")
def shapes_report_fixture(stdout_of: StdoutOf) -> str:
    return stdout_of(SHAPES, OVER_SRC)


def test_reports_the_field_nothing_reads(shapes_report: str) -> None:
    assert "Plain.never_read" in shapes_report


def test_reports_nothing_else(shapes_report: str) -> None:
    assert len(shapes_report.strip().splitlines()) == 1


def test_exits_on_the_finding(exit_code_of: ExitCodeOf) -> None:
    assert exit_code_of(SHAPES, OVER_SRC) == 1


@pytest.mark.parametrize(
    "field_name",
    [
        "read_by_arg",
        "read_by_local",
        "read_by_class",
        "read_by_self",
        "read_by_getattr",
        "read_by_loop",
        "read_by_comprehension",
        "read_by_mapping",
        "read_by_tuple",
        "read_by_union",
        "read_by_quoted",
        "read_by_return",
        "read_by_augment",
        "read_by_loose",
        "read_by_chain",
        "read_by_base",
        "size",
    ],
)
def test_keeps_a_read_field_out_of_the_report(shapes_report: str, field_name: str) -> None:
    assert f"Plain.{field_name}" not in shapes_report


@pytest.mark.parametrize(
    "declared",
    ["Plain.kind", "Plain.quoted_kind", "Plain.material", "Fancy.extra"],
)
def test_leaves_out_what_is_not_a_read_field(shapes_report: str, declared: str) -> None:
    assert declared not in shapes_report


@pytest.mark.parametrize(
    "declared",
    ["Inner.depth", "Outer.inner", "Outer.label", "Alpha.beta", "Beta.alpha", "Beta.weight"],
)
def test_spread_covers_the_nested_classes(shapes_report: str, declared: str) -> None:
    assert declared not in shapes_report


def test_complains_about_a_missing_tree(stderr_of: StderrOf) -> None:
    assert "Path not found: gone" in stderr_of({"src/w.py": ALL_READ}, ["src", "gone"])


def test_errors_when_every_tree_is_missing(exit_code_of: ExitCodeOf) -> None:
    assert exit_code_of({"src/w.py": ALL_READ}, ["gone"]) == 2


def test_errors_beside_a_missing_tree(exit_code_of: ExitCodeOf) -> None:
    assert exit_code_of({"src/w.py": ALL_READ}, ["src", "gone"]) == 2


def test_excludes_a_named_file(exit_code_of: ExitCodeOf) -> None:
    assert exit_code_of({"src/w.py": PAIR}, ["src", "--exclude", "w.py"]) == 0


def test_says_nothing_when_quiet(stdout_of: StdoutOf) -> None:
    assert stdout_of({"src/w.py": PAIR}, ["src", "--quiet"]) == ""


def test_counts_the_fields_when_verbose(stdout_of: StdoutOf) -> None:
    assert "Fields declared: 2" in stdout_of({"src/w.py": PAIR}, ["src", "--verbose"])


def test_names_each_file_when_verbose(stdout_of: StdoutOf) -> None:
    assert "Scanning: src/w.py" in stdout_of({"src/w.py": PAIR}, ["src", "--verbose"])


def test_names_the_exclusions_when_verbose(stdout_of: StdoutOf) -> None:
    printed = stdout_of({"src/w.py": PAIR}, ["src", "--verbose", "--exclude", "z.py"])
    assert "Excluding patterns: z.py" in printed


def test_names_an_unparsed_search_file(stdout_of: StdoutOf) -> None:
    files = {"src/w.py": ALL_READ, "other/bad.py": "def ("}
    args = ["src", "--search-in", "src", "--search-in", "other", "--verbose"]
    assert "Skipping (will not parse): other/bad.py" in stdout_of(files, args)


def test_complains_about_a_broken_declaration(stderr_of: StderrOf) -> None:
    assert "Syntax error" in stderr_of({"src/bad.py": "def ("}, OVER_SRC)


def test_errors_on_a_broken_declaration(exit_code_of: ExitCodeOf) -> None:
    assert exit_code_of({"src/bad.py": "def ("}, OVER_SRC) == 2


def test_errors_on_an_unreadable_declaration(write_tree: WriteTree, run_over: RunOver) -> None:
    tree = write_tree({"src/locked.py": PAIR})
    (tree / "src" / "locked.py").chmod(0o000)
    assert run_over({"src/w.py": ALL_READ}, OVER_SRC)[0] == 2


def test_accepts_a_tree_holding_no_python(exit_code_of: ExitCodeOf) -> None:
    assert exit_code_of({"notes.txt": "nothing\n"}, ["notes.txt"]) == 0


def test_ignores_a_hidden_directory(stdout_of: StdoutOf) -> None:
    assert "Widget.color" not in stdout_of({"src/.hidden/h.py": PAIR}, OVER_SRC)


def test_leaves_out_the_package_tests(stdout_of: StdoutOf) -> None:
    files = {"src/widgets/w.py": PAIR, "test/widgets/t.py": READS_NAME_ONLY}
    args = searching_both("test/{package}")
    assert "Widget.name" in stdout_of(files, args)


def test_leaves_out_an_exactly_named_file(stdout_of: StdoutOf) -> None:
    files = {"src/widgets/w.py": PAIR, "test/widgets/t.py": READS_NAME_ONLY}
    args = searching_both("test/{package}/t.py")
    assert "Widget.name" in stdout_of(files, args)


def test_keeps_a_tree_the_template_misses(stdout_of: StdoutOf) -> None:
    files = {"src/widgets/w.py": PAIR, "test/gadgets/t.py": READS_NAME_ONLY}
    args = searching_both("test/{package}")
    assert "Widget.name" not in stdout_of(files, args)


def test_assumes_a_named_field_is_read(exit_code_of: ExitCodeOf) -> None:
    args = ["src", "--assume-read-matching", "name,color"]
    assert exit_code_of({"src/w.py": PAIR}, args) == 0


def test_counts_an_assumed_field(stdout_of: StdoutOf) -> None:
    args = ["src", "--assume-read-matching", "col*", "--verbose"]
    assert "Assumed read by name: 1" in stdout_of({"src/w.py": PAIR}, args)


def test_refuses_quiet_beside_verbose(exit_code_of: ExitCodeOf) -> None:
    assert exit_code_of({"src/w.py": PAIR}, ["src", "--quiet", "--verbose"]) == 2


def test_runs_as_a_module(write_tree: WriteTree, monkeypatch: pytest.MonkeyPatch) -> None:
    write_tree({"src/w.py": ALL_READ})
    monkeypatch.setattr("sys.argv", [ENTRY_POINT, "src"])
    assert module_exit_code(ENTRY_POINT) == 0


def test_says_an_error_happened_when_verbose(stdout_of: StdoutOf) -> None:
    printed = stdout_of({"src/bad.py": "def ("}, ["src", "--verbose"])
    assert "Errors occurred during scanning." in printed
