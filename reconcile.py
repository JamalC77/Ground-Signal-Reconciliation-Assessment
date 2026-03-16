from __future__ import annotations

import argparse
import logging
from pathlib import Path

from inventory_reconciliation.records import SnapshotName
from inventory_reconciliation.reporting import (
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


def run_reconciliation(
    snapshot_1_path: Path = DEFAULT_SNAPSHOT_1_PATH,
    snapshot_2_path: Path = DEFAULT_SNAPSHOT_2_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> dict[str, object]:
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
    report = build_reconciliation_report(
        snapshot_1_result,
        snapshot_2_result,
        reconciliation_result,
        additional_issues=temporal_issues,
    )
    write_reconciliation_report(report, output_path)
    return report


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    arguments = _build_argument_parser().parse_args()
    run_reconciliation(
        snapshot_1_path=arguments.snapshot_1,
        snapshot_2_path=arguments.snapshot_2,
        output_path=arguments.output,
    )
    log.info("Wrote reconciliation report to %s", arguments.output)
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
