from __future__ import annotations

import argparse
import fnmatch
import os
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .scanner import (
    Field,
    Finding,
    Searched,
    assumed_read,
    declared_fields,
    owner_names,
    read_searched,
    unread_fields,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

EXIT_SUCCESS = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2


@dataclass
class ScanResult:
    findings: list[Finding] = field(default_factory=list)
    fields_declared: int = 0
    files_scanned: int = 0
    assumed: int = 0
    had_error: bool = False


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="assert-every-dataclass-field-is-read",
        description=(
            "Assert that every field declared by a dataclass in the given trees is read "
            "somewhere. A field whose last reader was deleted is still written on every "
            "instance, still costs every caller a value, and nothing else reports it."
        ),
    )

    parser.add_argument(
        "trees",
        nargs="+",
        metavar="TREE",
        help=(
            "One or more file paths or directory paths holding the dataclasses to check. "
            "Directories are read recursively for *.py files."
        ),
    )

    parser.add_argument(
        "--search-in",
        action="append",
        default=None,
        metavar="PATH",
        dest="search_in",
        help=(
            "A tree to search for reads, repeatable. Defaults to the declaration trees, "
            "so pass it for every other place a reader may live."
        ),
    )

    parser.add_argument(
        "--dont-search-in",
        metavar="TEMPLATE",
        help=(
            "A path template containing {package} to leave out of the search, such as "
            "'test/{package}'. Without it a field read only by the tests covering it "
            "always reads as read."
        ),
    )

    parser.add_argument(
        "--exclude",
        metavar="PATTERNS",
        help="Comma-separated glob patterns to exclude files, from both trees.",
    )

    parser.add_argument(
        "--assume-read-matching",
        metavar="PATTERNS",
        help=(
            "Comma-separated glob patterns matched against a field's name. A field a "
            "runtime reads has no read to find, so name it here instead."
        ),
    )

    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress all output. Exit code indicates success (0) or findings (1).",
    )
    output_group.add_argument(
        "--verbose",
        action="store_true",
        help="Show trees read, fields found, findings and a summary.",
    )

    return parser


def parse_patterns(patterns_str: str | None) -> list[str]:
    if not patterns_str:
        return []
    return [pattern.strip() for pattern in patterns_str.split(",") if pattern.strip()]


def _walk_python_files(directory: str) -> list[str]:
    found: list[str] = []
    for root, directories, filenames in os.walk(directory):
        directories[:] = [name for name in directories if not name.startswith(".")]
        found.extend(
            os.path.join(root, filename) for filename in filenames if filename.endswith(".py")
        )
    return found


def _expand(path: str) -> tuple[list[str], bool]:
    if os.path.isfile(path):
        return ([path], True)
    if os.path.isdir(path):
        return (_walk_python_files(path), True)
    return ([], False)


def package_of(path: str, tree: str) -> str | None:
    relative = os.path.relpath(os.path.normpath(path), os.path.normpath(tree))
    parts = relative.split(os.sep)
    return parts[0] if len(parts) > 1 else None


def should_skip(path: str, exclude_patterns: list[str]) -> bool:
    return any(
        fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(os.path.basename(path), pattern)
        for pattern in exclude_patterns
    )


def _collect(paths: Sequence[str], exclude_patterns: list[str]) -> tuple[dict[str, str], list[str]]:
    trees: dict[str, str] = {}
    missing: list[str] = []
    for path in paths:
        found, matched = _expand(path)
        if not matched:
            missing.append(path)
            continue
        root = path if os.path.isdir(path) else os.path.dirname(path) or "."
        for entry in found:
            normalised = os.path.normpath(entry)
            if normalised.endswith(".py") and not should_skip(normalised, exclude_patterns):
                trees.setdefault(normalised, root)
    return (trees, missing)


def _read(path: str, result: ScanResult) -> str | None:
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except OSError as error:
        print(f"Error reading {path}: {error}", file=sys.stderr)
        result.had_error = True
        return None


def read_sources(paths: dict[str, str], result: ScanResult) -> dict[str, str]:
    sources: dict[str, str] = {}
    for path in sorted(paths):
        content = _read(path, result)
        if content is not None:
            sources[path] = content
    return sources


def read_fields(
    paths: dict[str, str], sources: dict[str, str], result: ScanResult, verbose: bool = False
) -> list[Field]:
    found: list[Field] = []
    for path in sorted(paths):
        if path not in sources:
            continue
        if verbose:
            print(f"Scanning: {path}")
        try:
            found.extend(declared_fields(path, sources[path], package_of(path, paths[path])))
        except SyntaxError as error:
            print(f"Syntax error in {path}: {error}", file=sys.stderr)
            result.had_error = True
            continue
        result.files_scanned += 1
    result.fields_declared = len(found)
    return found


def split_assumed(fields: list[Field], patterns: list[str]) -> tuple[list[Field], list[Field]]:
    to_check: list[Field] = []
    assumed: list[Field] = []
    for declared in fields:
        chosen = assumed if assumed_read(declared.name, patterns) else to_check
        chosen.append(declared)
    return (to_check, assumed)


def report_unparsed(searched: Searched) -> None:
    for path in searched.unparsed:
        print(f"Skipping (will not parse): {path}")


def output_findings(findings: list[Finding]) -> None:
    for finding in findings:
        print(finding)


def determine_exit_code(result: ScanResult) -> int:
    if result.findings:
        return EXIT_FINDINGS
    if result.had_error:
        return EXIT_ERROR
    return EXIT_SUCCESS


def _report(result: ScanResult, args: argparse.Namespace) -> None:
    if args.verbose:
        print()
        print(f"Files scanned: {result.files_scanned}")
        print(f"Fields declared: {result.fields_declared}")
        if result.assumed:
            print(f"Assumed read by name: {result.assumed}")
        print(f"Findings: {len(result.findings)}")
        for finding in result.findings:
            print(f"  Unread: {finding}")
        if result.had_error:
            print("Errors occurred during scanning.")
        return
    if not args.quiet:
        output_findings(result.findings)


def _announce(declarations: int, searches: int, excludes: list[str]) -> None:
    print(f"Reading {declarations} declaration file(s)...")
    print(f"Searching {searches} file(s) for reads.")
    if excludes:
        print(f"Excluding patterns: {', '.join(excludes)}")
    print()


def main(argv: Sequence[str] | None = None) -> None:
    args = create_parser().parse_args(argv)
    exclude_patterns = parse_patterns(args.exclude)
    result = ScanResult()

    field_paths, missing = _collect(args.trees, exclude_patterns)
    search_paths, search_missing = _collect(args.search_in or args.trees, exclude_patterns)
    missing.extend(search_missing)

    for path in missing:
        print(f"Error: Path not found: {path}", file=sys.stderr)
    if not field_paths and missing:
        sys.exit(EXIT_ERROR)
    if missing:
        result.had_error = True

    if args.verbose:
        _announce(len(field_paths), len(search_paths), exclude_patterns)

    sources = read_sources({**search_paths, **field_paths}, result)
    fields = read_fields(field_paths, sources, result, args.verbose)
    to_check, assumed = split_assumed(fields, parse_patterns(args.assume_read_matching))
    result.assumed = len(assumed)

    to_search = {path: content for path, content in sources.items() if path in search_paths}
    searched = read_searched(to_search, owner_names(fields))
    if args.verbose:
        report_unparsed(searched)

    result.findings = unread_fields(to_check, searched, args.dont_search_in)
    _report(result, args)
    sys.exit(determine_exit_code(result))
