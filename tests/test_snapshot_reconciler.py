from datetime import date
from pathlib import Path

import pytest

from inventory_reconciliation.records import CanonicalInventoryRecord, SnapshotName
from inventory_reconciliation.snapshot_loader import load_snapshot
from inventory_reconciliation.snapshot_reconciler import (
    QuantityChangeKind,
    reconcile_snapshots,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DATA_DIR = _REPO_ROOT / "data"


def test_reconcile_snapshots_classifies_matches_additions_and_removals() -> None:
    snapshot_1_records = [
        _build_record(
            snapshot=SnapshotName.SNAPSHOT_1,
            source_line=4,
            sku="SKU-003",
            name="Cable Pack",
            quantity=12,
            location="Warehouse A",
            counted_on=date(2024, 1, 8),
        ),
        _build_record(
            snapshot=SnapshotName.SNAPSHOT_1,
            source_line=2,
            sku="SKU-001",
            name="Widget A",
            quantity=10,
            location="Warehouse A",
            counted_on=date(2024, 1, 8),
        ),
        _build_record(
            snapshot=SnapshotName.SNAPSHOT_1,
            source_line=3,
            sku="SKU-002",
            name="Widget B",
            quantity=5,
            location="Warehouse B",
            counted_on=date(2024, 1, 8),
        ),
    ]
    snapshot_2_records = [
        _build_record(
            snapshot=SnapshotName.SNAPSHOT_2,
            source_line=4,
            sku="SKU-004",
            name="Widget D",
            quantity=9,
            location="Warehouse C",
            counted_on=date(2024, 1, 15),
        ),
        _build_record(
            snapshot=SnapshotName.SNAPSHOT_2,
            source_line=3,
            sku="SKU-002",
            name="Widget B",
            quantity=5,
            location="Warehouse B",
            counted_on=date(2024, 1, 15),
        ),
        _build_record(
            snapshot=SnapshotName.SNAPSHOT_2,
            source_line=2,
            sku="SKU-001",
            name="Widget A Plus",
            quantity=8,
            location="Warehouse C",
            counted_on=date(2024, 1, 15),
        ),
    ]

    result = reconcile_snapshots(snapshot_1_records, snapshot_2_records)

    assert [item.sku for item in result.present_in_both] == ["SKU-001", "SKU-002"]
    assert [record.sku for record in result.only_in_snapshot_1] == ["SKU-003"]
    assert [record.sku for record in result.only_in_snapshot_2] == ["SKU-004"]

    first_match = result.present_in_both[0]
    second_match = result.present_in_both[1]

    assert first_match.quantity_change is QuantityChangeKind.DECREASED
    assert first_match.quantity_delta == -2
    assert first_match.quantity_changed is True
    assert first_match.name_changed is True
    assert first_match.location_changed is True

    assert second_match.quantity_change is QuantityChangeKind.UNCHANGED
    assert second_match.quantity_delta == 0
    assert second_match.quantity_changed is False
    assert second_match.name_changed is False
    assert second_match.location_changed is False

    assert result.summary.snapshot_1_records == 3
    assert result.summary.snapshot_2_records == 3
    assert result.summary.present_in_both == 2
    assert result.summary.quantity_changed == 1
    assert result.summary.quantity_unchanged == 1
    assert result.summary.quantity_increased == 0
    assert result.summary.quantity_decreased == 1
    assert result.summary.only_in_snapshot_1 == 1
    assert result.summary.only_in_snapshot_2 == 1
    assert result.summary.name_changed == 1
    assert result.summary.location_changed == 1


def test_reconcile_snapshots_rejects_duplicate_skus() -> None:
    duplicate_records = [
        _build_record(
            snapshot=SnapshotName.SNAPSHOT_1,
            source_line=2,
            sku="SKU-001",
            name="Widget A",
            quantity=10,
            location="Warehouse A",
            counted_on=date(2024, 1, 8),
        ),
        _build_record(
            snapshot=SnapshotName.SNAPSHOT_1,
            source_line=3,
            sku="SKU-001",
            name="Widget A Duplicate",
            quantity=9,
            location="Warehouse A",
            counted_on=date(2024, 1, 8),
        ),
    ]

    with pytest.raises(ValueError, match="Duplicate sku SKU-001"):
        reconcile_snapshots(duplicate_records, [])


def test_reconcile_snapshots_classifies_increased_quantity() -> None:
    snapshot_1_records = [
        _build_record(
            snapshot=SnapshotName.SNAPSHOT_1,
            source_line=2,
            sku="SKU-001",
            name="Widget A",
            quantity=10,
            location="Warehouse A",
            counted_on=date(2024, 1, 8),
        )
    ]
    snapshot_2_records = [
        _build_record(
            snapshot=SnapshotName.SNAPSHOT_2,
            source_line=2,
            sku="SKU-001",
            name="Widget A",
            quantity=14,
            location="Warehouse A",
            counted_on=date(2024, 1, 15),
        )
    ]

    result = reconcile_snapshots(snapshot_1_records, snapshot_2_records)

    assert len(result.present_in_both) == 1
    assert result.present_in_both[0].quantity_change is QuantityChangeKind.INCREASED
    assert result.present_in_both[0].quantity_delta == 4
    assert result.summary.quantity_changed == 1
    assert result.summary.quantity_unchanged == 0
    assert result.summary.quantity_increased == 1
    assert result.summary.quantity_decreased == 0


def test_reconcile_snapshots_handles_empty_inputs() -> None:
    result = reconcile_snapshots([], [])

    assert result.present_in_both == []
    assert result.only_in_snapshot_1 == []
    assert result.only_in_snapshot_2 == []
    assert result.summary.snapshot_1_records == 0
    assert result.summary.snapshot_2_records == 0
    assert result.summary.present_in_both == 0
    assert result.summary.quantity_changed == 0
    assert result.summary.quantity_unchanged == 0
    assert result.summary.quantity_increased == 0
    assert result.summary.quantity_decreased == 0
    assert result.summary.only_in_snapshot_1 == 0
    assert result.summary.only_in_snapshot_2 == 0
    assert result.summary.name_changed == 0
    assert result.summary.location_changed == 0


def test_reconcile_snapshots_matches_real_snapshot_counts() -> None:
    snapshot_1 = load_snapshot(
        _DATA_DIR / "snapshot_1.csv",
        snapshot=SnapshotName.SNAPSHOT_1,
    )
    snapshot_2 = load_snapshot(
        _DATA_DIR / "snapshot_2.csv",
        snapshot=SnapshotName.SNAPSHOT_2,
    )

    result = reconcile_snapshots(snapshot_1.records, snapshot_2.records)
    matched_by_sku = {item.sku: item for item in result.present_in_both}

    assert len(result.present_in_both) == 73
    assert [record.sku for record in result.only_in_snapshot_1] == [
        "SKU-025",
        "SKU-026",
    ]
    assert [record.sku for record in result.only_in_snapshot_2] == [
        "SKU-076",
        "SKU-077",
        "SKU-078",
        "SKU-079",
        "SKU-080",
    ]

    assert result.summary.snapshot_1_records == 75
    assert result.summary.snapshot_2_records == 78
    assert result.summary.present_in_both == 73
    assert result.summary.quantity_changed == 71
    assert result.summary.quantity_unchanged == 2
    assert result.summary.quantity_increased == 0
    assert result.summary.quantity_decreased == 71
    assert result.summary.only_in_snapshot_1 == 2
    assert result.summary.only_in_snapshot_2 == 5
    assert result.summary.name_changed == 1
    assert result.summary.location_changed == 0

    assert matched_by_sku["SKU-045"].name_changed is True
    assert matched_by_sku["SKU-045"].quantity_delta == -2
    assert matched_by_sku["SKU-045"].quantity_change is QuantityChangeKind.DECREASED
    assert matched_by_sku["SKU-006"].quantity_change is QuantityChangeKind.UNCHANGED
    assert matched_by_sku["SKU-007"].quantity_change is QuantityChangeKind.UNCHANGED


def _build_record(
    *,
    snapshot: SnapshotName,
    source_line: int,
    sku: str,
    name: str,
    quantity: int,
    location: str,
    counted_on: date,
) -> CanonicalInventoryRecord:
    return CanonicalInventoryRecord(
        snapshot=snapshot,
        source_line=source_line,
        sku=sku,
        name=name,
        quantity=quantity,
        location=location,
        counted_on=counted_on,
    )
