import json
import sys
from pathlib import Path

import pytest

from reconcile import main, run_reconciliation

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_run_reconciliation_writes_expected_json_report(tmp_path: Path) -> None:
    output_path = tmp_path / "reconciliation_report.json"

    report = run_reconciliation(
        snapshot_1_path=_REPO_ROOT / "data" / "snapshot_1.csv",
        snapshot_2_path=_REPO_ROOT / "data" / "snapshot_2.csv",
        output_path=output_path,
    )

    written_report = json.loads(output_path.read_text(encoding="utf-8"))

    assert written_report == report
    assert list(written_report) == [
        "flagged_items",
        "only_in_snapshot_1",
        "only_in_snapshot_2",
        "present_in_both",
        "summary",
    ]
    assert len(written_report["present_in_both"]) == 73
    assert len(written_report["only_in_snapshot_1"]) == 2
    assert len(written_report["only_in_snapshot_2"]) == 5
    assert len(written_report["flagged_items"]) == 2
    assert [item["code"] for item in written_report["flagged_items"]] == [
        "duplicate_sku",
        "negative_quantity",
    ]
    assert written_report["summary"] == {
        "snapshot_1_records": 75,
        "snapshot_2_records": 78,
        "present_in_both": 73,
        "quantity_changed": 71,
        "quantity_unchanged": 2,
        "quantity_increased": 0,
        "quantity_decreased": 71,
        "only_in_snapshot_1": 2,
        "only_in_snapshot_2": 5,
        "name_changed": 1,
        "location_changed": 0,
        "total_quality_issues": 14,
        "flagged_items_count": 2,
        "quality_issue_counts_by_code": {
            "coerced_quantity": 2,
            "duplicate_sku": 1,
            "negative_quantity": 1,
            "normalized_date": 1,
            "normalized_sku": 3,
            "skipped_empty_row": 1,
            "trimmed_whitespace": 5,
        },
    }


def test_run_reconciliation_includes_temporal_validation_issues(
    tmp_path: Path,
) -> None:
    snapshot_1_path = tmp_path / "snapshot_1.csv"
    snapshot_2_path = tmp_path / "snapshot_2.csv"
    output_path = tmp_path / "reconciliation_report.json"

    snapshot_1_path.write_text(
        (
            "sku,name,quantity,location,last_counted\n"
            "SKU-001,Widget A,10,Warehouse A,2024-01-15\n"
        ),
        encoding="utf-8",
    )
    snapshot_2_path.write_text(
        (
            "sku,product_name,qty,warehouse,updated_at\n"
            "SKU-001,Widget A,8,Warehouse A,2024-01-14\n"
        ),
        encoding="utf-8",
    )

    report = run_reconciliation(
        snapshot_1_path=snapshot_1_path,
        snapshot_2_path=snapshot_2_path,
        output_path=output_path,
    )

    assert [item["code"] for item in report["flagged_items"]] == [
        "snapshot_order_invalid"
    ]
    assert report["flagged_items"][0]["source_line"] is None
    assert report["summary"]["total_quality_issues"] == 1
    assert report["summary"]["flagged_items_count"] == 1
    assert report["summary"]["quality_issue_counts_by_code"] == {
        "snapshot_order_invalid": 1
    }


def test_main_returns_zero_when_report_has_no_error_issues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "reconciliation_report.json"
    snapshot_1_path = _REPO_ROOT / "data" / "snapshot_1.csv"
    snapshot_2_path = _REPO_ROOT / "data" / "snapshot_2.csv"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "reconcile.py",
            "--snapshot-1",
            str(snapshot_1_path),
            "--snapshot-2",
            str(snapshot_2_path),
            "--output",
            str(output_path),
        ],
    )

    exit_code = main()

    assert exit_code == 0
    assert output_path.exists()


def test_main_returns_non_zero_when_report_has_error_issues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot_1_path = tmp_path / "snapshot_1.csv"
    snapshot_2_path = tmp_path / "snapshot_2.csv"
    output_path = tmp_path / "reconciliation_report.json"

    snapshot_1_path.write_text(
        (
            "sku,name,quantity,location,last_counted\n"
            "SKU-001,Widget A,10,Warehouse A,2024-01-15\n"
        ),
        encoding="utf-8",
    )
    snapshot_2_path.write_text(
        (
            "sku,product_name,qty,warehouse,updated_at\n"
            "SKU-001,Widget A,8,Warehouse A,2024-01-14\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "reconcile.py",
            "--snapshot-1",
            str(snapshot_1_path),
            "--snapshot-2",
            str(snapshot_2_path),
            "--output",
            str(output_path),
        ],
    )

    exit_code = main()
    written_report = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert [item["code"] for item in written_report["flagged_items"]] == [
        "snapshot_order_invalid"
    ]
