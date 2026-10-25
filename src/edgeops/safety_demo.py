"""Safety showcase: attempts a read, an unknown tool, and forbidden/approval-gated
actions, and prints the deterministic policy outcome for each attempt.

The medium-risk and forbidden adapters raise if ever invoked. In Stage 1 the
executor reaches them only as APPROVAL_REQUIRED or POLICY_DENIED, so a call
would mean a policy bypass. Every attempt is audited.
"""

import asyncio

from edgeops.tools.contracts import (
    Actor,
    Idempotency,
    RiskLevel,
    Target,
    ToolDefinition,
    ToolRequest,
    StrictModel,
)
from edgeops.tools.definitions.demo import (
    demo_target,
    DiskInput,
    DiskOutput,
    disk_usage,
)
from edgeops.tools.executor import InMemoryAuditLog, ToolExecutor
from edgeops.tools.registry import ToolRegistry


class StreamInput(StrictModel):
    pass


class StreamOutput(StrictModel):
    source: str


async def _never_invoked(target: Target, arguments: StrictModel) -> StreamOutput:
    raise RuntimeError("Stage 1 must never execute a mutating adapter.")


async def run() -> None:
    local = Target(host_id="demo-host")
    prod = Target(host_id="demo-host", environment="production")

    full_actor = Actor(
        "demo-user",
        frozenset({"tools.host.read", "actions.demo.restart"}),
        frozenset({local}),
    )

    registry = ToolRegistry()
    registry.register(ToolDefinition(
        name="get_demo_disk_usage",
        input_schema=DiskInput,
        output_schema=DiskOutput,
        risk_level=RiskLevel.READ_ONLY,
        required_permission="tools.host.read",
        timeout_seconds=2,
        idempotency=Idempotency.READ_ONLY,
        target_validator=demo_target,
        adapter=disk_usage,
    ))
    registry.register(ToolDefinition(
        name="restart_demo_stream",
        input_schema=StreamInput,
        output_schema=StreamOutput,
        risk_level=RiskLevel.MEDIUM_RISK,
        required_permission="actions.demo.restart",
        timeout_seconds=2,
        idempotency=Idempotency.KEY_REQUIRED,
        target_validator=demo_target,
        adapter=_never_invoked,
    ))
    registry.register(ToolDefinition(
        name="delete_demo_records",
        input_schema=StreamInput,
        output_schema=StreamOutput,
        risk_level=RiskLevel.FORBIDDEN,
        required_permission="actions.demo.restart",
        timeout_seconds=2,
        idempotency=Idempotency.KEY_REQUIRED,
        target_validator=demo_target,
        adapter=_never_invoked,
    ))

    executor = ToolExecutor(registry, InMemoryAuditLog())
    attempts = [
        ("read-only tool, permitted caller              ", ToolRequest(tool_name="get_demo_disk_usage", target=local)),
        ("unregistered tool                             ", ToolRequest(tool_name="run_raw_shell_fixture", target=local)),
        ("production target, not in caller scope        ", ToolRequest(tool_name="restart_demo_stream", target=prod)),
        ("mutation, correctly permitted and targeted    ", ToolRequest(tool_name="restart_demo_stream", target=local)),
        ("forbidden risk category                       ", ToolRequest(tool_name="delete_demo_records", target=local)),
    ]
    for label, request in attempts:
        result = await executor.execute(request, full_actor)
        print(f"{label} -> {result.status:6} " + (result.error.error_code if result.error else "-"))

    print(f"Audit events: {len(executor.audit.events)} -- every attempt, including denials, is audited.")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
