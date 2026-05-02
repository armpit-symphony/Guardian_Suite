from __future__ import annotations

import importlib
import json
import sqlite3
from pathlib import Path

from tools.spine_readonly_adapter_prototype import SparkbotReadonlySpineAdapterPrototype


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
        conn.executemany(
            """
            INSERT INTO guardian_spine_tasks VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "task-1",
                    "room-1",
                    "Open task",
                    "Needs work",
                    "project-1",
                    "feature",
                    "high",
                    "open",
                    "unassigned",
                    None,
                    "message",
                    "msg-1",
                    "guardian_spine",
                    "task_master",
                    "task_master",
                    1,
                    "required",
                    0.91,
                    None,
                    json.dumps(["task-2"]),
                    json.dumps(["alpha"]),
                    "2026-05-02T00:00:00+00:00",
                    "2026-05-02T00:00:00+00:00",
                    "2026-05-02T00:00:00+00:00",
                    None,
                    "contains token=abc",
                    "chat-1",
                ),
                (
                    "task-2",
                    "room-1",
                    "Blocked task",
                    "Blocked now",
                    "project-1",
                    "ops",
                    "normal",
                    "blocked",
                    "human",
                    "user-1",
                    "message",
                    "msg-2",
                    "guardian_spine",
                    "task_master",
                    "task_master",
                    0,
                    "not_required",
                    0.7,
                    None,
                    json.dumps([]),
                    json.dumps(["beta"]),
                    "2026-05-02T00:00:00+00:00",
                    "2026-05-02T00:00:00+00:00",
                    "2026-05-02T00:00:00+00:00",
                    None,
                    None,
                    "chat-2",
                ),
            ],
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
        conn.executemany(
            """
            INSERT INTO guardian_spine_events VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
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
                (
                    "evt-2",
                    "handoff.created",
                    "2026-05-02T01:00:00+00:00",
                    "room-1",
                    "handoff",
                    "system",
                    None,
                    "task_master",
                    "handoff-1",
                    "corr-2",
                    "task-2",
                    "project-1",
                    json.dumps({"summary": "handoff"}),
                ),
            ],
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


def test_missing_db_fails_safely(tmp_path):
    missing = tmp_path / "missing.db"
    try:
        SparkbotReadonlySpineAdapterPrototype.from_source_db(missing)
    except FileNotFoundError as exc:
        assert "Source DB not found" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError")


def test_temp_copy_is_used(tmp_path):
    source = tmp_path / "source.db"
    _create_sample_db(source)
    adapter = SparkbotReadonlySpineAdapterPrototype.from_source_db(source)
    try:
        assert adapter.used_temp_copy is True
        assert adapter.temp_copy_path != source
        assert adapter.temp_copy_path.exists()
    finally:
        adapter.close()


def test_list_open_and_blocked_queues(tmp_path):
    source = tmp_path / "source.db"
    _create_sample_db(source)
    adapter = SparkbotReadonlySpineAdapterPrototype.from_source_db(source)
    try:
        open_queue = adapter.list_open_queue(room_id="room-1")
        blocked_queue = adapter.list_blocked_queue(room_id="room-1")
        assert [task.task_id for task in open_queue] == ["task-1"]
        assert [task.task_id for task in blocked_queue] == ["task-2"]
    finally:
        adapter.close()


def test_list_approval_waiting_queue(tmp_path):
    source = tmp_path / "source.db"
    _create_sample_db(source)
    adapter = SparkbotReadonlySpineAdapterPrototype.from_source_db(source)
    try:
        waiting = adapter.list_approval_waiting_queue(room_id="room-1")
        assert [task.task_id for task in waiting] == ["task-1"]
    finally:
        adapter.close()


def test_recent_events_are_redacted(tmp_path):
    source = tmp_path / "source.db"
    _create_sample_db(source)
    adapter = SparkbotReadonlySpineAdapterPrototype.from_source_db(source)
    try:
        events = adapter.list_recent_events(room_id="room-1")
        assert events[0].event_id == "evt-2"
        approval = next(event for event in events if event.event_id == "evt-1")
        assert approval.payload["tool_args"]["api_key"] == "[REDACTED]"
        assert "secret-value" not in json.dumps([event.to_dict() for event in events])
    finally:
        adapter.close()


def test_room_overview_and_project_workload(tmp_path):
    source = tmp_path / "source.db"
    _create_sample_db(source)
    adapter = SparkbotReadonlySpineAdapterPrototype.from_source_db(source)
    try:
        overview = adapter.get_room_overview(room_id="room-1")
        workload = adapter.get_project_workload_summary(room_id="room-1")
        assert overview["task_count"] == 2
        assert overview["project_count"] == 1
        assert overview["handoff_count"] == 1
        assert workload[0]["project_id"] == "project-1"
        assert workload[0]["total_tasks"] == 2
        assert workload[0]["blocked_tasks"] == 1
    finally:
        adapter.close()


def test_task_detail_includes_dependencies_and_empty_runtime_only_sections(tmp_path):
    source = tmp_path / "source.db"
    _create_sample_db(source)
    adapter = SparkbotReadonlySpineAdapterPrototype.from_source_db(source)
    try:
        detail = adapter.get_task_detail(task_id="task-1")
        assert detail is not None
        assert detail["task"].task_id == "task-1"
        assert [task.task_id for task in detail["dependencies"]] == ["task-2"]
        assert detail["approvals"] == []
        assert detail["handoffs"] == []
    finally:
        adapter.close()


def test_no_disallowed_imports():
    mod = importlib.import_module("tools.spine_readonly_adapter_prototype")
    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "from app" not in src
    assert "import app" not in src
    assert "from sparkbot" not in src.lower()
    assert "import sparkbot" not in src.lower()
    assert "fastapi" not in src.lower()
    assert "sqlmodel" not in src.lower()
