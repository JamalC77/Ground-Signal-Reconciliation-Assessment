## Build Plan

This plan is optimized for the assessment goals: show clear problem decomposition, produce readable and testable Python, and demonstrate disciplined use of AI tooling. The main risk in this task is not formatting the final report. It is producing a confident but incorrect reconciliation because the two inputs disagree on schema, identity, or data quality. For that reason, the build sequence prioritizes normalization and auditability before comparison and packaging. The implementation should favor correctness and clarity over cleverness or premature abstraction.

## Success Criteria

- Both snapshots are mapped into a canonical schema before comparison.
- Shared items are matched by normalized SKU and clearly report quantity changes.
- Items present in only one snapshot are classified deterministically as removed or added.
- Data quality issues are surfaced separately from business conclusions and do not silently distort counts.
- `output/reconciliation_report.json` contains the structured reconciliation report with explicit sections for `present_in_both`, `only_in_snapshot_1`, `only_in_snapshot_2`, `flagged_items`, and `summary`.
- Flagged data quality issues and ambiguous records are preserved inside the JSON report so a human can review them before fully trusting the conclusions.
- A single command reproduces the report artifact in `output/`.
- Tests cover the core reconciliation logic plus the edge cases identified in `DataAudit.md`.
- Final artifacts are straightforward for a reviewer to inspect: `reconcile.py`, `tests/`, `output/`, and `NOTES.md`.

### Phase 1: Define the Canonical Contract

- Status: complete
- Focus: map both input files into one internal record shape before attempting any diff.
- Deliverables: per-snapshot column mapping, SKU normalization, quantity parsing, whitespace cleanup, date normalization, duplicate handling rules, and a quality issue log.
- Exit criteria: every non-empty row is either converted into the canonical schema or represented as a logged quality issue.

### Phase 2: Build the Reconciliation Core

- Status: complete
- Focus: compare normalized records in a deterministic and explainable way.
- Deliverables: items present in both snapshots with quantity comparison details, items only in snapshot 1, items only in snapshot 2, and a summary that ties back to row-level results.
- Exit criteria: for any SKU, the system can explain whether it matched, was added, was removed, or could not be fully compared because of data quality constraints.

### Phase 3: Harden Against Real-World Data Quality

- Status: complete
- Focus: ensure messy input produces inspectable warnings instead of plausible but wrong conclusions.
- Deliverables: targeted handling and tests for malformed SKUs, duplicate conflicts, invalid or coerced quantities, whitespace issues, format inconsistencies, blank trailing rows, file-level temporal validation, and clear criteria for what belongs in the `flagged_items` section of the report.
- Exit criteria: known edge cases degrade gracefully, remain visible in the output, and are covered by regression tests.

### Phase 4: Package for Review

- Status: complete
- Focus: make the solution easy to run, audit, and discuss.
- Deliverables: a thin `reconcile.py` entrypoint, `output/reconciliation_report.json` with all three reconciliation categories plus `flagged_items` and summary, focused tests, and a concise `NOTES.md` covering assumptions, quality issues, and approach.
- Exit criteria: one command reproduces the report, and a reviewer can distinguish between accepted reconciliation results and items that still require manual verification.

## File Structure

```text
.
├── data/
│   ├── snapshot_1.csv
│   └── snapshot_2.csv
├── output/
│   └── reconciliation_report.json
├── reconcile.py
├── inventory_reconciliation/
│   ├── records.py
│   ├── snapshot_loader.py
│   ├── canonicalization.py
│   ├── snapshot_reconciler.py
│   ├── quality_review.py
│   ├── temporal_validation.py
│   └── reporting.py
├── tests/
│   ├── test_snapshot_loader.py
│   ├── test_canonicalization.py
│   ├── test_snapshot_reconciler.py
│   ├── test_quality_review.py
│   ├── test_temporal_validation.py
│   └── test_end_to_end.py
├── NOTES.md
├── BuildPlan.md
└── DataAudit.md
```

### Module Responsibilities

- `reconcile.py`: thin orchestration layer that wires inputs to outputs.
- `inventory_reconciliation/records.py`: canonical record and quality-issue data shapes.
- `inventory_reconciliation/snapshot_loader.py`: load CSVs, apply column mapping, and skip structurally empty rows.
- `inventory_reconciliation/canonicalization.py`: normalize SKU, quantity, whitespace, and date fields.
- `inventory_reconciliation/snapshot_reconciler.py`: classify matched, added, removed, and quantity-changed items.
- `inventory_reconciliation/quality_review.py`: define which quality issues require manual review and belong in `flagged_items`.
- `inventory_reconciliation/temporal_validation.py`: validate per-file snapshot dates and cross-file temporal ordering before trusting the comparison.
- `inventory_reconciliation/reporting.py`: write `reconciliation_report.json` with the three reconciliation categories, a `flagged_items` section for reviewer verification, and a summary.
- `tests/`: mirror the risk areas, then verify the full workflow end to end.

## AI Workflow And Validation

I am using AI to speed up the work, not to replace judgment. I want it helping with decomposition, drafting, and test generation, but I am still responsible for whether the final result is correct, explainable, and safe to trust.

- I will use AI early to break the task down, suggest module boundaries, and draft implementation candidates from the success criteria.
- I will use it again to turn the findings in `DataAudit.md` into focused tests and validation checks.
- If AI writes code, I will review it for clarity, error handling, and a clean separation between reconciliation logic and data quality reporting.
