from datetime import date

from inventory_reconciliation.quality_review import issue_requires_manual_review
from inventory_reconciliation.records import (
    CanonicalInventoryRecord,
    IssueCode,
    IssueSeverity,
    RowAction,
    SnapshotName,
)
from inventory_reconciliation.temporal_validation import validate_temporal_consistency


def test_validate_temporal_consistency_flags_mixed_dates_for_manual_review() -> None:
    snapshot_1_records = [
        _build_record(
            snapshot=SnapshotName.SNAPSHOT_1,
            counted_on=date(2024, 1, 8),
        ),
        _build_record(
            snapshot=SnapshotName.SNAPSHOT_1,
            counted_on=date(2024, 1, 9),
            sku="SKU-002",
        ),
    ]
    snapshot_2_records = [
        _build_record(
            snapshot=SnapshotName.SNAPSHOT_2,
            counted_on=date(2024, 1, 15),
        )
    ]

    issues = validate_temporal_consistency(snapshot_1_records, snapshot_2_records)

    assert len(issues) == 1
    assert issues[0].code is IssueCode.MIXED_SNAPSHOT_DATES
    assert issues[0].severity is IssueSeverity.WARNING
    assert issues[0].source_line is None
    assert issues[0].row_action is RowAction.NOT_APPLICABLE
    assert issues[0].details == {
        "distinct_date_count": 2,
        "min_date": "2024-01-08",
        "max_date": "2024-01-09",
        "distinct_dates": "2024-01-08, 2024-01-09",
    }
    assert issue_requires_manual_review(issues[0]) is True


def test_validate_temporal_consistency_flags_invalid_snapshot_order() -> None:
    snapshot_1_records = [
        _build_record(
            snapshot=SnapshotName.SNAPSHOT_1,
            counted_on=date(2024, 1, 15),
        )
    ]
    snapshot_2_records = [
        _build_record(
            snapshot=SnapshotName.SNAPSHOT_2,
            counted_on=date(2024, 1, 14),
        )
    ]

    issues = validate_temporal_consistency(snapshot_1_records, snapshot_2_records)

    assert len(issues) == 1
    assert issues[0].code is IssueCode.SNAPSHOT_ORDER_INVALID
    assert issues[0].severity is IssueSeverity.ERROR
    assert issues[0].source_line is None
    assert issues[0].row_action is RowAction.NOT_APPLICABLE
    assert issues[0].details == {
        "snapshot_1_max_date": "2024-01-15",
        "snapshot_2_min_date": "2024-01-14",
    }
    assert issue_requires_manual_review(issues[0]) is True


def _build_record(
    *,
    snapshot: SnapshotName,
    counted_on: date,
    sku: str = "SKU-001",
) -> CanonicalInventoryRecord:
    return CanonicalInventoryRecord(
        snapshot=snapshot,
        source_line=2,
        sku=sku,
        name="Widget",
        quantity=10,
        location="Warehouse A",
        counted_on=counted_on,
    )
