from inventory_reconciliation.quality_review import (
    collect_flagged_issues,
    collect_flagged_issues_from_results,
    issue_requires_manual_review,
)
from inventory_reconciliation.records import (
    IssueCode,
    IssueSeverity,
    QualityIssue,
    RowAction,
    SnapshotName,
)
from inventory_reconciliation.snapshot_loader import load_snapshot


def test_issue_requires_manual_review_filters_routine_cleanup_noise() -> None:
    issues = [
        _build_issue(
            code=IssueCode.TRIMMED_WHITESPACE,
            severity=IssueSeverity.INFO,
            snapshot=SnapshotName.SNAPSHOT_2,
            source_line=11,
        ),
        _build_issue(
            code=IssueCode.NORMALIZED_DATE,
            severity=IssueSeverity.WARNING,
            snapshot=SnapshotName.SNAPSHOT_2,
            source_line=34,
        ),
        _build_issue(
            code=IssueCode.INVALID_SKU,
            severity=IssueSeverity.ERROR,
            snapshot=SnapshotName.SNAPSHOT_1,
            source_line=3,
        ),
        _build_issue(
            code=IssueCode.DUPLICATE_SKU,
            severity=IssueSeverity.WARNING,
            snapshot=SnapshotName.SNAPSHOT_2,
            source_line=54,
        ),
        _build_issue(
            code=IssueCode.NEGATIVE_QUANTITY,
            severity=IssueSeverity.WARNING,
            snapshot=SnapshotName.SNAPSHOT_2,
            source_line=54,
        ),
    ]

    flagged_issues = collect_flagged_issues(issues)

    assert issue_requires_manual_review(issues[0]) is False
    assert issue_requires_manual_review(issues[1]) is False
    assert issue_requires_manual_review(issues[2]) is True
    assert issue_requires_manual_review(issues[3]) is True
    assert issue_requires_manual_review(issues[4]) is True
    assert [(issue.code, issue.source_line) for issue in flagged_issues] == [
        (IssueCode.INVALID_SKU, 3),
        (IssueCode.DUPLICATE_SKU, 54),
        (IssueCode.NEGATIVE_QUANTITY, 54),
    ]


def test_collect_flagged_issues_from_results_uses_real_snapshot_issues() -> None:
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    snapshot_1 = load_snapshot(
        repo_root / "data" / "snapshot_1.csv",
        snapshot=SnapshotName.SNAPSHOT_1,
    )
    snapshot_2 = load_snapshot(
        repo_root / "data" / "snapshot_2.csv",
        snapshot=SnapshotName.SNAPSHOT_2,
    )

    flagged_issues = collect_flagged_issues_from_results([snapshot_1, snapshot_2])

    assert [(issue.code, issue.source_line) for issue in flagged_issues] == [
        (IssueCode.DUPLICATE_SKU, 54),
        (IssueCode.NEGATIVE_QUANTITY, 54),
    ]


def _build_issue(
    *,
    code: IssueCode,
    severity: IssueSeverity,
    snapshot: SnapshotName,
    source_line: int,
) -> QualityIssue:
    return QualityIssue(
        code=code,
        severity=severity,
        snapshot=snapshot,
        source_line=source_line,
        message=code.value,
        row_action=RowAction.ACCEPTED,
    )
