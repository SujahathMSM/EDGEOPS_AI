# EDGEOPS AI — Technical Blueprint

## 1. Product definition

EDGEOPS AI is an AI-assisted operations platform for small-to-medium infrastructure and industrial-software environments. It helps an engineer investigate incidents across Linux hosts, Docker services, applications, databases, telemetry, Git history, and internal documentation—then proposes safe, evidence-backed remediation and verifies the result.

The core problem is not “answer operational questions with a chatbot.” It is reducing the time from alert or symptom to an auditable, verified operational outcome.

Target users:

- Backend, DevOps, platform, and SRE-minded engineers.
- Teams operating Dockerized services on Linux or EC2.
- Industrial/energy engineers supporting APIs, gateways, telemetry collectors, BMS/inverter integrations, and RS-485/Modbus-connected systems.
- A solo engineer or small team that needs disciplined operations without a full commercial observability platform.

Realistic early use cases:

- “Why did `control-api` begin returning 5xx after the latest deployment?”
- “Which Docker services are unhealthy, restarting, or out of disk space?”
- “Find incidents similar to the current PostgreSQL connection exhaustion.”
- “Did restarting the telemetry worker restore message ingestion?”
- “What changed in Git shortly before this service degraded?”
- “Which hosts have the highest memory usage or failed systemd services?”
- “Summarize repeated Modbus timeout patterns in the last six hours.”

What makes it distinct from a generic AI chatbot:

- It uses typed, capability-limited operational tools rather than arbitrary shell access.
- It works from collected evidence, timestamps, health checks, Git state, metrics, and RAG retrieval.
- It separates observation, hypothesis, recommendation, approval, action, and verification.
- Every conclusion has evidence references and confidence—not ungrounded prose.
- Every model call and tool execution is auditable.
- Expensive reasoning is an explicit escalation path, not the default.

The product’s governing principle:

> Deterministic tools collect facts. Local models compress and classify facts. Better models reason only when the evidence and task justify escalation. Humans approve meaningful changes.

---

## 2. System architecture

Start as a modular monolith: one FastAPI application, one PostgreSQL database, Docker Compose, and optional local Ollama. Keep internal module boundaries clean enough to extract workers or services later.

```text
                    ┌───────────────────────────┐
                    │ Web UI / CLI / API Client │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │ FastAPI API / Auth / RBAC │
                    └─────────────┬─────────────┘
                                  │
     ┌────────────────────────────┼─────────────────────────────┐
     │                            │                             │
┌────▼─────┐                ┌─────▼─────┐                ┌──────▼──────┐
│ Incident │                │  Model    │                │ Policy /    │
│ Engine   │                │  Router   │                │ Approval    │
└────┬─────┘                └─────┬─────┘                └──────┬──────┘
     │                            │                             │
     └──────────────┬─────────────┴──────────────┬──────────────┘
                    │                            │
            ┌───────▼────────┐          ┌────────▼─────────┐
            │ Typed Tool     │          │ Knowledge / RAG   │
            │ Registry       │          │ Service           │
            └───────┬────────┘          └────────┬─────────┘
                    │                            │
      ┌─────────────┼───────────────┐     ┌──────▼────────────┐
      │             │               │     │ PostgreSQL +       │
┌─────▼────┐ ┌──────▼─────┐ ┌───────▼───┐ │ pgvector           │
│ Host /   │ │ Docker /   │ │ Git / DB  │ └────────────────────┘
│ systemd  │ │ HTTP / logs│ │ telemetry │
└──────────┘ └────────────┘ └───────────┘
```

### Component responsibilities

| Component | Responsibility |
|---|---|
| FastAPI API | Request validation, authentication, authorization, SSE/WebSocket updates, API contracts. |
| Incident engine | Coordinates investigation state, evidence collection, timeline construction, hypotheses, recommendations, and verification. |
| Tool registry | Defines typed tool contracts, validates arguments, checks permission/risk metadata, invokes adapters, normalizes results. |
| Tool adapters | Concrete integrations for host inspection, Docker, HTTP, Git, PostgreSQL, metrics, and later SSH agents. |
| Policy engine | Determines whether a proposed action is automatically allowed, requires approval, or is prohibited. |
| Approval service | Creates immutable approval requests and binds approvals to exact action parameters and expiry windows. |
| Model router | Selects `NO_LLM`, `LOCAL_LLM`, `CHEAP_REMOTE_LLM`, or `ASTRA`, based on task complexity, evidence quality, data sensitivity, and budget. |
| RAG service | Retrieves runbooks, architecture documents, prior incidents, deployment notes, and relevant operational context. |
| PostgreSQL | Primary source of truth for assets, incidents, evidence, actions, approvals, audit records, model invocations, and vectors. |
| Worker subsystem, later | Handles long-running ingestion, scheduled checks, embeddings, log processing, and action verification. |

### Standard request flow

1. A user submits a question or starts an incident.
2. The API authenticates the user and checks RBAC permissions.
3. The incident engine classifies the request.
4. The model router first decides whether deterministic parsing and tools are sufficient.
5. The tool planner selects only approved read-only tools.
6. Tools collect structured evidence.
7. The system locally filters, aggregates, deduplicates, and timestamps the evidence.
8. RAG retrieves relevant operational knowledge.
9. A model, if needed, produces hypotheses or a concise explanation from the reduced evidence set.
10. The incident engine stores observations, evidence links, hypotheses, and recommendations.
11. If a remediation is proposed, policy evaluates it.
12. The system either executes an allowed action or creates an approval request.
13. Verification tools run after execution.
14. The incident timeline and audit trail are finalized.

### Incident-investigation flow

```text
Symptom / alert
   ↓
Create incident
   ↓
Collect bounded read-only evidence
   ↓
Normalize + correlate timestamps
   ↓
Retrieve similar incidents/runbooks
   ↓
Generate and rank hypotheses
   ↓
Recommend a minimally risky next step
   ↓
Approval if state change is needed
   ↓
Execute exact approved action
   ↓
Verify health / metrics / logs
   ↓
Record outcome and incident memory
```

### Remediation flow

A remediation is never free-form shell text. It is a typed action request.

```text
Proposed action
  → validate schema
  → validate target ownership/environment
  → calculate risk
  → enforce RBAC and policy
  → require approval when required
  → execute idempotently
  → capture result
  → run verification checks
  → write audit event
```

---

## 3. Model-routing architecture

The router should be deterministic Python logic first. Do not delegate routing itself to an LLM.

### Routing tiers

| Tier | Use when | Examples |
|---|---|---|
| `NO_LLM` | A typed tool, query, parser, rule, or template can produce the result reliably. | Disk usage, container status, HTTP health, known alert correlation, SQL aggregation, restart verification. |
| `LOCAL_LLM` | Small bounded text transformation or simple reasoning is useful; privacy and low cost matter. | Log clustering, short summaries, incident tagging, extracting error signatures, classifying a request, creating a concise evidence brief. |
| `CHEAP_REMOTE_LLM` | Multi-source synthesis exceeds the local model’s reliability, but the decision is not high impact or deeply ambiguous. | Compare several plausible causes, synthesize a medium-sized incident report, generate a runbook draft from sanitized evidence. |
| `ASTRA` | Difficult cross-system reasoning, high uncertainty, complex planning, architecture-level decisions, or an unresolved incident after cheaper paths. | Root-cause investigation spanning deployments, database behavior, logs, metrics, Git changes, and operational history. |

### Router inputs

The router should evaluate:

- Request type: information lookup, investigation, diagnosis, recommendation, action proposal, postmortem.
- Impact: development, staging, production; affected service criticality.
- Evidence breadth: one source versus multiple systems.
- Evidence volume after reduction.
- Ambiguity: known rule match versus competing plausible causes.
- Required output: structured classification versus multi-step reasoning.
- Safety sensitivity: whether model output could lead to a production action.
- Privacy classification: can evidence leave the local environment?
- Cost budget: per incident and daily limits.
- Previous failure/escalation history.

### Default decision rules

1. Use `NO_LLM` whenever the output can be produced by a tool, query, threshold, parser, or deterministic template.
2. Use `LOCAL_LLM` for bounded text under a configured context limit, after redaction and deduplication.
3. Use `CHEAP_REMOTE_LLM` only after local processing has created a compact incident packet and the task is not safety-critical.
4. Use `ASTRA` only when all of the following hold:
   - The task requires cross-system reasoning or complex planning.
   - Local/cheap methods cannot resolve the issue with adequate confidence.
   - A compact, evidence-linked incident packet is available.
   - Sensitive fields are redacted or explicitly permitted.
   - A budget and escalation policy allow it.
5. Model output may propose actions, but it cannot bypass policy or approvals.

### Escalation logic

```text
Start: deterministic collection and rules
  ├─ Clear known condition → NO_LLM result
  ├─ Need short classification/summarization → LOCAL_LLM
  ├─ Local result confidence insufficient and incident remains bounded
  │    → CHEAP_REMOTE_LLM
  └─ Multiple systems, conflicting evidence, high consequence, or unresolved
       → ASTRA escalation
```

Escalation should record:

- Why the prior tier was insufficient.
- The exact compact prompt/evidence packet.
- Cost and token estimate.
- Whether remote transmission was allowed.
- The returned confidence and unresolved questions.

### Example routing

| Request | Initial tier | Escalation condition |
|---|---|---|
| “Is `control-api` healthy?” | `NO_LLM` | None; call HTTP and container health tools. |
| “Summarize recurring errors in this 20 MB log.” | `LOCAL_LLM` after deterministic clustering | Remote only if the classified clusters remain ambiguous. |
| “What changed just before this regression?” | `NO_LLM` for Git/log/metric collection, then `LOCAL_LLM` | `CHEAP_REMOTE_LLM` or Astra if correlations conflict. |
| “Why did the deployment cause failures?” | Begin with tools and local summarization | Astra if multi-system causal reasoning remains unresolved. |
| “Restart service X.” | `NO_LLM` | Policy and approval determine execution; no model required. |
| “Design a safe rollback plan for a partially failed migration.” | Astra likely appropriate | Must remain proposal-only until approved. |

### Cost and context control

- Use deterministic filters before every model invocation.
- Store raw logs externally or in bounded retention; send only extracted windows and signatures to models.
- Deduplicate identical errors by normalized fingerprint.
- Aggregate repeated telemetry into rates, percentiles, anomalies, and time windows.
- Summarize progressively: raw events → cluster summaries → investigation brief.
- Use strict maximum context sizes per model tier.
- Cache embeddings and reusable summaries by content hash.
- Keep per-incident model budgets, daily tenant/user budgets, and Astra quotas.
- Prefer structured outputs, such as JSON hypotheses with evidence IDs.
- Persist model invocations so repeated prompts are visible and measurable.

### Context-reduction packet

Before remote or Astra reasoning, produce an evidence packet containing:

- Incident statement and exact time window.
- Affected host, service, deployment version, and environment.
- 5–20 most relevant evidence items, each with a stable ID.
- Error signatures and counts, not unbounded logs.
- Metric deltas and timestamps.
- Recent code/configuration changes.
- Retrieved prior incidents/runbooks.
- Explicit unknowns and contradictions.
- A required instruction: “Do not claim causality without linked evidence.”

---

## 4. Tool-execution architecture

Tools are typed application capabilities, not generic commands. Each tool has a name, schema, risk category, target constraints, required permission, timeout, idempotency behavior, and output contract.

### Initial tool catalog

Read-only tools:

```python
get_host_health(host_id)
get_disk_usage(host_id)
get_memory_usage(host_id)
get_running_containers(host_id)
get_container_status(host_id, container_id)
get_container_logs(host_id, container_id, since, until, tail)
get_service_status(host_id, service_name)
get_git_status(repository_id)
get_recent_commits(repository_id, since, limit)
query_metrics(metric_query, start, end)
query_database(query_template_id, parameters)
search_knowledge_base(query, filters, limit)
check_http_health(url_or_service_id)
```

Controlled actions:

```python
restart_container(host_id, container_id)
restart_service(host_id, service_name)
rollback_deployment(service_id, target_version)
```

Do not add arbitrary shell execution to the MVP. If it is eventually needed, represent it as a highly restricted tool with fixed command templates, predefined arguments, allowlisted targets, and mandatory approval.

### Tool registry contract

```python
ToolDefinition(
    name="get_container_logs",
    input_schema=GetContainerLogsRequest,
    output_schema=ContainerLogsResult,
    risk_level=RiskLevel.READ_ONLY,
    required_permission="tools.containers.read",
    timeout_seconds=20,
    idempotency=Idempotency.READ_ONLY,
    target_validator=validate_host_and_container_scope,
)
```

Use Pydantic models for all input and output schemas. Reject unknown fields by default.

### Tool permissions

Permissions should be explicit and composable:

```text
tools.host.read
tools.docker.read
tools.git.read
tools.database.read
tools.metrics.read
tools.http.read
actions.container.restart
actions.service.restart
actions.deployment.rollback
incidents.read
incidents.manage
approvals.grant
audit.read
```

### Execution lifecycle

1. Parse and validate typed arguments.
2. Resolve the target and environment.
3. Check caller RBAC.
4. Check tool policy and risk.
5. For actions, bind exact parameters to an approval if required.
6. Execute through the adapter.
7. Normalize output to the registered output schema.
8. Redact secrets before persistence/display.
9. Persist an observation or action result.
10. Emit audit and telemetry events.
11. Return a stable result with timestamps, status, warnings, and evidence ID.

### Output normalization

All tools should return a common envelope:

```json
{
  "status": "success",
  "tool_name": "get_container_status",
  "target": {
    "host_id": "host-prod-1",
    "resource_id": "control-api"
  },
  "observed_at": "2026-09-05T10:15:00Z",
  "duration_ms": 84,
  "data": {},
  "warnings": [],
  "redactions_applied": [],
  "evidence_id": "obs_..."
}
```

Failures should be structured, never raw stack traces:

```json
{
  "status": "error",
  "error_code": "TARGET_UNREACHABLE",
  "retryable": true,
  "message": "Host agent could not be reached.",
  "observed_at": "2026-09-05T10:15:00Z"
}
```

---

## 5. Safety architecture

### Policy engine

The policy engine is deterministic and lives between the planner and executor. It evaluates:

- Action type and risk level.
- Environment: local, development, staging, production.
- Target service criticality.
- User role and approval authority.
- Change window or maintenance mode.
- Existing incident state.
- Exact action parameters.
- Rate limits and cooldowns.
- Whether verification is defined.
- Whether the action is allowlisted.

Policy outcomes:

```text
ALLOW_AUTOMATICALLY
REQUIRE_APPROVAL
DENY
```

### Risk categories

| Category | Examples | Default behavior |
|---|---|---|
| `READ_ONLY` | Health checks, status, logs, Git history. | Automatically execute if user has read permission. |
| `LOW_RISK` | Restart a noncritical development container. | Require approval initially; later allow tightly scoped automation. |
| `MEDIUM_RISK` | Restart production service, scale deployment. | Human approval, defined verification, cooldown. |
| `HIGH_RISK` | Rollback production deployment, alter database configuration. | Elevated approval, explicit change reason, stronger safeguards. |
| `FORBIDDEN` | Arbitrary shell, deleting production data, credential export, unrestricted SQL writes. | Never execute through EDGEOPS AI. |

### Human approval

An approval must be immutable and bound to:

- Action name and exact arguments.
- Environment and target.
- Reason and linked incident.
- Requesting user.
- Approving user.
- Expiration time.
- Required verification plan.
- One-time action token.

Changing any action parameter invalidates the approval.

### Production safeguards

- Production is opt-in per host/service; default registrations are non-production.
- Separate production credentials and roles.
- Deny destructive database statements; expose read-only query templates only in MVP.
- Require verification checks for every mutable action.
- Use action cooldowns to prevent restart loops.
- Enforce “one active action per target” through a lock.
- Add dry-run support wherever meaningful.
- Never let a model create a new tool definition at runtime.
- Never pass secrets, full environment files, SSH keys, or raw credentials to models.

### Audit trail

Write append-only records for:

- Authentication and authorization decisions.
- Every tool invocation.
- Every policy decision.
- Every approval lifecycle event.
- Every action attempt and result.
- Every model invocation and external data transmission.
- Redactions and access denials.

---

## 6. RAG architecture

Your AeroIntel foundation is directly reusable. Keep PostgreSQL, pgvector, `VECTOR(768)`, `embeddinggemma`, chunk storage, and cosine-similarity search as the knowledge layer of EDGEOPS AI.

Do not rebuild it as a separate RAG microservice. Move or adapt it into a `knowledge` module in the modular monolith.

### Documents to ingest

- Runbooks and operational procedures.
- Architecture decision records.
- Service READMEs and deployment documentation.
- Docker Compose and sanitized configuration references.
- API contracts and dependency maps.
- Database schema documentation.
- Alert definitions and dashboards-as-code.
- Postmortems.
- Resolved incident summaries.
- Release notes and deployment notes.
- Git commit messages and pull request summaries.
- Hardware integration notes: Modbus registers, BMS/inverter behavior, field troubleshooting.
- Sanitized log exemplars and known error signatures.

### Chunking strategy

Use document-aware chunking:

- Markdown: split by headings, preserving hierarchical heading path.
- Runbooks: preserve procedure steps and preconditions together.
- Code/configuration: split by logical blocks; preserve filename, service, and version metadata.
- Incident reports: separate symptoms, timeline, cause, remediation, verification, and lessons.
- Logs: do not indiscriminately embed raw logs. Extract recurring signatures, categorized errors, and representative examples.

Recommended initial chunk size:

- Target 400–800 tokens.
- Overlap 60–120 tokens where prose continuity matters.
- Smaller chunks for individual runbook steps and error patterns.
- Store content hash to avoid repeat embeddings.

### Document-chunk metadata

```text
document_id
chunk_index
content
content_hash
embedding VECTOR(768)
source_type
source_path
title
heading_path
service_id
host_id
repository_id
environment
version_or_commit_sha
tags
created_at
updated_at
valid_from
valid_to
sensitivity_level
incident_id
```

### Retrieval pipeline

1. Normalize query and apply explicit metadata filters first.
2. Generate local embedding with `embeddinggemma`.
3. Retrieve top candidates through pgvector cosine similarity.
4. Apply metadata and recency weighting.
5. Optionally run a local lexical search as a hybrid signal.
6. Deduplicate near-identical chunks.
7. Optionally rerank the top 10–30 results using:
   - deterministic metadata scoring first;
   - a local reranker later if retrieval quality requires it.
8. Return compact citations with document/chunk IDs.

### Incident memory

At incident closure, create structured incident memory rather than embedding only the complete transcript.

Store:

- Symptom and impact.
- Affected services and environment.
- Timeline.
- Evidence fingerprints.
- Root cause confidence and status.
- Successful/failed remediation.
- Verification result.
- Related runbooks and commits.
- Lessons and prevention items.

Embed a concise “incident knowledge record” so future incidents can retrieve meaningful precedents without pulling massive raw evidence.

---

## 7. Data model

Use a dedicated PostgreSQL schema such as `edgeops`, leaving existing AeroIntel data easy to migrate or reuse.

### Core tables

```sql
CREATE SCHEMA IF NOT EXISTS edgeops;

CREATE TYPE edgeops.environment_type AS ENUM (
  'local', 'development', 'staging', 'production'
);

CREATE TYPE edgeops.incident_status AS ENUM (
  'open', 'investigating', 'mitigated', 'resolved', 'closed'
);

CREATE TYPE edgeops.risk_level AS ENUM (
  'read_only', 'low_risk', 'medium_risk', 'high_risk', 'forbidden'
);

CREATE TYPE edgeops.action_status AS ENUM (
  'proposed', 'awaiting_approval', 'approved', 'running',
  'succeeded', 'failed', 'denied', 'expired', 'cancelled'
);

CREATE TABLE edgeops.hosts (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  environment edgeops.environment_type NOT NULL,
  address TEXT NOT NULL,
  platform TEXT NOT NULL,
  agent_status TEXT NOT NULL DEFAULT 'unknown',
  labels JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE edgeops.services (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  host_id UUID REFERENCES edgeops.hosts(id),
  environment edgeops.environment_type NOT NULL,
  service_type TEXT NOT NULL,
  criticality SMALLINT NOT NULL DEFAULT 2,
  health_url TEXT,
  repository_url TEXT,
  deployment_identifier TEXT,
  labels JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (name, environment)
);

CREATE TABLE edgeops.incidents (
  id UUID PRIMARY KEY,
  title TEXT NOT NULL,
  status edgeops.incident_status NOT NULL DEFAULT 'open',
  severity SMALLINT,
  environment edgeops.environment_type,
  summary TEXT,
  started_at TIMESTAMPTZ,
  detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  mitigated_at TIMESTAMPTZ,
  resolved_at TIMESTAMPTZ,
  created_by UUID NOT NULL,
  closed_by UUID
);

CREATE TABLE edgeops.incident_events (
  id UUID PRIMARY KEY,
  incident_id UUID NOT NULL REFERENCES edgeops.incidents(id),
  event_type TEXT NOT NULL,
  occurred_at TIMESTAMPTZ NOT NULL,
  source_type TEXT NOT NULL,
  source_reference TEXT,
  payload JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE edgeops.observations (
  id UUID PRIMARY KEY,
  incident_id UUID REFERENCES edgeops.incidents(id),
  tool_name TEXT NOT NULL,
  target JSONB NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL,
  duration_ms INTEGER,
  status TEXT NOT NULL,
  data JSONB NOT NULL,
  evidence_hash TEXT,
  sensitivity_level TEXT NOT NULL DEFAULT 'internal',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE edgeops.hypotheses (
  id UUID PRIMARY KEY,
  incident_id UUID NOT NULL REFERENCES edgeops.incidents(id),
  statement TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  confidence NUMERIC(4,3) NOT NULL DEFAULT 0,
  reasoning_summary TEXT,
  model_invocation_id UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE edgeops.hypothesis_evidence (
  hypothesis_id UUID NOT NULL REFERENCES edgeops.hypotheses(id),
  observation_id UUID NOT NULL REFERENCES edgeops.observations(id),
  relation TEXT NOT NULL,
  weight NUMERIC(4,3),
  PRIMARY KEY (hypothesis_id, observation_id)
);

CREATE TABLE edgeops.actions (
  id UUID PRIMARY KEY,
  incident_id UUID REFERENCES edgeops.incidents(id),
  action_name TEXT NOT NULL,
  risk_level edgeops.risk_level NOT NULL,
  target JSONB NOT NULL,
  arguments JSONB NOT NULL,
  status edgeops.action_status NOT NULL DEFAULT 'proposed',
  idempotency_key TEXT NOT NULL UNIQUE,
  requested_by UUID NOT NULL,
  policy_decision JSONB NOT NULL DEFAULT '{}',
  verification_plan JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  executed_at TIMESTAMPTZ
);

CREATE TABLE edgeops.action_results (
  id UUID PRIMARY KEY,
  action_id UUID NOT NULL REFERENCES edgeops.actions(id),
  status TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL,
  finished_at TIMESTAMPTZ,
  output JSONB NOT NULL DEFAULT '{}',
  error_code TEXT,
  verification_status TEXT,
  verification_output JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE edgeops.approvals (
  id UUID PRIMARY KEY,
  action_id UUID NOT NULL REFERENCES edgeops.actions(id),
  requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  requested_by UUID NOT NULL,
  decision TEXT NOT NULL DEFAULT 'pending',
  decided_at TIMESTAMPTZ,
  decided_by UUID,
  reason TEXT,
  expires_at TIMESTAMPTZ NOT NULL,
  action_fingerprint TEXT NOT NULL
);

CREATE TABLE edgeops.audit_log (
  id UUID PRIMARY KEY,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  actor_id UUID,
  event_type TEXT NOT NULL,
  resource_type TEXT NOT NULL,
  resource_id UUID,
  correlation_id UUID,
  outcome TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE edgeops.document_chunks (
  id UUID PRIMARY KEY,
  document_id UUID NOT NULL,
  chunk_index INTEGER NOT NULL,
  content TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  embedding VECTOR(768),
  source_type TEXT NOT NULL,
  source_path TEXT,
  title TEXT,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(document_id, chunk_index)
);

CREATE TABLE edgeops.model_invocations (
  id UUID PRIMARY KEY,
  incident_id UUID REFERENCES edgeops.incidents(id),
  tier TEXT NOT NULL,
  provider TEXT NOT NULL,
  model_name TEXT NOT NULL,
  task_type TEXT NOT NULL,
  prompt_hash TEXT NOT NULL,
  input_tokens INTEGER,
  output_tokens INTEGER,
  estimated_cost_usd NUMERIC(12,6),
  latency_ms INTEGER,
  outcome TEXT NOT NULL,
  escalation_reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Add indexes early for:

- `incidents(status, detected_at DESC)`
- `incident_events(incident_id, occurred_at)`
- `observations(incident_id, observed_at)`
- `actions(status, created_at)`
- `audit_log(correlation_id, occurred_at)`
- vector index on `document_chunks.embedding`
- GIN indexes on frequently filtered JSONB metadata

For a first portfolio-quality version, use UUIDs, `TIMESTAMPTZ`, JSONB for evolving adapter outputs, and relational links for important accountability relationships.

---

## 8. Incident reasoning engine

The reasoning engine is an orchestration and evidence model, not a single giant prompt.

### Evidence collection

Begin with an investigation template based on incident type. For a deployment-related API failure:

1. Capture current service/container state.
2. Capture image tag, container start time, restart count, and health status.
3. Retrieve bounded logs around first failure.
4. Check HTTP health.
5. Check host memory/disk and relevant system service status.
6. Retrieve recent Git commits and deployment identifiers.
7. Query relevant database health/connection indicators.
8. Retrieve matching runbooks and past incidents.

Do not collect everything blindly. Every new tool call should answer a question or discriminate between hypotheses.

### Timelines and correlation

Normalize every observation into UTC and store source timestamp, observed timestamp, and any clock-skew warning.

Build a timeline from:

- Deployment start and completion.
- Container creation/restarts.
- Git commit and release times.
- Error-rate changes.
- Health-check failures.
- Database/telemetry anomalies.
- Manual interventions.
- Configuration changes.

Correlation is not causation. The engine must label a relationship as one of:

```text
temporal_association
supporting_evidence
contradicting_evidence
verified_cause
```

### Hypothesis generation

A hypothesis must include:

- A concise causal statement.
- Linked evidence IDs.
- Expected observable consequences.
- Contradicting evidence.
- Suggested discriminating next check.
- Confidence score.
- Status: open, supported, rejected, verified.

Example:

```json
{
  "statement": "The latest control-api image cannot authenticate to PostgreSQL because the deployed database credential configuration is missing.",
  "supporting_evidence_ids": ["obs_11", "obs_15"],
  "contradicting_evidence_ids": [],
  "next_check": "Inspect sanitized application configuration fingerprint and database authentication failures.",
  "confidence": 0.72,
  "status": "supported"
}
```

### Confidence

Do not let an LLM invent confidence alone. Calculate a deterministic base score from:

- Evidence reliability.
- Number of independent supporting sources.
- Presence of direct error signals.
- Temporal alignment.
- Contradicting evidence.
- Whether a discriminating check passed.
- Whether remediation verification confirmed the predicted outcome.

Models may suggest hypothesis relevance; the incident engine calculates and records the final score.

### Avoiding hallucinated causes

- Require evidence IDs in all model-produced hypotheses.
- Reject or flag claims with no linked evidence.
- Separate facts, inferences, and unknowns in the output.
- Tell the model that temporal proximity alone is insufficient.
- Ask for alternative hypotheses, including one non-deployment explanation.
- Require a verification plan before calling a cause “verified.”
- Use “most likely explanation” rather than “root cause” until verification succeeds.
- Preserve model uncertainty rather than forcing a definitive answer.

### Root-cause verification

A root cause becomes verified only when:

1. A direct mechanism is observed or tested.
2. A remediation targeting that mechanism produces the predicted recovery.
3. Verification checks show restored service behavior.
4. No stronger contradictory explanation remains.

If this standard is not met, close with “probable cause” and retain open follow-up work.

---

## 9. Distributed-systems evolution

Do not introduce distributed infrastructure because it sounds production-grade. Add it when concrete workload or reliability needs appear.

| Component | Introduce when | Why |
|---|---|---|
| Redis | You need rate limits, short-lived caching, job coordination, or ephemeral state beyond PostgreSQL. | Fast shared state; not your source of truth. |
| Worker process | Ingestion, embeddings, long log processing, scheduled health checks, or actions exceed API request duration. | Keeps the API responsive and isolates long-running work. |
| NATS or RabbitMQ | Multiple workers/services require reliable asynchronous commands/events. | Decouples producers and consumers; supports backpressure. |
| NATS default | You want a lightweight operations/event bus and simple developer experience. | Good fit for telemetry and operational events. |
| RabbitMQ alternative | You need mature queue semantics and conventional task routing. | A sound choice, but select one—do not deploy both. |
| Caching | Repeated health/status reads, RAG results, expensive summaries become common. | Reduces latency and model/tool load; always use short TTLs for operational state. |
| Distributed locks | Multiple workers can act on the same service/incident. | Prevents conflicting actions and restart storms. |
| Retries | A remote host, API, or message consumer has transient failure modes. | Improves reliability; use bounded retries with jitter. |
| Idempotency | API clients or workers may retry action creation/execution. | Prevents duplicate restarts or duplicate incident actions. |
| API gateway | Multiple independently deployed services or external clients require centralized auth/routing. | Not needed for a modular-monolith MVP. |
| Service separation | Modules have distinct scaling, release cadence, team ownership, or failure isolation needs. | Split only after those boundaries are real. |

Recommended progression:

1. FastAPI + PostgreSQL modular monolith.
2. Add an in-process/background task mechanism only for small work.
3. Add Redis and a worker process for embeddings, ingestion, and scheduled checks.
4. Add NATS when independent workers or remote agent event streams need reliable decoupling.
5. Extract services only after measurable operational pressure.

Use PostgreSQL transactions as the source-of-truth boundary. Use an outbox table later if you need reliable publication of database events to NATS.

---

## 10. Observability

EDGEOPS AI should observe itself as rigorously as it observes other systems.

### Logs

Emit structured JSON logs with:

- Request ID / correlation ID.
- Incident ID.
- User ID or service account ID.
- Tool name and target class, never secrets.
- Policy decision.
- Model tier and model name.
- Duration, status, retry count, and error code.

### Metrics

Prometheus-style metrics:

```text
edgeops_http_requests_total
edgeops_http_request_duration_seconds
edgeops_tool_invocations_total
edgeops_tool_duration_seconds
edgeops_tool_failures_total
edgeops_policy_decisions_total
edgeops_actions_total
edgeops_action_verification_total
edgeops_model_invocations_total
edgeops_model_input_tokens_total
edgeops_model_output_tokens_total
edgeops_model_estimated_cost_usd_total
edgeops_rag_retrieval_duration_seconds
edgeops_rag_retrieved_chunks_total
edgeops_incidents_total
edgeops_incident_time_to_mitigate_seconds
edgeops_incident_time_to_resolve_seconds
```

### Traces

Use OpenTelemetry once the MVP has multiple meaningful internal boundaries:

```text
HTTP request
  → incident orchestration
    → tool invocation
    → RAG retrieval
    → model invocation
    → policy decision
    → action and verification
```

A trace should allow you to answer: “Why did this investigation take 40 seconds and call Astra?”

### Operational dashboards

Prioritize dashboards for:

- API error and latency.
- Tool success/failure and latency by adapter.
- Model use by tier, cost, token count, latency, and escalation reason.
- RAG retrieval quality signals.
- Approval and action outcomes.
- Incidents by service/severity/status.
- Mean time to acknowledge, mitigate, and resolve.
- Failed verification checks and repeated-action loops.

---

## 11. Security

### SSH and remote execution

Do not begin by allowing the API server to SSH arbitrarily into machines.

Preferred evolution:

1. Local-only inspection adapters for development.
2. A narrowly scoped host agent or SSH integration using per-host service accounts.
3. Explicitly allowlisted capabilities, not arbitrary command strings.
4. Mutual authentication, host identity verification, and separate production credentials.

SSH keys should be:

- Stored outside the repository.
- Scoped per environment and host group.
- Passphrase-protected where applicable.
- Rotated.
- Never logged or sent to models.
- Exposed to the runtime through a secrets manager or Docker secrets, not `.env` files committed to Git.

### Secrets

- Use local `.env` only for development and commit only `.env.example`.
- Redact secrets from tool output before storage.
- Store secret references, not secret values, in incident data.
- Add a cloud secret manager when moving to AWS production.
- Maintain a sensitive-data classification for chunks and evidence.

### Service accounts and least privilege

Use separate identities for:

- API server.
- Read-only infrastructure inspector.
- Action executor.
- Database read-only queries.
- Embedding/ingestion worker.
- Production versus non-production environments.

The action executor should have fewer permissions than an administrator and only the capabilities needed by registered action tools.

### Network boundaries

- Keep PostgreSQL private.
- Keep Ollama local/private.
- Restrict host-agent access to a private network, WireGuard, VPC, or security-group-controlled path.
- Do not expose Docker sockets over the network.
- Use TLS for all remote control channels.
- Restrict outbound model-provider access through egress policy where practical.

### Tenant isolation

Not needed for the personal MVP, but design identifiers with future isolation in mind:

- Add `organization_id` to primary domain tables before multi-user deployment.
- Scope every query by organization/environment.
- Use tenant-aware authorization checks in the service layer.
- Never rely solely on a UI filter for tenancy.

---

## 12. Repository structure

```text
EDGEOPS_AI/
├── README.md
├── pyproject.toml
├── docker-compose.yml
├── .env.example
├── alembic.ini
├── docs/
│   ├── architecture.md
│   ├── adr/
│   ├── runbooks/
│   ├── threat-model.md
│   ├── tool-catalog.md
│   └── development-stages.md
├── infra/
│   ├── postgres/
│   ├── prometheus/
│   └── grafana/
├── scripts/
│   ├── bootstrap_dev.ps1
│   ├── ingest_knowledge.py
│   └── verify_environment.py
├── src/
│   └── edgeops/
│       ├── __init__.py
│       ├── main.py
│       ├── api/
│       │   ├── dependencies.py
│       │   ├── routes/
│       │   │   ├── health.py
│       │   │   ├── incidents.py
│       │   │   ├── tools.py
│       │   │   └── approvals.py
│       │   └── schemas/
│       ├── core/
│       │   ├── config.py
│       │   ├── logging.py
│       │   ├── security.py
│       │   ├── errors.py
│       │   └── ids.py
│       ├── db/
│       │   ├── base.py
│       │   ├── session.py
│       │   ├── models/
│       │   ├── repositories/
│       │   └── migrations/
│       ├── domain/
│       │   ├── incidents/
│       │   ├── assets/
│       │   ├── actions/
│       │   └── knowledge/
│       ├── tools/
│       │   ├── registry.py
│       │   ├── contracts.py
│       │   ├── executor.py
│       │   ├── policy.py
│       │   ├── adapters/
│       │   │   ├── host.py
│       │   │   ├── docker.py
│       │   │   ├── git.py
│       │   │   ├── http.py
│       │   │   └── postgres.py
│       │   └── definitions/
│       ├── reasoning/
│       │   ├── incident_engine.py
│       │   ├── timeline.py
│       │   ├── hypotheses.py
│       │   ├── evidence.py
│       │   └── model_router.py
│       ├── knowledge/
│       │   ├── ingestion.py
│       │   ├── chunking.py
│       │   ├── embeddings.py
│       │   ├── retrieval.py
│       │   └── incident_memory.py
│       ├── integrations/
│       │   ├── ollama.py
│       │   ├── git.py
│       │   └── telemetry.py
│       └── workers/
│           └── tasks.py
└── tests/
    ├── unit/
    ├── integration/
    ├── contract/
    └── fixtures/
```

Keep adapters isolated from domain logic. For example, `tools/adapters/docker.py` knows how to inspect Docker, while `reasoning/incident_engine.py` knows why that evidence matters.

---

## 13. Development roadmap

Each stage follows your discipline: explain, implement only that stage, test, verify, review, update documentation, commit, push to `main`, then proceed.

### Stage 0 — Establish the EDGEOPS baseline

Preserve and document the AeroIntel foundation. Decide whether to rename/migrate it or create EDGEOPS AI around reusable modules. Verify PostgreSQL, pgvector, Ollama, embeddings, and semantic retrieval.

### Stage 1 — Typed tool foundation

Build the tool contract, registry, common result envelope, risk enum, tool execution interface, and test fixtures. No real privileged infrastructure operations yet.

### Stage 2 — Read-only local host inspection

Implement safe local machine tools: host health, disk usage, memory use, and basic process/system information. Expose a minimal FastAPI endpoint or CLI. No remote access.

### Stage 3 — Read-only Docker inspection

Add Docker adapters for listing containers, inspecting status, bounded logs, and image/container metadata. Use allowlisted local Docker socket access only.

### Stage 4 — Service and HTTP health model

Add services/hosts database models, service registration, HTTP health checks, and structured observations. Make the system store tool results as evidence.

### Stage 5 — Incident lifecycle and timeline

Implement incidents, incident events, observations, correlation IDs, and a basic timeline endpoint. Start manual incident creation.

### Stage 6 — RAG integration

Port AeroIntel knowledge components. Ingest runbooks, architecture docs, and selected resolved incidents. Return evidence-linked retrieval results.

### Stage 7 — Local evidence summarization

Use qwen3:4b-instruct for constrained log clustering, incident summaries, and classification. Enforce JSON schemas, prompt limits, and model invocation tracking.

### Stage 8 — Deterministic model router

Implement routing rules, budgets, context reduction, redaction, and tier-level observability. Initially support only `NO_LLM` and `LOCAL_LLM`; log when remote escalation would have occurred.

### Stage 9 — Incident hypothesis engine

Add evidence-linked hypotheses, confidence calculation, alternative hypotheses, and a structured investigation brief. Keep recommendations read-only.

### Stage 10 — Controlled remediation

Implement one safe action, such as restarting a local development Docker container. Add policy checks, approval records, idempotency keys, cooldowns, and post-action verification.

### Stage 11 — Remote target support

Add secure, read-only remote host inspection through a constrained SSH or host-agent design. Use separate non-production targets first.

### Stage 12 — Cheap remote model and Astra escalation

Enable opt-in remote model tiers, only with compact redacted evidence packets, budgets, audit records, and explicit escalation criteria.

### Stage 13 — Asynchronous workers and scheduling

Introduce a worker process for document ingestion, embeddings, long-running log processing, periodic checks, and verification jobs. Add Redis only when the worker design needs it.

### Stage 14 — Observability stack

Add OpenTelemetry instrumentation, Prometheus metrics, Grafana dashboards, and operational runbooks for EDGEOPS AI itself.

### Stage 15 — Event bus and distributed operation

Introduce NATS when asynchronous events, remote agents, or multiple workers need reliable decoupling. Add outbox/idempotency patterns.

### Stage 16 — Deployment hardening

Production deployment design: AWS/VPC boundaries, secrets manager, CI/CD, backups, least privilege, image scanning, and security review. Kubernetes remains optional and should follow demonstrated deployment needs—not precede them.

---

## 14. MVP boundary

Do not build these initially:

- Kubernetes support.
- Microservices.
- Generic chat interface with unrestricted questions/tools.
- Arbitrary local or remote shell execution.
- Production mutation capabilities.
- Autonomous remediation.
- Multi-tenant SaaS controls.
- A full SIEM/log platform.
- A full Prometheus replacement.
- Complex agent-to-agent orchestration.
- NATS/RabbitMQ, Redis, distributed locks, or worker fleets before asynchronous workload exists.
- Hosted models or Astra integration before local evidence and routing are trustworthy.
- A frontend dashboard beyond a minimal API, CLI, or simple investigation view.
- Broad cloud-provider integrations.
- Continuous ingestion of unlimited raw logs.

The MVP should prove one complete, safe loop:

> Collect read-only Docker/host/HTTP evidence → create an incident timeline → retrieve relevant knowledge → summarize locally → present evidence-backed findings.

That is portfolio-worthy because it demonstrates backend architecture, AI discipline, observability thinking, safety design, and operational judgment.

---

## 15. First implementation stage

### Stage 1 — Typed tool foundation

Objective:

Create the safe internal tool abstraction that every future inspection and remediation capability will use. This is the platform boundary that prevents the project from becoming an arbitrary-shell chatbot.

Files to add or change:

```text
src/edgeops/tools/contracts.py
src/edgeops/tools/registry.py
src/edgeops/tools/executor.py
src/edgeops/tools/policy.py
src/edgeops/tools/definitions/__init__.py
src/edgeops/core/errors.py
tests/unit/tools/test_registry.py
tests/unit/tools/test_executor.py
tests/unit/tools/test_policy.py
docs/tool-catalog.md
docs/architecture.md
README.md
```

Concepts to understand:

- Pydantic input/output schemas.
- Registry pattern.
- Dependency inversion: domain code depends on a tool interface, not Docker/SSH implementations.
- Risk classification.
- RBAC permission checks.
- Normalized result envelopes.
- Idempotency concepts.
- Why free-form command execution is unsafe and difficult to audit.

Implementation scope:

- Define `RiskLevel`.
- Define a `ToolDefinition` contract.
- Define typed `ToolRequest` and `ToolResult` envelopes.
- Implement a registry that safely registers and resolves tools.
- Implement an executor that validates schema, checks policy, executes a test adapter, and normalizes result/error output.
- Implement a policy engine with `ALLOW_AUTOMATICALLY`, `REQUIRE_APPROVAL`, and `DENY`.
- Add two fake read-only tools for tests, for example `get_demo_host_health` and `get_demo_disk_usage`.
- Do not connect to Docker, SSH, PostgreSQL, FastAPI routes, or models in this stage.

Acceptance criteria:

- A tool cannot run unless it is registered.
- Invalid input is rejected with structured validation errors.
- A registered read-only tool runs and returns the normalized envelope.
- A medium-risk action is classified as requiring approval.
- A forbidden action is denied.
- Tool exceptions become structured, non-secret error responses.
- Every execution yields an auditable event object, even if only in-memory for Stage 1.
- Unit tests pass.
- Documentation explains the tool lifecycle and risk model.

Tests:

- Register and resolve a tool.
- Attempt to resolve an unknown tool.
- Validate good and invalid Pydantic input.
- Execute a successful read-only fake tool.
- Normalize an adapter exception.
- Assert read-only policy allows execution.
- Assert medium/high-risk policy requires approval.
- Assert forbidden policy denies execution.
- Assert unknown fields and invalid targets are rejected.

Expected output:

A small, tested Python foundation where future host, Docker, database, Git, and remediation tools share one strict safety and execution path. At the end of Stage 1, you should be able to explain exactly how a tool is defined, authorized, run, normalized, and audited—before connecting it to any real infrastructure.