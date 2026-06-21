from __future__ import annotations

from time import perf_counter
from typing import Any

from ..core.exceptions import AuditIntegrityError
from ..core.schemas import AgentRole, AuditEvent, ExecutionStatus
from ..core.serialization import redact_private_fields, stable_hash


class AuditLedger:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._chain: list[str] = []

    def append(
        self,
        agent: AgentRole,
        event_type: str,
        payload: dict[str, Any],
        status: ExecutionStatus,
        message: str,
        correlation_id: str | None = None,
        input_payload: dict[str, Any] | None = None,
        output_payload: dict[str, Any] | None = None,
        elapsed_ms: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        safe_payload = redact_private_fields(payload)
        event = AuditEvent(
            agent=agent,
            event_type=event_type,
            payload_hash=stable_hash(safe_payload),
            status=status,
            message=message,
            correlation_id=correlation_id,
            input_hash=stable_hash(redact_private_fields(input_payload)) if input_payload else None,
            output_hash=stable_hash(redact_private_fields(output_payload)) if output_payload else None,
            elapsed_ms=elapsed_ms,
            metadata=redact_private_fields(metadata or {}),
        )
        previous = self._chain[-1] if self._chain else ""
        self._chain.append(stable_hash({"previous": previous, "event": event}))
        self._events.append(event)
        return event

    def events(self, correlation_id: str | None = None) -> list[AuditEvent]:
        if correlation_id is None:
            return list(self._events)
        return [event for event in self._events if event.correlation_id == correlation_id]

    def chain_tip(self) -> str | None:
        return self._chain[-1] if self._chain else None

    def verify_chain(self) -> bool:
        previous = ""
        rebuilt: list[str] = []
        for event in self._events:
            current = stable_hash({"previous": previous, "event": event})
            rebuilt.append(current)
            previous = current
        if rebuilt != self._chain:
            raise AuditIntegrityError("audit chain mismatch")
        return True


class TimedAudit:
    def __init__(
        self,
        ledger: AuditLedger,
        agent: AgentRole,
        event_type: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
    ) -> None:
        self.ledger = ledger
        self.agent = agent
        self.event_type = event_type
        self.payload = payload
        self.correlation_id = correlation_id
        self.started = 0.0

    def __enter__(self) -> "TimedAudit":
        self.started = perf_counter()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        elapsed = (perf_counter() - self.started) * 1000.0
        status = ExecutionStatus.FAILED if exc else ExecutionStatus.COMPLETED
        message = str(exc) if exc else "completed"
        self.ledger.append(
            self.agent,
            self.event_type,
            self.payload,
            status,
            message,
            correlation_id=self.correlation_id,
            elapsed_ms=elapsed,
        )
