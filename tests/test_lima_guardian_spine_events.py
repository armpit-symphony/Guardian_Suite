from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from lima_guardian.spine_events import (
    approval_event,
    build_event,
    meeting_event,
    memory_event,
    project_event,
    redact_sensitive,
    scheduled_job_event,
    security_event,
    task_event,
    validate_required_fields,
    verifier_event,
)
from lima_guardian.spine_models import SpineEventType, SpineProducer
from lima_guardian.spine_producers import ProducerNotRegisteredError, SpineProducerRegistry


def test_required_fields_validation():
    with pytest.raises(ValueError):
        validate_required_fields(event_type="", source_kind="x", source_ref="y")
    with pytest.raises(ValueError):
        validate_required_fields(event_type="x", source_kind="", source_ref="y")
    with pytest.raises(ValueError):
        validate_required_fields(event_type="x", source_kind="y", source_ref="")


def test_sensitive_metadata_redaction():
    raw = {"api_key": "secret", "nested": {"password": "p", "ok": 1}, "list": [{"token": "t"}]}
    redacted = redact_sensitive(raw)
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["password"] == "[REDACTED]"
    assert redacted["nested"]["ok"] == 1
    assert redacted["list"][0]["token"] == "[REDACTED]"


def test_builds_each_supported_event_type():
    base = dict(source_kind="test", source_ref="ref-1", room_id="room-1")
    events = [
        task_event(**base, event_type="task.created", task_id="t-1", project_id="p-1"),
        approval_event(**base, event_type="approval.required"),
        memory_event(**base, event_type="memory.signal"),
        meeting_event(**base, event_type="meeting.summary.created"),
        project_event(**base, event_type="project.updated", project_id="p-1"),
        security_event(**base, event_type="breakglass.opened"),
        verifier_event(**base, event_type="verification.completed", task_id="t-1"),
        scheduled_job_event(**base, event_type="task.progress", task_id="t-1"),
    ]
    categories = {e.category for e in events}
    assert SpineEventType.TASK in categories
    assert SpineEventType.APPROVAL in categories
    assert SpineEventType.MEMORY in categories
    assert SpineEventType.MEETING in categories
    assert SpineEventType.PROJECT in categories
    assert SpineEventType.SECURITY in categories
    assert SpineEventType.VERIFIER in categories
    assert SpineEventType.SCHEDULED_JOB in categories


def test_build_event_sets_redacted_flag_and_metadata():
    e = build_event(
        category=SpineEventType.APPROVAL,
        event_type="approval.required",
        source_kind="approval",
        source_ref="confirm-1",
        payload={"token": "secret"},
        metadata={"api_key": "secret"},
    )
    assert e.redacted is True
    assert e.payload["token"] == "[REDACTED]"
    assert e.metadata["api_key"] == "[REDACTED]"


def test_producer_registry_register_and_validate():
    reg = SpineProducerRegistry()
    reg.register(SpineProducer(subsystem="memory", description="memory producer", event_types=["memory.signal"]))
    reg.validate_producer_for_event("memory", "memory.signal")
    with pytest.raises(ValueError):
        reg.validate_producer_for_event("memory", "task.created")


def test_producer_missing_validation():
    reg = SpineProducerRegistry()
    with pytest.raises(ProducerNotRegisteredError):
        reg.validate_producer_for_event("missing", "task.created")


def test_no_disallowed_imports_in_new_modules():
    for name in ("lima_guardian.spine_events", "lima_guardian.spine_producers"):
        mod = importlib.import_module(name)
        src = Path(mod.__file__).read_text(encoding="utf-8").lower()
        assert "from app" not in src
        assert "import app" not in src
        assert "fastapi" not in src
        assert "sqlmodel" not in src
