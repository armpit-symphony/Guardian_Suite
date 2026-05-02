"""Spine event helpers for LIMA Guardian.

No persistence. No Sparkbot/runtime coupling.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from lima_guardian.spine_models import SpineEventEnvelope, SpineEventType


_SENSITIVE_KEY_PARTS = (
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


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_event_id(prefix: str = "evt") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def validate_required_fields(*, event_type: str, source_kind: str, source_ref: str) -> None:
    if not str(event_type or "").strip():
        raise ValueError("event_type is required")
    if not str(source_kind or "").strip():
        raise ValueError("source_kind is required")
    if not str(source_ref or "").strip():
        raise ValueError("source_ref is required")


def redact_sensitive(obj: Any) -> Any:
    """Recursively redact values where a key looks secret-like."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for key, value in obj.items():
            key_str = str(key)
            lowered = key_str.lower()
            if any(part in lowered for part in _SENSITIVE_KEY_PARTS):
                out[key_str] = "[REDACTED]"
            else:
                out[key_str] = redact_sensitive(value)
        return out
    if isinstance(obj, list):
        return [redact_sensitive(v) for v in obj]
    return obj


def build_event(
    *,
    category: SpineEventType,
    event_type: str,
    source_kind: str,
    source_ref: str,
    room_id: str | None = None,
    subsystem: str | None = None,
    actor_kind: str = "system",
    actor_id: str | None = None,
    correlation_id: str | None = None,
    task_id: str | None = None,
    project_id: str | None = None,
    payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    occurred_at: str | None = None,
    redact: bool = True,
) -> SpineEventEnvelope:
    validate_required_fields(event_type=event_type, source_kind=source_kind, source_ref=source_ref)
    raw_payload = dict(payload or {})
    raw_metadata = dict(metadata or {})
    redacted_payload = redact_sensitive(raw_payload) if redact else raw_payload
    redacted_metadata = redact_sensitive(raw_metadata) if redact else raw_metadata
    return SpineEventEnvelope(
        event_id=new_event_id("spine"),
        event_type=str(event_type),
        category=category,
        occurred_at=occurred_at or utc_now_iso(),
        room_id=room_id,
        subsystem=subsystem,
        actor_kind=actor_kind,
        actor_id=actor_id,
        source_kind=source_kind,
        source_ref=source_ref,
        correlation_id=correlation_id or new_event_id("corr"),
        task_id=task_id,
        project_id=project_id,
        payload=redacted_payload,
        metadata=redacted_metadata,
        redacted=bool(redact),
    )


def task_event(
    *,
    event_type: str,
    source_kind: str,
    source_ref: str,
    room_id: str | None = None,
    task_id: str | None = None,
    project_id: str | None = None,
    payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> SpineEventEnvelope:
    return build_event(
        category=SpineEventType.TASK,
        event_type=event_type,
        source_kind=source_kind,
        source_ref=source_ref,
        room_id=room_id,
        task_id=task_id,
        project_id=project_id,
        payload=payload,
        metadata=metadata,
        **kwargs,
    )


def approval_event(
    *,
    event_type: str,
    source_kind: str,
    source_ref: str,
    room_id: str | None = None,
    task_id: str | None = None,
    payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> SpineEventEnvelope:
    return build_event(
        category=SpineEventType.APPROVAL,
        event_type=event_type,
        source_kind=source_kind,
        source_ref=source_ref,
        room_id=room_id,
        task_id=task_id,
        payload=payload,
        metadata=metadata,
        **kwargs,
    )


def memory_event(
    *,
    event_type: str,
    source_kind: str,
    source_ref: str,
    room_id: str | None = None,
    task_id: str | None = None,
    payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> SpineEventEnvelope:
    return build_event(
        category=SpineEventType.MEMORY,
        event_type=event_type,
        source_kind=source_kind,
        source_ref=source_ref,
        room_id=room_id,
        task_id=task_id,
        payload=payload,
        metadata=metadata,
        **kwargs,
    )


def meeting_event(
    *,
    event_type: str,
    source_kind: str,
    source_ref: str,
    room_id: str | None = None,
    task_id: str | None = None,
    project_id: str | None = None,
    payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> SpineEventEnvelope:
    return build_event(
        category=SpineEventType.MEETING,
        event_type=event_type,
        source_kind=source_kind,
        source_ref=source_ref,
        room_id=room_id,
        task_id=task_id,
        project_id=project_id,
        payload=payload,
        metadata=metadata,
        **kwargs,
    )


def project_event(
    *,
    event_type: str,
    source_kind: str,
    source_ref: str,
    room_id: str | None = None,
    project_id: str | None = None,
    payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> SpineEventEnvelope:
    return build_event(
        category=SpineEventType.PROJECT,
        event_type=event_type,
        source_kind=source_kind,
        source_ref=source_ref,
        room_id=room_id,
        project_id=project_id,
        payload=payload,
        metadata=metadata,
        **kwargs,
    )


def security_event(
    *,
    event_type: str,
    source_kind: str,
    source_ref: str,
    room_id: str | None = None,
    payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> SpineEventEnvelope:
    return build_event(
        category=SpineEventType.SECURITY,
        event_type=event_type,
        source_kind=source_kind,
        source_ref=source_ref,
        room_id=room_id,
        payload=payload,
        metadata=metadata,
        **kwargs,
    )


def verifier_event(
    *,
    event_type: str,
    source_kind: str,
    source_ref: str,
    room_id: str | None = None,
    task_id: str | None = None,
    payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> SpineEventEnvelope:
    return build_event(
        category=SpineEventType.VERIFIER,
        event_type=event_type,
        source_kind=source_kind,
        source_ref=source_ref,
        room_id=room_id,
        task_id=task_id,
        payload=payload,
        metadata=metadata,
        **kwargs,
    )


def scheduled_job_event(
    *,
    event_type: str,
    source_kind: str,
    source_ref: str,
    room_id: str | None = None,
    task_id: str | None = None,
    payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> SpineEventEnvelope:
    return build_event(
        category=SpineEventType.SCHEDULED_JOB,
        event_type=event_type,
        source_kind=source_kind,
        source_ref=source_ref,
        room_id=room_id,
        task_id=task_id,
        payload=payload,
        metadata=metadata,
        **kwargs,
    )
