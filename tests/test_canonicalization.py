from datetime import date

import pytest

from inventory_reconciliation.canonicalization import (
    CanonicalRowInput,
    canonicalize_row,
    normalize_date,
    normalize_sku,
    parse_quantity,
)
from inventory_reconciliation.records import IssueCode, RowAction, SnapshotName


def test_normalize_sku_repairs_case_and_missing_hyphen() -> None:
    normalized_sku, issues = normalize_sku(
        "sku005",
        snapshot=SnapshotName.SNAPSHOT_2,
        source_line=6,
    )

    assert normalized_sku == "SKU-005"
    assert [issue.code for issue in issues] == [IssueCode.NORMALIZED_SKU]
    assert issues[0].normalized_value == "SKU-005"


def test_normalize_sku_rejects_invalid_pattern() -> None:
    normalized_sku, issues = normalize_sku(
        "ABCXYZ",
        snapshot=SnapshotName.SNAPSHOT_2,
        source_line=6,
    )

    assert normalized_sku is None
    assert [issue.code for issue in issues] == [IssueCode.INVALID_SKU]


def test_parse_quantity_coerces_whole_number_float_and_logs_it() -> None:
    quantity, issues = parse_quantity(
        "80.00",
        snapshot=SnapshotName.SNAPSHOT_2,
        source_line=8,
        sku="SKU-007",
    )

    assert quantity == 80
    assert [issue.code for issue in issues] == [IssueCode.COERCED_QUANTITY]
    assert issues[0].normalized_value == 80


def test_parse_quantity_rejects_fractional_values() -> None:
    quantity, issues = parse_quantity(
        "70.5",
        snapshot=SnapshotName.SNAPSHOT_2,
        source_line=3,
        sku="SKU-002",
    )

    assert quantity is None
    assert [issue.code for issue in issues] == [IssueCode.INVALID_QUANTITY]


def test_parse_quantity_rejects_non_numeric_values() -> None:
    quantity, issues = parse_quantity(
        "abc",
        snapshot=SnapshotName.SNAPSHOT_2,
        source_line=3,
        sku="SKU-002",
    )

    assert quantity is None
    assert [issue.code for issue in issues] == [IssueCode.INVALID_QUANTITY]


def test_normalize_date_converts_mmddyyyy_to_iso_date() -> None:
    normalized_date, issues = normalize_date(
        "01/15/2024",
        snapshot=SnapshotName.SNAPSHOT_2,
        source_line=34,
        sku="SKU-035",
    )

    assert normalized_date == date(2024, 1, 15)
    assert [issue.code for issue in issues] == [IssueCode.NORMALIZED_DATE]
    assert issues[0].normalized_value == "2024-01-15"


def test_normalize_date_rejects_unsupported_format() -> None:
    normalized_date, issues = normalize_date(
        "not-a-date",
        snapshot=SnapshotName.SNAPSHOT_2,
        source_line=34,
        sku="SKU-035",
    )

    assert normalized_date is None
    assert [issue.code for issue in issues] == [IssueCode.INVALID_DATE]


def test_canonicalize_row_rejects_blank_required_name_after_trimming() -> None:
    record, issues = canonicalize_row(
        CanonicalRowInput(
            sku="SKU-001",
            name="   ",
            quantity="10",
            location="Warehouse A",
            counted_on="2024-01-15",
        ),
        snapshot=SnapshotName.SNAPSHOT_1,
        source_line=2,
    )

    assert record is None
    assert any(
        issue.code == IssueCode.BLANK_REQUIRED_FIELD and issue.field_name == "name"
        for issue in issues
    )
    assert issues
    assert all(issue.row_action == RowAction.REJECTED for issue in issues)


@pytest.mark.parametrize(
    ("raw_quantity", "expected_codes"),
    [
        ("-5", [IssueCode.NEGATIVE_QUANTITY]),
        ("  -5  ", [IssueCode.TRIMMED_WHITESPACE, IssueCode.NEGATIVE_QUANTITY]),
    ],
)
def test_negative_quantity_is_preserved_but_flagged(
    raw_quantity: str,
    expected_codes: list[IssueCode],
) -> None:
    quantity, issues = parse_quantity(
        raw_quantity,
        snapshot=SnapshotName.SNAPSHOT_2,
        source_line=54,
        sku="SKU-045",
    )

    assert quantity == -5
    assert [issue.code for issue in issues] == expected_codes
