# Python 3.14.3 Code Quality Reference
## Use this to steer LLM-generated Python code.

This contains concrete patterns for writing clean, auditable Python in a data reconciliation codebase. Favor correctness, deterministic behavior, explicit data models, and static typing over cleverness or terseness.
I've found guide maps helpful for steering the code generation process since this instruction set is a bit long. 

## Guide Map

Use this guide by task:

- Typing, aliases, `TypedDict`, and dataclass defaults: Sections 2 and 8.
- Function shape, guard clauses, and separation of concerns: Sections 4 and 6.
- Exceptions, validation, and issue reporting: Section 5.
- Paths, files, serialization, and logging: Section 7.
- Naming, module layout, comments, and docstrings: Sections 8 and 9.
- Tests and reconciliation-specific edge cases: Section 10.
- Common mistakes and what to write instead: Section 11.
- Ruff, mypy, and pytest defaults: Section 12.

### Fast Rules

- Prefer `TypedDict` at boundaries and dataclasses in core logic.
- Use `Decimal` for money and exact decimal quantities.
- Keep I/O at the edges and core logic pure.
- Make output deterministic and easy to diff.
- Validate inputs explicitly; do not rely on `assert`.

## 1. What This Guide Optimizes For

- Correctness over cleverness.
- Auditability over hidden magic.
- Explicit data-quality handling over silent coercion.
- Structured quality issues over log-only error reporting.
- Boundary normalization over scattered ad-hoc cleanup.
- Pure, testable logic over I/O-heavy functions.
- Stable, deterministic outputs that are easy to diff.
- Standard library first; add third-party dependencies only when they clearly improve clarity, correctness, or performance.

## 2. Python 3.14.3 Defaults

### Modern Typing and Annotations

```python
from typing import NotRequired, Protocol, ReadOnly, Self, TypedDict

type RecordId = str

class RawRow(TypedDict):
    sku: ReadOnly[str]
    quantity: str
    warehouse: NotRequired[str]

class Normalizer(Protocol):
    def __call__(self, raw: str) -> str: ...

class IssueCollector:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def add(self, message: str) -> Self:
        self.messages.append(message)
        return self
```

- Use built-in generics: `list[str]`, `dict[str, int]`, `set[str]`, `tuple[int, ...]`.
- Use the `type` statement for aliases in 3.14+ code. Do not introduce new `TypeAlias` declarations unless you are intentionally supporting older Python versions.
- Do not add `from __future__ import annotations` in 3.14-only modules. Annotation evaluation is already deferred.
- Forward references do not need quotes in normal 3.14 code. Use quotes only when a specific tool or compatibility constraint requires them.
- `X | None` means a value may be present and null. `NotRequired[X]` means a `TypedDict` key may be missing. Do not conflate them.
- Use `Self` for instance methods that return `self`.
- Use `Protocol` when callers care about behavior, not inheritance.
- Use `TypedDict` for external dict-shaped data such as CSV rows, JSON payloads, or config blobs.
- Avoid `Any`. If you truly need it at a boundary, isolate it and narrow it immediately.
- If runtime annotation introspection matters, use `annotationlib.get_annotations()` deliberately rather than relying on older eager-evaluation behavior.
- New 3.14 features like template string literals and `concurrent.interpreters` are specialized tools, not default style choices for ordinary business code.

### Prefer Explicit Models in Core Logic

```python
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

@dataclass(frozen=True, slots=True, kw_only=True)
class InventoryRecord:
    sku: str
    quantity: Decimal
    captured_at: datetime

    def __post_init__(self) -> None:
        if self.captured_at.tzinfo is None:
            raise ValueError("captured_at must be timezone-aware")
```

- Inside the reconciliation core, prefer `@dataclass(frozen=True, slots=True)` or a small class over raw `dict`.
- Use `kw_only=True` when a record has multiple same-looking fields and positional construction would be error-prone.
- Prefer `StrEnum` or `Enum` for closed sets of statuses and result kinds.
- Use `Decimal` for money and exact decimal quantities. Use `float` only when measurement noise is intrinsic and `math.isclose()` is the right comparison model.
- Use aware `datetime` values with `datetime.UTC`. Use `date` when time of day is irrelevant.

### Accept Abstract Inputs, Return Concrete Results

```python
from collections.abc import Iterable, Mapping

def build_index(records: Iterable[InventoryRecord]) -> dict[str, InventoryRecord]:
    return {record.sku: record for record in records}

def find_missing(
    source: Iterable[InventoryRecord],
    target_by_sku: Mapping[str, InventoryRecord],
) -> list[InventoryRecord]:
    return [record for record in source if record.sku not in target_by_sku]
```

- In parameters, prefer `Iterable`, `Mapping`, `Sequence`, and `Collection` when the function does not need a concrete container.
- In return types, prefer concrete collections like `list`, `dict`, and `set` when callers depend on materialized results.

## 3. Idiomatic Python

### Dictionary Access

```python
timeout = config.get("timeout", 30)

if "timeout" in config:
    timeout = config["timeout"]

counterpart = target_index.get(record_id)
if counterpart is not None:
    matched.append((record_id, counterpart))
else:
    unmatched.append(record_id)
```

- Use `dict.get()` with a default when missing keys are normal.
- Use `in` plus direct indexing when `None` is a valid stored value.
- Reserve `try`/`except KeyError` for truly exceptional cases.

### Truthiness

```python
if rows:                 # non-empty collection
    ...

if not name:             # empty string
    ...

if value is None:        # explicit sentinel check
    ...

if count == 0:           # explicit numeric comparison
    ...
```

- Use truthiness for empty/non-empty collections and strings.
- Be explicit with `None`, `0`, and other sentinel-like values that have domain meaning.
- Do not use truthiness when a falsey value is still valid business data.

### Comprehensions and Generators

```python
active_skus = [row["sku"] for row in rows if row["status"] == "active"]
has_error = any(result.status == Status.ERROR for result in results)
all_valid = all(issue.is_resolved for issue in issues)
```

- Use a comprehension for one `for` clause plus, at most, one simple `if`.
- Prefer generator expressions with `any()`, `all()`, `sum()`, and `max()` when you do not need an intermediate list.
- If the expression needs comments, exception handling, or multiple branches, write a loop or extract a helper.
- Never use a comprehension for side effects.

### Unpacking

```python
host, port = connection_info
first, *rest = values
sku, *_unused, quantity = row
config = defaults | overrides
```

- Unpack fixed-position data instead of indexing by magic number.
- Use `|` for dict merging in 3.14 code when creating a new mapping.

### Walrus Operator

Use it only when it removes real duplication and keeps the code easier to read.

```python
parsed_rows = [
    parsed
    for raw in raw_rows
    if (parsed := parse_row(raw)) is not None
]
```

Good places:
- `while` loops that read until empty input.
- comprehension filters where the computed value is immediately reused.

Bad places:
- nested conditions
- long boolean expressions
- anywhere a named intermediate variable is clearer

### Structural Pattern Matching

Use `match` when you have a closed set of structural cases. Do not force it into simple `if`/`elif` logic.

```python
from enum import StrEnum

class IssueKind(StrEnum):
    DUPLICATE_SKU = "duplicate_sku"
    INVALID_QUANTITY = "invalid_quantity"
    MISSING_SKU = "missing_sku"

def render_issue(kind: IssueKind) -> str:
    match kind:
        case IssueKind.DUPLICATE_SKU:
            return "Duplicate SKU"
        case IssueKind.INVALID_QUANTITY:
            return "Invalid quantity"
        case IssueKind.MISSING_SKU:
            return "Missing SKU"
        case _:
            raise AssertionError(f"Unhandled issue kind: {kind}")
```

## 4. Function Design

### Guard Clauses Over Nesting

```python
from decimal import Decimal

def comparable_quantity(record: InventoryRecord | None) -> Decimal | None:
    if record is None:
        return None
    if record.quantity <= 0:
        return None
    return record.quantity
```

- Handle invalid or edge cases first.
- Keep the happy path flat and obvious.
- Prefer early return over nested condition pyramids.

### Single Responsibility

Each function should do one thing. If you need the word "and" to describe it, split it.

```python
import csv
from pathlib import Path

def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]

def validate_rows(rows: list[dict[str, str]]) -> list[RawRow]:
    return [validate_row(row) for row in rows]

def canonicalize_rows(rows: list[RawRow]) -> list[InventoryRecord]:
    return [canonicalize_row(row) for row in rows]

def build_index(records: list[InventoryRecord]) -> dict[str, InventoryRecord]:
    return {record.sku: record for record in records}
```

### Pure Logic Separated from I/O

```python
from pathlib import Path

def reconcile_records(
    source: list[InventoryRecord],
    target: list[InventoryRecord],
) -> ReconciliationReport:
    target_by_sku = build_index(target)
    return compare_snapshots(source, target_by_sku)

def run_reconciliation(
    source_path: Path,
    target_path: Path,
    output_path: Path,
) -> None:
    source_raw_rows = load_rows(source_path)
    target_raw_rows = load_rows(target_path)
    source_rows = validate_rows(source_raw_rows)
    target_rows = validate_rows(target_raw_rows)
    source_records = canonicalize_rows(source_rows)
    target_records = canonicalize_rows(target_rows)
    report = reconcile_records(source_records, target_records)
    write_report(report, output_path)
```

- Pure functions are easy to test and reuse.
- I/O functions should be small, obvious, and boundary-focused.
- Orchestrators should read like a pipeline.

### Keyword-Only Options

```python
from decimal import Decimal

def reconcile(
    source: list[InventoryRecord],
    target: list[InventoryRecord],
    *,
    case_sensitive: bool = False,
    quantity_tolerance: Decimal = Decimal("0"),
) -> ReconciliationReport:
    ...
```

- Use `*` to make optional behavior keyword-only.
- Never pass multiple booleans positionally.
- If a function takes many configuration switches, consider a config dataclass instead.

### Function Size

Target small functions with one clear purpose.

Good signs:
- one level of abstraction per function
- the name accurately describes the whole body
- minimal branching and local state

Signs a function needs splitting:
- section-separating comments
- more than 3 levels of indentation
- multiple unrelated loops
- more than 3 positional parameters
- logging, parsing, business rules, and serialization mixed together

## 5. Error Handling

### Catch Narrow Exceptions and Add Context

```python
from decimal import Decimal, InvalidOperation

def parse_quantity(raw: str) -> Decimal | None:
    text = raw.strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid quantity: {raw!r}") from exc
```

- Catch the narrowest exception that represents the expected failure.
- Add domain context when re-raising.
- Use `raise ... from exc` to preserve the original cause.
- Catch exceptions where you can recover, translate, or add useful context. Do not catch them just to hide them.

### Assertions Are Not Input Validation

```python
def validate_header(columns: set[str]) -> None:
    missing = REQUIRED_COLUMNS - columns
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
```

- Use `assert` for internal invariants in tests or truly unreachable states.
- Do not use `assert` for user input, file contents, CSV structure, or API payload validation.

### Avoid Double Logging

- Either log an exception at the boundary where it is handled, or re-raise it for a higher layer to log.
- Do not log and re-raise the same error in multiple layers unless each layer adds meaningfully new context.

## 6. Data Flow and State

### Pipeline with Intermediate Variables

```python
source_raw_rows = load_rows(source_path)
target_raw_rows = load_rows(target_path)

source_rows = validate_rows(source_raw_rows)
target_rows = validate_rows(target_raw_rows)

source_records = canonicalize_rows(source_rows)
target_records = canonicalize_rows(target_rows)

report = reconcile_records(source_records, target_records)
write_report(report, output_path)
```

- Intermediate names make pipelines debuggable.
- Each step should be inspectable in a REPL, debugger, or failing test.
- Prefer explicit stages over dense one-liners.

### Deterministic Output

```python
def sorted_discrepancies(
    discrepancies: list[Discrepancy],
) -> list[Discrepancy]:
    return sorted(discrepancies, key=lambda item: item.sku)
```

- Sort output when order matters for reports, snapshots, or tests.
- Emit stable JSON keys when human diffability matters.
- Deterministic output reduces false-positive diffs and flaky tests.

### Mutable Defaults

```python
from dataclasses import dataclass, field

@dataclass(slots=True)
class ReportBuilder:
    issues: list[str] = field(default_factory=list)

def append_issue(issue: str, issues: list[str] | None = None) -> list[str]:
    if issues is None:
        issues = []
    issues.append(issue)
    return issues
```

- Never use mutable defaults like `[]`, `{}`, or `set()` in function signatures.
- Use `field(default_factory=...)` in dataclasses.
- Use `None` sentinel plus local initialization in functions.

## 7. I/O, Paths, and Serialization

### Prefer `pathlib.Path`

```python
from pathlib import Path

input_path = Path("data") / "snapshot_1.csv"
output_path = Path("output") / "reconciliation_report.json"
```

- Use `Path` internally instead of raw path strings.
- Accept `Path` in I/O-heavy functions once the caller has resolved the path.
- Convert to `str` only at integration boundaries that require it.

### Open Files Explicitly

```python
import json
from pathlib import Path

def write_report(report: dict[str, object], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, indent=2, sort_keys=True)
        f.write("\n")
```

- Always set `encoding="utf-8"` for text files.
- Use `newline=""` for CSV readers and writers.
- Use `newline="\n"` when writing plain text or JSON intended for stable diffs.
- Prefer `path.open()` over raw `open(path, ...)` once you already have a `Path`.

### Serialization Rules

- Serialize plain data, not rich domain objects.
- Convert dataclasses or models to dictionaries at the boundary.
- Avoid ad-hoc `default=` JSON encoders unless there is a shared, well-tested serialization policy.

```python
from dataclasses import asdict

payload = asdict(report)
```

### Logging Over `print`

```python
import csv
import logging
from pathlib import Path

log = logging.getLogger(__name__)

def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    log.info("Loaded %s rows from %s", len(rows), path)
    return rows
```

- Use `logging` in library or reusable code.
- Prefer lazy `%s` formatting in logging calls.
- Reserve `print()` for deliberate CLI output in thin entrypoints or debugging scripts.

## 8. Naming and Organization

### Naming Conventions

```python
# Modules:    snake_case              snapshot_reconciler.py
# Classes:    PascalCase              ReconciliationReport
# Functions:  snake_case verbs        canonicalize_row()
# Constants:  UPPER_SNAKE             REQUIRED_COLUMNS = frozenset(...)
# Variables:  snake_case nouns        unmatched_records = []
# Private:    leading underscore      _normalize_quantity()

# Booleans
is_valid = True
has_duplicates = False
should_write_report = True

# Collections
records = [...]
issues_by_sku = {}
seen_skus = set()

# Type aliases
type RecordIndex = dict[str, InventoryRecord]
```

- Prefer names that reflect business meaning, not just data structure.
- Booleans should read like a question: `is_`, `has_`, `can_`, `should_`.
- Collection names should be plural or explicitly keyed: `records`, `issues_by_sku`, `record_by_sku`.
- Avoid project-specific abbreviations that require a decoder ring.
- Universally understood abbreviations are fine: `id`, `db`, `df`, `src`, `dst`, `config`.

### Module Layout

```python
"""Reconcile canonical inventory snapshots."""

import csv
import logging
from collections.abc import Iterable, Mapping
from decimal import Decimal
from pathlib import Path

from inventory_reconciliation.models import InventoryRecord, ReconciliationReport

log = logging.getLogger(__name__)

AMOUNT_TOLERANCE = Decimal("0.01")
REQUIRED_COLUMNS = frozenset({"sku", "quantity"})


def reconcile(
    source: Iterable[InventoryRecord],
    target: Mapping[str, InventoryRecord],
) -> ReconciliationReport:
    ...


def _build_index(records: Iterable[InventoryRecord]) -> dict[str, InventoryRecord]:
    ...
```

- Group imports as stdlib, third-party, local.
- Keep module-level constants near the top.
- Public API first, helpers below it.
- Avoid wildcard imports.
- Keep side effects out of module import time unless they are truly constant definitions.

## 9. Comments and Docstrings

### Docstrings

Use Google style for public modules, classes, and functions. Skip obvious private helpers.

```python
from decimal import Decimal

def find_discrepancies(
    source: list[InventoryRecord],
    target: list[InventoryRecord],
    *,
    tolerance: Decimal = Decimal("0.01"),
) -> list[Discrepancy]:
    """Compare matched records and return those exceeding tolerance.

    Args:
        source: Records from the authoritative system.
        target: Records from the system under test.
        tolerance: Maximum absolute difference considered acceptable.

    Returns:
        Discrepancies for each pair exceeding the tolerance.

    Raises:
        ValueError: If either input contains duplicate SKUs.
    """
```

### Comments

- Comments explain why, invariants, edge cases, or non-obvious business rules.
- If renaming something removes the need for a comment, rename it.
- In reconciliation code, comment the reason for a coercion, ordering rule, or business exception.
- Do not narrate obvious code line by line.

## 10. Testing

### `pytest` Is the Default

```python
import pytest

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("00123", "123"),
        ("  sku-9  ", "SKU-9"),
        ("", None),
    ],
)
def test_normalize_sku(raw: str, expected: str | None) -> None:
    assert normalize_sku(raw) == expected
```

- Test behavior, not implementation details.
- Add a regression test for every bug or messy data case you fix.
- Favor small, explicit fixtures over giant opaque sample files unless end-to-end coverage is the goal.
- Name tests after business rules: `test_invalid_quantity_is_reported_not_silently_zeroed`.

### Reconciliation-Specific Cases to Cover

- duplicate IDs or SKUs
- blank or whitespace-only fields
- malformed numeric values
- case and whitespace normalization
- missing required columns
- shared IDs with incomparable values
- deterministic output ordering
- bad input that should produce a quality issue instead of a false add/remove

## 11. Anti-Patterns

```python
# Bad: falsey lookup can drop valid values
if match := index.get(key):
    ...

# Better
match = index.get(key)
if match is not None:
    ...
```

```python
# Bad: broad exception hides real bugs
except Exception:
    return None

# Better
except InvalidOperation as exc:
    raise ValueError(f"Invalid quantity: {raw!r}") from exc
```

```python
# Bad: raw dicts deep in core logic
record = {"sku": sku, "quantity": qty}

# Better
record = InventoryRecord(sku=sku, quantity=qty, captured_at=captured_at)
```

```python
# Bad: string concatenation in a loop
output = ""
for row in rows:
    output += f"{row['sku']},{row['quantity']}\n"

# Better
output = "".join(f"{row['sku']},{row['quantity']}\n" for row in rows)
```

```python
# Bad: naive datetime
captured_at = datetime.now()

# Better
captured_at = datetime.now(UTC)
```

```python
# Bad: validation with assert
assert "sku" in row

# Better
if "sku" not in row:
    raise ValueError("Missing required field: sku")
```

## 12. Tooling

### Ruff

Ruff replaces `black`, `isort`, and most `flake8` plugins with one fast tool.

```toml
[tool.ruff]
target-version = "py314"
line-length = 88

[tool.ruff.lint]
select = [
    "E", "W", "F", "I", "N", "UP",
    "B", "C4", "SIM", "RET", "PTH", "RUF",
]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

### mypy

Prefer a strict baseline, then relax per module only when there is a clear reason.

```toml
[tool.mypy]
python_version = "3.14"
strict = true
warn_unreachable = true
pretty = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
```

### Test Runner

```toml
[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["tests"]
```

- If a tool lags behind Python 3.14 syntax, upgrade the tool before downgrading the code style.
- Treat linting, formatting, typing, and tests as part of the definition of done.

## Quick Reference

| Avoid | Prefer |
|---|---|
| `from typing import TypeAlias` | `type Alias = ...` |
| Quoted forward refs everywhere | Normal 3.14 annotations |
| Raw `dict` in core logic | `TypedDict` at edges, dataclass inside |
| `float` for money | `Decimal` |
| `datetime.now()` | `datetime.now(UTC)` |
| `if x == None:` | `if x is None:` |
| `if len(x) > 0:` | `if x:` |
| `if match := index.get(key):` | `match = index.get(key)` then `if match is not None:` |
| `process(a, True, False, 3)` | `process(a, dry_run=True, retries=3)` |
| `except:` or `except Exception:` | `except SpecificError as exc:` |
| `assert` for input validation | explicit `ValueError` or domain error |
| `def f(items=[]):` | `def f(items=None):` |
| raw path strings throughout | `pathlib.Path` |
| `print()` in library code | `logging` |
| unstable JSON output | `json.dump(..., indent=2, sort_keys=True)` |
| 200-line orchestration function | small pipeline steps |

## Sources

- [Python 3.14.3: What's New](https://docs.python.org/3.14/whatsnew/3.14.html)
- [Python 3.14.3 `typing` docs](https://docs.python.org/3.14/library/typing.html)
- [PEP 8](https://peps.python.org/pep-0008/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [mypy Documentation](https://mypy.readthedocs.io/)
