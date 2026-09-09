import asyncio

from edgeops.tools.contracts import Actor, Target, ToolRequest
from edgeops.tools.definitions.demo import build_demo_registry
from edgeops.tools.executor import InMemoryAuditLog, ToolExecutor


async def run() -> None:
    target = Target(host_id="demo-host")
    actor = Actor("demo-user", frozenset({"tools.host.read"}), frozenset({target}))
    audit = InMemoryAuditLog()
    registry = build_demo_registry()
    executor = ToolExecutor(registry, audit)
    for name in registry.names():
        result = await executor.execute(ToolRequest(tool_name=name, target=target), actor)
        print(result.model_dump_json(indent=2))
    print(f"Audit events: {len(audit.events)} (in memory; synthetic data only)")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
