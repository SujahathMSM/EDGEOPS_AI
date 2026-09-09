import asyncio
from dataclasses import replace
import unittest
import warnings

from edgeops.tools.contracts import Actor, Idempotency, RiskLevel, StrictModel, Target, ToolRequest
from edgeops.tools.definitions.demo import HostOutput, build_demo_registry
from edgeops.tools.executor import InMemoryAuditLog, ToolExecutor
from edgeops.tools.registry import ToolRegistry


class ExecutorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.target = Target(host_id="demo-host")
        self.actor = Actor("user", frozenset({"tools.host.read"}), frozenset({self.target}))
        self.registry = build_demo_registry()
        self.audit = InMemoryAuditLog()
        self.executor = ToolExecutor(self.registry, self.audit)
        self.request = ToolRequest(tool_name="get_demo_host_health", target=self.target)

    def custom(self, **changes):
        registry = ToolRegistry()
        registry.register(replace(self.registry.resolve(self.request.tool_name), **changes))
        return ToolExecutor(registry, self.audit)

    async def test_success_and_correlated_audit(self):
        result = await self.executor.execute(self.request, self.actor)
        self.assertEqual(result.status, "success")
        self.assertTrue(result.data["healthy"])
        self.assertIsNotNone(result.observed_at.tzinfo)
        event, = self.audit.events
        self.assertEqual(event.evidence_id, result.evidence_id)
        self.assertEqual(event.correlation_id, self.request.correlation_id)
        self.assertEqual(event.outcome, "success")
        self.assertGreaterEqual(result.duration_ms, 0)

    async def test_disk_fixture(self):
        result = await self.executor.execute(ToolRequest(tool_name="get_demo_disk_usage", target=self.target), self.actor)
        self.assertEqual(result.data["used_bytes"], 25_000)

    async def test_unknown_tool_audited(self):
        result = await self.executor.execute(self.request.model_copy(update={"tool_name": "unknown"}), self.actor)
        self.assertEqual(result.error.error_code, "UNKNOWN_TOOL")
        self.assertEqual(len(self.audit.events), 1)

    async def test_unknown_argument_never_echoes_secret(self):
        raw = self.request.model_dump()
        raw["arguments"] = {"secret-value-in-field-name": "private-value"}
        result = await self.executor.execute(raw, self.actor)
        self.assertEqual(result.error.error_code, "INVALID_ARGUMENTS")
        self.assertTrue(result.error.details)
        self.assertNotIn("private-value", result.model_dump_json())
        self.assertNotIn("secret-value", result.model_dump_json())

    async def test_malformed_envelopes_audited(self):
        for changes in ({"extra": "secret"}, {"target": {"host_id": "../etc"}},
                        {"target": {"host_id": "demo-host", "extra": True}},
                        {"arguments": []}, {"correlation_id": "invalid"}):
            with self.subTest(changes=changes):
                result = await self.executor.execute(self.request.model_dump() | changes, self.actor)
                self.assertEqual(result.error.error_code, "INVALID_REQUEST")
        self.assertEqual(len(self.audit.events), 5)

    async def test_wrong_argument_type_and_mount_rejected(self):
        for mount in (123, "/etc"):
            result = await self.executor.execute(ToolRequest(tool_name="get_demo_disk_usage", target=self.target,
                                                arguments={"mount": mount}), self.actor)
            self.assertEqual(result.error.error_code, "INVALID_ARGUMENTS")

    async def test_missing_permission_prevents_adapter(self):
        called = False
        async def adapter(*_):
            nonlocal called
            called = True
            return HostOutput(healthy=True, source="fixture")
        result = await self.custom(adapter=adapter).execute(self.request, replace(self.actor, permissions=frozenset()))
        self.assertEqual(result.error.error_code, "POLICY_DENIED")
        self.assertFalse(called)

    async def test_out_of_scope_prevents_execution(self):
        result = await self.executor.execute(self.request, replace(self.actor, allowed_targets=frozenset()))
        self.assertEqual(result.error.error_code, "POLICY_DENIED")

    async def test_tool_target_validator_rejects_even_authorized_target(self):
        target = Target(host_id="other-host")
        actor = replace(self.actor, allowed_targets=frozenset({target}))
        result = await self.executor.execute(self.request.model_copy(update={"target": target}), actor)
        self.assertEqual(result.error.error_code, "INVALID_TARGET")

    async def test_mutations_and_forbidden_never_invoke_adapter(self):
        async def must_not_run(*_):
            self.fail("Action adapter must not execute.")
        for risk in (RiskLevel.LOW_RISK, RiskLevel.MEDIUM_RISK, RiskLevel.HIGH_RISK, RiskLevel.FORBIDDEN):
            with self.subTest(risk=risk):
                executor = self.custom(risk_level=risk, idempotency=Idempotency.KEY_REQUIRED, adapter=must_not_run)
                result = await executor.execute(self.request, self.actor)
                self.assertEqual(result.error.error_code,
                                 "POLICY_DENIED" if risk == RiskLevel.FORBIDDEN else "APPROVAL_REQUIRED")

    async def test_exception_is_sanitized_and_audited(self):
        async def broken(*_):
            raise RuntimeError("password=top-secret")
        result = await self.custom(adapter=broken).execute(self.request, self.actor)
        self.assertEqual(result.error.error_code, "TOOL_FAILED")
        self.assertNotIn("top-secret", result.model_dump_json() + self.audit.events[0].model_dump_json())

    async def test_invalid_output_rejected(self):
        async def broken(*_):
            return HostOutput.model_construct(healthy="secret", source="fixture")
        with warnings.catch_warnings(record=True) as emitted:
            warnings.simplefilter("always")
            result = await self.custom(adapter=broken).execute(self.request, self.actor)
        self.assertEqual(emitted, [])
        self.assertEqual(result.error.error_code, "INVALID_OUTPUT")
        self.assertEqual(result.data, {})

    async def test_timeout_cancels_cooperative_adapter(self):
        stopped = asyncio.Event()
        async def slow(*_):
            try:
                await asyncio.sleep(10)
            finally:
                stopped.set()
        result = await self.custom(adapter=slow, timeout_seconds=0.01).execute(self.request, self.actor)
        self.assertEqual(result.error.error_code, "TOOL_TIMEOUT")
        self.assertTrue(result.error.retryable)
        self.assertTrue(stopped.is_set())

    async def test_external_cancellation_audited_and_propagated(self):
        started = asyncio.Event()
        async def slow(*_):
            started.set()
            await asyncio.sleep(10)
        task = asyncio.create_task(self.custom(adapter=slow).execute(self.request, self.actor))
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.audit.events[0].error_code, "CANCELLED")

    async def test_secrets_redacted_before_return(self):
        class Output(StrictModel):
            payload: dict
        async def secrets(*_):
            return Output(payload={"password": "secret-one", "nested": [
                "Bearer secret-two", "token=secret-three", "postgres://user:secret-four@db/test"],
                "healthy": True})
        result = await self.custom(adapter=secrets, output_schema=Output).execute(self.request, self.actor)
        self.assertEqual(result.status, "success")
        for secret in ("secret-one", "secret-two", "secret-three", "secret-four"):
            self.assertNotIn(secret, result.model_dump_json())
        self.assertTrue(result.data["payload"]["healthy"])
        self.assertTrue(result.redactions_applied)
        self.assertEqual(self.audit.events[0].redactions_applied, result.redactions_applied)

    async def test_concurrent_calls_have_distinct_evidence(self):
        results = await asyncio.gather(*(self.executor.execute(self.request, self.actor) for _ in range(10)))
        self.assertEqual(len({r.evidence_id for r in results}), 10)
        self.assertEqual(len(self.audit.events), 10)

    async def test_audit_events_are_immutable_snapshots(self):
        snapshot = self.audit.events
        await self.executor.execute(self.request, self.actor)
        self.assertEqual(snapshot, ())
        with self.assertRaises(ValueError):
            self.audit.events[0].actor_id = "replacement"
