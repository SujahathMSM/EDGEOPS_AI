# EDGEOPS AI

AI-assisted operations with typed tools, evidence-backed investigations, and human-approved changes.

**Current implementation: Stage 1 — typed tool foundation.** Two synthetic tools demonstrate validation, permission checks, target restrictions, execution, redaction, normalized results, and correlated audit events. They do not inspect your computer.

## Run locally

Requires Python 3.11+ and Pydantic 2.13+. From this project folder in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m edgeops.demo
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

On Linux/macOS, use `.venv/bin/python` instead of `.\.venv\Scripts\python.exe`.
The installed `edgeops-demo` command also runs the demo.

If Pydantic is already installed, you can run directly from source without installing the package:

```powershell
$env:PYTHONPATH = 'src'
python -m edgeops.demo
python -m unittest discover -s tests -v
```

The demo prints two successful JSON result envelopes and `Audit events: 2`. Disk usage is fixed fixture data: 25,000 used bytes out of 100,000 total bytes. No database, Docker, Ollama, network access, or credentials are needed.

## Stage 1 capabilities

- Strict Pydantic request and adapter schemas reject unknown fields and type coercion.
- Explicit registration rejects duplicate tools, invalid contracts, and incompatible risk metadata.
- Trusted caller identities supply permissions and exact allowed targets, including environment and resource.
- Read-only tools run after authorization and tool-specific target validation.
- Low, medium, and high risk actions return `APPROVAL_REQUIRED`; forbidden actions return `POLICY_DENIED`. There is no approval override or mutation execution path in this stage.
- Cooperative async adapters have bounded timeouts. Exceptions become generic structured errors.
- Results carry UTC timestamps, duration, correlation ID and evidence ID; common secrets are redacted from output.
- Every execution attempt, including validation failures and cancellations, appends an in-memory audit event.

## Project documentation

- [Architecture and lifecycle](docs/architecture.md)
- [Tool catalog and extension guide](docs/tool-catalog.md)
- [Phase tracker and validation record](docs/development-stages.md)
- [Baseline decision](docs/adr/0001-standalone-tool-foundation.md)
- [Original technical blueprint](docs/technical-blueprint.md)

Stage 0 remains partially deferred: this workspace contained no AeroIntel source or configured infrastructure. Existing PostgreSQL/pgvector/Ollama/embedding retrieval has not been verified. Stage 1 intentionally has no dependency on that stack. Stage 2 will add read-only local host inspection after the Stage 1 checkpoint.

## Scope and limitations

This is an internal Python library and fixture demo, not a deployed operations service. Authentication, durable auditing, approval records, idempotent mutations, real adapters, API routes and models belong to later phases. Audit memory disappears when the process exits. Generic redaction is defense in depth; future adapters must produce bounded, sanitized data themselves. See the architecture document for the trusted-code and timeout boundaries.
