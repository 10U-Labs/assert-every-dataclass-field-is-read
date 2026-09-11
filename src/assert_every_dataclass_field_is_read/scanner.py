from __future__ import annotations

import ast
import fnmatch
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

DATACLASS = "dataclass"
CLASS_VAR = "ClassVar"
SELF = "self"
GETATTR = "getattr"
SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
SPREAD_PATHS = (
    "asdict",
    "astuple",
    "replace",
    "dataclasses.asdict",
    "dataclasses.astuple",
    "dataclasses.replace",
)
MAPPINGS = ("dict", "Dict", "Mapping", "MutableMapping", "OrderedDict", "defaultdict")
SEQUENCES = (
    "list",
    "List",
    "set",
    "Set",
    "frozenset",
    "tuple",
    "Tuple",
    "Sequence",
    "Iterable",
    "Iterator",
    "Collection",
)


@dataclass(frozen=True)
class Field:
    path: str
    line_number: int
    owner: str
    name: str
    package: str | None = None
    holds: tuple[str, ...] = ()

    def __str__(self) -> str:
        return f"{self.path}:{self.line_number}:{self.owner}.{self.name}"


@dataclass(frozen=True)
class Finding:
    unread: Field

    def __str__(self) -> str:
        return str(self.unread)


@dataclass
class Reads:
    owned: set[tuple[str, str]] = field(default_factory=set)
    loose: set[str] = field(default_factory=set)
    spread: set[str] = field(default_factory=set)

    def merge(self, other: Reads) -> None:
        self.owned |= other.owned
        self.loose |= other.loose
        self.spread |= other.spread

    def reads(self, declared: Field) -> bool:
        return (
            declared.owner in self.spread
            or (declared.owner, declared.name) in self.owned
            or declared.name in self.loose
        )


@dataclass(frozen=True)
class Held:
    classes: frozenset[str]
    owner_of: dict[str, str] = field(default_factory=dict)
    element_of: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Searched:
    per_file: dict[str, Reads]
    unparsed: tuple[str, ...]


def _dotted(node: ast.expr) -> str | None:
    if isinstance(node, ast.Call):
        return _dotted(node.func)
    if isinstance(node, ast.Attribute):
        parent = _dotted(node.value)
        return None if parent is None else f"{parent}.{node.attr}"
    if isinstance(node, ast.Name):
        return node.id
    return None


def _tail(dotted: str | None) -> str | None:
    return None if dotted is None else dotted.split(".")[-1]


def is_dataclass_definition(node: ast.ClassDef) -> bool:
    return any(_tail(_dotted(item)) == DATACLASS for item in node.decorator_list)


def _candidates(annotation: ast.expr | None) -> tuple[str, ...]:
    if isinstance(annotation, ast.BinOp):
        return _candidates(annotation.left) + _candidates(annotation.right)
    if isinstance(annotation, ast.Subscript):
        return _candidates(annotation.value)
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        return (annotation.value.split("[")[0].strip().split(".")[-1],)
    named = _tail(_dotted(annotation)) if annotation is not None else None
    return () if named is None else (named,)


def is_class_var(annotation: ast.expr) -> bool:
    return CLASS_VAR in _candidates(annotation)


def _resolve(candidates: Iterable[str], classes: frozenset[str]) -> str | None:
    for named in candidates:
        if named in classes:
            return named
    return None


def _annotated_class(annotation: ast.expr | None, classes: frozenset[str]) -> str | None:
    return _resolve(_candidates(annotation), classes)


def _slice_of(annotation: ast.Subscript) -> ast.expr | None:
    container = _tail(_dotted(annotation.value))
    held = annotation.slice
    if isinstance(held, ast.Tuple):
        wanted = 1 if container in MAPPINGS else 0
        return held.elts[wanted] if len(held.elts) > wanted else None
    return None if container in MAPPINGS else held


def _element_candidates(annotation: ast.expr | None) -> tuple[str, ...]:
    if isinstance(annotation, ast.BinOp):
        return _element_candidates(annotation.left) + _element_candidates(annotation.right)
    if not isinstance(annotation, ast.Subscript):
        return ()
    container = _tail(_dotted(annotation.value))
    if container not in MAPPINGS and container not in SEQUENCES:
        return ()
    held = _slice_of(annotation)
    return _candidates(held) if held is not None else ()


def _element_class(annotation: ast.expr | None, classes: frozenset[str]) -> str | None:
    return _resolve(_element_candidates(annotation), classes)


def _fields_of(node: ast.ClassDef, path: str, package: str | None) -> Iterator[Field]:
    for statement in node.body:
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            if not is_class_var(statement.annotation):
                yield Field(
                    path=path,
                    line_number=statement.lineno,
                    owner=node.name,
                    name=statement.target.id,
                    package=package,
                    holds=_candidates(statement.annotation)
                    + _element_candidates(statement.annotation),
                )


def declared_fields(path: str, content: str, package: str | None = None) -> list[Field]:
    tree = ast.parse(content, filename=path)
    return [
        declared
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and is_dataclass_definition(node)
        for declared in _fields_of(node, path, package)
    ]


def _annotation_of(node: ast.AST) -> tuple[str, ast.expr | None] | None:
    if isinstance(node, ast.arg):
        return (node.arg, node.annotation)
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return (node.target.id, node.annotation)
    return None


def _hold_annotated(node: ast.AST, held: Held) -> None:
    annotated = _annotation_of(node)
    if annotated is None:
        return
    name, annotation = annotated
    owner = _annotated_class(annotation, held.classes)
    if owner is not None:
        held.owner_of[name] = owner
    element = _element_class(annotation, held.classes)
    if element is not None:
        held.element_of[name] = element


def _returned_classes(tree: ast.Module, classes: frozenset[str]) -> dict[str, str]:
    returning: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            owner = _annotated_class(node.returns, classes)
            if owner is not None:
                returning[node.name] = owner
    return returning


def _called_class(node: ast.Call, held: Held, returning: dict[str, str]) -> str | None:
    called = _tail(_dotted(node.func))
    if called is None:
        return None
    if called in held.classes:
        return called
    return returning.get(called)


def _hold_constructed(node: ast.AST, held: Held, returning: dict[str, str]) -> None:
    if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
        return
    owner = _called_class(node.value, held, returning)
    if owner is None:
        return
    for target in node.targets:
        if isinstance(target, ast.Name):
            held.owner_of[target.id] = owner


def _iterated(node: ast.AST) -> tuple[ast.expr, ast.expr] | None:
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return (node.target, node.iter)
    if isinstance(node, ast.comprehension):
        return (node.target, node.iter)
    return None


def _hold_iterated(node: ast.AST, held: Held) -> None:
    iterated = _iterated(node)
    if iterated is None:
        return
    target, source = iterated
    if not isinstance(target, ast.Name) or not isinstance(source, ast.Name):
        return
    element = held.element_of.get(source.id)
    if element is not None:
        held.owner_of[target.id] = element


def _own_nodes(node: ast.AST) -> Iterator[ast.AST]:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, SCOPES):
            continue
        yield child
        yield from _own_nodes(child)


def _scopes_in(node: ast.AST) -> Iterator[ast.AST]:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, SCOPES):
            yield child
        else:
            yield from _scopes_in(child)


def _inner_scope(held: Held) -> Held:
    return Held(
        classes=held.classes,
        owner_of=dict(held.owner_of),
        element_of=dict(held.element_of),
    )


def _attribute_read(node: ast.AST) -> ast.Attribute | None:
    if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
        return node
    if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Attribute):
        return node.target
    return None


def _record_attribute(node: ast.AST, held: Held, found: Reads) -> None:
    attribute = _attribute_read(node)
    if attribute is None:
        return
    base = attribute.value
    if not isinstance(base, ast.Name):
        found.loose.add(attribute.attr)
        return
    if base.id == SELF:
        return
    owner = held.owner_of.get(base.id, base.id if base.id in held.classes else None)
    if owner is None:
        found.loose.add(attribute.attr)
        return
    found.owned.add((owner, attribute.attr))


def _record_getattr(node: ast.Call, found: Reads) -> None:
    for argument in node.args[1:2]:
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            found.loose.add(argument.value)


def _record_spread(node: ast.Call, held: Held, found: Reads) -> None:
    first = node.args[0] if node.args else None
    owner = held.owner_of.get(first.id) if isinstance(first, ast.Name) else None
    if owner is not None:
        found.spread.add(owner)


def _record_call(node: ast.AST, held: Held, found: Reads) -> None:
    if not isinstance(node, ast.Call):
        return
    dotted = _dotted(node.func)
    if dotted == GETATTR:
        _record_getattr(node, found)
        return
    if dotted in SPREAD_PATHS:
        _record_spread(node, held, found)


def _owners_of(node: ast.ClassDef) -> tuple[str, ...]:
    inherited = (_tail(_dotted(base)) for base in node.bases)
    return (node.name, *(name for name in inherited if name is not None))


def _record_self_in(node: ast.ClassDef, found: Reads) -> None:
    owners = _owners_of(node)
    for inner in ast.walk(node):
        attribute = _attribute_read(inner)
        if attribute is None or not isinstance(attribute.value, ast.Name):
            continue
        if attribute.value.id == SELF:
            found.owned.update((owner, attribute.attr) for owner in owners)


def _record_self(tree: ast.Module, found: Reads) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            _record_self_in(node, found)


def _visit(node: ast.AST, held: Held, returning: dict[str, str], found: Reads) -> None:
    own = list(_own_nodes(node))
    for inner in own:
        _hold_annotated(inner, held)
        _hold_constructed(inner, held, returning)
        _hold_iterated(inner, held)
    for inner in own:
        _record_attribute(inner, held, found)
        _record_call(inner, held, found)
    for scope in _scopes_in(node):
        _visit(scope, _inner_scope(held), returning, found)


def reads_in(path: str, content: str, classes: frozenset[str]) -> Reads:
    tree = ast.parse(content, filename=path)
    found = Reads()
    _visit(tree, Held(classes=classes), _returned_classes(tree, classes), found)
    _record_self(tree, found)
    return found


def read_searched(sources: dict[str, str], classes: frozenset[str]) -> Searched:
    per_file: dict[str, Reads] = {}
    unparsed: list[str] = []
    for path in sorted(sources):
        try:
            per_file[path] = reads_in(path, sources[path], classes)
        except SyntaxError:
            unparsed.append(path)
    return Searched(per_file=per_file, unparsed=tuple(unparsed))


def owner_names(fields: Iterable[Field]) -> frozenset[str]:
    return frozenset(declared.owner for declared in fields)


def _left_out(path: str, template: str | None, package: str | None) -> bool:
    if template is None or package is None:
        return False
    prefix = os.path.normpath(template.format(package=package))
    return path == prefix or path.startswith(prefix + os.sep)


def _reads_outside(searched: Searched, template: str | None, package: str | None) -> Reads:
    merged = Reads()
    for path, found in searched.per_file.items():
        if not _left_out(path, template, package):
            merged.merge(found)
    return merged


def assumed_read(name: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


def _nesting(fields: Iterable[Field]) -> dict[str, set[str]]:
    nesting: dict[str, set[str]] = {}
    for declared in fields:
        nesting.setdefault(declared.owner, set()).update(declared.holds)
    return nesting


def _spread_through(spread: set[str], nesting: Mapping[str, set[str]]) -> set[str]:
    reached = set(spread)
    pending = list(spread)
    while pending:
        owner = pending.pop()
        for held in nesting.get(owner, ()):
            if held not in reached:
                reached.add(held)
                pending.append(held)
    return reached


def unread_fields(
    fields: Iterable[Field], searched: Searched, dont_search_in: str | None = None
) -> list[Finding]:
    declared_fields_given = list(fields)
    nesting = _nesting(declared_fields_given)
    merged: dict[str | None, Reads] = {}
    findings: list[Finding] = []
    for declared in declared_fields_given:
        if declared.package not in merged:
            found = _reads_outside(searched, dont_search_in, declared.package)
            found.spread = _spread_through(found.spread, nesting)
            merged[declared.package] = found
        if not merged[declared.package].reads(declared):
            findings.append(Finding(unread=declared))
    return findings
