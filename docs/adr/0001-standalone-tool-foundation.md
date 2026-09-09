# ADR 0001: Start with a standalone typed tool package

Date: 2026-09-08

Status: Accepted for Stage 1

## Context

The supplied blueprint references an existing AeroIntel foundation with PostgreSQL, pgvector, 768-dimensional embeddinggemma vectors and local Ollama. The selected EDGEOPS_AI folder was empty and had no Git repository or remote. No AeroIntel source, database connection or model endpoint was supplied here.

## Decision

Preserve the blueprint in documentation and create a standalone `src/edgeops` Python package for Stage 1. Do not infer infrastructure credentials, alter external AeroIntel files, or claim retrieval verification. Stage 1 uses Pydantic and Python's standard-library unittest runner; fake adapters let the complete tool boundary be tested independently.

## Consequences

Stage 1 can be implemented now. Stage 0 infrastructure verification remains deferred until the existing source and connection details are available. Later RAG work must inspect and reuse the AeroIntel components before proposing a migration. This decision does not create a second database or replace existing data.

Git publication requires a user-provided repository destination. The phase publication checkpoint cannot be completed without one; do not invent a remote URL.
