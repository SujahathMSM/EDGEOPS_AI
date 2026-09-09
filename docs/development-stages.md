# Development stages

Follow the blueprint's phase boundary: explain, implement one stage, test, verify, review, document, commit, publish, then proceed.

| Stage | Deliverable | Status |
| --- | --- | --- |
| 0 | Establish baseline; inspect/reuse AeroIntel; verify local retrieval stack | Workspace assessed; infrastructure portion deferred |
| 1 | Typed contracts, registry, executor, policy and fake tools | Implemented and locally verified |
| 2 | Read-only local host health, disk, memory and system info | Next |
| 3 | Read-only Docker status and bounded logs | Planned |
| 4 | Service/host registration, HTTP health and persistent evidence | Planned |
| 5 | Incident lifecycle and timeline | Planned |
| 6 | AeroIntel RAG integration and evidence-linked retrieval | Planned |
| 7 | Constrained local evidence summaries and model-call tracking | Planned |
| 8 | Deterministic router, budgets, reduction and tier visibility | Planned |
| 9 | Evidence-linked hypotheses and deterministic confidence | Planned |
| 10 | One approved local development remediation with verification | Planned |
| 11 | Constrained read-only remote targets | Planned |
| 12 | Opt-in cheap remote and Astra reasoning | Planned |
| 13 | Workers and scheduling; Redis only if needed | Planned |
| 14 | OpenTelemetry, Prometheus, Grafana and runbooks | Planned |
| 15 | NATS and outbox patterns when justified | Planned |
| 16 | Production deployment hardening | Planned |

## Stage 1 acceptance record

Verified on 2026-09-08 with Python 3.11.15 and Pydantic 2.13.4 on Windows.

- 27 unittest tests pass, including subcases for all risk levels and malformed requests.
- Both demo tools return successful normalized results, with two correlated audit events.
- Unknown tools, unknown input fields, malformed targets and target-scope violations fail closed.
- Mutable and forbidden adapters never execute in the tests.
- Exceptions and validation errors do not echo secret values; invalid-output serialization warnings are suppressed before revalidation to prevent value leakage.
- Timeouts clean up cooperative adapters; cancellation propagates after audit.
- Redaction handles nested values, while audit records exclude raw arguments and output.
- Review covered the trusted-adapter boundary, missing authentication and durable audit, and cooperative timeout limitations; these are recorded in architecture documentation.

Run from source in PowerShell:

```powershell
$env:PYTHONPATH = 'src'
python -m unittest discover -s tests -v
python -m edgeops.demo
```

Stage 1 publication is pending a Git remote destination. Stage 2 has not been implemented; the blueprint requires the phase publication checkpoint before proceeding.
