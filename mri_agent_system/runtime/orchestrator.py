from __future__ import annotations

from typing import Any
from uuid import uuid4

from ..agents.preprocessing import PreprocessingCoordinator
from ..agents.protocol import ProtocolAnalyst
from ..agents.quantitative import QuantitativeAnalyzer
from ..agents.verification import VerificationAuditor
from ..core.schemas import (
    AgentRole,
    ExecutionStatus,
    MessageKind,
    PreprocessingPlan,
    ProtocolCard,
    QuantitativeReport,
    TaskContext,
    VerificationResult,
)
from ..core.serialization import normalise
from .audit import AuditLedger
from .message_bus import MessageBus


class MRIAgentSystem:
    def __init__(
        self,
        protocol_analyst: ProtocolAnalyst | None = None,
        preprocessing_coordinator: PreprocessingCoordinator | None = None,
        quantitative_analyzer: QuantitativeAnalyzer | None = None,
        verification_auditor: VerificationAuditor | None = None,
        message_bus: MessageBus | None = None,
        audit_ledger: AuditLedger | None = None,
    ) -> None:
        self.protocol_analyst = protocol_analyst or ProtocolAnalyst()
        self.preprocessing_coordinator = preprocessing_coordinator or PreprocessingCoordinator()
        self.quantitative_analyzer = quantitative_analyzer or QuantitativeAnalyzer()
        self.verification_auditor = verification_auditor or VerificationAuditor()
        self.message_bus = message_bus or MessageBus()
        self.audit_ledger = audit_ledger or AuditLedger()

    def prepare(
        self,
        metadata: dict[str, Any],
        intensities: list[float] | None = None,
        task_hint: str | None = None,
        context: TaskContext | None = None,
    ) -> tuple[ProtocolCard, PreprocessingPlan]:
        correlation_id = uuid4().hex
        task = context or TaskContext(task_id=correlation_id, task_hint=task_hint, metadata=metadata)
        self.message_bus.publish(
            MessageKind.TASK_REQUEST,
            AgentRole.SYSTEM,
            AgentRole.PROTOCOL_ANALYST,
            {"task": normalise(task)},
            correlation_id=correlation_id,
        )
        card = self.protocol_analyst.analyse(metadata, intensities, task_hint)
        self.message_bus.publish(
            MessageKind.PROTOCOL_CARD,
            AgentRole.PROTOCOL_ANALYST,
            AgentRole.PREPROCESSING_COORDINATOR,
            {"protocol_card": normalise(card)},
            correlation_id=correlation_id,
        )
        self.audit_ledger.append(
            AgentRole.PROTOCOL_ANALYST,
            "protocol_analysis",
            {"protocol_card": normalise(card)},
            ExecutionStatus.COMPLETED,
            "protocol card emitted",
            correlation_id=correlation_id,
            input_payload={"metadata": metadata, "task_hint": task_hint},
            output_payload=normalise(card),
        )
        plan = self.preprocessing_coordinator.plan(card)
        self.message_bus.publish(
            MessageKind.PREPROCESSING_PLAN,
            AgentRole.PREPROCESSING_COORDINATOR,
            AgentRole.QUANTITATIVE_ANALYZER,
            {"preprocessing_plan": normalise(plan)},
            correlation_id=correlation_id,
        )
        self.audit_ledger.append(
            AgentRole.PREPROCESSING_COORDINATOR,
            "preprocessing_plan",
            {"preprocessing_plan": normalise(plan)},
            ExecutionStatus.COMPLETED,
            "route plan emitted",
            correlation_id=correlation_id,
            input_payload=normalise(card),
            output_payload=normalise(plan),
        )
        return card, plan

    def report(
        self,
        plan: PreprocessingPlan,
        task_id: str,
        measurements: dict[str, Any],
        provenance: list[dict[str, Any]] | None = None,
        retry_count: int = 0,
    ) -> tuple[QuantitativeReport, VerificationResult]:
        correlation_id = plan.plan_id
        report = self.quantitative_analyzer.build_report(plan, task_id, measurements, provenance)
        report.status = ExecutionStatus.COMPLETED
        self.message_bus.publish(
            MessageKind.QUANTITATIVE_REPORT,
            AgentRole.QUANTITATIVE_ANALYZER,
            AgentRole.VERIFICATION_AUDITOR,
            {"quantitative_report": normalise(report)},
            correlation_id=correlation_id,
        )
        self.audit_ledger.append(
            AgentRole.QUANTITATIVE_ANALYZER,
            "quantitative_report",
            {"quantitative_report": normalise(report)},
            ExecutionStatus.COMPLETED,
            "report emitted",
            correlation_id=correlation_id,
            input_payload={"measurements": measurements},
            output_payload=normalise(report),
        )
        verification = self.verification_auditor.audit(report, retry_count)
        self.message_bus.publish(
            MessageKind.VERIFICATION_RESULT,
            AgentRole.VERIFICATION_AUDITOR,
            AgentRole.SYSTEM,
            {"verification_result": normalise(verification)},
            correlation_id=correlation_id,
        )
        self.audit_ledger.append(
            AgentRole.VERIFICATION_AUDITOR,
            "verification_result",
            {"verification_result": normalise(verification)},
            ExecutionStatus.COMPLETED if verification.status != "failed" else ExecutionStatus.BLOCKED,
            verification.status,
            correlation_id=correlation_id,
            input_payload=normalise(report),
            output_payload=normalise(verification),
        )
        if verification.retry_target:
            self.message_bus.publish(
                MessageKind.RETRY_REQUEST,
                AgentRole.VERIFICATION_AUDITOR,
                AgentRole.SYSTEM,
                {"retry_target": verification.retry_target, "issues": normalise(verification.issues)},
                correlation_id=correlation_id,
            )
        return report, verification

    def audit_trail(self, correlation_id: str | None = None) -> list[dict[str, Any]]:
        return [normalise(event) for event in self.audit_ledger.events(correlation_id)]
