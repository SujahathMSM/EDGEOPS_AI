# Tool catalog — Stage 1

Both tools are synthetic, read-only and require `tools.host.read`. The only supported target is host `demo-host`, environment `local`, with no resource ID. The caller must also have this exact target in its trusted scope. Each tool has a two-second timeout and read-only idempotency metadata.

| Tool | Arguments | Output |
| --- | --- | --- |
| `get_demo_host_health` | Empty object | `healthy: true`, `source: synthetic_fixture` |
| `get_demo_disk_usage` | Optional `mount`, restricted to `/` | Mount, total bytes 100000, used bytes 25000, synthetic source |

## Defining a future tool

1. Define input and output Pydantic schemas inheriting `StrictModel`; use bounded fields and strict nested models. Do not weaken `extra='forbid'` or strict validation.
2. Write a cooperative async adapter accepting the resolved `Target` and typed input, and returning the declared output. Handle external I/O with its own timeouts and response bounds.
3. Write a synchronous validator restricting targets and arguments to the capability's supported scope.
4. Create a `ToolDefinition` with an explicit permission, risk, timeout, idempotency behavior, schemas, validator and adapter.
5. Register it explicitly from trusted startup code. Supply an `Actor` from trusted authentication/authorization code when that layer exists.
6. Invoke it through `ToolExecutor`, and test denied and malformed requests as well as successful results.

`definitions/demo.py` is the executable example. Importing definitions does not register tools automatically.

## Result contract

Every completed call returns `status`, `tool_name`, `target`, `observed_at`, `duration_ms`, `correlation_id`, `evidence_id`, `data`, `warnings`, `redactions_applied`, and `error`. Failure data is empty. Validation details expose error categories only, never input values, unknown field names, or custom validator messages. Caller cancellation records an event and propagates cancellation instead of returning a result.

| Error code | Meaning |
| --- | --- |
| `INVALID_REQUEST` | Malformed common envelope |
| `UNKNOWN_TOOL` | Capability not registered |
| `INVALID_ARGUMENTS` | Tool-specific input validation failed |
| `POLICY_DENIED` | Permission, target scope or forbidden risk rejected |
| `INVALID_TARGET` | Tool-specific target validator rejected |
| `APPROVAL_REQUIRED` | Mutable action is blocked in Stage 1 |
| `TOOL_TIMEOUT` | Cooperative execution deadline elapsed |
| `INVALID_OUTPUT` | Adapter result violates its schema |
| `TOOL_FAILED` | Internal failure with details withheld |
| `CANCELLED` | Caller cancelled; recorded in audit |

Approval is a policy outcome only. There is no client-supplied approval flag, action execution, credential export or shell capability.
