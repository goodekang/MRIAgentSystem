from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any, Literal
from uuid import uuid4


class ProtocolClass(str, Enum):
    T1_MPRAGE = "T1-MPRAGE"
    T1_SE = "T1-SE"
    T1_GD = "T1-Gd"
    T2_SE = "T2-SE"
    T2_FLAIR = "T2-FLAIR"
    T2_STAR = "T2*"
    PD = "PD"
    CINE_SSFP = "cine-SSFP"
    CINE_GRE = "cine-GRE"
    DWI = "DWI"
    SWI = "SWI"
    MRA = "MRA"
    UNKNOWN = "unknown"


class Domain(str, Enum):
    BRAIN_TUMOUR = "brain_tumour"
    CARDIAC = "cardiac"
    NEURODEGENERATION = "neurodegeneration"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class AgentRole(str, Enum):
    PROTOCOL_ANALYST = "protocol_analyst"
    PREPROCESSING_COORDINATOR = "preprocessing_coordinator"
    QUANTITATIVE_ANALYZER = "quantitative_analyzer"
    VERIFICATION_AUDITOR = "verification_auditor"
    SYSTEM = "system"


class MessageKind(str, Enum):
    TASK_REQUEST = "task_request"
    PROTOCOL_CARD = "protocol_card"
    PREPROCESSING_PLAN = "preprocessing_plan"
    QUANTITATIVE_REPORT = "quantitative_report"
    VERIFICATION_RESULT = "verification_result"
    RETRY_REQUEST = "retry_request"
    AUDIT_EVENT = "audit_event"


class ExecutionStatus(str, Enum):
    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass(slots=True)
class ImageStatistics:
    mean: float | None = None
    median: float | None = None
    std: float | None = None
    coefficient_of_variation: float | None = None
    snr: float | None = None
    histogram: list[float] = dataclass_field(default_factory=list)


@dataclass(slots=True)
class ProtocolCard:
    protocol_class: ProtocolClass
    domain: Domain
    confidence: float
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)
    image_statistics: ImageStatistics = dataclass_field(default_factory=ImageStatistics)
    evidence: list[str] = dataclass_field(default_factory=list)
    preprocessing_constraints: dict[str, Any] = dataclass_field(default_factory=dict)
    card_id: str = dataclass_field(default_factory=lambda: uuid4().hex)


@dataclass(slots=True)
class ToolDescriptor:
    name: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    compatible_protocols: tuple[ProtocolClass, ...]
    compatible_domains: tuple[Domain, ...]
    dependencies: tuple[str, ...] = ()
    parameters: dict[str, Any] = dataclass_field(default_factory=dict)
    expected_runtime_s: float | None = None


@dataclass(slots=True)
class PreprocessingStep:
    tool_name: str
    parameters: dict[str, Any] = dataclass_field(default_factory=dict)
    dependencies: tuple[str, ...] = ()
    parallel_group: int = 0
    step_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    status: ExecutionStatus = ExecutionStatus.CREATED


@dataclass(slots=True)
class PreprocessingPlan:
    protocol_card: ProtocolCard
    steps: list[PreprocessingStep]
    route_id: str
    qc_requirements: dict[str, Any] = dataclass_field(default_factory=dict)
    plan_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    status: ExecutionStatus = ExecutionStatus.READY


@dataclass(slots=True)
class Biomarker:
    name: str
    value: float | int | str | list[float]
    unit: str
    source: str
    confidence: float | None = None
    bounds: tuple[float, float] | None = None
    attributes: dict[str, Any] = dataclass_field(default_factory=dict)


@dataclass(slots=True)
class QuantitativeReport:
    task_id: str
    domain: Domain
    protocol_class: ProtocolClass
    biomarkers: dict[str, Biomarker]
    provenance: list[dict[str, Any]] = dataclass_field(default_factory=list)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)
    report_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    status: ExecutionStatus = ExecutionStatus.CREATED


@dataclass(slots=True)
class VerificationIssue:
    code: str
    message: str
    severity: Severity
    field: str | None = None
    suggested_action: str | None = None
    evidence: dict[str, Any] = dataclass_field(default_factory=dict)


@dataclass(slots=True)
class VerificationResult:
    status: Literal["passed", "warning", "failed"]
    confidence: float
    issues: list[VerificationIssue] = dataclass_field(default_factory=list)
    retry_target: str | None = None
    result_id: str = dataclass_field(default_factory=lambda: uuid4().hex)


@dataclass(slots=True)
class MessageEnvelope:
    kind: MessageKind
    sender: AgentRole
    receiver: AgentRole
    payload: dict[str, Any]
    correlation_id: str
    message_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    parent_id: str | None = None
    schema_version: str = "2026.1"
    created_at: float | None = None
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)


@dataclass(slots=True)
class AuditEvent:
    agent: AgentRole
    event_type: str
    payload_hash: str
    status: ExecutionStatus
    message: str
    event_id: str = dataclass_field(default_factory=lambda: uuid4().hex)
    correlation_id: str | None = None
    input_hash: str | None = None
    output_hash: str | None = None
    elapsed_ms: float | None = None
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)


@dataclass(slots=True)
class AgentState:
    role: AgentRole
    status: ExecutionStatus = ExecutionStatus.CREATED
    memory: dict[str, Any] = dataclass_field(default_factory=dict)
    pending_messages: list[str] = dataclass_field(default_factory=list)
    completed_messages: list[str] = dataclass_field(default_factory=list)


@dataclass(slots=True)
class TaskContext:
    task_id: str
    task_hint: str | None = None
    dataset_id: str | None = None
    subject_id: str | None = None
    acquisition_id: str | None = None
    private_config_ref: str | None = None
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)
