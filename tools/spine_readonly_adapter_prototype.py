"""Read-only Sparkbot Spine adapter prototype backed by temp-copy data only."""
from __future__ import annotations

import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from lima_guardian.spine_models import SpineEventEnvelope, SpineProject, SpineRelation, SpineTask
from tools.spine_translation_parity import (
    translate_event_row,
    translate_project_row,
    translate_relation_row,
    translate_task_row,
)


class SparkbotReadonlySpineAdapterPrototype:
    """Test-only read adapter over a copied Sparkbot Spine DB.

    This prototype intentionally does not implement any runtime wiring or write
    paths. It exists to exercise Sparkbot-like read models over translated LIMA
    objects before any adapter is introduced into Sparkbot itself.
    """

    def __init__(
        self,
        *,
        source_db_path: Path,
        temp_dir: tempfile.TemporaryDirectory[str],
        temp_copy_path: Path,
        tasks: list[SpineTask],
        projects: list[SpineProject],
        events: list[SpineEventEnvelope],
        relations: list[SpineRelation],
    ) -> None:
        self.source_db_path = source_db_path
        self._temp_dir = temp_dir
        self.temp_copy_path = temp_copy_path
        self.used_temp_copy = True
        self.tasks = tasks
        self.projects = projects
        self.events = events
        self.relations = relations
        self._task_map = {task.task_id: task for task in tasks}
        self._project_map = {project.project_id: project for project in projects}

    @classmethod
    def from_source_db(cls, source_db: str | Path) -> "SparkbotReadonlySpineAdapterPrototype":
        source_path = Path(source_db)
        if not source_path.exists():
            raise FileNotFoundError(f"Source DB not found: {source_path}")
        if not source_path.is_file():
            raise FileNotFoundError(f"Source DB is not a file: {source_path}")

        temp_dir = tempfile.TemporaryDirectory(prefix="spine-readonly-adapter-")
        temp_copy = Path(temp_dir.name) / source_path.name
        shutil.copy2(source_path, temp_copy)

        conn = sqlite3.connect(str(temp_copy))
        conn.row_factory = sqlite3.Row
        try:
            tasks = [translate_task_row(row) for row in conn.execute("SELECT * FROM guardian_spine_tasks")]
            projects = [translate_project_row(row) for row in conn.execute("SELECT * FROM guardian_spine_projects")]
            events = [translate_event_row(row) for row in conn.execute("SELECT * FROM guardian_spine_events")]
            relations = [translate_relation_row(row) for row in conn.execute("SELECT * FROM guardian_spine_links")]
        finally:
            conn.close()

        return cls(
            source_db_path=source_path,
            temp_dir=temp_dir,
            temp_copy_path=temp_copy,
            tasks=tasks,
            projects=projects,
            events=events,
            relations=relations,
        )

    def close(self) -> None:
        self._temp_dir.cleanup()

    def _filter_tasks(self, *, room_id: str | None = None) -> list[SpineTask]:
        if room_id is None:
            return list(self.tasks)
        return [task for task in self.tasks if task.room_id == room_id]

    def list_open_queue(self, *, room_id: str | None = None, limit: int = 100) -> list[SpineTask]:
        allowed = {"open", "triaged", "queued", "in_progress"}
        tasks = [task for task in self._filter_tasks(room_id=room_id) if task.status in allowed]
        return tasks[:limit]

    def list_blocked_queue(self, *, room_id: str | None = None, limit: int = 100) -> list[SpineTask]:
        tasks = [task for task in self._filter_tasks(room_id=room_id) if task.status == "blocked"]
        return tasks[:limit]

    def list_approval_waiting_queue(self, *, room_id: str | None = None, limit: int = 100) -> list[SpineTask]:
        allowed = {"required", "requested", "pending", "awaiting_review", "review"}
        tasks = [
            task
            for task in self._filter_tasks(room_id=room_id)
            if task.approval_required and task.approval_state in allowed
        ]
        return tasks[:limit]

    def list_recent_events(
        self,
        *,
        room_id: str | None = None,
        task_id: str | None = None,
        project_id: str | None = None,
        limit: int = 100,
    ) -> list[SpineEventEnvelope]:
        events = list(self.events)
        if room_id is not None:
            events = [event for event in events if event.room_id == room_id]
        if task_id is not None:
            events = [event for event in events if event.task_id == task_id]
        if project_id is not None:
            events = [event for event in events if event.project_id == project_id]
        events.sort(key=lambda event: event.occurred_at, reverse=True)
        return events[:limit]

    def get_room_overview(self, *, room_id: str) -> dict[str, Any]:
        tasks = self._filter_tasks(room_id=room_id)
        projects = [project for project in self.projects if project.room_id == room_id]
        events = self.list_recent_events(room_id=room_id, limit=max(len(self.events), 1))
        status_counts: dict[str, int] = {}
        for task in tasks:
            status_counts[task.status] = status_counts.get(task.status, 0) + 1
        return {
            "room_id": room_id,
            "task_count": len(tasks),
            "status_counts": status_counts,
            "event_count": len(events),
            "awaiting_approval_count": len(self.list_approval_waiting_queue(room_id=room_id)),
            "handoff_count": len([event for event in events if event.category.value == "handoff"]),
            "orphan_task_count": len([task for task in tasks if not task.project_id]),
            "unassigned_open_task_count": len(
                [
                    task
                    for task in tasks
                    if task.status not in {"done", "closed", "canceled", "cancelled"}
                    and task.owner_kind in {"", "unassigned", None}
                ]
            ),
            "project_count": len(projects),
            "projects": [{"project_id": project.project_id, "display_name": project.display_name} for project in projects],
        }

    def get_project_workload_summary(self, *, room_id: str | None = None) -> list[dict[str, Any]]:
        projects = self.projects if room_id is None else [project for project in self.projects if project.room_id == room_id]
        summary: list[dict[str, Any]] = []
        for project in projects:
            project_tasks = [task for task in self.tasks if task.project_id == project.project_id]
            summary.append(
                {
                    "project_id": project.project_id,
                    "display_name": project.display_name,
                    "status": project.status,
                    "total_tasks": len(project_tasks),
                    "open_tasks": len([task for task in project_tasks if task.status in {"open", "triaged", "queued", "in_progress"}]),
                    "blocked_tasks": len([task for task in project_tasks if task.status == "blocked"]),
                    "approval_waiting_tasks": len(
                        [
                            task
                            for task in project_tasks
                            if task.approval_required and task.approval_state in {"required", "requested", "pending", "awaiting_review", "review"}
                        ]
                    ),
                }
            )
        return summary

    def get_task_detail(self, *, task_id: str) -> dict[str, Any] | None:
        task = self._task_map.get(task_id)
        if task is None:
            return None
        parent = self._task_map.get(task.parent_task_id) if task.parent_task_id else None
        children = [candidate for candidate in self.tasks if candidate.parent_task_id == task_id]
        dependencies = [
            self._task_map[relation.to_entity_id]
            for relation in self.relations
            if relation.from_entity_id == task_id
            and relation.relation_type == "dependency"
            and relation.to_entity_id in self._task_map
        ]
        related = [
            self._task_map[relation.to_entity_id]
            for relation in self.relations
            if relation.from_entity_id == task_id
            and relation.relation_type != "dependency"
            and relation.to_entity_id in self._task_map
        ]
        return {
            "task": task,
            "parent": parent,
            "children": children,
            "dependencies": dependencies,
            "related": related,
            "approvals": [],
            "handoffs": [],
            "events": self.list_recent_events(task_id=task_id, limit=20),
        }

