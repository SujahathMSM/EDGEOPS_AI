import asyncio
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from edgeops.core.errors import UnknownToolError
from edgeops.core.redaction import redact
from edgeops.tools.contracts import (
    Actor, AuditEvent, PolicyDecision, ToolError, ToolRequest, ToolResult, ValidationIssue,
)
from edgeops.tools.policy import PolicyEngine
from edgeops.tools.registry import ToolRegistry


class InMemoryAuditLog:
    """Append-only public interface; process-local and not durable or tamper-proof."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> None:
        self._events.append(event)

    @property
    def events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)


def validation_error(code: str, exc: ValidationError) -> ToolError:
    return ToolError(error_code=code, message="Input does not match the required schema.",
                     details=tuple(ValidationIssue(code=e["type"]) for e in exc.errors(
                         include_url=False, include_context=False, include_input=False)))


class ToolExecutor:
    def __init__(self, registry: ToolRegistry, audit: InMemoryAuditLog,
                 policy: PolicyEngine | None = None) -> None:
        self.registry = registry
        self.audit = audit
        self.policy = policy or PolicyEngine()

    async def execute(self, raw: ToolRequest | dict[str, Any], actor: Actor) -> ToolResult:
        start = perf_counter()
        request = None
        decision = None
        error = None
        data: dict[str, Any] = {}
        redactions: tuple[str, ...] = ()
        cancelled = False
        try:
            try:
                # Revalidate even model instances: frozen models may contain mutable dicts.
                request = ToolRequest.model_validate(raw.model_dump(warnings=False) if isinstance(raw, ToolRequest) else raw)
            except ValidationError as exc:
                error = validation_error("INVALID_REQUEST", exc)
            if request is not None:
                definition = self.registry.resolve(request.tool_name)
                try:
                    arguments = definition.input_schema.model_validate(request.arguments)
                except ValidationError as exc:
                    error = validation_error("INVALID_ARGUMENTS", exc)
                if error is None:
                    decision = self.policy.evaluate(definition, actor, request.target)
                    if decision == PolicyDecision.DENY:
                        error = ToolError(error_code="POLICY_DENIED", message="Permission, target scope or risk policy denied this tool.")
                    elif definition.target_validator(request.target, arguments) is not True:
                        decision = PolicyDecision.DENY
                        error = ToolError(error_code="INVALID_TARGET", message="Target is not supported by this tool.")
                    elif decision == PolicyDecision.REQUIRE_APPROVAL:
                        error = ToolError(error_code="APPROVAL_REQUIRED", message="This action requires approval. Action execution is unavailable in Stage 1.")
                    else:
                        async with asyncio.timeout(definition.timeout_seconds):
                            output = await definition.adapter(request.target, arguments)
                        # Dump and revalidate to catch constructed or mutated invalid model instances.
                        output = definition.output_schema.model_validate(
                            output.model_dump(warnings=False) if isinstance(output, definition.output_schema) else output)
                        data, redactions = redact(output.model_dump(mode="json"))
        except UnknownToolError:
            error = ToolError(error_code="UNKNOWN_TOOL", message="Tool is not registered.")
        except TimeoutError:
            error = ToolError(error_code="TOOL_TIMEOUT", message="Tool exceeded its time limit.", retryable=True)
        except ValidationError:
            error = ToolError(error_code="INVALID_OUTPUT", message="Adapter returned an invalid result.")
        except asyncio.CancelledError:
            cancelled = True
            error = ToolError(error_code="CANCELLED", message="Tool execution was cancelled.")
        except Exception:
            error = ToolError(error_code="TOOL_FAILED", message="Tool execution failed.")

        result = ToolResult(
            status="error" if error else "success", tool_name=request.tool_name if request else None,
            target=request.target if request else None, observed_at=datetime.now(timezone.utc),
            duration_ms=max(0, int((perf_counter() - start) * 1000)),
            correlation_id=request.correlation_id if request else uuid4(),
            data={} if error else data, redactions_applied=redactions, error=error,
        )
        self.audit.append(AuditEvent(
            evidence_id=result.evidence_id, correlation_id=result.correlation_id,
            actor_id=actor.actor_id, tool_name=result.tool_name, target=result.target,
            occurred_at=result.observed_at, duration_ms=result.duration_ms, outcome=result.status,
            policy_decision=decision, error_code=error.error_code if error else None,
            redactions_applied=redactions,
        ))
        if cancelled:
            raise asyncio.CancelledError
        return result
