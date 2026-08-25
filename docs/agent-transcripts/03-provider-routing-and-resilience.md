# 03 — Provider Routing and Resilience

This record documents how the Lenny Growth Assistant evolved from a single-model execution path into explicit Local, Cloud, and Auto provider modes, along with the failure handling required to make those modes predictable.

## 1. Why Provider Routing Was Needed

The assignment required the evaluator to be able to switch the underlying model without changing application code.

The system also had two different generation workloads:

- conversational answers, which are relatively short;
- artifacts and Ship 30 essays, which require longer and more structured output.

Treating every request identically would either make local execution unnecessarily expensive or make complex artifact generation unreliable.

Provider selection was therefore moved behind a dedicated routing layer instead of being embedded directly inside individual API routes.

## 2. Provider Plans

`provider.py` defines a `ProviderPlan` describing:

- selected mode;
- provider;
- model;
- whether execution starts locally;
- whether cloud fallback is allowed;
- and optional output-token limits.

The supported user-facing modes are:

- `auto`
- `local`
- `cloud`

The routing decision also receives a generation purpose:

- `chat`
- `artifact`

This allows provider behavior to differ by workload without changing the higher-level product workflows.

## 3. Local Mode

Local mode explicitly prevents cloud fallback.

For chat, the configured local conversational model is used:

`llama3.2:3b`

For artifact generation, the configured local artifact model is used:

`qwen3:4b-instruct`

This makes Local mode useful for the mandatory Ollama demonstration because selecting Local guarantees that generation remains on the local provider.

A failure in explicit Local mode is surfaced to the user instead of silently sending the request to a cloud provider.

## 4. Cloud Mode

Cloud mode routes directly to the configured cloud provider and model.

The current configuration uses OpenAI through Pi Coding Agent.

Before cloud execution begins, the application checks whether the required cloud configuration is available.

For the configured OpenAI provider, a missing `OPENAI_API_KEY` raises `CloudProviderUnavailableError` rather than starting a generation process that cannot succeed.

This provides a predictable failure before model execution begins.

## 5. Auto Chat Routing

Auto mode for normal chat is local-first.

The initial request uses the configured Ollama chat model.

If local execution fails and cloud fallback is enabled, the same generation operation is retried using the configured cloud provider.

The routing test suite verifies this behavior by forcing the first execution attempt to time out and confirming that a second provider attempt occurs.

Cloud fallback is controlled by configuration rather than being unconditional.

## 6. Auto Artifact Routing

Artifact generation uses a deliberately different Auto policy.

In Auto mode, artifacts route directly to the configured cloud provider rather than attempting the local model first.

This decision reflects the different workload characteristics of long-form Markdown, HTML, and Ship 30 generation.

Explicit Local mode remains available for artifact generation and uses the configured local artifact model, so local artifact capability is still supported and can be demonstrated independently.

The provider-routing tests verify that:

- Auto artifact mode selects the cloud provider directly;
- Local artifact mode disables cloud fallback;
- Cloud artifact mode calls the cloud provider directly.

## 7. Timeout Behavior

Model generation is bounded by configurable timeouts.

The configuration distinguishes between chat and artifact generation so longer artifact workflows can receive a larger execution window.

Timeout behavior also respects provider mode.

For example, the routing tests verify that a Local artifact timeout returns:

`504`

with the structured error code:

`artifact_generation_timeout`

and does not fall back to cloud.

For Auto chat, a local timeout can trigger the configured cloud fallback path.

This distinction is important because an explicit Local selection should remain local even when that provider fails.

## 8. Database Connection Handling During Generation

LLM inference can take substantially longer than normal database operations.

Holding an active database transaction while waiting for local or cloud generation would unnecessarily occupy a connection from the SQLAlchemy pool.

Before long-running generation begins, relevant request flows end the current read transaction using:

`await db.rollback()`

The generated result is persisted afterward using a fresh transaction.

This reduces the amount of time database connections are held across model inference.

## 9. Empty Retrieval

Generation is not attempted when retrieval returns no usable source chunks for a grounded chat answer.

Instead, the assistant returns a controlled response indicating that it could not find enough relevant information in the Lenny knowledge base.

The resilience test verifies that this path returns:

- no sources;
- no grounding issues;
- and the expected graceful answer.

Artifact workflows use their own structured insufficient-source failure behavior rather than attempting unsupported generation.

## 10. Embedding Failure Handling

The embedding service is a dependency of retrieval, so its failure modes are surfaced separately.

If the local embedding service is unavailable, the application maps the failure to:

`503 Service Unavailable`

with:

`embedding_unavailable`

If the embedding service responds but fails while processing the request, the application maps the failure to:

`502 Bad Gateway`

with:

`embedding_failed`

This distinction helps separate dependency availability problems from dependency execution failures.

## 11. Database Failure Handling

SQLAlchemy failures are handled centrally.

A database failure is mapped to:

`503 Service Unavailable`

with the structured code:

`database_unavailable`

The resilience test also verifies that the raw database exception message is not returned to the client.

This prevents internal database details from leaking through API responses while still giving the frontend a stable error contract.

## 12. Provider Visibility

Provider selection is visible to the user through the UI.

Generation results also retain the actual provider and model metadata returned by the generation layer.

This makes it possible to distinguish, for example, a request fulfilled by local Ollama from one fulfilled by the configured cloud model.

This is especially useful when Auto mode performs fallback because the user can see which provider ultimately produced the result.

## 13. Structured Logging

The application includes structured logging around important execution stages.

Events provide visibility into areas such as:

- generation start;
- retrieval completion;
- provider failures;
- fallback decisions;
- grounding retries;
- and other request lifecycle events.

The goal is lightweight operational visibility from application logs without requiring an external tracing platform for the take-home environment.

## 14. Verification

Provider behavior is covered by automated tests.

The routing tests verify:

- Auto artifacts route directly to cloud;
- Local artifacts disable cloud fallback;
- Cloud chat uses the configured cloud model;
- missing cloud credentials are detected;
- Local artifact timeouts do not fall back;
- Auto chat failures can trigger cloud fallback;
- and explicit Cloud mode calls cloud directly.

The resilience tests verify:

- graceful empty-retrieval behavior;
- embedding-unavailable handling;
- embedding-service failure handling;
- and sanitized database failure responses.

These tests made provider behavior an application contract rather than relying only on manual model testing.

## 15. Result

At the end of this phase, the application had:

- explicit Auto, Local, and Cloud modes;
- purpose-aware routing for chat and artifacts;
- mandatory local Ollama support;
- explicit local artifact generation;
- configurable cloud fallback for Auto chat;
- cloud pre-flight validation;
- bounded generation timeouts;
- structured dependency errors;
- database connection relief during long inference;
- provider/model visibility;
- structured operational logs;
- and automated tests covering routing and resilience behavior.

The main design principle from this phase was that provider selection should be predictable. Explicit Local and Cloud modes honor the user's choice, while Auto mode is free to apply workload-specific routing and configured fallback behavior.
