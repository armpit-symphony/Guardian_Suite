from __future__ import annotations

import importlib
import json
import sqlite3
from pathlib import Path

import pytest

from tools.spine_compatibility_probe import build_report, main, write_report


def _create_sample_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            """
            CREATE TABLE guardian_spine_tasks (
              task_id TEXT PRIMARY KEY,
              room_id TEXT NOT NULL,
              title TEXT NOT NULL,
              summary TEXT,
              project_id TEXT,
              type TEXT NOT NULL,
              priority TEXT NOT NULL,
              status TEXT NOT NULL,
              owner_kind TEXT NOT NULL,
              owner_id TEXT,
              source_kind TEXT NOT NULL,
              source_ref TEXT NOT NULL,
              created_by_guardian TEXT NOT NULL,
              created_by_subsystem TEXT,
              updated_by_subsystem TEXT,
              approval_required INTEGER NOT NULL DEFAULT 0,
              approval_state TEXT NOT NULL DEFAULT 'not_required',
              confidence REAL NOT NULL,
              parent_task_id TEXT,
              depends_on_json TEXT NOT NULL DEFAULT '[]',
              tags_json TEXT NOT NULL DEFAULT '[]',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              last_progress_at TEXT NOT NULL,
              closed_at TEXT,
              source_excerpt TEXT,
              chat_task_id TEXT
            );
            CREATE TABLE guardian_spine_events (
              event_id TEXT PRIMARY KEY,
              event_type TEXT NOT NULL,
              occurred_at TEXT NOT NULL,
              room_id TEXT,
              subsystem TEXT,
              actor_kind TEXT NOT NULL,
              actor_id TEXT,
              source_kind TEXT NOT NULL,
              source_ref TEXT NOT NULL,
              correlation_id TEXT NOT NULL,
              task_id TEXT,
              project_id TEXT,
              payload_json TEXT NOT NULL
            );
            CREATE TABLE guardian_spine_links (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              related_task_id TEXT NOT NULL,
              link_type TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE guardian_spine_assignments (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              owner_kind TEXT NOT NULL,
              owner_id TEXT,
              assigned_at TEXT NOT NULL,
              assigned_by TEXT
            );
            CREATE TABLE guardian_spine_approvals (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              requester_id TEXT,
              approver_id TEXT,
              approval_method TEXT,
              state TEXT NOT NULL,
              scope_json TEXT NOT NULL DEFAULT '[]',
              expires_at TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE guardian_spine_handoffs (
              id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              room_id TEXT NOT NULL,
              summary TEXT NOT NULL,
              created_at TEXT NOT NULL,
              source_ref TEXT
            );
            CREATE TABLE guardian_spine_projects (
              project_id TEXT PRIMARY KEY,
              room_id TEXT,
              display_name TEXT NOT NULL,
              slug TEXT NOT NULL UNIQUE,
              summary TEXT,
              status TEXT,
              source_kind TEXT,
              source_ref TEXT,
              created_by_subsystem TEXT,
              updated_by_subsystem TEXT,
              tags_json TEXT,
              parent_project_id TEXT,
              created_at TEXT,
              updated_at TEXT NOT NULL,
              owner_kind TEXT DEFAULT 'unassigned',
              owner_id TEXT
            );
            CREATE TABLE guardian_spine_project_events (
              event_id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              event_type TEXT NOT NULL,
              occurred_at TEXT NOT NULL,
              room_id TEXT,
              subsystem TEXT,
              source_kind TEXT NOT NULL,
              source_ref TEXT NOT NULL,
              payload_json TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            INSERT INTO guardian_spine_events (
              event_id, event_type, occurred_at, room_id, subsystem, actor_kind,
              actor_id, source_kind, source_ref, correlation_id, task_id,
              project_id, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "evt-1",
                "approval.required",
                "2026-05-02T00:00:00+00:00",
                "room-1",
                "approval",
                "system",
                None,
                "approval",
                "confirm-1",
                "corr-1",
                "task-1",
                "project-1",
                json.dumps({"tool_args": {"api_key": "[REDACTED]"}, "safe": True}),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def test_missing_db_fails_safely(tmp_path, capsys):
    output = tmp_path / "report.json"
    code = main(["--source-db", str(tmp_path / "missing.db"), "--output", str(output)])
    captured = capsys.readouterr()
    assert code == 2
    assert "Source DB not found" in captured.err
    assert not output.exists()


def test_temp_copy_is_used_and_report_generated(tmp_path):
    source = tmp_path / "source.db"
    output = tmp_path / "report.json"
    _create_sample_db(source)

    report = write_report(source, output)
    disk_report = json.loads(output.read_text(encoding="utf-8"))

    assert report["used_temp_copy"] is True
    assert report["temp_copy_path"] != report["source_db_path"]
    assert disk_report["sparkbot_expected_comparison"]["tables"]["guardian_spine_events"]["present"] is True


def test_json_report_includes_table_and_column_comparison(tmp_path):
    source = tmp_path / "source.db"
    _create_sample_db(source)

    report = build_report(source)

    assert "sparkbot_expected_comparison" in report
    assert "guardian_spine_tasks" in report["sparkbot_expected_comparison"]["tables"]
    assert "missing_columns" in report["sparkbot_expected_comparison"]["tables"]["guardian_spine_tasks"]
    assert "lima_generic_expected_schema" in report
    assert "spine_tasks" in report["lima_generic_expected_schema"]


def test_no_secret_like_values_printed_in_report(tmp_path):
    source = tmp_path / "source.db"
    output = tmp_path / "report.json"
    secret_value = "super-secret-token-value"
    _create_sample_db(source)

    conn = sqlite3.connect(str(source))
    try:
        conn.execute(
            "UPDATE guardian_spine_events SET payload_json = ? WHERE event_id = ?",
            (json.dumps({"tool_args": {"api_key": secret_value, "password": "[REDACTED]"}}), "evt-1"),
        )
        conn.commit()
    finally:
        conn.close()

    write_report(source, output)
    report_text = output.read_text(encoding="utf-8")

    assert secret_value not in report_text
    assert report_text.count("[REDACTED]") == 0
    data = json.loads(report_text)
    assert data["redaction_checks"]["raw_values_emitted"] is False
    assert data["event_translation_checks"]["rows_with_sensitive_keys"] >= 1


def test_no_disallowed_imports(tmp_path):
    _ = tmp_path
    mod = importlib.import_module("tools.spine_compatibility_probe")
    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "from app" not in src
    assert "import app" not in src
    assert "from sparkbot" not in src.lower()
    assert "import sparkbot" not in src.lower()
    assert "fastapi" not in src.lower()
    assert "sqlmodel" not in src.lower()
