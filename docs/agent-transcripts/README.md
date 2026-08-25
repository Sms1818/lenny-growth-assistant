# Agent Development Records

This directory contains curated development records from the coding-agent-assisted implementation of the Lenny Growth Assistant.

The assignment asks for agent transcripts/logs, including failed attempts and how they were corrected. Rather than presenting an artificial clean-room development history, these records preserve the important implementation decisions, debugging events, regressions, corrections, and verification steps that shaped the final system.

Secrets, credentials, machine-specific sensitive values, and irrelevant conversational material are intentionally excluded.

## Records

### [01 — Foundation and Local LLM](./01-foundation-and-local-llm.md)

Covers the initial environment, FastAPI and PostgreSQL foundation, pgvector, Ollama, local embeddings, Pi Coding Agent integration, Docker setup, and early infrastructure verification.

### [02 — RAG and Grounding](./02-rag-and-grounding.md)

Covers transcript ingestion, semantic and lexical retrieval, Reciprocal Rank Fusion, metadata reranking, conversational retrieval behavior, grounding controls, source traceability, and the retrieval-contamination regression.

### [03 — Provider Routing and Resilience](./03-provider-routing-and-resilience.md)

Covers Local, Cloud, and Auto provider modes, purpose-aware model routing, fallback behavior, timeouts, missing-provider handling, database failure handling, structured errors, and operational logging.

### [04 — Artifacts and Ship 30](./04-artifacts-and-ship30.md)

Covers Markdown and HTML artifact generation, Artifact Viewer behavior, HTML isolation, standalone viewing, the dedicated Ship 30 workflow, retrieval scoping, structural validation, and the refinement regression that was later reverted.

### [05 — Failures and Corrections](./05-failures-and-corrections.md)

A focused debugging record of representative failures, first fixes, regressions, final corrections, verification steps, and the engineering lessons that resulted from them.

## What These Records Demonstrate

Across the five records, the development history includes examples of:

- validating infrastructure before application integration;
- evolving semantic retrieval into hybrid retrieval;
- debugging retrieval independently from generation;
- discovering conversation-history contamination;
- introducing a fix that caused a regression;
- adding regression coverage before finalizing the correction;
- testing provider and resilience behavior;
- discovering that a grounding refinement degraded real Ship 30 output;
- reverting a technically reasonable change after end-to-end testing showed worse product behavior;
- and using both automated tests and representative real-model runs.

These files are intended to make the implementation process inspectable without requiring the evaluator to reconstruct it from source-code diffs alone.

## Verification

The repository's current automated test run is the authoritative source for the final test count.

See the root [`README.md`](../../README.md) for setup, execution, testing, troubleshooting, and demo instructions.
