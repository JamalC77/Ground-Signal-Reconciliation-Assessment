import argparse
import logging
from dataclasses import dataclass
from pathlib import Path

from inventory_reconciliation.records import IssueSeverity, SnapshotName
from inventory_reconciliation.reporting import (
    ReconciliationReport,
    build_reconciliation_report,
    write_reconciliation_report,
)
from inventory_reconciliation.snapshot_loader import load_snapshot
from inventory_reconciliation.snapshot_reconciler import reconcile_snapshots
from inventory_reconciliation.temporal_validation import validate_temporal_consistency

log = logging.getLogger(__name__)

DEFAULT_SNAPSHOT_1_PATH = Path("data") / "snapshot_1.csv"
DEFAULT_SNAPSHOT_2_PATH = Path("data") / "snapshot_2.csv"
DEFAULT_OUTPUT_PATH = Path("output") / "reconciliation_report.json"


@dataclass(frozen=True, slots=True)
class ReconciliationRunResult:
    report: ReconciliationReport
    has_error_quality_issues: bool


def run_reconciliation(
    snapshot_1_path: Path = DEFAULT_SNAPSHOT_1_PATH,
    snapshot_2_path: Path = DEFAULT_SNAPSHOT_2_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> ReconciliationReport:
    return _run_reconciliation_with_status(
        snapshot_1_path=snapshot_1_path,
        snapshot_2_path=snapshot_2_path,
        output_path=output_path,
    ).report


def _run_reconciliation_with_status(
    *,
    snapshot_1_path: Path,
    snapshot_2_path: Path,
    output_path: Path,
) -> ReconciliationRunResult:
    snapshot_1_result = load_snapshot(
        snapshot_1_path,
        snapshot=SnapshotName.SNAPSHOT_1,
    )
    snapshot_2_result = load_snapshot(
        snapshot_2_path,
        snapshot=SnapshotName.SNAPSHOT_2,
    )
    reconciliation_result = reconcile_snapshots(
        snapshot_1_result.records,
        snapshot_2_result.records,
    )
    temporal_issues = validate_temporal_consistency(
        snapshot_1_result.records,
        snapshot_2_result.records,
    )
    all_issues = [
        *snapshot_1_result.issues,
        *snapshot_2_result.issues,
        *temporal_issues,
    ]
    report = build_reconciliation_report(
        snapshot_1_result,
        snapshot_2_result,
        reconciliation_result,
        additional_issues=temporal_issues,
    )
    write_reconciliation_report(report, output_path)
    return ReconciliationRunResult(
        report=report,
        has_error_quality_issues=any(
            issue.severity is IssueSeverity.ERROR for issue in all_issues
        ),
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    arguments = _build_argument_parser().parse_args()
    result = _run_reconciliation_with_status(
        snapshot_1_path=arguments.snapshot_1,
        snapshot_2_path=arguments.snapshot_2,
        output_path=arguments.output,
    )
    log.info("Wrote reconciliation report to %s", arguments.output)
    if result.has_error_quality_issues:
        log.error(
            "Reconciliation report contains error-severity quality issues; "
            "review %s before trusting the results.",
            arguments.output,
        )
        return 1
    return 0


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reconcile two inventory snapshots into a structured JSON report.",
    )
    parser.add_argument(
        "--snapshot-1",
        type=Path,
        default=DEFAULT_SNAPSHOT_1_PATH,
        help="Path to the older snapshot CSV file.",
    )
    parser.add_argument(
        "--snapshot-2",
        type=Path,
        default=DEFAULT_SNAPSHOT_2_PATH,
        help="Path to the newer snapshot CSV file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path for the generated JSON report.",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
