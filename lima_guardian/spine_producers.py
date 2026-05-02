"""Standalone Spine producer registry for LIMA Guardian."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from lima_guardian.spine_models import SpineProducer


class ProducerNotRegisteredError(KeyError):
    pass


@dataclass
class SpineProducerRegistry:
    _producers: dict[str, SpineProducer] = field(default_factory=dict)

    def register(self, producer: SpineProducer) -> SpineProducer:
        key = str(producer.subsystem or "").strip()
        if not key:
            raise ValueError("producer.subsystem is required")
        self._producers[key] = producer
        return producer

    def unregister(self, subsystem: str) -> bool:
        key = str(subsystem or "").strip()
        if not key:
            return False
        return self._producers.pop(key, None) is not None

    def get(self, subsystem: str) -> SpineProducer | None:
        key = str(subsystem or "").strip()
        if not key:
            return None
        return self._producers.get(key)

    def list(self) -> list[SpineProducer]:
        return sorted(self._producers.values(), key=lambda p: p.subsystem)

    def validate_producer_for_event(self, subsystem: str, event_type: str) -> None:
        key = str(subsystem or "").strip()
        if not key:
            raise ValueError("subsystem is required")
        producer = self.get(key)
        if producer is None:
            raise ProducerNotRegisteredError(f"Producer not registered: {key!r}")
        if producer.event_types and str(event_type or "").strip() not in set(producer.event_types):
            raise ValueError(f"Event type {event_type!r} not declared by producer {key!r}")


def producer_from_dict(raw: Mapping[str, Any]) -> SpineProducer:
    return SpineProducer.from_dict(raw)

