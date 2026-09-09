# Architecture — Stage 1

EDGEOPS starts with the internal tool boundary of a future FastAPI/PostgreSQL modular monolith. The current package has no infrastructure connections.

## Tool lifecycle

1. Trusted application startup registers frozen `ToolDefinition` objects. There is no endpoint for runtime registration or arbitrary command strings.
2. A trusted service caller supplies an `Actor`. Permissions and allowed targets never come from `ToolRequest` fields.
3. `ToolExecutor` parses/revalidates the envelope and resolves the tool. Unknown tools and malformed requests return errors and audit events.
4. The tool's strict input schema validates arguments. Unknown fields and implicit coercion fail.
5. Deterministic policy checks the explicit permission, exact target scope, and risk category. Exact scope includes host, resource, and environment.
6. The tool-specific validator confirms the target is supported. Validators must return the literal boolean `True` to authorize a target.
7. Authorized read-only adapters execute under a cooperative asynchronous timeout. Every mutable category is blocked pending the future approval service.
8. The output schema revalidates adapter results, including previously constructed model instances. Common secret fields and patterns are recursively redacted before the result is returned.
9. A result envelope and one immutable audit event share evidence and correlation IDs. Audit events contain identity, target, outcome, policy, duration, and redaction categories; they omit raw arguments, output and exception text.

The observed timestamp records completion, in UTC. Durations use a monotonic clock. Correlation IDs may be shared by related calls; each attempt gets its own evidence ID. Invalid envelopes get a generated correlation ID and omit untrusted tool/target metadata. Cancellation is audited, then re-raised to the caller.

## Module boundaries

| Module | Responsibility |
| --- | --- |
| `tools/contracts.py` | Schemas, risk, idempotency metadata, identity and tool definition |
| `tools/registry.py` | Trusted registration and lookup |
| `tools/policy.py` | Deterministic permission, target scope and risk decisions |
| `tools/executor.py` | Validation, invocation, timeouts, normalization and audit |
| `tools/definitions/demo.py` | Explicitly opted-in synthetic adapters |
| `core/redaction.py` | Recursive common-secret masking |
| `core/errors.py` | Internal registry exceptions |

Domain code depends on a tool definition and executor; infrastructure integration details will stay in adapters. There is no dependency on Docker, SSH, HTTP services, a database, or a model provider.

## Risk model

| Risk | Result for an authorized caller and valid target |
| --- | --- |
| Read-only | Allow automatically |
| Low risk | Require approval; do not execute |
| Medium risk | Require approval; do not execute |
| High risk | Require approval; do not execute |
| Forbidden | Deny |

Missing permission or a target outside the caller's scope always denies access. Target environment is matched against trusted caller scope, rather than trusting a request's claim that a production host is local. Real asset resolution remains a later phase. `KEY_REQUIRED` is contract metadata only: no mutation is executed and no idempotency guarantee is implemented yet.

## Trust and limits

Adapters, schemas, validators, actor creation, and tool registration are trusted application code. This is a capability boundary for callers, not a Python sandbox. A malicious adapter can bypass application logic; only reviewed adapters should be registered. Schemas should use bounded fields and nested strict models, with explicit serialization contracts. Custom serializers must not expose secrets.

Async timeouts cancel cooperative adapters. They cannot interrupt blocking Python, suppressions of cancellation, or external work already started. Future adapters must also configure transport timeouts and bounded output; privileged operations require a separate action design.

Secret-key matching, bearer tokens, key/value secret patterns, credential-bearing URLs, and private-key blocks are masked in adapter data. This is not exhaustive secret detection. Request identifiers must be non-secret, and raw user arguments are intentionally excluded from auditing. Redaction occurs after typed normalization and may replace a typed secret value with a string, so the returned `data` is a sanitized view of the output schema.

Audit storage exposes append and immutable snapshot reads. It is process-local, unbounded, and neither durable nor tamper-proof. Database persistence, retention and access controls must precede real deployments. If audit append fails, no successful result is returned; the in-memory implementation provides no cross-process transactional guarantee.

## Verification

Unit tests exercise registration, all risk categories, exact target scope, invalid envelopes and arguments, output validation, exception secrecy, recursive redaction, timeout cleanup, cancellation, concurrent evidence IDs, and audit snapshots. The demo checks the complete synthetic flow. Infrastructure validation is explicitly deferred.
