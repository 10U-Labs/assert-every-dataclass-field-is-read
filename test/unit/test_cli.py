from __future__ import annotations

import argparse
from pathlib import Path
from test.samples import ALL_READ, MODULE, PAIR, READS_NAME_ONLY, holding, searching_both
from typing import TYPE_CHECKING

import pytest

from assert_every_dataclass_field_is_read.cli import (
    EXIT_ERROR,
    EXIT_FINDINGS,
    EXIT_SUCCESS,
    ScanResult,
    _announce,
    _collect,
    _expand,
    _read,
    _report,
    _walk_python_files,
    create_parser,
    determine_exit_code,
    output_findings,
    package_of,
    parse_patterns,
    read_fields,
    read_sources,
    report_unparsed,
    should_skip,
    split_assumed,
)
from assert_every_dataclass_field_is_read.scanner import Finding, Searched

if TYPE_CHECKING:
    from test.runners import RunCli, WriteTree


def _arguments(**given: object) -> argparse.Namespace:
    defaults = {"verbose": False, "quiet": False}
    return argparse.Namespace(**{**defaults, **given})


def _finding() -> Finding:
    return Finding(unread=holding("Widget", "color"))


def test_parses_no_patterns() -> None:
    assert parse_patterns(None) == []


def test_parses_an_empty_string() -> None:
    assert parse_patterns("") == []


def test_parses_two_patterns() -> None:
    assert parse_patterns("a*, b*") == ["a*", "b*"]


def test_drops_an_empty_pattern() -> None:
    assert parse_patterns("a*,,b*") == ["a*", "b*"]


def test_parser_takes_a_tree() -> None:
    assert create_parser().parse_args(["src"]).trees == ["src"]


def test_parser_repeats_search_in() -> None:
    parsed = create_parser().parse_args(["src", "--search-in", "a", "--search-in", "b"])
    assert parsed.search_in == ["a", "b"]


def test_parser_refuses_quiet_with_verbose() -> None:
    with pytest.raises(SystemExit):
        create_parser().parse_args(["src", "--quiet", "--verbose"])


def test_walks_a_python_file(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    assert _walk_python_files(str(tmp_path)) == [str(tmp_path / "a.py")]


def test_ignores_a_file_that_is_not_python(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("x\n", encoding="utf-8")
    assert not _walk_python_files(str(tmp_path))


def test_ignores_a_hidden_directory(tmp_path: Path) -> None:
    hidden = tmp_path / ".git"
    hidden.mkdir()
    (hidden / "a.py").write_text("x = 1\n", encoding="utf-8")
    assert not _walk_python_files(str(tmp_path))


def test_expands_a_file(tmp_path: Path) -> None:
    path = tmp_path / "a.py"
    path.write_text("x = 1\n", encoding="utf-8")
    assert _expand(str(path)) == ([str(path)], True)


def test_expands_a_directory(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    assert _expand(str(tmp_path))[1]


def test_refuses_a_missing_path(tmp_path: Path) -> None:
    assert _expand(str(tmp_path / "gone")) == ([], False)


def test_names_the_package(tmp_path: Path) -> None:
    assert package_of(str(tmp_path / "widgets" / "w.py"), str(tmp_path)) == "widgets"


def test_has_no_package_at_the_tree_root(tmp_path: Path) -> None:
    assert package_of(str(tmp_path / "w.py"), str(tmp_path)) is None


def test_skips_a_matching_path() -> None:
    assert should_skip("src/vendor/a.py", ["*/vendor/*"])


def test_skips_a_matching_basename() -> None:
    assert should_skip("src/vendor/a.py", ["a.py"])


def test_keeps_an_unmatched_path() -> None:
    assert not should_skip("src/a.py", ["*/vendor/*"])


def test_collects_a_directory(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    collected, _ = _collect([str(tmp_path)], [])
    assert collected == {str(tmp_path / "a.py"): str(tmp_path)}


def test_collects_a_file_beside_itself(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert _collect(["a.py"], [])[0] == {"a.py": "."}


def test_reports_a_missing_tree(tmp_path: Path) -> None:
    assert _collect([str(tmp_path / "gone")], [])[1] == [str(tmp_path / "gone")]


def test_leaves_out_a_file_that_is_not_python(tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_text("x\n", encoding="utf-8")
    assert not _collect([str(path)], [])[0]


def test_leaves_out_an_excluded_file(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    assert not _collect([str(tmp_path)], ["a.py"])[0]


def test_reads_a_file(tmp_path: Path) -> None:
    path = tmp_path / "a.py"
    path.write_text("x = 1\n", encoding="utf-8")
    assert _read(str(path), ScanResult()) == "x = 1\n"


def test_refuses_a_directory(tmp_path: Path) -> None:
    assert _read(str(tmp_path), ScanResult()) is None


def test_records_a_read_error(tmp_path: Path) -> None:
    result = ScanResult()
    _read(str(tmp_path), result)
    assert result.had_error


def test_read_sources_skips_what_it_cannot_read(tmp_path: Path) -> None:
    assert not read_sources({str(tmp_path): str(tmp_path)}, ScanResult())


def test_read_sources_keeps_what_it_reads(tmp_path: Path) -> None:
    path = tmp_path / "a.py"
    path.write_text("x = 1\n", encoding="utf-8")
    assert read_sources({str(path): str(tmp_path)}, ScanResult()) == {str(path): "x = 1\n"}


def test_reads_the_declared_fields() -> None:
    found = read_fields({MODULE: "."}, {MODULE: PAIR}, ScanResult())
    assert [declared.name for declared in found] == ["name", "color"]


def test_counts_the_files_scanned() -> None:
    result = ScanResult()
    read_fields({MODULE: "."}, {MODULE: PAIR}, result)
    assert result.files_scanned == 1


def test_counts_the_fields_declared() -> None:
    result = ScanResult()
    read_fields({MODULE: "."}, {MODULE: PAIR}, result)
    assert result.fields_declared == 2


def test_skips_a_source_it_never_read() -> None:
    assert not read_fields({MODULE: "."}, {}, ScanResult())


def test_announces_each_file_scanned(capsys: pytest.CaptureFixture[str]) -> None:
    read_fields({MODULE: "."}, {MODULE: PAIR}, ScanResult(), verbose=True)
    assert f"Scanning: {MODULE}" in capsys.readouterr().out


def test_records_a_syntax_error() -> None:
    result = ScanResult()
    read_fields({MODULE: "."}, {MODULE: "def ("}, result)
    assert result.had_error


def test_complains_about_a_syntax_error(capsys: pytest.CaptureFixture[str]) -> None:
    read_fields({MODULE: "."}, {MODULE: "def ("}, ScanResult())
    assert "Syntax error" in capsys.readouterr().err


def test_splits_out_an_assumed_field() -> None:
    fields = [holding("Widget", "name"), holding("Widget", "color")]
    assert [declared.name for declared in split_assumed(fields, ["na*"])[1]] == ["name"]


def test_keeps_an_unassumed_field() -> None:
    fields = [holding("Widget", "name"), holding("Widget", "color")]
    assert [declared.name for declared in split_assumed(fields, ["na*"])[0]] == ["color"]


def test_reports_an_unparsed_file(capsys: pytest.CaptureFixture[str]) -> None:
    report_unparsed(Searched(per_file={}, unparsed=(MODULE,)))
    assert f"Skipping (will not parse): {MODULE}" in capsys.readouterr().out


def test_prints_a_finding(capsys: pytest.CaptureFixture[str]) -> None:
    output_findings([_finding()])
    assert str(_finding()) in capsys.readouterr().out


def test_exits_with_findings() -> None:
    assert determine_exit_code(ScanResult(findings=[_finding()])) == EXIT_FINDINGS


def test_exits_with_an_error() -> None:
    assert determine_exit_code(ScanResult(had_error=True)) == EXIT_ERROR


def test_exits_clean() -> None:
    assert determine_exit_code(ScanResult()) == EXIT_SUCCESS


def test_announces_the_trees_read(capsys: pytest.CaptureFixture[str]) -> None:
    _announce(2, 3, [])
    assert "Reading 2 declaration file(s)..." in capsys.readouterr().out


def test_announces_the_excluded_patterns(capsys: pytest.CaptureFixture[str]) -> None:
    _announce(2, 3, ["a.py"])
    assert "Excluding patterns: a.py" in capsys.readouterr().out


def test_reports_the_findings_plainly(capsys: pytest.CaptureFixture[str]) -> None:
    _report(ScanResult(findings=[_finding()]), _arguments())
    assert str(_finding()) in capsys.readouterr().out


def test_reports_nothing_when_quiet(capsys: pytest.CaptureFixture[str]) -> None:
    _report(ScanResult(findings=[_finding()]), _arguments(quiet=True))
    assert capsys.readouterr().out == ""


def test_reports_the_count_when_verbose(capsys: pytest.CaptureFixture[str]) -> None:
    _report(ScanResult(findings=[_finding()]), _arguments(verbose=True))
    assert "Findings: 1" in capsys.readouterr().out


def test_reports_the_assumed_count(capsys: pytest.CaptureFixture[str]) -> None:
    _report(ScanResult(assumed=2), _arguments(verbose=True))
    assert "Assumed read by name: 2" in capsys.readouterr().out


def test_reports_an_error_when_verbose(capsys: pytest.CaptureFixture[str]) -> None:
    _report(ScanResult(had_error=True), _arguments(verbose=True))
    assert "Errors occurred during scanning." in capsys.readouterr().out


def test_main_reports_an_unread_field(write_tree: WriteTree, run_cli: RunCli) -> None:
    write_tree({"src/w.py": PAIR})
    assert "Widget.color" in run_cli(["src"])[1]


def test_main_exits_on_findings(write_tree: WriteTree, run_cli: RunCli) -> None:
    write_tree({"src/w.py": PAIR})
    assert run_cli(["src"])[0] == EXIT_FINDINGS


def test_main_stays_silent_on_a_read_field(write_tree: WriteTree, run_cli: RunCli) -> None:
    write_tree({"src/w.py": READS_NAME_ONLY})
    assert "Widget.name" not in run_cli(["src"])[1]


def test_main_searches_another_tree(write_tree: WriteTree, run_cli: RunCli) -> None:
    write_tree({"src/w.py": PAIR, "other/r.py": READS_NAME_ONLY})
    assert "Widget.name" not in run_cli(["src", "--search-in", "src", "--search-in", "other"])[1]


def test_main_leaves_out_the_named_tree(write_tree: WriteTree, run_cli: RunCli) -> None:
    write_tree({"src/widgets/w.py": PAIR, "test/widgets/t.py": READS_NAME_ONLY})
    args = searching_both("test/{package}")
    assert "Widget.name" in run_cli(args)[1]


def test_main_assumes_a_named_field_is_read(write_tree: WriteTree, run_cli: RunCli) -> None:
    write_tree({"src/w.py": PAIR})
    assert "Widget.color" not in run_cli(["src", "--assume-read-matching", "col*"])[1]


def test_main_counts_an_assumed_field(write_tree: WriteTree, run_cli: RunCli) -> None:
    write_tree({"src/w.py": PAIR})
    printed = run_cli(["src", "--assume-read-matching", "col*", "--verbose"])[1]
    assert "Assumed read by name: 1" in printed


def test_main_stays_quiet(write_tree: WriteTree, run_cli: RunCli) -> None:
    write_tree({"src/w.py": PAIR})
    assert run_cli(["src", "--quiet"])[1] == ""


def test_main_announces_the_exclusions(write_tree: WriteTree, run_cli: RunCli) -> None:
    write_tree({"src/w.py": PAIR})
    assert "Excluding patterns: z.py" in run_cli(["src", "--verbose", "--exclude", "z.py"])[1]


def test_main_complains_about_a_missing_tree(write_tree: WriteTree, run_cli: RunCli) -> None:
    write_tree({"src/w.py": PAIR})
    assert "Path not found: gone" in run_cli(["src", "gone"])[2]


def test_main_errors_on_a_missing_tree(write_tree: WriteTree, run_cli: RunCli) -> None:
    write_tree({"src/w.py": ALL_READ})
    assert run_cli(["src", "gone"])[0] == EXIT_ERROR


def test_main_errors_when_every_tree_is_missing(write_tree: WriteTree, run_cli: RunCli) -> None:
    write_tree({"src/w.py": PAIR})
    assert run_cli(["gone"])[0] == EXIT_ERROR


def test_main_reports_an_unparsed_search_file(write_tree: WriteTree, run_cli: RunCli) -> None:
    write_tree({"src/w.py": READS_NAME_ONLY, "other/bad.py": "def ("})
    args = ["src", "--search-in", "src", "--search-in", "other", "--verbose"]
    assert "Skipping (will not parse): other/bad.py" in run_cli(args)[1]


def test_main_skips_an_unreadable_declaration(write_tree: WriteTree, run_cli: RunCli) -> None:
    tree = write_tree({"src/w.py": ALL_READ, "src/locked.py": PAIR})
    (tree / "src" / "locked.py").chmod(0o000)
    assert run_cli(["src"])[0] == EXIT_ERROR
