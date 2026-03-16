from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path

from inventory_reconciliation.canonicalization import (
    CanonicalRowInput,
    canonicalize_row,
)
from inventory_reconciliation.records import (
    CanonicalInventoryRecord,
    IssueCode,
    IssueSeverity,
    QualityIssue,
    RowAction,
    SnapshotLoadResult,
    SnapshotName,
    mark_row_action,
)


class SnapshotSchemaError(ValueError):
    """Raised when a snapshot does not expose the required source columns."""


@dataclass(frozen=True, slots=True, kw_only=True)
class SnapshotColumnMapping:
    sku: str
    name: str
    quantity: str
    location: str
    counted_on: str

    def required_columns(self) -> set[str]:
        return {
            self.sku,
            self.name,
            self.quantity,
            self.location,
            self.counted_on,
        }


SNAPSHOT_COLUMN_MAPPINGS: dict[SnapshotName, SnapshotColumnMapping] = {
    SnapshotName.SNAPSHOT_1: SnapshotColumnMapping(
        sku="sku",
        name="name",
        quantity="quantity",
        location="location",
        counted_on="last_counted",
    ),
    SnapshotName.SNAPSHOT_2: SnapshotColumnMapping(
        sku="sku",
        name="product_name",
        quantity="qty",
        location="warehouse",
        counted_on="updated_at",
    ),
}


def load_snapshot(path: Path, *, snapshot: SnapshotName) -> SnapshotLoadResult:
    mapping = SNAPSHOT_COLUMN_MAPPINGS[snapshot]

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        fieldnames = _normalize_headers(next(reader, None))
        _validate_headers(fieldnames, mapping=mapping, path=path)

        records: list[CanonicalInventoryRecord] = []
        issues: list[QualityIssue] = []
        records_by_sku: dict[str, CanonicalInventoryRecord] = {}

        for source_line, row in enumerate(reader, start=2):
            if _is_structurally_empty_row(row):
                issues.append(
                    QualityIssue(
                        code=IssueCode.SKIPPED_EMPTY_ROW,
                        severity=IssueSeverity.INFO,
                        snapshot=snapshot,
                        source_line=source_line,
                        field_name="row",
                        message="Skipped a structurally empty row.",
                        row_action=RowAction.SKIPPED_EMPTY,
                    )
                )
                continue

            mapped_row = _build_row_mapping(fieldnames or [], row)
            canonical_input = _map_row_to_canonical_input(mapped_row, mapping)
            record, row_issues = canonicalize_row(
                canonical_input,
                snapshot=snapshot,
                source_line=source_line,
            )
            issues.extend(row_issues)

            if record is None:
                continue

            existing_record = records_by_sku.get(record.sku)
            if existing_record is not None:
                mark_row_action(row_issues, RowAction.SKIPPED_DUPLICATE)
                issues.append(
                    _build_duplicate_issue(
                        duplicate_record=record,
                        kept_record=existing_record,
                    )
                )
                continue

            records.append(record)
            records_by_sku[record.sku] = record

    return SnapshotLoadResult(snapshot=snapshot, records=records, issues=issues)


def _validate_headers(
    fieldnames: Sequence[str] | None,
    *,
    mapping: SnapshotColumnMapping,
    path: Path,
) -> None:
    if fieldnames is None:
        raise SnapshotSchemaError(f"{path} is missing a header row.")

    duplicate_columns = sorted(
        column_name
        for column_name, count in Counter(fieldnames).items()
        if column_name and count > 1
    )
    if duplicate_columns:
        duplicate_list = ", ".join(duplicate_columns)
        raise SnapshotSchemaError(
            f"{path} has duplicate columns after normalization: {duplicate_list}."
        )

    actual_columns = set(fieldnames)
    missing_columns = sorted(mapping.required_columns() - actual_columns)
    if not missing_columns:
        return

    missing_list = ", ".join(missing_columns)
    raise SnapshotSchemaError(
        f"{path} is missing required columns: {missing_list}."
    )


def _normalize_headers(fieldnames: Sequence[str] | None) -> list[str] | None:
    if fieldnames is None:
        return None
    return [_normalize_header(fieldname) for fieldname in fieldnames]


def _normalize_header(fieldname: str) -> str:
    return fieldname.removeprefix("\ufeff").strip().lower()


def _is_structurally_empty_row(row: Sequence[str]) -> bool:
    return all(not value.strip() for value in row)


def _build_row_mapping(
    fieldnames: Sequence[str],
    row: Sequence[str],
) -> dict[str, str]:
    return {
        fieldname: value
        for fieldname, value in zip_longest(fieldnames, row, fillvalue="")
        if fieldname
    }


def _map_row_to_canonical_input(
    row: Mapping[str, str | None],
    mapping: SnapshotColumnMapping,
) -> CanonicalRowInput:
    return CanonicalRowInput(
        sku=row.get(mapping.sku, "") or "",
        name=row.get(mapping.name, "") or "",
        quantity=row.get(mapping.quantity, "") or "",
        location=row.get(mapping.location, "") or "",
        counted_on=row.get(mapping.counted_on, "") or "",
    )


def _build_duplicate_issue(
    *,
    duplicate_record: CanonicalInventoryRecord,
    kept_record: CanonicalInventoryRecord,
) -> QualityIssue:
    conflicting_fields = _conflicting_fields(kept_record, duplicate_record)
    details: dict[str, str | int] = {"first_line": kept_record.source_line}
    if conflicting_fields:
        details["conflicting_fields"] = ", ".join(conflicting_fields)

    return QualityIssue(
        code=IssueCode.DUPLICATE_SKU,
        severity=IssueSeverity.WARNING,
        snapshot=duplicate_record.snapshot,
        source_line=duplicate_record.source_line,
        field_name="sku",
        sku=duplicate_record.sku,
        message=(
            f"Duplicate sku {duplicate_record.sku} encountered. "
            f"Kept line {kept_record.source_line} and skipped line "
            f"{duplicate_record.source_line}."
        ),
        row_action=RowAction.SKIPPED_DUPLICATE,
        details=details,
    )


def _conflicting_fields(
    kept_record: CanonicalInventoryRecord,
    duplicate_record: CanonicalInventoryRecord,
) -> list[str]:
    conflicts: list[str] = []
    if kept_record.name != duplicate_record.name:
        conflicts.append("name")
    if kept_record.quantity != duplicate_record.quantity:
        conflicts.append("quantity")
    if kept_record.location != duplicate_record.location:
        conflicts.append("location")
    if kept_record.counted_on != duplicate_record.counted_on:
        conflicts.append("counted_on")
    return conflicts
