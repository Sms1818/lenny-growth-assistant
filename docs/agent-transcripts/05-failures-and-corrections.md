# 05 — Failures and Corrections

This document records representative engineering failures encountered while building the Lenny Growth Assistant.

The purpose is not to present a perfect development path. It captures cases where an implementation behaved incorrectly, a first fix caused a regression, or testing exposed a mismatch between the intended product behavior and the actual system.

---

## 1. Existing PostgreSQL Instance Conflicted With the Project Database

### Problem

During local infrastructure setup, PostgreSQL was already running on the development machine.

The project also needed PostgreSQL with the `pgvector` extension for conversation persistence and knowledge embeddings.

Using the same host port would have caused the Dockerized database to conflict with the existing PostgreSQL installation.

### Correction

The Dockerized `pgvector/pgvector:pg16` database was configured to use a separate host port.

The backend database configuration was then pointed at that Dockerized instance.

### Lesson

Development environments should not assume ownership of common host ports. A reproducible setup should coexist with services already installed on the developer or evaluator machine whenever possible.

---

## 2. Semantic Retrieval Alone Was Not Precise Enough

### Problem

The initial retrieval approach relied primarily on semantic similarity using `nomic-embed-text`.

Testing showed that semantic similarity alone was less reliable for exact company names, guest names, acronyms, and distinctive episode terminology.

### Correction

The retrieval pipeline was expanded into hybrid search combining:

- semantic vector similarity;
- PostgreSQL lexical full-text search;
- Reciprocal Rank Fusion;
- metadata-aware reranking.

The semantic and lexical candidate sets are combined using:

`RRF_K = 60`

### Lesson

Embedding similarity is useful, but exact lexical and entity signals remain important when users ask about specific companies, people, metrics, or case studies.

---

## 3. Conversation History Contaminated Ship 30 Retrieval

### Problem

A real product test exposed a retrieval-scoping bug.

The conversation had previously discussed Anthropic. The user then issued a new, self-contained Ship 30 request about how Duolingo reignited growth.

The resulting artifact retrieval included unrelated Anthropic context.

### Root Cause

Artifact and Ship 30 retrieval queries automatically incorporated recent user conversation history.

That behavior is useful for requests such as:

`Turn the Duolingo discussion into an essay.`

However, it is harmful when the current request already contains a complete topic.

In the self-contained Duolingo request, previous Anthropic turns added irrelevant terms to the retrieval query and contaminated the evidence set.

### First Correction Attempt

The first fix removed conversation-history contribution from artifact and Ship 30 retrieval.

This solved the contamination problem for explicit topics.

However, it introduced a regression.

The following test failed:

`test_ship30_uses_source_chunks_directly`

The test expected the retrieval query to contain:

`Tell me about Duolingo growth.`

for the contextual instruction:

`Turn the Duolingo discussion into an essay.`

Instead, retrieval received only the current instruction.

### Final Correction

The retrieval logic was changed to distinguish self-contained requests from requests that genuinely depend on conversation context.

`build_retrieval_query()` retained its bounded-history behavior.

Artifact and Ship 30 workflows now decide whether that history should participate using conversation-reference detection.

This preserves contextual requests while preventing unrelated previous topics from contaminating explicit new requests.

### Verification

The focused conversation and Ship 30 tests passed:

`22 passed`

The complete backend suite then passed:

`60 passed`

A further regression test was added specifically to ensure that a self-contained Duolingo Ship 30 request does not inherit earlier Anthropic context.

After that addition:

`5 passed`

for the Ship 30 tests, followed by:

`61 passed`

for the complete backend suite at that stage.

### Lesson

Conversation history should not automatically become retrieval history.

The system needs to distinguish conversational references from explicit new tasks.


---

## 4. Fixing Retrieval Too Aggressively Broke Contextual Requests

### Problem

The first response to the retrieval contamination bug was to stop using conversation history for artifact retrieval.

That fixed self-contained requests while breaking a valid contextual use case.

### Evidence

The regression appeared in:

`tests/test_ship30.py::test_ship30_uses_source_chunks_directly`

The test expected:

`Tell me about Duolingo growth.`

to participate in retrieval for:

`Turn the Duolingo discussion into an essay.`

Instead, the retrieval query contained only the current instruction.

### Root Cause

The implementation treated every artifact request as independent.

However, some artifact instructions explicitly refer to earlier conversation context.

### Correction

Conversation-reference detection was improved.

History inclusion became conditional rather than globally enabled or disabled.

The resulting behavior was checked with examples:

`True - Turn the Duolingo discussion into an essay.`

`True - Turn the discussion into an essay.`

`True - Turn that into an essay.`

`False - Create a Ship 30 essay about how Duolingo reignited user growth.`

### Lesson

The correct abstraction was not simply "history" versus "no history."

It was conditional history based on whether the current request depends on previous turns.

---

## 5. Ship 30 Grounding Refinement Passed Tests but Broke Real Generation

### Problem

A grounding refinement pass was added to the Ship 30 workflow.

The goal was to improve factual reliability by running the generated essay through another model pass using the retrieved evidence.

Automated tests passed after adapting them to the new two-call workflow.

However, real product testing exposed a regression.

### Evidence

A real Ship 30 generation returned:

`The generated Ship 30 essay did not meet grounding or structure requirements.`

The reported structure issues included:

`essay_too_short:755`

and:

`missing_h1`

Instead of improving the usable initial essay, the refinement stage changed the output enough to violate the Ship 30 structural contract.

### Why the Tests Missed It

The unit tests used fake agent responses to verify control flow.

After introducing refinement, an existing assertion expecting one model call failed because the workflow now made two calls.

The test was updated to verify the initial generation and refinement calls.

That correctly tested the new control flow, but the fake model responses did not reproduce the degradation caused by a real model rewriting a long-form essay.

### Correction

The problematic refinement behavior was reverted rather than weakening the Ship 30 structural requirements.

The previously working generation path was restored.

Structural validation remained responsible for enforcing the Ship 30 contract.

### Verification

After reverting the refinement behavior, the application again successfully generated the demonstrated Duolingo Ship 30 artifact.

The resulting artifact had:

- an H1 headline;
- a clear narrative structure;
- inline source citations;
- retrieved Duolingo sources;
- and successful rendering through the Artifact Viewer.

### Lesson

Generative workflows cannot be evaluated only through mocked unit tests.

Mocks verify application control flow, while representative real-model runs are also necessary to validate output behavior.

---

## 6. Long-Form Generation Exposed Model Capability Differences

### Problem

The local Ollama path worked for grounded conversational questions, but long-form structured generation proved more demanding.

The Ship 30 workflow combines several requirements:

- approximately 1,250 words;
- a strong hook;
- narrative progression;
- skimmable formatting;
- an H1 headline;
- a concrete takeaway;
- citations;
- and grounded factual claims.

Testing showed that satisfying all of these constraints consistently is harder for smaller local models than normal conversational generation.

### Correction

Provider routing was made purpose-aware rather than assuming that every generation task should use the same model strategy.

The application supports explicit Local and Cloud modes, while Auto mode can choose the configured strategy appropriate for the generation purpose.

The provider abstraction keeps product workflows independent from the underlying model while still allowing task complexity to influence routing.

### Lesson

A common provider interface does not mean every model has identical capabilities.

Model routing should preserve the product contract rather than assuming one model is optimal for every workload.

---

## 7. Tests Were Expanded Around Real Failures

The failures above directly influenced the automated test coverage.

Tests were added or expanded around:

- bounded conversation history;
- conversational retrieval queries;
- self-contained versus context-dependent Ship 30 requests;
- retrieval isolation;
- provider-mode routing;
- artifact generation;
- Ship 30 structural validation;
- session history;
- grounding behavior;
- and resilience paths.

At the end of the retrieval and Ship 30 regression work described above, the complete backend suite reported:

`61 passed`

The repository's current test run remains the authoritative result because additional tests may be added after this record was written.

---

## Final Engineering Takeaways

### Retrieval context and conversation context are different concerns

Conversation history can improve understanding of a follow-up request, but indiscriminately adding history to retrieval can reduce evidence quality.

### Fixes need regression coverage

The first retrieval fix solved one bug while breaking another valid workflow. The regression test made that architectural distinction explicit.

### Deterministic constraints still require model-aware workflows

Structural and grounding validators enforce useful boundaries, but additional model passes can themselves alter otherwise valid output.

### Unit tests and real-model tests serve different purposes

Mocked responses are useful for verifying application logic.

Representative end-to-end generations are necessary for verifying actual model behavior.

### Provider abstraction should preserve flexibility

Local and cloud models can share the same application interface while still being selected differently according to task requirements.

### Failed attempts are useful engineering evidence

The retrieval-history regression and Ship 30 refinement regression both resulted in clearer system boundaries and stronger regression coverage.
