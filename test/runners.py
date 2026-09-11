from __future__ import annotations

import runpy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    WriteTree = Callable[[dict[str, str]], Path]
    RunCli = Callable[[list[str]], tuple[int, str, str]]
    RunOver = Callable[[dict[str, str], list[str]], tuple[int, str, str]]
    StdoutOf = Callable[[dict[str, str], list[str]], str]
    StderrOf = Callable[[dict[str, str], list[str]], str]
    ExitCodeOf = Callable[[dict[str, str], list[str]], int]


def build_runner(write: WriteTree, run: RunCli) -> RunOver:
    def runner(files: dict[str, str], args: list[str]) -> tuple[int, str, str]:
        write(files)
        return run(args)

    return runner


def module_exit_code(name: str) -> int | None:
    try:
        runpy.run_module(name, run_name="__main__")
    except SystemExit as exited:
        return int(exited.code) if exited.code is not None else 0
    return None
