from collections.abc import Iterable

from inventory_reconciliation.records import (
    IssueCode,
    IssueSeverity,
    QualityIssue,
    SnapshotLoadResult,
)

_MANUAL_REVIEW_WARNING_CODES = frozenset(
    {
        IssueCode.DUPLICATE_SKU,
        IssueCode.MIXED_SNAPSHOT_DATES,
        IssueCode.NEGATIVE_QUANTITY,
    }
)


def issue_requires_manual_review(issue: QualityIssue) -> bool:
    if issue.severity is IssueSeverity.ERROR:
        return True
    return issue.code in _MANUAL_REVIEW_WARNING_CODES


def collect_flagged_issues(issues: Iterable[QualityIssue]) -> list[QualityIssue]:
    flagged_issues = [issue for issue in issues if issue_requires_manual_review(issue)]
    return sorted(flagged_issues, key=_issue_sort_key)


def collect_flagged_issues_from_results(
    results: Iterable[SnapshotLoadResult],
) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    for result in results:
        issues.extend(result.issues)
    return collect_flagged_issues(issues)


def _issue_sort_key(issue: QualityIssue) -> tuple[str, int, str, str, str]:
    return (
        issue.snapshot.value,
        issue.source_line if issue.source_line is not None else -1,
        issue.code.value,
        issue.field_name or "",
        issue.sku or "",
    )
