from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Awaitable, Callable, Generic, Literal, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class RiskLevel(StrEnum):
    READ_ONLY = "read_only"
    LOW_RISK = "low_risk"
    MEDIUM_RISK = "medium_risk"
    HIGH_RISK = "high_risk"
    FORBIDDEN = "forbidden"


class Idempotency(StrEnum):
    READ_ONLY = "read_only"
    KEY_REQUIRED = "key_required"


class PolicyDecision(StrEnum):
    ALLOW_AUTOMATICALLY = "allow_automatically"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


class Target(StrictModel):
    host_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_.-]+$")
    resource_id: str | None = Field(default=None, min_length=1, max_length=128,
                                     pattern=r"^[a-zA-Z0-9_.-]+$")
    environment: Literal["local", "development", "staging", "production"] = "local"


class ToolRequest(StrictModel):
    tool_name: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    target: Target
    arguments: dict[str, Any] = Field(default_factory=dict)
    correlation_id: UUID = Field(default_factory=uuid4)


@dataclass(frozen=True)
class Actor:
    """Trusted service-layer identity; never derive permissions from request JSON."""

    actor_id: str
    permissions: frozenset[str]
    allowed_targets: frozenset[Target]


InputT = TypeVar("InputT", bound=StrictModel)
OutputT = TypeVar("OutputT", bound=StrictModel)


@dataclass(frozen=True, kw_only=True)
class ToolDefinition(Generic[InputT, OutputT]):
    name: str
    input_schema: type[InputT]
    output_schema: type[OutputT]
    risk_level: RiskLevel
    required_permission: str
    timeout_seconds: float
    idempotency: Idempotency
    target_validator: Callable[[Target, InputT], bool]
    adapter: Callable[[Target, InputT], Awaitable[OutputT]]


class ValidationIssue(StrictModel):
    # Do not echo input, unknown field names, validator messages or context.
    code: str


class ToolError(StrictModel):
    error_code: str
    message: str
    retryable: bool = False
    details: tuple[ValidationIssue, ...] = ()


class ToolResult(StrictModel):
    status: Literal["success", "error"]
    tool_name: str | None
    target: Target | None
    observed_at: datetime
    duration_ms: int = Field(ge=0)
    correlation_id: UUID
    evidence_id: UUID = Field(default_factory=uuid4)
    data: dict[str, Any] = Field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    redactions_applied: tuple[str, ...] = ()
    error: ToolError | None = None


class AuditEvent(StrictModel):
    event_id: UUID = Field(default_factory=uuid4)
    evidence_id: UUID
    correlation_id: UUID
    actor_id: str
    tool_name: str | None
    target: Target | None
    occurred_at: datetime
    duration_ms: int
    outcome: Literal["success", "error"]
    policy_decision: PolicyDecision | None
    error_code: str | None
    redactions_applied: tuple[str, ...]
