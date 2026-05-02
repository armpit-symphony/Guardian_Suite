from __future__ import annotations

import importlib
import json
import sqlite3
from pathlib import Path

from lima_guardian.spine_models import SpineEntityType, SpineEventType, SpineProducer, SpineProject, SpineRelation, SpineTask
from tools.spine_translation_parity import (
    build_report,
    main,
    translate_event_row,
    translate_producer_rows,
    translate_project_row,
    translate_relation_row,
    translate_task_row,
    write_report,
)


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
            """
        )
        conn.execute(
            """
            INSERT INTO guardian_spine_tasks VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "task-1",
                "room-1",
                "Task Title",
                "Task summary",
                "project-1",
                "feature",
                "high",
                "open",
                "human",
                "user-1",
                "message",
                "msg-1",
                "guardian_spine",
                "task_master",
                "task_master",
                1,
                "required",
                0.91,
                None,
                json.dumps(["task-0"]),
                json.dumps(["alpha"]),
                "2026-05-02T00:00:00+00:00",
                "2026-05-02T00:00:00+00:00",
                "2026-05-02T00:00:00+00:00",
                None,
                "contains token=abc",
                "chat-1",
            ),
        )
        conn.execute(
            """
            INSERT INTO guardian_spine_projects VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "project-1",
                "room-1",
                "Project One",
                "project-one",
                "Project summary",
                "active",
                "system",
                "proj-src-1",
                "project_lifecycle",
                "project_lifecycle",
                json.dumps(["ops"]),
                None,
                "2026-05-02T00:00:00+00:00",
                "2026-05-02T00:00:00+00:00",
                "human",
                "user-1",
            ),
        )
        conn.execute(
            """
            INSERT INTO guardian_spine_events VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                json.dumps({"tool_args": {"api_key": "secret-value"}, "safe": True}),
            ),
        )
        conn.execute(
            """
            INSERT INTO guardian_spine_links VALUES
            (?, ?, ?, ?, ?)
            """,
            ("rel-1", "task-1", "task-2", "dependency", "2026-05-02T00:00:00+00:00"),
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


def test_temp_copy_is_used(tmp_path):
    source = tmp_path / "source.db"
    _create_sample_db(source)
    report = build_report(source)
    assert report["used_temp_copy"] is True
    assert report["temp_copy_path"] != report["source_db_path"]


def test_task_row_translates_to_spine_task(tmp_path):
    source = tmp_path / "source.db"
    _create_sample_db(source)
    conn = sqlite3.connect(str(source))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM guardian_spine_tasks").fetchone()
    finally:
        conn.close()
    task = translate_task_row(row)
    assert isinstance(task, SpineTask)
    assert task.task_id == "task-1"
    assert task.depends_on == ["task-0"]
    assert task.metadata["chat_task_id"] == "chat-1"


def test_project_row_translates_to_spine_project(tmp_path):
    source = tmp_path / "source.db"
    _create_sample_db(source)
    conn = sqlite3.connect(str(source))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM guardian_spine_projects").fetchone()
    finally:
        conn.close()
    project = translate_project_row(row)
    assert isinstance(project, SpineProject)
    assert project.project_id == "project-1"
    assert project.tags == ["ops"]


def test_event_row_translates_to_spine_event_envelope(tmp_path):
    source = tmp_path / "source.db"
    _create_sample_db(source)
    conn = sqlite3.connect(str(source))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM guardian_spine_events").fetchone()
    finally:
        conn.close()
    event = translate_event_row(row)
    assert event.event_id == "evt-1"
    assert event.category == SpineEventType.APPROVAL
    assert event.payload["tool_args"]["api_key"] == "[REDACTED]"


def test_relation_row_translates_to_spine_relation(tmp_path):
    source = tmp_path / "source.db"
    _create_sample_db(source)
    conn = sqlite3.connect(str(source))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM guardian_spine_links").fetchone()
    finally:
        conn.close()
    relation = translate_relation_row(row)
    assert isinstance(relation, SpineRelation)
    assert relation.from_entity_type == SpineEntityType.TASK
    assert relation.relation_type == "dependency"


def test_producer_rows_translate_to_spine_producer(tmp_path):
    source = tmp_path / "source.db"
    _create_sample_db(source)
    conn = sqlite3.connect(str(source))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT subsystem, event_type FROM guardian_spine_events").fetchall()
    finally:
        conn.close()
    producers = translate_producer_rows(rows)
    assert producers
    assert isinstance(producers[0], SpineProducer)
    assert producers[0].subsystem == "approval"


def test_sensitive_metadata_is_redacted(tmp_path):
    source = tmp_path / "source.db"
    _create_sample_db(source)
    conn = sqlite3.connect(str(source))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM guardian_spine_events").fetchone()
    finally:
        conn.close()
    event = translate_event_row(row)
    assert event.redacted is True
    assert "secret-value" not in json.dumps(event.to_dict())


def test_json_report_generated(tmp_path):
    source = tmp_path / "source.db"
    output = tmp_path / "report.json"
    _create_sample_db(source)
    report = write_report(source, output)
    data = json.loads(output.read_text(encoding="utf-8"))
    assert report["summary"]["pass"] is True
    assert data["translation_counts"]["tasks"]["success"] == 1
    assert data["translation_counts"]["producers"]["success"] == 1
    assert "secret-value" not in output.read_text(encoding="utf-8")


def test_no_disallowed_imports():
    mod = importlib.import_module("tools.spine_translation_parity")
    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "from app" not in src
    assert "import app" not in src
    assert "from sparkbot" not in src.lower()
    assert "import sparkbot" not in src.lower()
    assert "fastapi" not in src.lower()
    assert "sqlmodel" not in src.lower()
