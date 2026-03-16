from datetime import date
from pathlib import Path

import pytest

from inventory_reconciliation.records import IssueCode, RowAction, SnapshotName
from inventory_reconciliation.snapshot_loader import SnapshotSchemaError, load_snapshot

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DATA_DIR = _REPO_ROOT / "data"


def test_load_snapshot_1_uses_the_snapshot_specific_mapping() -> None:
    result = load_snapshot(
        _DATA_DIR / "snapshot_1.csv",
        snapshot=SnapshotName.SNAPSHOT_1,
    )

    assert len(result.records) == 75
    assert result.records[0].sku == "SKU-001"
    assert result.records[0].name == "Widget A"
    assert result.records[0].quantity == 150
    assert result.records[0].counted_on == date(2024, 1, 8)

    whitespace_issue_lines = {
        issue.source_line
        for issue in result.issues
        if issue.code == IssueCode.TRIMMED_WHITESPACE and issue.field_name == "name"
    }
    skipped_empty_lines = {
        issue.source_line
        for issue in result.issues
        if issue.code == IssueCode.SKIPPED_EMPTY_ROW
    }

    assert whitespace_issue_lines == {36, 53}
    assert skipped_empty_lines == {77}


def test_load_snapshot_2_applies_known_normalizations_and_duplicate_rules() -> None:
    result = load_snapshot(
        _DATA_DIR / "snapshot_2.csv",
        snapshot=SnapshotName.SNAPSHOT_2,
    )
    records_by_sku = {record.sku: record for record in result.records}

    assert len(result.records) == 78
    assert records_by_sku["SKU-005"].quantity == 480
    assert records_by_sku["SKU-008"].quantity == 42
    assert records_by_sku["SKU-018"].quantity == 750
    assert records_by_sku["SKU-045"].name == "Multimeter Professional"
    assert records_by_sku["SKU-045"].quantity == 23

    assert any(
        issue.code == IssueCode.NORMALIZED_SKU
        and issue.source_line == 6
        and issue.normalized_value == "SKU-005"
        for issue in result.issues
    )
    assert any(
        issue.code == IssueCode.NORMALIZED_SKU
        and issue.source_line == 9
        and issue.normalized_value == "SKU-008"
        for issue in result.issues
    )
    assert any(
        issue.code == IssueCode.NORMALIZED_SKU
        and issue.source_line == 19
        and issue.normalized_value == "SKU-018"
        for issue in result.issues
    )
    assert any(
        issue.code == IssueCode.COERCED_QUANTITY
        and issue.source_line == 3
        and issue.normalized_value == 70
        for issue in result.issues
    )
    assert any(
        issue.code == IssueCode.COERCED_QUANTITY
        and issue.source_line == 8
        and issue.normalized_value == 80
        for issue in result.issues
    )
    assert any(
        issue.code == IssueCode.NORMALIZED_DATE
        and issue.source_line == 34
        and issue.normalized_value == "2024-01-15"
        for issue in result.issues
    )

    duplicate_issue = next(
        issue
        for issue in result.issues
        if issue.code == IssueCode.DUPLICATE_SKU and issue.source_line == 54
    )
    negative_quantity_issue = next(
        issue
        for issue in result.issues
        if issue.code == IssueCode.NEGATIVE_QUANTITY and issue.source_line == 54
    )

    assert duplicate_issue.row_action == RowAction.SKIPPED_DUPLICATE
    assert duplicate_issue.details["first_line"] == 44
    assert duplicate_issue.details["conflicting_fields"] == "name, quantity, location"
    assert negative_quantity_issue.row_action == RowAction.SKIPPED_DUPLICATE


def test_load_snapshot_rejects_missing_required_columns(tmp_path: Path) -> None:
    broken_snapshot = tmp_path / "broken_snapshot.csv"
    broken_snapshot.write_text(
        "sku,product_name,qty\nSKU-001,Widget A,10\n",
        encoding="utf-8",
    )

    with pytest.raises(SnapshotSchemaError, match="missing required columns"):
        load_snapshot(
            broken_snapshot,
            snapshot=SnapshotName.SNAPSHOT_2,
        )


def test_load_snapshot_rejects_missing_header_row(tmp_path: Path) -> None:
    empty_snapshot = tmp_path / "empty_snapshot.csv"
    empty_snapshot.write_text("", encoding="utf-8")

    with pytest.raises(SnapshotSchemaError, match="missing a header row"):
        load_snapshot(
            empty_snapshot,
            snapshot=SnapshotName.SNAPSHOT_2,
        )


def test_load_snapshot_rejects_duplicate_headers_after_normalization(
    tmp_path: Path,
) -> None:
    duplicate_header_snapshot = tmp_path / "duplicate_header_snapshot.csv"
    duplicate_header_snapshot.write_text(
        (
            "sku, sku , product_name, qty, warehouse, updated_at\n"
            "SKU-001,IGNORED,Widget A,10,Warehouse A,2024-01-15\n"
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        SnapshotSchemaError,
        match="duplicate columns after normalization: sku",
    ):
        load_snapshot(
            duplicate_header_snapshot,
            snapshot=SnapshotName.SNAPSHOT_2,
        )


def test_load_snapshot_accepts_headers_with_extra_whitespace(tmp_path: Path) -> None:
    spaced_header_snapshot = tmp_path / "spaced_header_snapshot.csv"
    spaced_header_snapshot.write_text(
        (
            " sku , product_name , qty , warehouse , updated_at \n"
            "SKU-001,Widget A,10,Warehouse A,2024-01-15\n"
        ),
        encoding="utf-8",
    )

    result = load_snapshot(
        spaced_header_snapshot,
        snapshot=SnapshotName.SNAPSHOT_2,
    )

    assert len(result.records) == 1
    assert result.records[0].sku == "SKU-001"
    assert result.records[0].quantity == 10
    assert not any(
        issue.code == IssueCode.BLANK_REQUIRED_FIELD for issue in result.issues
    )


def test_load_snapshot_accepts_bom_prefixed_case_insensitive_headers(
    tmp_path: Path,
) -> None:
    bom_snapshot = tmp_path / "bom_snapshot.csv"
    bom_snapshot.write_text(
        (
            "SKU,Product_Name,Qty,Warehouse,Updated_At\n"
            "SKU-001,Widget A,10,Warehouse A,2024-01-15\n"
        ),
        encoding="utf-8-sig",
    )

    result = load_snapshot(
        bom_snapshot,
        snapshot=SnapshotName.SNAPSHOT_2,
    )

    assert len(result.records) == 1
    assert result.records[0].sku == "SKU-001"
    assert result.records[0].quantity == 10


def test_load_snapshot_rejects_short_rows_as_quality_issues(tmp_path: Path) -> None:
    short_row_snapshot = tmp_path / "short_row_snapshot.csv"
    short_row_snapshot.write_text(
        (
            "sku,product_name,qty,warehouse,updated_at\n"
            "SKU-001,Widget A,10\n"
        ),
        encoding="utf-8",
    )

    result = load_snapshot(
        short_row_snapshot,
        snapshot=SnapshotName.SNAPSHOT_2,
    )

    assert result.records == []
    assert [
        (issue.code, issue.field_name, issue.row_action)
        for issue in result.issues
        if issue.source_line == 2
    ] == [
        (IssueCode.BLANK_REQUIRED_FIELD, "location", RowAction.REJECTED),
        (IssueCode.BLANK_REQUIRED_FIELD, "counted_on", RowAction.REJECTED),
    ]
