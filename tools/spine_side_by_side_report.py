"""Side-by-side Sparkbot vs LIMA Spine comparison report."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from tools.spine_compatibility_probe import build_report as build_compatibility_probe
from tools.spine_field_parity import build_report as build_field_parity
from tools.spine_readonly_adapter_prototype import SparkbotReadonlySpineAdapterPrototype
from tools.spine_route_shape_parity import build_report as build_route_shape_parity
from tools.spine_serializer_fixture_compare import build_report as build_fixture_compare
from tools.spine_translation_parity import build_report as build_translation_parity


def _fixture_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "spine_serializer_expected"


def _gaps_from_reports(
    compatibility: dict[str, Any],
    translation: dict[str, Any],
    route_shape: dict[str, Any],
    field_parity: dict[str, Any],
    fixture_compare: dict[str, Any],
) -> list[str]:
    gaps: list[str] = []
    if compatibility["sparkbot_expected_comparison"]["missing_tables"]:
        gaps.append("Sparkbot expected schema tables are missing from the copied DB.")
    for table, info in compatibility["sparkbot_expected_comparison"]["tables"].items():
        if info["missing_columns"]:
            gaps.append(f"{table} is missing migrated columns required by the comparison contract.")
    for name, mapping in compatibility["lima_generic_mapping"].items():
        if mapping["missing_sources"]:
            gaps.append(f"{name} still lacks Sparkbot source coverage for: {', '.join(mapping['missing_sources'])}.")
    for name, counts in translation["translation_counts"].items():
        if counts["failure"]:
            gaps.append(f"{name} translation still has failures.")
    for limitation in translation.get("limitations", []):
        gaps.append(str(limitation))
    for name, validation in route_shape["route_validations"].items():
        if not validation["valid"]:
            gaps.append(f"{name} route envelope is missing required keys.")
    for name, validation in field_parity["field_checks"].items():
        if not validation["valid"]:
            gaps.append(f"{name} field-level contract is not yet satisfied.")
    for name, comparison in fixture_compare["comparisons"].items():
        if not comparison["match"]:
            gaps.append(f"{name} serializer fixture comparison still has mismatched paths.")
    deduped: list[str] = []
    for gap in gaps:
        if gap not in deduped:
            deduped.append(gap)
    return deduped


def _markdown_report(summary: dict[str, Any]) -> str:
    sparkbot = summary["sparkbot_side"]
    lima = summary["lima_side"]
    pass_fail = summary["pass_fail"]
    gaps = summary["known_gaps"]
    lines = [
        "# Sparkbot vs LIMA Spine Side-by-Side Report",
        "",
        "## Purpose",
        "",
        "This report aggregates the copied-data-only Spine comparison layers to show current compatibility between Sparkbot Spine and the extracted LIMA Spine stack.",
        "",
        "## Sparkbot Side",
        "",
        f"- Expected Sparkbot tables present: {sparkbot['present_expected_tables']} / {sparkbot['expected_table_count']}",
        f"- Missing Sparkbot tables: {', '.join(sparkbot['missing_tables']) if sparkbot['missing_tables'] else 'none'}",
        f"- Sparkbot route-shaped read surface probed: {', '.join(sparkbot['route_surfaces'])}",
        "",
        "## LIMA Side",
        "",
        f"- Translation coverage pass: {lima['translation_pass']}",
        f"- Route envelope pass: {lima['route_shape_pass']}",
        f"- Field-level pass: {lima['field_parity_pass']}",
        f"- Serializer fixture pass: {lima['serializer_fixture_pass']}",
        f"- Redaction checks pass: {lima['redaction_pass']}",
        "",
        "## Pass/Fail",
        "",
        f"- Overall pass: {pass_fail['overall_pass']}",
        f"- Compatibility probe pass: {pass_fail['compatibility_probe_pass']}",
        f"- Translation parity pass: {pass_fail['translation_parity_pass']}",
        f"- Read-only adapter surface available: {pass_fail['readonly_adapter_available']}",
        f"- Route-shape parity pass: {pass_fail['route_shape_pass']}",
        f"- Field-level parity pass: {pass_fail['field_level_pass']}",
        f"- Serializer fixture pass: {pass_fail['serializer_fixture_pass']}",
        "",
        "## Known Gaps",
        "",
    ]
    if gaps:
        lines.extend([f"- {gap}" for gap in gaps])
    else:
        lines.append("- none recorded by the current copied-data report stack")
    lines.extend(
        [
            "",
            "## What This Does Not Do",
            "",
            "- it does not rewire Sparkbot runtime",
            "- it does not perform live DB migration",
            "- it does not introduce dual-write",
            "- it does not validate HTTP transport or auth behavior",
        ]
    )
    return "\n".join(lines) + "\n"


def build_summary(source_db: str | Path) -> dict[str, Any]:
    source_path = Path(source_db)
    if not source_path.exists():
        raise FileNotFoundError(f"Source DB not found: {source_path}")
    if not source_path.is_file():
        raise FileNotFoundError(f"Source DB is not a file: {source_path}")

    with tempfile.TemporaryDirectory(prefix="spine-side-by-side-") as temp_dir:
        temp_copy = Path(temp_dir) / source_path.name
        shutil.copy2(source_path, temp_copy)

        compatibility = build_compatibility_probe(temp_copy)
        translation = build_translation_parity(temp_copy)
        route_shape = build_route_shape_parity(temp_copy)
        field_parity = build_field_parity(temp_copy)
        fixture_compare = build_fixture_compare(temp_copy, _fixture_dir())
        adapter = SparkbotReadonlySpineAdapterPrototype.from_source_db(temp_copy)
        try:
            readonly_adapter_summary = {
                "used_temp_copy": adapter.used_temp_copy,
                "task_count": len(adapter.tasks),
                "project_count": len(adapter.projects),
                "event_count": len(adapter.events),
                "relation_count": len(adapter.relations),
            }
        finally:
            adapter.close()

        sparkbot_side = {
            "expected_table_count": len(compatibility["sparkbot_expected_comparison"]["tables"]),
            "present_expected_tables": len(
                [
                    name
                    for name, info in compatibility["sparkbot_expected_comparison"]["tables"].items()
                    if info["present"]
                ]
            ),
            "missing_tables": compatibility["sparkbot_expected_comparison"]["missing_tables"],
            "route_surfaces": [
                "open_queue",
                "blocked_queue",
                "approval_waiting_queue",
                "recent_events",
                "room_overview",
                "project_workload",
                "task_detail",
            ],
        }
        lima_side = {
            "translation_pass": translation["summary"]["pass"],
            "route_shape_pass": route_shape["summary"]["pass"],
            "field_parity_pass": field_parity["summary"]["pass"],
            "serializer_fixture_pass": fixture_compare["summary"]["pass"],
            "redaction_pass": (
                compatibility["redaction_checks"]["raw_values_emitted"] is False
                and translation["redaction_checks"]["raw_values_emitted"] is False
                and field_parity["redaction_checks"]["raw_values_emitted"] is False
            ),
            "readonly_adapter_summary": readonly_adapter_summary,
        }
        pass_fail = {
            "compatibility_probe_pass": compatibility["summary"]["pass"],
            "translation_parity_pass": translation["summary"]["pass"],
            "readonly_adapter_available": readonly_adapter_summary["used_temp_copy"],
            "route_shape_pass": route_shape["summary"]["pass"],
            "field_level_pass": field_parity["summary"]["pass"],
            "serializer_fixture_pass": fixture_compare["summary"]["pass"],
        }
        pass_fail["overall_pass"] = all(pass_fail.values())

        known_gaps = _gaps_from_reports(compatibility, translation, route_shape, field_parity, fixture_compare)

        return {
            "probe_version": 1,
            "source_db_path": str(source_path),
            "used_temp_copy": True,
            "temp_copy_path": str(temp_copy),
            "source_db_touched_read_only": True,
            "sparkbot_side": sparkbot_side,
            "lima_side": lima_side,
            "pass_fail": pass_fail,
            "known_gaps": known_gaps,
            "sections": {
                "compatibility_probe": compatibility["summary"],
                "translation_parity": translation["summary"],
                "route_shape_parity": route_shape["summary"],
                "field_level_parity": field_parity["summary"],
                "serializer_fixture_comparison": fixture_compare["summary"],
            },
        }


def write_reports(source_db: str | Path, output_dir: str | Path) -> dict[str, Any]:
    summary = build_summary(source_db)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "side_by_side_summary.json"
    report_path = out_dir / "side_by_side_report.md"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(_markdown_report(summary), encoding="utf-8")
    return {
        "summary": summary,
        "summary_path": str(summary_path),
        "report_path": str(report_path),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a Sparkbot vs LIMA Spine side-by-side report")
    parser.add_argument("--source-db", required=True, help="Path to the source Sparkbot Spine SQLite DB")
    parser.add_argument("--output-dir", required=True, help="Directory to write the side-by-side report outputs")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        write_reports(args.source_db, args.output_dir)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Side-by-side report failed safely: {exc.__class__.__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
