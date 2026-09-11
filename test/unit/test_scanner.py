from __future__ import annotations

import ast
from test.samples import (
    MODULE,
    NESTED,
    PAIR,
    READS_NAME_ONLY,
    fields_for,
    findings_over,
    holding,
    loose_in,
    names_in,
    owned_in,
    spread_in,
    unread_names,
)

from assert_every_dataclass_field_is_read.scanner import (
    Reads,
    assumed_read,
    declared_fields,
    is_class_var,
    is_dataclass_definition,
    owner_names,
    read_searched,
    unread_fields,
)


def _class_in(source: str) -> ast.ClassDef:
    found = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ClassDef)]
    return found[0]


def _annotation_in(source: str) -> ast.expr:
    found = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.AnnAssign)]
    return found[0].annotation


def test_declares_both_fields() -> None:
    assert names_in(PAIR) == ["name", "color"]


def test_records_the_owner() -> None:
    assert fields_for(PAIR)[0].owner == "Widget"


def test_records_the_line_number() -> None:
    assert fields_for(PAIR)[0].line_number == 6


def test_records_the_path() -> None:
    assert fields_for(PAIR)[0].path == MODULE


def test_records_the_package() -> None:
    assert fields_for(PAIR, "widgets")[0].package == "widgets"


def test_package_defaults_to_none() -> None:
    assert fields_for(PAIR)[0].package is None


def test_field_prints_owner_and_name() -> None:
    assert str(fields_for(PAIR)[0]) == f"{MODULE}:6:Widget.name"


def test_ignores_a_plain_class() -> None:
    assert names_in("class Widget:\n    name: str\n") == []


def test_ignores_a_subscripted_class_var() -> None:
    source = (
        "from dataclasses import dataclass\n@dataclass\nclass W:\n"
        "    kind: ClassVar[str] = 'w'\n"
    )
    assert names_in(source) == []


def test_ignores_a_bare_class_var() -> None:
    source = "from dataclasses import dataclass\n@dataclass\nclass W:\n    kind: ClassVar = 'w'\n"
    assert names_in(source) == []


def test_ignores_a_quoted_class_var() -> None:
    source = (
        "from dataclasses import dataclass\n@dataclass\nclass W:\n    kind: 'ClassVar[str]' = 'w'\n"
    )
    assert names_in(source) == []


def test_ignores_an_unannotated_assignment() -> None:
    source = "from dataclasses import dataclass\n@dataclass\nclass W:\n    material = 'steel'\n"
    assert names_in(source) == []


def test_ignores_a_method() -> None:
    source = (
        "from dataclasses import dataclass\n@dataclass\nclass W:\n"
        "    def shout(self): return 1\n"
    )
    assert names_in(source) == []


def test_reads_a_dotted_decorator() -> None:
    source = "import dataclasses\n@dataclasses.dataclass\nclass W:\n    name: str\n"
    assert names_in(source) == ["name"]


def test_reads_a_called_decorator() -> None:
    source = "from dataclasses import dataclass\n@dataclass(frozen=True)\nclass W:\n    name: str\n"
    assert names_in(source) == ["name"]


def test_ignores_an_unnameable_decorator() -> None:
    source = "@marks[0]\nclass W:\n    name: str\n"
    assert names_in(source) == []


def test_holds_the_annotated_class() -> None:
    assert "Inner" in fields_for(NESTED)[1].holds


def test_holds_the_element_class() -> None:
    source = "from dataclasses import dataclass\n@dataclass\nclass W:\n    parts: list[Inner]\n"
    assert "Inner" in fields_for(source)[0].holds


def test_is_dataclass_definition_sees_the_decorator() -> None:
    assert is_dataclass_definition(_class_in(PAIR))


def test_is_dataclass_definition_refuses_a_plain_class() -> None:
    assert not is_dataclass_definition(_class_in("class W:\n    pass\n"))


def test_is_class_var_sees_a_subscript() -> None:
    assert is_class_var(_annotation_in("kind: ClassVar[str] = 'w'\n"))


def test_is_class_var_refuses_a_plain_annotation() -> None:
    assert not is_class_var(_annotation_in("kind: str = 'w'\n"))


def test_reads_an_annotated_argument() -> None:
    assert ("Widget", "name") in owned_in(READS_NAME_ONLY, ["Widget"])


def test_leaves_the_unread_field_unowned() -> None:
    assert ("Widget", "color") not in owned_in(READS_NAME_ONLY, ["Widget"])


def test_reads_a_constructed_local() -> None:
    source = "w = Widget('a')\nprint(w.name)\n"
    assert ("Widget", "name") in owned_in(source, ["Widget"])


def test_reads_through_a_return_annotation() -> None:
    source = "def build() -> Widget: ...\nw = build()\nprint(w.name)\n"
    assert ("Widget", "name") in owned_in(source, ["Widget"])


def test_reads_an_annotated_assignment() -> None:
    source = "w: Widget = thing\nprint(w.name)\n"
    assert ("Widget", "name") in owned_in(source, ["Widget"])


def test_reads_a_union_annotation() -> None:
    source = "def f(w: Widget | None) -> None:\n    print(w.name)\n"
    assert ("Widget", "name") in owned_in(source, ["Widget"])


def test_reads_a_quoted_annotation() -> None:
    source = "def f(w: 'Widget') -> None:\n    print(w.name)\n"
    assert ("Widget", "name") in owned_in(source, ["Widget"])


def test_reads_the_class_itself() -> None:
    assert ("Widget", "name") in owned_in("print(Widget.name)\n", ["Widget"])


def test_reads_an_unknown_base_loosely() -> None:
    assert "name" in loose_in("print(thing.name)\n", ["Widget"])


def test_reads_a_chained_base_loosely() -> None:
    assert "tuning" in loose_in("print(thing.params.tuning)\n", ["Widget"])


def test_ignores_a_tuple_target_assignment() -> None:
    source = "a, b = Widget('x')\nprint(a.name)\n"
    assert ("Widget", "name") not in owned_in(source, ["Widget"])


def test_reads_self_for_the_class() -> None:
    source = "class Widget:\n    def shout(self):\n        return self.name\n"
    assert ("Widget", "name") in owned_in(source, ["Widget"])


def test_reads_self_for_a_base_class() -> None:
    source = "class Child(Widget):\n    def shout(self):\n        return self.name\n"
    assert ("Widget", "name") in owned_in(source, ["Widget", "Child"])


def test_ignores_an_unnameable_base() -> None:
    source = "class Child(bases[0]):\n    def shout(self):\n        return self.name\n"
    assert ("Child", "name") in owned_in(source, ["Child"])


def test_reads_an_augmented_attribute() -> None:
    source = "def f(w: Widget) -> None:\n    w.count += 1\n"
    assert ("Widget", "count") in owned_in(source, ["Widget"])


def test_ignores_a_written_attribute() -> None:
    source = "def f(w: Widget) -> None:\n    w.count = 1\n"
    assert ("Widget", "count") not in owned_in(source, ["Widget"])


def test_reads_a_getattr_name() -> None:
    assert "color" in loose_in("getattr(thing, 'color')\n")


def test_ignores_a_getattr_without_a_name() -> None:
    assert loose_in("getattr(thing)\n") == set()


def test_ignores_a_computed_getattr_name() -> None:
    assert loose_in("getattr(thing, wanted)\n") == set()


def test_spreads_a_resolved_asdict() -> None:
    source = "def f(w: Widget) -> None:\n    asdict(w)\n"
    assert spread_in(source, ["Widget"]) == {"Widget"}


def test_spreads_a_dotted_asdict() -> None:
    source = "def f(w: Widget) -> None:\n    dataclasses.asdict(w)\n"
    assert spread_in(source, ["Widget"]) == {"Widget"}


def test_ignores_an_unresolved_replace() -> None:
    assert spread_in("replace(row, required=1)\n", ["Widget"]) == set()


def test_ignores_a_replace_with_no_arguments() -> None:
    assert spread_in("replace()\n", ["Widget"]) == set()


def test_ignores_a_string_replace() -> None:
    source = "def f(w: Widget) -> None:\n    name.replace('a', 'b')\n"
    assert spread_in(source, ["Widget"]) == set()


def test_resolves_a_loop_element() -> None:
    source = "def f(rows: list[Widget]) -> None:\n    for row in rows:\n        replace(row)\n"
    assert spread_in(source, ["Widget"]) == {"Widget"}


def test_resolves_a_comprehension_element() -> None:
    source = "def f(rows: list[Widget]) -> None:\n    [row.name for row in rows]\n"
    assert ("Widget", "name") in owned_in(source, ["Widget"])


def test_resolves_an_async_loop_element() -> None:
    source = (
        "async def f(rows: list[Widget]) -> None:\n    async for row in rows:\n"
        "        print(row.name)\n"
    )
    assert ("Widget", "name") in owned_in(source, ["Widget"])


def test_resolves_a_mapping_value() -> None:
    source = (
        "def f(held: dict[str, Widget]) -> None:\n    for row in held:\n"
        "        print(row.name)\n"
    )
    assert ("Widget", "name") in owned_in(source, ["Widget"])


def test_resolves_a_tuple_element() -> None:
    source = (
        "def f(rows: tuple[Widget, ...]) -> None:\n    for row in rows:\n"
        "        print(row.name)\n"
    )
    assert ("Widget", "name") in owned_in(source, ["Widget"])


def test_ignores_a_mapping_without_a_value_type() -> None:
    source = "def f(held: dict) -> None:\n    for row in held:\n        print(row.name)\n"
    assert ("Widget", "name") not in owned_in(source, ["Widget"])


def test_ignores_a_short_mapping_annotation() -> None:
    source = "def f(held: dict[str]) -> None:\n    for row in held:\n        print(row.name)\n"
    assert ("Widget", "name") not in owned_in(source, ["Widget"])


def test_ignores_an_unknown_container() -> None:
    source = "def f(held: Holder[Widget]) -> None:\n    for row in held:\n        print(row.name)\n"
    assert ("Widget", "name") not in owned_in(source, ["Widget"])


def test_resolves_a_union_container() -> None:
    source = (
        "def f(rows: list[Widget] | None) -> None:\n    for row in rows:\n        print(row.name)\n"
    )
    assert ("Widget", "name") in owned_in(source, ["Widget"])


def test_ignores_an_unnamed_iteration_source() -> None:
    source = (
        "def f(rows: list[Widget]) -> None:\n    for row in rows.values():\n"
        "        print(row.name)\n"
    )
    assert ("Widget", "name") not in owned_in(source, ["Widget"])


def test_ignores_a_tuple_loop_target() -> None:
    source = "def f(rows: list[Widget]) -> None:\n    for a, b in rows:\n        print(a.name)\n"
    assert ("Widget", "name") not in owned_in(source, ["Widget"])


def test_merge_unions_the_owned_reads() -> None:
    left = Reads(owned={("Widget", "name")})
    left.merge(Reads(owned={("Widget", "color")}))
    assert left.owned == {("Widget", "name"), ("Widget", "color")}


def test_merge_unions_the_loose_reads() -> None:
    left = Reads(loose={"name"})
    left.merge(Reads(loose={"color"}))
    assert left.loose == {"name", "color"}


def test_merge_unions_the_spread_owners() -> None:
    left = Reads(spread={"Widget"})
    left.merge(Reads(spread={"Gadget"}))
    assert left.spread == {"Widget", "Gadget"}


def test_reads_answers_for_an_owned_pair() -> None:
    assert Reads(owned={("Widget", "name")}).reads(holding("Widget", "name"))


def test_reads_answers_for_a_loose_name() -> None:
    assert Reads(loose={"name"}).reads(holding("Widget", "name"))


def test_reads_answers_for_a_spread_owner() -> None:
    assert Reads(spread={"Widget"}).reads(holding("Widget", "name"))


def test_reads_refuses_an_untouched_field() -> None:
    assert not Reads().reads(holding("Widget", "name"))


def test_records_an_unparsed_file() -> None:
    assert read_searched({MODULE: "def ("}, frozenset()).unparsed == (MODULE,)


def test_keeps_a_parsed_file() -> None:
    assert MODULE in read_searched({MODULE: "x = 1\n"}, frozenset()).per_file


def test_owner_names_collects_the_classes() -> None:
    assert owner_names(fields_for(NESTED)) == frozenset({"Inner", "Outer"})


def test_assumed_read_matches_a_pattern() -> None:
    assert assumed_read("name", ["na*"])


def test_assumed_read_refuses_a_miss() -> None:
    assert not assumed_read("color", ["na*"])


def test_reports_a_field_nothing_reads() -> None:
    assert unread_names(PAIR, {MODULE: PAIR}) == ["Widget.name", "Widget.color"]


def test_stays_silent_on_a_read_field() -> None:
    assert unread_names(READS_NAME_ONLY, {MODULE: READS_NAME_ONLY}) == ["Widget.color"]


def test_finding_carries_the_field() -> None:
    assert findings_over(PAIR, {MODULE: PAIR})[0].unread.owner == "Widget"


def test_finding_prints_as_the_field() -> None:
    assert str(findings_over(PAIR, {MODULE: PAIR})[0]) == f"{MODULE}:6:Widget.name"


def test_spread_reaches_a_nested_class() -> None:
    reader = "def f(o: Outer) -> None:\n    asdict(o)\n"
    assert unread_names(NESTED, {MODULE: NESTED, "r.py": reader}) == []


def test_spread_stops_on_a_cycle() -> None:
    looped = (
        "from dataclasses import dataclass\n@dataclass\nclass A:\n    b: 'B'\n"
        "@dataclass\nclass B:\n    a: A\n"
    )
    reader = "def f(a: A) -> None:\n    asdict(a)\n"
    assert unread_names(looped, {MODULE: looped, "r.py": reader}) == []


def test_leaves_out_the_named_tree() -> None:
    fields = declared_fields("src/widgets/w.py", PAIR, "widgets")
    searched = read_searched({"test/widgets/t.py": READS_NAME_ONLY}, frozenset({"Widget"}))
    assert len(unread_fields(fields, searched, "test/{package}")) == 2


def test_keeps_a_tree_that_is_not_named() -> None:
    fields = declared_fields("src/widgets/w.py", PAIR, "widgets")
    searched = read_searched({"test/gadgets/t.py": READS_NAME_ONLY}, frozenset({"Widget"}))
    assert len(unread_fields(fields, searched, "test/{package}")) == 1


def test_leaves_out_an_exactly_named_file() -> None:
    fields = declared_fields("src/widgets/w.py", PAIR, "widgets")
    searched = read_searched({"test/widgets": READS_NAME_ONLY}, frozenset({"Widget"}))
    assert len(unread_fields(fields, searched, "test/{package}")) == 2


def test_searches_everything_without_a_package() -> None:
    fields = declared_fields("w.py", PAIR, None)
    searched = read_searched({"test/widgets/t.py": READS_NAME_ONLY}, frozenset({"Widget"}))
    assert len(unread_fields(fields, searched, "test/{package}")) == 1


def test_ignores_an_unnameable_call_target() -> None:
    source = "w = builders[0]()\nprint(w.name)\n"
    assert ("Widget", "name") not in owned_in(source, ["Widget"])


def test_ignores_a_call_to_an_unknown_function() -> None:
    source = "w = other()\nprint(w.name)\n"
    assert ("Widget", "name") not in owned_in(source, ["Widget"])


def test_ignores_a_non_self_attribute_in_a_class() -> None:
    source = "class Widget:\n    def shout(self):\n        return other.name\n"
    assert ("Widget", "name") not in owned_in(source, ["Widget"])
