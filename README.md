# assert-every-dataclass-field-is-read

Assert that every field a dataclass declares is read somewhere.

## Why

A dataclass field is written on every instance whether or not anything
wants it. The generated `__init__` stores what it is handed, so the
write is automatic and guaranteed. Only a read is evidence that the
field is still wanted, and a read is what disappears quietly.

Delete the last line that reads a field and nothing reports it. The
program still runs, the field is still declared, every caller still has
to supply a value, and the tests covering the field still pass, because
they construct their own instance and assert on a value they passed in
themselves. The declaration has become a claim about the program that is
no longer true, and the test suite is the thing that hides it.

This tool asks the other question. For every field declared by a
`@dataclass` in the trees you point it at, it asks whether anything
reads the value back, and reports the ones nothing does.

## Installation

```bash
pip install assert-every-dataclass-field-is-read
```

## Usage

```bash
# Every dataclass field in the program must be read by the program
assert-every-dataclass-field-is-read src lib/python scripts

# Search the tests too, but not the tests belonging to the package
# whose field is being checked
assert-every-dataclass-field-is-read lib/python \
  --search-in lib/python --search-in test \
  --dont-search-in 'test/lib/python/{package}'
```

The first form is the one to reach for. Leaving the test tree out of the
search entirely is both simpler and stricter than excusing a package's
own tests, and it is the right default whenever the trees you check are
the deployed program rather than test support code.

Reach for `--dont-search-in` when a tree holds dataclasses that tests are
entitled to read — fixtures, doubles, helpers — and you still want a
field kept alive only by its own tests to be reported.

### Options

| Option | Effect |
| --- | --- |
| `--search-in PATH` | A tree to search for reads. Repeatable. |
| `--dont-search-in TEMPLATE` | Template holding `{package}`, left out. |
| `--exclude PATTERNS` | Comma-separated globs to leave out of both trees. |
| `--assume-read-matching PATTERNS` | Globs of field names a runtime reads. |
| `--quiet` | Print nothing; report through the exit code. |
| `--verbose` | Print each file scanned, each one skipped, and a summary. |

### Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Every field is read. |
| 1 | At least one field is read by nothing. |
| 2 | A path was missing, unreadable, or would not parse. |

## What counts as a read

A field `Widget.color` is read when the tool can see an expression that
fetches it. It pairs an attribute with the class that owns it, rather
than matching the bare name, so a local variable called `color` is not
mistaken for a read of the field.

| Shape | Resolved through |
| --- | --- |
| `widget.color` | An argument or variable annotated `Widget`. |
| `widget.color` | A local assigned from `Widget(...)`. |
| `widget.color` | A local assigned from a function returning `Widget`. |
| `Widget.color` | The class itself. |
| `self.color` | The body of `Widget` or of a subclass. |
| `widget.color += 1` | An augmented assignment still reads first. |
| `row.color` | A loop or comprehension over `list[Widget]`. |
| `getattr(widget, "color")` | The name given as a string. |
| `asdict(widget)` | Every field of `Widget`, and of what it holds. |

Annotations are resolved through `X | None`, quoted forms, and the
element of a container (`list[X]`, `tuple[X, ...]`, `dict[K, X]` and
their typing equivalents). Variables are scoped per function, so a name
bound in one function says nothing about the same name in another.

Writes do not count. `widget.color = "red"` is how the field is filled
in, not evidence that anything wants it, and `dataclasses.replace` is
treated as a read only when the instance it is handed resolves to a
class.

### What it does not see

An attribute read whose base cannot be resolved to a class — a bare
parameter, a subscript, a chained attribute — is counted as a read of
every field of that name, because reporting it would be a guess. So a
field whose name is shared with an attribute read loosely somewhere else
is not reported.

A field a runtime reads for you, through a serializer or a template, has
no read to find. Name it with `--assume-read-matching` rather than
leaving it to be reported.

`ClassVar` annotations and unannotated class attributes are not
dataclass fields, and are not checked.

## GitHub Action

```yaml
- uses: 10U-Labs/assert-every-dataclass-field-is-read@latest
  with:
    trees: src lib/python scripts
    verbose: "true"
```

| Input | Effect |
| --- | --- |
| `trees` | Trees holding the dataclasses to check. Required. |
| `search-in` | Trees to search for reads, space-separated. |
| `dont-search-in` | Template holding `{package}` to leave out. |
| `exclude` | Comma-separated globs to exclude files. |
| `assume-read-matching` | Comma-separated globs of field names. |
| `quiet` | Suppress output, exit code only. |
| `verbose` | Show trees read, fields found, findings, summary. |

## License

Apache-2.0.
