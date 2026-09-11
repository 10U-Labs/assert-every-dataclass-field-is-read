from __future__ import annotations

from typing import TYPE_CHECKING

from assert_every_dataclass_field_is_read.scanner import (
    Field,
    Finding,
    Reads,
    declared_fields,
    read_searched,
    reads_in,
    unread_fields,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

MODULE = "m.py"

PAIR = """
from dataclasses import dataclass

@dataclass
class Widget:
    name: str
    color: str
"""

READS_NAME_ONLY = """
from dataclasses import dataclass

@dataclass
class Widget:
    name: str
    color: str

def render(widget: Widget) -> str:
    return widget.name
"""

ALL_READ = """
from dataclasses import dataclass

@dataclass
class Widget:
    name: str
    color: str

def render(widget: Widget) -> str:
    return widget.name + widget.color
"""

NESTED = """
from dataclasses import dataclass

@dataclass
class Inner:
    depth: int

@dataclass
class Outer:
    inner: Inner
"""


def fields_for(source: str, package: str | None = None) -> list[Field]:
    return declared_fields(MODULE, source, package)


def names_in(source: str) -> list[str]:
    return [declared.name for declared in fields_for(source)]


def reads_for(source: str, classes: Iterable[str] = ()) -> Reads:
    return reads_in(MODULE, source, frozenset(classes))


def owned_in(source: str, classes: Iterable[str] = ()) -> set[tuple[str, str]]:
    return reads_for(source, classes).owned


def loose_in(source: str, classes: Iterable[str] = ()) -> set[str]:
    return reads_for(source, classes).loose


def spread_in(source: str, classes: Iterable[str] = ()) -> set[str]:
    return reads_for(source, classes).spread


def findings_over(
    declaration: str, searched: dict[str, str], dont_search_in: str | None = None
) -> list[Finding]:
    fields = fields_for(declaration)
    owners = frozenset(declared.owner for declared in fields)
    return unread_fields(fields, read_searched(searched, owners), dont_search_in)


def shown(finding: Finding) -> str:
    return f"{finding.unread.owner}.{finding.unread.name}"


def unread_names(declaration: str, searched: dict[str, str]) -> list[str]:
    return [shown(finding) for finding in findings_over(declaration, searched)]


def holding(owner: str, name: str, holds: tuple[str, ...] = ()) -> Field:
    return Field(path=MODULE, line_number=1, owner=owner, name=name, holds=holds)


DECLARED = """
from dataclasses import dataclass
from typing import ClassVar

@dataclass
class Plain:
    read_by_arg: str
    read_by_local: str
    read_by_class: str
    read_by_self: str
    read_by_getattr: str
    read_by_loop: str
    read_by_comprehension: str
    read_by_mapping: str
    read_by_tuple: str
    read_by_union: str
    read_by_quoted: str
    read_by_return: str
    read_by_augment: int
    read_by_loose: str
    read_by_chain: str
    read_by_base: str
    size: int
    never_read: str
    kind: ClassVar[str] = "plain"
    quoted_kind: "ClassVar[int]" = 0
    material = "steel"

    def shout(self) -> str:
        return self.read_by_self + helper.size


@dataclass
class Fancy(Plain):
    extra: str = ""

    def announce(self) -> str:
        return self.read_by_base + self.extra
"""

SPREAD = """
from dataclasses import dataclass

@dataclass
class Inner:
    depth: int

@dataclass
class Outer:
    inner: Inner
    label: str

@dataclass(frozen=True)
class Alpha:
    beta: "Beta"

@dataclass(frozen=True)
class Beta:
    alpha: Alpha
    weight: int
"""

READERS = """
import dataclasses
from dataclasses import asdict, replace

from widgets.declared import Plain
from widgets.spread import Alpha, Outer


def by_arg(plain: Plain) -> str:
    return plain.read_by_arg


def by_local() -> str:
    made = Plain()
    return made.read_by_local


def by_class() -> str:
    return Plain.read_by_class


def by_getattr(thing) -> str:
    return getattr(thing, "read_by_getattr")


def by_unknown_getattr(thing, wanted) -> str:
    return getattr(thing, wanted) + getattr(thing)


def by_loop(rows: list[Plain]) -> list[str]:
    found = []
    for row in rows:
        found.append(row.read_by_loop)
    return found


def by_comprehension(rows: list[Plain]) -> list[str]:
    return [row.read_by_comprehension for row in rows]


def by_mapping(held: dict[str, Plain]) -> list[str]:
    return [row.read_by_mapping for row in held]


def by_tuple(rows: tuple[Plain, ...]) -> list[str]:
    return [row.read_by_tuple for row in rows]


def by_union(plain: Plain | None) -> str:
    return plain.read_by_union


def by_quoted(plain: "Plain") -> str:
    return plain.read_by_quoted


def build() -> Plain:
    return Plain()


def by_return() -> str:
    made = build()
    return made.read_by_return


def by_augment(plain: Plain) -> None:
    plain.read_by_augment += 1


def by_loose(thing) -> str:
    return thing.read_by_loose + thing.inner.read_by_chain


def by_spread(outer: Outer, alpha: Alpha) -> tuple:
    return asdict(outer), dataclasses.astuple(alpha)


def unresolved(row, name: str) -> None:
    replace(row, depth=1)
    replace()
    name.replace("a", "b")


def unnameable() -> None:
    spare = builders[0]()
    other = unknown()
    first, second = Plain()
    print(spare.size, other.size, first.size)


def odd_containers(held: Holder[Plain], bare: dict, one: dict[Plain], short: dict[str,]) -> None:
    for row in held:
        print(row.size)
    for row in bare:
        print(row.size)
    for row in one:
        print(row.size)
    for row in short:
        print(row.size)


def odd_iteration(rows: list[Plain] | None, pairs: list[Plain]) -> None:
    for row in rows:
        print(row.size)
    for row in rows.values():
        print(row.size)
    for left, right in pairs:
        print(left.size)


def stores(plain: Plain) -> None:
    plain.never_read = "x"
"""

SHAPES = {
    "src/widgets/declared.py": DECLARED,
    "src/widgets/spread.py": SPREAD,
    "src/readers/read_them.py": READERS,
}


def searching_both(template: str | None = None) -> list[str]:
    args = ["src", "--search-in", "src", "--search-in", "test"]
    return args if template is None else [*args, "--dont-search-in", template]
