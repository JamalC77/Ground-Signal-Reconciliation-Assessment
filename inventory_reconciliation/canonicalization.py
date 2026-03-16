import math
import re
from dataclasses import dataclass
from datetime import date, datetime

from inventory_reconciliation.records import (
    CanonicalInventoryRecord,
    IssueCode,
    IssueSeverity,
    QualityIssue,
    RowAction,
    SnapshotName,
    mark_row_action,
)

_SKU_PATTERN = re.compile(r"^SKU-(\d+)$")
_SKU_WITHOUT_HYPHEN_PATTERN = re.compile(r"^SKU(\d+)$")


@dataclass(frozen=True, slots=True, kw_only=True)
class CanonicalRowInput:
    sku: str
    name: str
    quantity: str
    location: str
    counted_on: str


def canonicalize_row(
    raw_row: CanonicalRowInput,
    *,
    snapshot: SnapshotName,
    source_line: int,
) -> tuple[CanonicalInventoryRecord | None, list[QualityIssue]]:
    issues: list[QualityIssue] = []

    sku, sku_issues = normalize_sku(
        raw_row.sku,
        snapshot=snapshot,
        source_line=source_line,
    )
    issues.extend(sku_issues)

    name, name_issues = normalize_required_text(
        raw_row.name,
        field_name="name",
        snapshot=snapshot,
        source_line=source_line,
        sku=sku,
    )
    issues.extend(name_issues)

    quantity, quantity_issues = parse_quantity(
        raw_row.quantity,
        snapshot=snapshot,
        source_line=source_line,
        sku=sku,
    )
    issues.extend(quantity_issues)

    location, location_issues = normalize_required_text(
        raw_row.location,
        field_name="location",
        snapshot=snapshot,
        source_line=source_line,
        sku=sku,
    )
    issues.extend(location_issues)

    counted_on, date_issues = normalize_date(
        raw_row.counted_on,
        snapshot=snapshot,
        source_line=source_line,
        sku=sku,
    )
    issues.extend(date_issues)

    if (
        sku is None
        or name is None
        or quantity is None
        or location is None
        or counted_on is None
    ):
        mark_row_action(issues, RowAction.REJECTED)
        return None, issues

    record = CanonicalInventoryRecord(
        snapshot=snapshot,
        source_line=source_line,
        sku=sku,
        name=name,
        quantity=quantity,
        location=location,
        counted_on=counted_on,
    )
    return record, issues


def normalize_required_text(
    raw_value: str,
    *,
    field_name: str,
    snapshot: SnapshotName,
    source_line: int,
    sku: str | None = None,
) -> tuple[str | None, list[QualityIssue]]:
    cleaned_value, issues = _strip_value(
        raw_value,
        field_name=field_name,
        snapshot=snapshot,
        source_line=source_line,
        sku=sku,
    )
    if cleaned_value:
        return cleaned_value, issues

    issues.append(
        _build_issue(
            code=IssueCode.BLANK_REQUIRED_FIELD,
            severity=IssueSeverity.ERROR,
            snapshot=snapshot,
            source_line=source_line,
            field_name=field_name,
            sku=sku,
            raw_value=raw_value,
            message=f"{field_name} is required after whitespace cleanup.",
        )
    )
    return None, issues


def normalize_sku(
    raw_sku: str,
    *,
    snapshot: SnapshotName,
    source_line: int,
) -> tuple[str | None, list[QualityIssue]]:
    cleaned_value, issues = _strip_value(
        raw_sku,
        field_name="sku",
        snapshot=snapshot,
        source_line=source_line,
    )
    if not cleaned_value:
        issues.append(
            _build_issue(
                code=IssueCode.BLANK_REQUIRED_FIELD,
                severity=IssueSeverity.ERROR,
                snapshot=snapshot,
                source_line=source_line,
                field_name="sku",
                raw_value=raw_sku,
                message="sku is required after whitespace cleanup.",
            )
        )
        return None, issues

    candidate = re.sub(r"\s*-\s*", "-", cleaned_value.upper())

    missing_hyphen_match = _SKU_WITHOUT_HYPHEN_PATTERN.fullmatch(candidate)
    if missing_hyphen_match is not None:
        normalized_sku = f"SKU-{missing_hyphen_match.group(1)}"
    elif _SKU_PATTERN.fullmatch(candidate) is not None:
        normalized_sku = candidate
    else:
        issues.append(
            _build_issue(
                code=IssueCode.INVALID_SKU,
                severity=IssueSeverity.ERROR,
                snapshot=snapshot,
                source_line=source_line,
                field_name="sku",
                raw_value=raw_sku,
                normalized_value=candidate,
                message="sku does not match the supported SKU pattern.",
            )
        )
        return None, issues

    if normalized_sku != raw_sku:
        issues.append(
            _build_issue(
                code=IssueCode.NORMALIZED_SKU,
                severity=IssueSeverity.WARNING,
                snapshot=snapshot,
                source_line=source_line,
                field_name="sku",
                sku=normalized_sku,
                raw_value=raw_sku,
                normalized_value=normalized_sku,
                message="sku was normalized before reconciliation.",
            )
        )

    return normalized_sku, issues


def parse_quantity(
    raw_quantity: str,
    *,
    snapshot: SnapshotName,
    source_line: int,
    sku: str | None = None,
) -> tuple[int | None, list[QualityIssue]]:
    cleaned_value, issues = _strip_value(
        raw_quantity,
        field_name="quantity",
        snapshot=snapshot,
        source_line=source_line,
        sku=sku,
    )
    if not cleaned_value:
        issues.append(
            _build_issue(
                code=IssueCode.BLANK_REQUIRED_FIELD,
                severity=IssueSeverity.ERROR,
                snapshot=snapshot,
                source_line=source_line,
                field_name="quantity",
                sku=sku,
                raw_value=raw_quantity,
                message="quantity is required after whitespace cleanup.",
            )
        )
        return None, issues

    try:
        quantity = int(cleaned_value)
    except ValueError:
        try:
            parsed_float = float(cleaned_value)
        except ValueError:
            issues.append(
                _build_issue(
                    code=IssueCode.INVALID_QUANTITY,
                    severity=IssueSeverity.ERROR,
                    snapshot=snapshot,
                    source_line=source_line,
                    field_name="quantity",
                    sku=sku,
                    raw_value=raw_quantity,
                    message="quantity is not a valid integer value.",
                )
            )
            return None, issues

        if not math.isfinite(parsed_float) or not parsed_float.is_integer():
            issues.append(
                _build_issue(
                    code=IssueCode.INVALID_QUANTITY,
                    severity=IssueSeverity.ERROR,
                    snapshot=snapshot,
                    source_line=source_line,
                    field_name="quantity",
                    sku=sku,
                    raw_value=raw_quantity,
                    message="fractional quantities are rejected instead of truncated.",
                )
            )
            return None, issues

        quantity = int(parsed_float)
        issues.append(
            _build_issue(
                code=IssueCode.COERCED_QUANTITY,
                severity=IssueSeverity.WARNING,
                snapshot=snapshot,
                source_line=source_line,
                field_name="quantity",
                sku=sku,
                raw_value=raw_quantity,
                normalized_value=quantity,
                message="quantity was coerced from a whole-number float.",
            )
        )

    if quantity < 0:
        issues.append(
            _build_issue(
                code=IssueCode.NEGATIVE_QUANTITY,
                severity=IssueSeverity.WARNING,
                snapshot=snapshot,
                source_line=source_line,
                field_name="quantity",
                sku=sku,
                raw_value=raw_quantity,
                normalized_value=quantity,
                message="quantity is negative and should be reviewed by a human.",
            )
        )

    return quantity, issues


def normalize_date(
    raw_date: str,
    *,
    snapshot: SnapshotName,
    source_line: int,
    sku: str | None = None,
) -> tuple[date | None, list[QualityIssue]]:
    cleaned_value, issues = _strip_value(
        raw_date,
        field_name="counted_on",
        snapshot=snapshot,
        source_line=source_line,
        sku=sku,
    )
    if not cleaned_value:
        issues.append(
            _build_issue(
                code=IssueCode.BLANK_REQUIRED_FIELD,
                severity=IssueSeverity.ERROR,
                snapshot=snapshot,
                source_line=source_line,
                field_name="counted_on",
                sku=sku,
                raw_value=raw_date,
                message="counted_on is required after whitespace cleanup.",
            )
        )
        return None, issues

    try:
        return date.fromisoformat(cleaned_value), issues
    except ValueError:
        pass

    try:
        normalized_date = datetime.strptime(cleaned_value, "%m/%d/%Y").date()
    except ValueError:
        issues.append(
            _build_issue(
                code=IssueCode.INVALID_DATE,
                severity=IssueSeverity.ERROR,
                snapshot=snapshot,
                source_line=source_line,
                field_name="counted_on",
                sku=sku,
                raw_value=raw_date,
                message="counted_on is not a supported date format.",
            )
        )
        return None, issues

    issues.append(
        _build_issue(
            code=IssueCode.NORMALIZED_DATE,
            severity=IssueSeverity.WARNING,
            snapshot=snapshot,
            source_line=source_line,
            field_name="counted_on",
            sku=sku,
            raw_value=raw_date,
            normalized_value=normalized_date.isoformat(),
            message="counted_on was normalized to ISO format.",
        )
    )
    return normalized_date, issues


def _strip_value(
    raw_value: str,
    *,
    field_name: str,
    snapshot: SnapshotName,
    source_line: int,
    sku: str | None = None,
) -> tuple[str, list[QualityIssue]]:
    cleaned_value = raw_value.strip()
    issues: list[QualityIssue] = []
    if cleaned_value != raw_value:
        issues.append(
            _build_issue(
                code=IssueCode.TRIMMED_WHITESPACE,
                severity=IssueSeverity.INFO,
                snapshot=snapshot,
                source_line=source_line,
                field_name=field_name,
                sku=sku,
                raw_value=raw_value,
                normalized_value=cleaned_value,
                message=f"{field_name} had leading or trailing whitespace removed.",
            )
        )
    return cleaned_value, issues


def _build_issue(
    *,
    code: IssueCode,
    severity: IssueSeverity,
    snapshot: SnapshotName,
    source_line: int,
    message: str,
    row_action: RowAction = RowAction.ACCEPTED,
    field_name: str | None = None,
    sku: str | None = None,
    raw_value: str | None = None,
    normalized_value: str | int | None = None,
) -> QualityIssue:
    return QualityIssue(
        code=code,
        severity=severity,
        snapshot=snapshot,
        source_line=source_line,
        message=message,
        row_action=row_action,
        field_name=field_name,
        sku=sku,
        raw_value=raw_value,
        normalized_value=normalized_value,
    )
