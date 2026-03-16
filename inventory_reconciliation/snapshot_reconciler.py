from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from inventory_reconciliation.records import CanonicalInventoryRecord


class QuantityChangeKind(StrEnum):
    DECREASED = "decreased"
    UNCHANGED = "unchanged"
    INCREASED = "increased"


@dataclass(frozen=True, slots=True, kw_only=True)
class MatchedInventoryItem:
    sku: str
    snapshot_1_record: CanonicalInventoryRecord
    snapshot_2_record: CanonicalInventoryRecord
    quantity_before: int
    quantity_after: int
    quantity_delta: int
    quantity_change: QuantityChangeKind
    quantity_changed: bool
    name_changed: bool
    location_changed: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class ReconciliationSummary:
    snapshot_1_records: int
    snapshot_2_records: int
    present_in_both: int
    quantity_changed: int
    quantity_unchanged: int
    quantity_increased: int
    quantity_decreased: int
    only_in_snapshot_1: int
    only_in_snapshot_2: int
    name_changed: int
    location_changed: int


@dataclass(frozen=True, slots=True, kw_only=True)
class SnapshotReconciliationResult:
    present_in_both: list[MatchedInventoryItem]
    only_in_snapshot_1: list[CanonicalInventoryRecord]
    only_in_snapshot_2: list[CanonicalInventoryRecord]
    summary: ReconciliationSummary


def reconcile_snapshots(
    snapshot_1_records: Iterable[CanonicalInventoryRecord],
    snapshot_2_records: Iterable[CanonicalInventoryRecord],
) -> SnapshotReconciliationResult:
    snapshot_1_by_sku = _build_index(snapshot_1_records)
    snapshot_2_by_sku = _build_index(snapshot_2_records)

    shared_skus = sorted(snapshot_1_by_sku.keys() & snapshot_2_by_sku.keys())
    snapshot_1_only_skus = sorted(snapshot_1_by_sku.keys() - snapshot_2_by_sku.keys())
    snapshot_2_only_skus = sorted(snapshot_2_by_sku.keys() - snapshot_1_by_sku.keys())

    present_in_both = [
        _build_matched_item(
            snapshot_1_record=snapshot_1_by_sku[sku],
            snapshot_2_record=snapshot_2_by_sku[sku],
        )
        for sku in shared_skus
    ]
    only_in_snapshot_1 = [snapshot_1_by_sku[sku] for sku in snapshot_1_only_skus]
    only_in_snapshot_2 = [snapshot_2_by_sku[sku] for sku in snapshot_2_only_skus]

    return SnapshotReconciliationResult(
        present_in_both=present_in_both,
        only_in_snapshot_1=only_in_snapshot_1,
        only_in_snapshot_2=only_in_snapshot_2,
        summary=_build_summary(
            present_in_both=present_in_both,
            only_in_snapshot_1=only_in_snapshot_1,
            only_in_snapshot_2=only_in_snapshot_2,
            snapshot_1_records=len(snapshot_1_by_sku),
            snapshot_2_records=len(snapshot_2_by_sku),
        ),
    )


def _build_index(
    records: Iterable[CanonicalInventoryRecord],
) -> dict[str, CanonicalInventoryRecord]:
    records_by_sku: dict[str, CanonicalInventoryRecord] = {}
    for record in records:
        if record.sku in records_by_sku:
            raise ValueError(
                f"Duplicate sku {record.sku} is not allowed during reconciliation."
            )
        records_by_sku[record.sku] = record
    return records_by_sku


def _build_matched_item(
    *,
    snapshot_1_record: CanonicalInventoryRecord,
    snapshot_2_record: CanonicalInventoryRecord,
) -> MatchedInventoryItem:
    quantity_delta = snapshot_2_record.quantity - snapshot_1_record.quantity
    quantity_change = _classify_quantity_change(quantity_delta)

    return MatchedInventoryItem(
        sku=snapshot_1_record.sku,
        snapshot_1_record=snapshot_1_record,
        snapshot_2_record=snapshot_2_record,
        quantity_before=snapshot_1_record.quantity,
        quantity_after=snapshot_2_record.quantity,
        quantity_delta=quantity_delta,
        quantity_change=quantity_change,
        quantity_changed=quantity_delta != 0,
        name_changed=snapshot_1_record.name != snapshot_2_record.name,
        location_changed=snapshot_1_record.location != snapshot_2_record.location,
    )


def _classify_quantity_change(quantity_delta: int) -> QuantityChangeKind:
    if quantity_delta < 0:
        return QuantityChangeKind.DECREASED
    if quantity_delta > 0:
        return QuantityChangeKind.INCREASED
    return QuantityChangeKind.UNCHANGED


def _build_summary(
    *,
    present_in_both: list[MatchedInventoryItem],
    only_in_snapshot_1: list[CanonicalInventoryRecord],
    only_in_snapshot_2: list[CanonicalInventoryRecord],
    snapshot_1_records: int,
    snapshot_2_records: int,
) -> ReconciliationSummary:
    quantity_changed = sum(item.quantity_changed for item in present_in_both)
    quantity_increased = sum(
        item.quantity_change is QuantityChangeKind.INCREASED
        for item in present_in_both
    )
    quantity_decreased = sum(
        item.quantity_change is QuantityChangeKind.DECREASED
        for item in present_in_both
    )
    name_changed = sum(item.name_changed for item in present_in_both)
    location_changed = sum(item.location_changed for item in present_in_both)

    return ReconciliationSummary(
        snapshot_1_records=snapshot_1_records,
        snapshot_2_records=snapshot_2_records,
        present_in_both=len(present_in_both),
        quantity_changed=quantity_changed,
        quantity_unchanged=len(present_in_both) - quantity_changed,
        quantity_increased=quantity_increased,
        quantity_decreased=quantity_decreased,
        only_in_snapshot_1=len(only_in_snapshot_1),
        only_in_snapshot_2=len(only_in_snapshot_2),
        name_changed=name_changed,
        location_changed=location_changed,
    )
