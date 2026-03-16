import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import TypedDict

from inventory_reconciliation.quality_review import collect_flagged_issues
from inventory_reconciliation.records import (
    CanonicalInventoryRecord,
    IssueDetails,
    QualityIssue,
    SnapshotLoadResult,
)
from inventory_reconciliation.snapshot_reconciler import (
    MatchedInventoryItem,
    SnapshotReconciliationResult,
)


class SerializedRecord(TypedDict):
    snapshot: str
    source_line: int
    sku: str
    name: str
    quantity: int
    location: str
    counted_on: str


class SerializedMatchedItem(TypedDict):
    sku: str
    quantity_before: int
    quantity_after: int
    quantity_delta: int
    quantity_change: str
    quantity_changed: bool
    name_changed: bool
    location_changed: bool
    snapshot_1_record: SerializedRecord
    snapshot_2_record: SerializedRecord


class SerializedIssue(TypedDict):
    snapshot: str
    source_line: int | None
    code: str
    severity: str
    row_action: str
    field_name: str | None
    sku: str | None
    message: str
    raw_value: str | None
    normalized_value: str | int | None
    details: IssueDetails


class SerializedSummary(TypedDict):
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
    total_quality_issues: int
    flagged_items_count: int
    quality_issue_counts_by_code: dict[str, int]


class ReconciliationReport(TypedDict):
    present_in_both: list[SerializedMatchedItem]
    only_in_snapshot_1: list[SerializedRecord]
    only_in_snapshot_2: list[SerializedRecord]
    flagged_items: list[SerializedIssue]
    summary: SerializedSummary


def build_reconciliation_report(
    snapshot_1_result: SnapshotLoadResult,
    snapshot_2_result: SnapshotLoadResult,
    reconciliation_result: SnapshotReconciliationResult,
    *,
    additional_issues: Iterable[QualityIssue] = (),
) -> ReconciliationReport:
    all_issues = [
        *snapshot_1_result.issues,
        *snapshot_2_result.issues,
        *additional_issues,
    ]
    flagged_issues = collect_flagged_issues(all_issues)

    return {
        "present_in_both": [
            _serialize_matched_item(item)
            for item in reconciliation_result.present_in_both
        ],
        "only_in_snapshot_1": [
            _serialize_record(record)
            for record in reconciliation_result.only_in_snapshot_1
        ],
        "only_in_snapshot_2": [
            _serialize_record(record)
            for record in reconciliation_result.only_in_snapshot_2
        ],
        "flagged_items": [_serialize_issue(issue) for issue in flagged_issues],
        "summary": _build_summary(
            reconciliation_result=reconciliation_result,
            all_issues=all_issues,
            flagged_issues=flagged_issues,
        ),
    }


def write_reconciliation_report(
    report: ReconciliationReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _build_summary(
    *,
    reconciliation_result: SnapshotReconciliationResult,
    all_issues: list[QualityIssue],
    flagged_issues: list[QualityIssue],
) -> SerializedSummary:
    issue_counts_by_code = Counter(issue.code.value for issue in all_issues)
    summary = reconciliation_result.summary

    return {
        "snapshot_1_records": summary.snapshot_1_records,
        "snapshot_2_records": summary.snapshot_2_records,
        "present_in_both": summary.present_in_both,
        "quantity_changed": summary.quantity_changed,
        "quantity_unchanged": summary.quantity_unchanged,
        "quantity_increased": summary.quantity_increased,
        "quantity_decreased": summary.quantity_decreased,
        "only_in_snapshot_1": summary.only_in_snapshot_1,
        "only_in_snapshot_2": summary.only_in_snapshot_2,
        "name_changed": summary.name_changed,
        "location_changed": summary.location_changed,
        "total_quality_issues": len(all_issues),
        "flagged_items_count": len(flagged_issues),
        "quality_issue_counts_by_code": dict(sorted(issue_counts_by_code.items())),
    }


def _serialize_record(record: CanonicalInventoryRecord) -> SerializedRecord:
    return {
        "snapshot": record.snapshot.value,
        "source_line": record.source_line,
        "sku": record.sku,
        "name": record.name,
        "quantity": record.quantity,
        "location": record.location,
        "counted_on": record.counted_on.isoformat(),
    }


def _serialize_matched_item(item: MatchedInventoryItem) -> SerializedMatchedItem:
    return {
        "sku": item.sku,
        "quantity_before": item.quantity_before,
        "quantity_after": item.quantity_after,
        "quantity_delta": item.quantity_delta,
        "quantity_change": item.quantity_change.value,
        "quantity_changed": item.quantity_changed,
        "name_changed": item.name_changed,
        "location_changed": item.location_changed,
        "snapshot_1_record": _serialize_record(item.snapshot_1_record),
        "snapshot_2_record": _serialize_record(item.snapshot_2_record),
    }


def _serialize_issue(issue: QualityIssue) -> SerializedIssue:
    return {
        "snapshot": issue.snapshot.value,
        "source_line": issue.source_line,
        "code": issue.code.value,
        "severity": issue.severity.value,
        "row_action": issue.row_action.value,
        "field_name": issue.field_name,
        "sku": issue.sku,
        "message": issue.message,
        "raw_value": issue.raw_value,
        "normalized_value": issue.normalized_value,
        "details": issue.details,
    }
