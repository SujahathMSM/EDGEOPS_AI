"""Synthetic fixtures only: these tools never inspect the actual machine."""

from pydantic import Field

from edgeops.tools.contracts import Idempotency, RiskLevel, StrictModel, Target, ToolDefinition
from edgeops.tools.registry import ToolRegistry


class HostInput(StrictModel):
    pass


class HostOutput(StrictModel):
    healthy: bool
    source: str


class DiskInput(StrictModel):
    mount: str = Field(default="/", pattern=r"^/$")


class DiskOutput(StrictModel):
    mount: str
    total_bytes: int = Field(gt=0)
    used_bytes: int = Field(ge=0)
    source: str


def demo_target(target: Target, arguments: StrictModel) -> bool:
    return target == Target(host_id="demo-host", environment="local")


async def host_health(target: Target, arguments: HostInput) -> HostOutput:
    return HostOutput(healthy=True, source="synthetic_fixture")


async def disk_usage(target: Target, arguments: DiskInput) -> DiskOutput:
    return DiskOutput(mount=arguments.mount, total_bytes=100_000, used_bytes=25_000,
                      source="synthetic_fixture")


def build_demo_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for name, input_schema, output_schema, adapter in (
        ("get_demo_host_health", HostInput, HostOutput, host_health),
        ("get_demo_disk_usage", DiskInput, DiskOutput, disk_usage),
    ):
        registry.register(ToolDefinition(
            name=name, input_schema=input_schema, output_schema=output_schema,
            risk_level=RiskLevel.READ_ONLY, required_permission="tools.host.read",
            timeout_seconds=2, idempotency=Idempotency.READ_ONLY,
            target_validator=demo_target, adapter=adapter,
        ))
    return registry
