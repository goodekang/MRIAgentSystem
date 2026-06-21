from __future__ import annotations

from collections import defaultdict, deque
from time import time
from typing import Any
from uuid import uuid4

from ..core.exceptions import SchemaValidationError
from ..core.schemas import AgentRole, MessageEnvelope, MessageKind
from ..core.serialization import stable_hash


class MessageBus:
    def __init__(self) -> None:
        self._queues: dict[AgentRole, deque[MessageEnvelope]] = defaultdict(deque)
        self._history: dict[str, MessageEnvelope] = {}
        self._payload_hashes: dict[str, str] = {}

    def publish(
        self,
        kind: MessageKind,
        sender: AgentRole,
        receiver: AgentRole,
        payload: dict[str, Any],
        correlation_id: str | None = None,
        parent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MessageEnvelope:
        self._validate(kind, payload)
        envelope = MessageEnvelope(
            kind=kind,
            sender=sender,
            receiver=receiver,
            payload=payload,
            correlation_id=correlation_id or uuid4().hex,
            parent_id=parent_id,
            created_at=time(),
            metadata=metadata or {},
        )
        self._queues[receiver].append(envelope)
        self._history[envelope.message_id] = envelope
        self._payload_hashes[envelope.message_id] = stable_hash(payload)
        return envelope

    def consume(self, receiver: AgentRole) -> MessageEnvelope | None:
        queue = self._queues[receiver]
        if not queue:
            return None
        return queue.popleft()

    def history(self, correlation_id: str | None = None) -> list[MessageEnvelope]:
        messages = list(self._history.values())
        if correlation_id is None:
            return messages
        return [message for message in messages if message.correlation_id == correlation_id]

    def payload_hash(self, message_id: str) -> str:
        return self._payload_hashes[message_id]

    def _validate(self, kind: MessageKind, payload: dict[str, Any]) -> None:
        required = {
            MessageKind.TASK_REQUEST: {"task"},
            MessageKind.PROTOCOL_CARD: {"protocol_card"},
            MessageKind.PREPROCESSING_PLAN: {"preprocessing_plan"},
            MessageKind.QUANTITATIVE_REPORT: {"quantitative_report"},
            MessageKind.VERIFICATION_RESULT: {"verification_result"},
            MessageKind.RETRY_REQUEST: {"retry_target", "issues"},
            MessageKind.AUDIT_EVENT: {"audit_event"},
        }[kind]
        missing = required.difference(payload)
        if missing:
            raise SchemaValidationError(f"{kind.value} missing fields: {sorted(missing)}")
