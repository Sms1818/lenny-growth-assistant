# Lenny Growth Assistant — Product Requirements Document

## 1. Product Overview
Lenny Growth Assistant is a conversational AI tool designed to provide highly specific, factually grounded answers to product and growth questions. By exclusively referencing Lenny's Newsletter and Podcast corpus, the assistant acts as a tactical advisor that cites its sources and reduces hallucinated advice. The product supports standard chat, layout-specific artifact generation (Markdown/HTML), and a dedicated Ship 30 for 30 essay writing skill.

## 2. Target Users
- **Product Managers & Growth Engineers:** Seeking specific tactical advice, historical case studies, or metric benchmarks.
- **Founders:** Researching go-to-market strategies and retention mechanics without the time to listen to hours of podcast audio.
- **Content Creators:** Using the Ship 30 for 30 skill to distill Lenny's curriculum into atomic essays.

## 3. Problem Statement
The Lenny knowledge base contains hundreds of hours of high-signal audio and long-form prose. Finding a specific case study (e.g., "Duolingo's retention strategy") requires tedious manual searching. While general-purpose LLMs can summarize concepts, they frequently hallucinate precise metrics, invent quotes, and blend outside knowledge, making their answers unreliable for professional engineering contexts. 

## 4. Goals and Success Metrics
Given the context of a take-home demonstration, success is measured by technical robustness and UX reliability rather than measured production business metrics:
- **Grounding Traceability:** Factual answers must include inline citations mapping to surfaced source cards.
- **Session Isolation:** Persistent independent chat sessions tracking messages accurately.
- **Provider Visibility:** Clear visibility into the active model generating the response.
- **Artifact Generation Correctness:** HTML/Markdown/Ship 30 generations should cleanly pass backend structural and security validation.
- **Graceful Degradation:** Predictable handling of expected failure states (e.g., proper error messages when Ollama is offline or retrieval is empty) rather than unhandled exceptions.
- **Reproducible Local Execution:** Successful local startup and execution capability.

## 5. Assumptions
- **Hardware:** The user is running the application on a machine capable of hosting local Ollama models (e.g., an Apple Silicon Mac or equivalent PC).
- **Latency Tolerance:** Users will tolerate a few seconds of latency (without streaming tokens) in exchange for the synchronous validation that increases confidence in factual grounding.
- **Corpus Availability:** The user has access to the raw Markdown files for Lenny's Podcasts and Newsletters to populate the local ingestion pipeline.

## 6. Scope

### In Scope
- Persistent, independent chat sessions backed by PostgreSQL.
- Conversational Q&A grounded in the Lenny corpus with follow-up context awareness.
- Explicit LLM provider selection (Auto, Local, Cloud) per request, with visible model metadata.
- Markdown and HTML artifact generation based on user instructions.
- A dedicated Ship 30 for 30 encoded workflow enforcing word count and structural contracts.
- In-app side panel for safe Artifact viewing, with a new-tab standalone viewing option.
- Hybrid search (semantic + lexical) for robust knowledge retrieval.
- Synchronous backend validation to reject dangerous HTML patterns and hallucinated quotes.

### Out of Scope
- Real-time web browsing or external API retrieval.
- Streaming token output (disabled to allow synchronous post-generation grounding validation).
- Editing or modifying generated artifacts directly within the application.
- Multi-user authentication, accounts, or role-based access control.

## 7. Core User Flows

1. **Grounded Q&A Flow:** The user selects a provider mode and asks a question. The system retrieves relevant corpus chunks, generates a response, validates the facts, and displays the answer with inline citations linked to explicit source cards (showing guest, episode title, timestamp, and URL).
2. **Follow-up Flow:** The user asks a clarifying question. Recent conversation context is injected for generation, and retrieval queries can be expanded with recent turns if context-dependent.
3. **Artifact Generation Flow (Markdown/HTML):** The user commands the generation of a table, brief, or layout. The system opens a side panel rendering the Markdown natively or sandboxing the generated HTML in an iframe.
4. **Ship 30 for 30 Flow:** The user provides a topic. The system retrieves 8 chunks of context and executes a strict writing contract (~1,250 words, H1 hook, clear takeaways). The completed essay opens in the Artifact Viewer.

## 8. Functional Requirements
- **Session Management:** The system must save independent chat histories. Sessions must auto-generate titles based on the first user message.
- **Provider Routing & Fallback:** The user must be able to force local execution (Ollama) or cloud execution (configured cloud provider via Pi Coding Agent). In "Auto" mode, chat attempts local execution first, falling back to the configured cloud provider on failure (if enabled). Auto mode artifact generation routes directly to the configured cloud provider.
- **Source Traceability:** Every generated message must store the exact `source_chunk_ids` used and hydrate them into the UI as clickable/readable references.
- **HTML Isolation:** HTML artifacts must be rendered in an `<iframe sandbox="">` which blocks script execution, same-origin access, forms, and top-level navigation.
- **Security Validation:** The backend must statically analyze HTML outputs and reject predefined patterns (e.g., `<script>`, `\bon...`) before saving them to the database.

## 9. Acceptance Criteria
- **AC1 (Grounding):** When a user asks a question, the assistant must return an answer grounded only in the Lenny corpus with inline citations. If the model hallucinates a quote, the backend must auto-correct or reject it.
- **AC2 (Empty Retrieval):** When retrieval yields zero relevant chunks, the system must explicitly refuse to answer using a fixed string, and no generation is attempted.
- **AC3 (Ship 30 Contract):** When a Ship 30 essay is generated, it targets approximately 1,250 words; the backend validator enforces bounds between 1,000 and 1,500 words, an H1 tag, and citations. If it fails these checks, the system must return a `422` error.
- **AC4 (Provider Visibility):** The UI must always display the provider mode toggle, and the chat feed must display the exact model provider and name that fulfilled each request.
- **AC5 (Artifact UI):** Generating an artifact must open it in a side panel without navigating the user away from their current chat context.

## 10. Failure States and Resilience
- **Empty Retrieval:** No generation is attempted; fixed refusal returned.
- **Unavailable Local Provider:** If Ollama is down (502/503), the UI displays a clear "Disconnected" state or inline error banner.
- **Missing Cloud Credentials:** If Cloud mode is requested without a configured cloud API key, a `503` error (`cloud_provider_unavailable`) is returned before generation begins.
- **Artifact Validation Failure:** If the LLM generates forbidden HTML or violates Ship 30 bounds after correction attempts, a `422` error (`artifact_generation_failed`) surfaces in the UI.
- **Database/API Failures:** Explicit exception handlers catch database errors and return `503` errors.
- **Timeouts:** Long-running generations (with configurable defaults of 120s for chat, 300s for artifacts) are caught and surfaced as `504` errors rather than hanging indefinitely.

## 11. Risks and Trade-offs
- **Grounding False Positives:** The rigid deterministic grounding checks (quotes and acronyms) may occasionally reject factually accurate answers if the LLM paraphrases poorly. *Trade-off: Factual reliability prioritized over generation speed.*
- **No Streaming:** Synchronous backend validation requires the full response before returning a byte to the frontend. *Trade-off: Higher time-to-first-byte mitigated by a live UI elapsed-time counter.*
- **Local Capability Limits:** The local `llama3.2:3b` model is fast but struggles with complex 1,500-word formatting constraints. *Trade-off: Auto mode bypasses local execution for artifact generation to leverage cloud models.*
- **HTML Isolation Limits:** While the backend blocks `<script>` tags and the iframe `sandbox=""` locks down the DOM, the system cannot natively prevent passive external resource loading (e.g., tracking pixels via `<img>`). Furthermore, opening an artifact in a new tab bypasses the iframe sandbox, relying entirely on the backend's pattern-blocking for security.

## 12. Implementation Plan (Executed)
- **Phase 1: Knowledge Pipeline:** Built the parser, chunker (1,200 chars for podcasts, 1,500 for newsletters), `pgvector` schema, and hybrid RRF retrieval script.
- **Phase 2: Core Chat & Grounding:** Implemented FastAPI routes, Ollama integration, context injection, and the deterministic `GroundingValidator`.
- **Phase 3: Skills & Artifacts:** Added Ship 30 structure validation, HTML security pattern checks, and the Pi Coding Agent integration for Cloud generation.
- **Phase 4: Frontend Application:** Built the React/Vite UI, integrating the session sidebar, Provider toggle, Source cards, and the sandboxed Artifact Viewer.

## 13. Future Improvements
- **Streaming with Speculative UI:** Stream tokens immediately, but visually redact or flag hallucinated quotes retroactively once the final string is validated.
- **In-App Artifact Editing:** Provide a rich-text editor for generated Markdown so users can polish Ship 30 essays directly in the app.
- **Dedicated Vector DB:** Explore alternative specialized vector stores if the user wishes to index tens of thousands of external documents, requiring out-of-the-box sparse/dense search tuning.
- **Expanded Skill Registry:** Allow users to define custom writing templates (e.g., "PRD format", "Executive Summary") alongside the dedicated Ship 30 encoded workflow.
