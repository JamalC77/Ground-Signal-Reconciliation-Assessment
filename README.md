# Ground Signal Reconciliation Assessment

Reconciles two inventory snapshot CSV files into a deterministic JSON report,
with explicit handling for messy real-world data such as malformed SKUs,
duplicate rows, whitespace issues, quantity coercion, and temporal
inconsistencies.

## What This Does

The pipeline:

1. Loads each CSV using a snapshot-specific schema mapping.
2. Normalizes rows into a shared internal record shape.
3. Validates and records data-quality issues instead of silently discarding bad
   data.
4. Reconciles records by normalized SKU across the two snapshots.
5. Produces a structured JSON report summarizing matches, differences, and
   flagged issues.

## Repository Layout

- `reconcile.py`: CLI entrypoint.
- `inventory_reconciliation/`: core reconciliation package.
- `tests/`: unit and end-to-end tests.
- `data/`: assessment input files.
- `output/`: generated reconciliation report.
- `pyproject.toml`: project metadata and `pytest`, `mypy`, and `ruff`
  configuration.
- `BuildPlan.md`: implementation approach and tradeoffs.
- `DataAudit.md`: source-data observations.
- `NOTES.md`: key decisions, assumptions, and final assessment notes.
- `PythonStyleReference.md`: code-quality guidance used during implementation.

Core modules inside `inventory_reconciliation/`:

- `records.py`: shared data models, enums, and issue structures.
- `snapshot_loader.py`: CSV parsing, header validation, and row loading.
- `canonicalization.py`: normalization and field-level validation.
- `snapshot_reconciler.py`: snapshot-to-snapshot comparison logic.
- `temporal_validation.py`: file-level date consistency checks.
- `quality_review.py`: rules for escalating issues into flagged review items.
- `reporting.py`: deterministic JSON serialization and summary generation.

## Requirements

- Python 3.12+

## Setup

```bash
python -m pip install -e ".[dev]"
```

## Run

Run from the repository root:

```bash
python reconcile.py --snapshot-1 data/snapshot_1.csv --snapshot-2 data/snapshot_2.csv --output output/reconciliation_report.json
```

The CLI writes the JSON report to the requested output path and returns a
non-zero exit code when the report contains error-severity quality issues.

## Quality Checks

Run tests:

```bash
python -m pytest
```

Run strict type checking:

```bash
python -m mypy --strict reconcile.py inventory_reconciliation tests
```

Run linting:

```bash
python -m ruff check .
```

## Output

The generated report includes:

- `flagged_items`
- `only_in_snapshot_1`
- `only_in_snapshot_2`
- `present_in_both`
- `summary`

The summary contains reconciliation counts and aggregated quality-issue counts
by code.