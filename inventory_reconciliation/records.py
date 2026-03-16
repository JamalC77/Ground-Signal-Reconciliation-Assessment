from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum


class SnapshotName(StrEnum):
    SNAPSHOT_1 = "snapshot_1"
    SNAPSHOT_2 = "snapshot_2"


class IssueSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class IssueCode(StrEnum):
    TRIMMED_WHITESPACE = "trimmed_whitespace"
    NORMALIZED_SKU = "normalized_sku"
    BLANK_REQUIRED_FIELD = "blank_required_field"
    INVALID_SKU = "invalid_sku"
    COERCED_QUANTITY = "coerced_quantity"
    INVALID_QUANTITY = "invalid_quantity"
    NEGATIVE_QUANTITY = "negative_quantity"
    NORMALIZED_DATE = "normalized_date"
    INVALID_DATE = "invalid_date"
    OVERLONG_ROW = "overlong_row"
    MIXED_SNAPSHOT_DATES = "mixed_snapshot_dates"
    SNAPSHOT_ORDER_INVALID = "snapshot_order_invalid"
    DUPLICATE_SKU = "duplicate_sku"
    SKIPPED_EMPTY_ROW = "skipped_empty_row"


class RowAction(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SKIPPED_EMPTY = "skipped_empty"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    NOT_APPLICABLE = "not_applicable"


type IssueDetails = dict[str, str | int]


@dataclass(frozen=True, slots=True, kw_only=True)
class CanonicalInventoryRecord:
    snapshot: SnapshotName
    source_line: int
    sku: str
    name: str
    quantity: int
    location: str
    counted_on: date


@dataclass(slots=True, kw_only=True)
class QualityIssue:
    code: IssueCode
    severity: IssueSeverity
    snapshot: SnapshotName
    source_line: int | None
    message: str
    row_action: RowAction
    field_name: str | None = None
    sku: str | None = None
    raw_value: str | None = None
    normalized_value: str | int | None = None
    details: IssueDetails = field(default_factory=dict)


@dataclass(slots=True, kw_only=True)
class SnapshotLoadResult:
    snapshot: SnapshotName
    records: list[CanonicalInventoryRecord]
    issues: list[QualityIssue]


def mark_row_action(issues: list[QualityIssue], row_action: RowAction) -> None:
    for issue in issues:
        issue.row_action = row_action
