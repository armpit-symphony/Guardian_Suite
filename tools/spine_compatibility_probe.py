"""Read-only Sparkbot Spine compatibility probe.

Copies a source SQLite database to a temporary location, inspects schema and
safe aggregate characteristics there, and writes a JSON report.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any


SPARKBOT_EXPECTED_SCHEMA: dict[str, set[str]] = {
    "guardian_spine_tasks": {
        "task_id",
        "room_id",
        "title",
        "summary",
        "project_id",
        "type",
        "priority",
        "status",
        "owner_kind",
        "owner_id",
        "source_kind",
        "source_ref",
        "created_by_guardian",
        "created_by_subsystem",
        "updated_by_subsystem",
        "approval_required",
        "approval_state",
        "confidence",
        "parent_task_id",
        "depends_on_json",
        "tags_json",
        "created_at",
        "updated_at",
        "last_progress_at",
        "closed_at",
        "source_excerpt",
        "chat_task_id",
    },
    "guardian_spine_events": {
        "event_id",
        "event_type",
        "occurred_at",
        "room_id",
        "subsystem",
        "actor_kind",
        "actor_id",
        "source_kind",
        "source_ref",
        "correlation_id",
        "task_id",
        "project_id",
        "payload_json",
    },
    "guardian_spine_links": {"id", "task_id", "related_task_id", "link_type", "created_at"},
    "guardian_spine_assignments": {"id", "task_id", "owner_kind", "owner_id", "assigned_at", "assigned_by"},
    "guardian_spine_approvals": {
        "id",
        "task_id",
        "requester_id",
        "approver_id",
        "approval_method",
        "state",
        "scope_json",
        "expires_at",
        "created_at",
        "updated_at",
    },
    "guardian_spine_handoffs": {"id", "task_id", "room_id", "summary", "created_at", "source_ref"},
    "guardian_spine_projects": {
        "project_id",
        "room_id",
        "display_name",
        "slug",
        "summary",
        "status",
        "source_kind",
        "source_ref",
        "created_by_subsystem",
        "updated_by_subsystem",
        "tags_json",
        "parent_project_id",
        "created_at",
        "updated_at",
        "owner_kind",
        "owner_id",
    },
    "guardian_spine_project_events": {
        "event_id",
        "project_id",
        "event_type",
        "occurred_at",
        "room_id",
        "subsystem",
        "source_kind",
        "source_ref",
        "payload_json",
    },
}

LIMA_GENERIC_EXPECTED_SCHEMA: dict[str, set[str]] = {
    "spine_events": {
        "event_id",
        "event_type",
        "category",
        "occurred_at",
        "room_id",
        "subsystem",
        "actor_kind",
        "actor_id",
        "source_kind",
        "source_ref",
        "correlation_id",
        "task_id",
        "project_id",
        "payload_json",
        "metadata_json",
        "redacted",
        "created_at",
        "updated_at",
    },
    "spine_tasks": {
        "task_id",
        "title",
        "room_id",
        "summary",
        "project_id",
        "type",
        "priority",
        "status",
        "owner_kind",
        "owner_id",
        "approval_required",
        "approval_state",
        "confidence",
        "parent_task_id",
        "depends_on_json",
        "tags_json",
        "source_kind",
        "source_ref",
        "created_at",
        "updated_at",
        "last_progress_at",
        "closed_at",
        "metadata_json",
        "redacted",
    },
    "spine_projects": {
        "project_id",
        "display_name",
        "slug",
        "room_id",
        "summary",
        "status",
        "tags_json",
        "parent_project_id",
        "owner_kind",
        "owner_id",
        "created_at",
        "updated_at",
        "metadata_json",
        "redacted",
    },
    "spine_relations": {
        "relation_id",
        "from_entity_type",
        "from_entity_id",
        "to_entity_type",
        "to_entity_id",
        "relation_type",
        "created_at",
        "metadata_json",
        "redacted",
    },
    "spine_producers": {
        "subsystem",
        "description",
        "event_types_json",
        "metadata_json",
        "redacted",
        "created_at",
        "updated_at",
    },
}

GENERIC_MAPPING: dict[str, dict[str, Any]] = {
    "spine_events": {
        "sparkbot_sources": ["guardian_spine_events"],
        "sparkbot_only_fields": [],
    },
    "spine_tasks": {
        "sparkbot_sources": ["guardian_spine_tasks"],
        "sparkbot_only_fields": [
            "created_by_guardian",
            "created_by_subsystem",
            "updated_by_subsystem",
            "source_excerpt",
            "chat_task_id",
        ],
    },
    "spine_projects": {
        "sparkbot_sources": ["guardian_spine_projects"],
        "sparkbot_only_fields": [
            "source_kind",
            "source_ref",
            "created_by_subsystem",
            "updated_by_subsystem",
        ],
    },
    "spine_relations": {
        "sparkbot_sources": ["guardian_spine_links"],
        "sparkbot_only_fields": [],
    },
    "spine_producers": {
        "sparkbot_sources": ["in_memory_registry"],
        "sparkbot_only_fields": [],
    },
}

SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_key",
    "auth_token",
    "private_key",
    "vault_key",
    "pin",
)


def _classify_event(*, event_type: str | None, subsystem: str | None, task_id: str | None, project_id: str | None) -> str:
    text = f"{event_type or ''} {subsystem or ''}".lower()
    if "approval" in text:
        return "approval"
    if "breakglass" in text or "security" in text:
        return "security"
    if "meeting" in text:
        return "meeting"
    if "handoff" in text:
        return "handoff"
    if "project" in text or project_id:
        return "project"
    if "worker" in text:
        return "worker"
    if "executive" in text or "verif" in text:
        return "executive_or_verifier"
    if "memory" in text:
        return "memory"
    if task_id:
        return "task"
    return "other"


def _safe_json_load(raw: str | None) -> tuple[dict[str, Any] | list[Any] | None, bool]:
    if not raw:
        return {}, False
    try:
        return json.loads(raw), False
    except Exception:
        return None, True


def _contains_sensitive_keys(value: Any) -> int:
    if isinstance(value, dict):
        count = 0
        for key, item in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in SENSITIVE_KEY_PARTS):
                count += 1
            count += _contains_sensitive_keys(item)
        return count
    if isinstance(value, list):
        return sum(_contains_sensitive_keys(item) for item in value)
    return 0


def _count_redacted_markers(value: Any) -> int:
    if isinstance(value, dict):
        return sum(_count_redacted_markers(item) for item in value.values())
    if isinstance(value, list):
        return sum(_count_redacted_markers(item) for item in value)
    return 1 if value == "[REDACTED]" else 0


def _schema_for_db(conn: sqlite3.Connection) -> dict[str, list[str]]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name ASC"
    ).fetchall()
    tables = [str(row[0]) for row in rows]
    schema: dict[str, list[str]] = {}
    for table in tables:
        cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
        schema[table] = [str(col[1]) for col in cols]
    return schema


def _compare_expected(actual: dict[str, list[str]], expected: dict[str, set[str]]) -> dict[str, Any]:
    actual_tables = set(actual)
    expected_tables = set(expected)
    missing_tables = sorted(expected_tables - actual_tables)
    extra_tables = sorted(actual_tables - expected_tables)
    tables: dict[str, Any] = {}
    for table, expected_columns in expected.items():
        actual_columns = set(actual.get(table, []))
        tables[table] = {
            "present": table in actual,
            "missing_columns": sorted(expected_columns - actual_columns),
            "extra_columns": sorted(actual_columns - expected_columns),
        }
    return {
        "missing_tables": missing_tables,
        "extra_tables": extra_tables,
        "tables": tables,
    }


def _mapping_report(actual: dict[str, list[str]]) -> dict[str, Any]:
    report: dict[str, Any] = {}
    for generic_table, config in GENERIC_MAPPING.items():
        sparkbot_sources = list(config["sparkbot_sources"])
        available_sources = [name for name in sparkbot_sources if name in actual or name == "in_memory_registry"]
        missing_sources = [name for name in sparkbot_sources if name not in actual and name != "in_memory_registry"]
        report[generic_table] = {
            "sparkbot_sources": sparkbot_sources,
            "available_sources": available_sources,
            "missing_sources": missing_sources,
            "sparkbot_only_fields": list(config["sparkbot_only_fields"]),
            "mapping_defined": not missing_sources,
        }
    return report


def _event_probe(conn: sqlite3.Connection) -> dict[str, Any]:
    if "guardian_spine_events" not in _schema_for_db(conn):
        return {
            "sampled_rows": 0,
            "invalid_json_rows": 0,
            "category_counts": {},
            "rows_with_sensitive_keys": 0,
            "redacted_marker_hits": 0,
        }
    rows = conn.execute(
        """
        SELECT event_type, subsystem, task_id, project_id, payload_json
        FROM guardian_spine_events
        ORDER BY occurred_at DESC
        LIMIT 100
        """
    ).fetchall()
    category_counts: dict[str, int] = {}
    invalid_json_rows = 0
    rows_with_sensitive_keys = 0
    redacted_marker_hits = 0
    for row in rows:
        category = _classify_event(
            event_type=row[0],
            subsystem=row[1],
            task_id=row[2],
            project_id=row[3],
        )
        category_counts[category] = category_counts.get(category, 0) + 1
        payload, invalid = _safe_json_load(row[4])
        if invalid:
            invalid_json_rows += 1
            continue
        sensitive_key_hits = _contains_sensitive_keys(payload)
        if sensitive_key_hits:
            rows_with_sensitive_keys += 1
        redacted_marker_hits += _count_redacted_markers(payload)
    return {
        "sampled_rows": len(rows),
        "invalid_json_rows": invalid_json_rows,
        "category_counts": category_counts,
        "rows_with_sensitive_keys": rows_with_sensitive_keys,
        "redacted_marker_hits": redacted_marker_hits,
    }


def build_report(source_db: str | Path) -> dict[str, Any]:
    source_path = Path(source_db)
    if not source_path.exists():
        raise FileNotFoundError(f"Source DB not found: {source_path}")
    if not source_path.is_file():
        raise FileNotFoundError(f"Source DB is not a file: {source_path}")

    with tempfile.TemporaryDirectory(prefix="spine-probe-") as temp_dir:
        temp_path = Path(temp_dir) / source_path.name
        shutil.copy2(source_path, temp_path)
        conn = sqlite3.connect(str(temp_path))
        try:
            actual_schema = _schema_for_db(conn)
            sparkbot_comparison = _compare_expected(actual_schema, SPARKBOT_EXPECTED_SCHEMA)
            generic_projection = _mapping_report(actual_schema)
            generic_schema = {
                table: sorted(columns)
                for table, columns in sorted(LIMA_GENERIC_EXPECTED_SCHEMA.items())
            }
            report = {
                "probe_version": 1,
                "source_db_path": str(source_path),
                "used_temp_copy": True,
                "temp_copy_path": str(temp_path),
                "source_db_touched_read_only": True,
                "sparkbot_actual_schema": {
                    "tables": {table: sorted(columns) for table, columns in sorted(actual_schema.items())},
                },
                "sparkbot_expected_comparison": sparkbot_comparison,
                "lima_generic_expected_schema": generic_schema,
                "lima_generic_mapping": generic_projection,
                "event_translation_checks": _event_probe(conn),
                "task_project_parity_checks": {
                    "task_table_present": "guardian_spine_tasks" in actual_schema,
                    "project_table_present": "guardian_spine_projects" in actual_schema,
                    "task_required_columns_missing": sparkbot_comparison["tables"].get("guardian_spine_tasks", {}).get("missing_columns", []),
                    "project_required_columns_missing": sparkbot_comparison["tables"].get("guardian_spine_projects", {}).get("missing_columns", []),
                },
                "redaction_checks": {
                    "event_rows_with_sensitive_keys": _event_probe(conn)["rows_with_sensitive_keys"],
                    "event_redacted_marker_hits": _event_probe(conn)["redacted_marker_hits"],
                    "raw_values_emitted": False,
                },
            }
            report["summary"] = {
                "pass": (
                    not sparkbot_comparison["missing_tables"]
                    and not report["task_project_parity_checks"]["task_required_columns_missing"]
                    and not report["task_project_parity_checks"]["project_required_columns_missing"]
                ),
                "missing_tables_count": len(sparkbot_comparison["missing_tables"]),
                "missing_task_columns_count": len(report["task_project_parity_checks"]["task_required_columns_missing"]),
                "missing_project_columns_count": len(report["task_project_parity_checks"]["project_required_columns_missing"]),
            }
            return report
        finally:
            conn.close()


def write_report(source_db: str | Path, output: str | Path) -> dict[str, Any]:
    report = build_report(source_db)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only Sparkbot Spine compatibility probe")
    parser.add_argument("--source-db", required=True, help="Path to the source Sparkbot Spine SQLite DB")
    parser.add_argument("--output", required=True, help="Path to write the JSON report")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        write_report(args.source_db, args.output)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Probe failed safely: {exc.__class__.__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
