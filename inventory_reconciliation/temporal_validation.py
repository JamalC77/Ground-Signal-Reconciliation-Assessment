from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from inventory_reconciliation.records import (
    CanonicalInventoryRecord,
    IssueCode,
    IssueSeverity,
    QualityIssue,
    RowAction,
    SnapshotName,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class SnapshotDateStats:
    snapshot: SnapshotName
    min_date: date
    max_date: date
    distinct_dates: tuple[date, ...]


def validate_temporal_consistency(
    snapshot_1_records: Iterable[CanonicalInventoryRecord],
    snapshot_2_records: Iterable[CanonicalInventoryRecord],
) -> list[QualityIssue]:
    issues: list[QualityIssue] = []

    snapshot_1_stats = _build_snapshot_date_stats(
        snapshot_1_records,
        snapshot=SnapshotName.SNAPSHOT_1,
    )
    snapshot_2_stats = _build_snapshot_date_stats(
        snapshot_2_records,
        snapshot=SnapshotName.SNAPSHOT_2,
    )

    for stats in (snapshot_1_stats, snapshot_2_stats):
        if stats is not None and len(stats.distinct_dates) > 1:
            issues.append(_build_mixed_dates_issue(stats))

    if snapshot_1_stats is None or snapshot_2_stats is None:
        return issues

    if snapshot_2_stats.min_date < snapshot_1_stats.max_date:
        issues.append(
            _build_snapshot_order_issue(
                snapshot_1_stats=snapshot_1_stats,
                snapshot_2_stats=snapshot_2_stats,
            )
        )

    return issues


def _build_snapshot_date_stats(
    records: Iterable[CanonicalInventoryRecord],
    *,
    snapshot: SnapshotName,
) -> SnapshotDateStats | None:
    distinct_dates = tuple(sorted({record.counted_on for record in records}))
    if not distinct_dates:
        return None

    return SnapshotDateStats(
        snapshot=snapshot,
        min_date=distinct_dates[0],
        max_date=distinct_dates[-1],
        distinct_dates=distinct_dates,
    )


def _build_mixed_dates_issue(stats: SnapshotDateStats) -> QualityIssue:
    return QualityIssue(
        code=IssueCode.MIXED_SNAPSHOT_DATES,
        severity=IssueSeverity.WARNING,
        snapshot=stats.snapshot,
        source_line=None,
        message=(
            f"{stats.snapshot.value} contains multiple dates and may not represent "
            "a single coherent inventory snapshot."
        ),
        row_action=RowAction.NOT_APPLICABLE,
        field_name="counted_on",
        normalized_value=stats.distinct_dates[0].isoformat(),
        details={
            "distinct_date_count": len(stats.distinct_dates),
            "min_date": stats.min_date.isoformat(),
            "max_date": stats.max_date.isoformat(),
            "distinct_dates": ", ".join(
                snapshot_date.isoformat() for snapshot_date in stats.distinct_dates
            ),
        },
    )


def _build_snapshot_order_issue(
    *,
    snapshot_1_stats: SnapshotDateStats,
    snapshot_2_stats: SnapshotDateStats,
) -> QualityIssue:
    return QualityIssue(
        code=IssueCode.SNAPSHOT_ORDER_INVALID,
        severity=IssueSeverity.ERROR,
        snapshot=SnapshotName.SNAPSHOT_2,
        source_line=None,
        message=(
            "snapshot_2 contains dates earlier than snapshot_1, so the temporal "
            "ordering should be reviewed before trusting the reconciliation."
        ),
        row_action=RowAction.NOT_APPLICABLE,
        field_name="counted_on",
        normalized_value=snapshot_2_stats.min_date.isoformat(),
        details={
            "snapshot_1_max_date": snapshot_1_stats.max_date.isoformat(),
            "snapshot_2_min_date": snapshot_2_stats.min_date.isoformat(),
        },
    )
