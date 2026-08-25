# Lenny Growth Assistant Product & Engineering Design

This document details the product design, user experience flows, UX trade-offs, and security posture for the Lenny Growth Assistant. It complements the `README.md` and `architecture.md` files by focusing on *what* was built, *why* it was built that way, and *how* the user experiences it.

---

## 1. Product Goal

**The Problem:** Product managers, growth engineers, and founders need quick, factual answers to growth questions. Lenny's Newsletter and Podcast contain hundreds of hours of high-signal advice, but searching and synthesizing that material manually is slow. Generic AI assistants hallucinate facts or give shallow advice when discussing specific historical case studies (e.g., "How did Duolingo reignite growth?"). 

**The Solution:** Lenny Growth Assistant is a conversational AI and content generator that uses Lenny's Podcast and Newsletter corpus as its factual evidence source. It prioritizes grounded, source-traceable output over unrestricted generation.

**Why Grounding Matters:** In professional growth engineering, a hallucinated metric or incorrectly attributed strategy is worse than no answer at all. The system is designed to keep factual claims grounded in retrieved podcast or newsletter sources.

---

## 2. Core User Experience

The application is a chat-first interface with specialized workflows for document generation.

- **Sessions:** Users manage independent chat sessions via a left-hand sidebar. Sessions are automatically titled based on the first message and maintain isolated conversation histories.
- **Provider Selection:** A toggle in the top navigation lets users explicitly choose the generation engine per request: Auto (local chat, cloud artifacts), Local (Ollama only), or Cloud (OpenAI only).
- **Grounded Q&A:** Users ask questions in the chat composer. The assistant answers with numbered inline citations (e.g., `[1]`) corresponding to source cards shown with the response.
- **Source Inspection:** Below the assistant's message, a "Sources" list displays the specific retrieved chunks, exposing the guest name, episode/newsletter title, URL, and exact YouTube timestamp.
- **Contextual Follow-ups:** Users can ask follow-up questions (e.g., "Expand on point 2") and the system injects the recent conversation history to resolve pronouns and context.
- **Artifact Generation:** Users can command the assistant to generate long-form Markdown documents, interactive HTML layouts, or specialized Ship 30 for 30 essays.
- **Artifact Viewer:** Generated documents open in a dedicated right-hand side panel, allowing the user to read the artifact while keeping the chat context visible.
- **Standalone Viewing:** A button in the viewer opens the generated artifact in a new browser tab for full-screen reading.

---

## 3. Major Product Flows

### Grounded Q&A Flow
1. The user types a question and submits it via the chat composer.
2. A progress banner appears, indicating the model is thinking (with a live elapsed-time counter).
3. The system returns the validated answer. If the retrieved knowledge lacked the answer, the system responds: *"I couldn't find enough relevant information in the Lenny knowledge base to answer that."*

### Follow-up Flow
1. The user asks a follow-up question.
2. The backend retrieves the last 6 messages and includes them in the generation prompt.
3. The LLM uses the history to generate a contextually accurate response.

### Ship 30 for 30 Generation Flow
1. The user requests a Ship 30 essay on a specific topic (e.g., "Create Ship 30 for 30 essay: Duolingo retention").
2. The backend invokes a specialized skill with a hardcoded writing contract (1,000–1,500 words, compelling hook, H1 headline, concrete takeaway).
3. The backend programmatically validates the length and structure. If it fails, an inline error banner informs the user (`422 Unprocessable Entity`).
4. On success, the Artifact Viewer opens displaying the rendered Markdown essay.

### General Artifact Flow (Markdown & HTML)
1. The user requests an artifact (e.g., "Create html artifact: A pricing tier comparison table").
2. The backend generates the layout using the retrieved knowledge.
3. For HTML, the backend statically analyzes the output and rejects it if forbidden executable patterns are found.
4. The artifact panel slides in. Markdown is rendered natively; HTML is rendered inside a secure `<iframe>`.

---

## 4. UX Decisions

- **Chat-First Interface:** Leverages the familiar ChatGPT paradigm, making it intuitive for users to explore the knowledge base conversationally.
- **Visible Provider Metadata:** Exposing the provider mode (and logging the exact model used on each message) is crucial for evaluators and developers to understand latency and quality differences between local (`llama3.2:3b`) and cloud (`gpt-5.4-mini`) execution.
- **Side Panel for Artifacts:** Instead of dumping 1,500 words of an essay or a raw HTML layout into the chat feed—which destroys vertical scrolling context—artifacts are rendered in a side panel. This allows side-by-side comparison with the conversation that prompted them.
- **No Streaming Response:** Because the backend must run synchronous, deterministic grounding checks (and potential auto-corrections) on the *complete* LLM output before deciding if it is safe to show, token streaming is disabled. To mitigate the UX impact of higher time-to-first-byte, a live elapsed-time counter provides continuous feedback.

---

## 5. Artifact Design: General vs. Ship 30

The system implements two distinct generation paradigms:

1. **General Artifacts (Markdown / HTML):** 
   Flexible, user-instructed generation. The user dictates the format (e.g., "Make a table," "Write a bulleted list") and the LLM fulfills the layout request using grounded facts.
2. **Ship 30 for 30 Skill:**  

   A specialized, opinionated workflow where the user's topic or instruction is combined with an encoded Ship 30 writing contract. The skill targets approximately 1,250 words and requires a strong hook, narrative progression, skimmable formatting, selective emphasis, a concrete takeaway, citations, and source-grounded factual claims.

   Unlike general artifact generation, Ship 30 applies its own retrieval depth and structural validation before the artifact is persisted. This demonstrates how the system can enforce a domain-specific content workflow rather than treating every request as generic text generation.

---

## 6. HTML Artifact Security UX

Allowing an LLM to generate arbitrary HTML and rendering it in the user's browser introduces significant Cross-Site Scripting (XSS) risks. The UX safely isolates this untrusted content.

**1. Backend Pattern Rejection**
Before an HTML artifact is ever persisted to the database, the backend scans it for known dangerous patterns (`<script\b`, `\bon...`, `javascript:`, `<iframe`, `<object`, `<embed`). If matched, the artifact is rejected.

**2. In-App Iframe Sandbox**
When viewed in the side panel, HTML artifacts are injected into an `<iframe sandbox="">`. The empty sandbox string is the most restrictive setting possible. It explicitly blocks:
- Script execution
- Same-origin access
- Form submission
- Popups
- Top-level navigation
*(Note: `sandbox=""` does not natively block the fetching of passive external resources such as `<img>` tags. Backend validation rejects known dangerous executable constructs, but it should not be treated as a complete network-isolation boundary).*

**3. New-Tab Standalone Viewing**
When the user clicks "Open in new tab", the frontend generates a transient `Blob` URL.
- `window.open` is called with `noopener,noreferrer` to sever the `window.opener` relationship, ensuring the opened document cannot manipulate the main application's DOM.
- **Crucial Security Distinction:** The iframe `sandbox=""` restrictions **do not apply** to the new tab. The new tab acts as a standard web page. Therefore, the security of the new-tab view relies entirely on the backend's pattern-based validation having successfully rejected executable scripts prior to storage.

---

## 7. Failure and Empty States

The UI is designed to handle failure gracefully without crashing the chat feed:

- **No Knowledge Retrieved:** Fixed, polite refusal message. No hallucinated LLM generation is attempted.
- **Grounding Failure:** If an answer cannot be automatically corrected to remove hallucinated quotes or acronyms, the backend substitutes a fixed refusal message indicating the LLM could not formulate a properly grounded response.
- **Artifact Validation Failure (`422`):** Displays a red inline banner indicating the artifact failed structural or grounding requirements.
- **Unavailable Local / Cloud Provider (`503` / `502`):** Triggers a "Disconnected" state or an explicit inline error (e.g., "Cloud provider unavailable - API key missing").
- **Timeouts (`504`):** Gracefully caught and surfaced as a timeout banner in the chat feed.

---

## 8. Design Trade-offs

1. **Grounding Quality vs. Latency:** 
   *Decision:* Withhold the response until deterministic grounding validation is complete. 
   *Consequence:* Slower response times (no streaming), and reduces the risk of displaying unsupported quotes or acronym expansions.
2. **Local Privacy vs. Model Quality:** 
   *Decision:* Default to Local chat, but route Artifacts to the Cloud. 
   *Consequence:* Fast, private, free conversational answers, but relies on a paid cloud provider to achieve the reasoning capabilities required for complex 1,500-word Ship 30 essays.
3. **Strict Validation vs. Creative Flexibility:** 
   *Decision:* The Ship 30 validator strictly enforces word counts and citations. 
   *Consequence:* Valid essays might occasionally be rejected (`422`) if the LLM writes 950 words instead of 1,000, prioritizing rigorous compliance over user leniency.
4. **Explicit Provider Visibility vs. Abstraction:** 
   *Decision:* The UI explicitly shows the Provider toggle and logs the model name per message. 
   *Consequence:* Slightly higher cognitive load for the user, but vastly superior observability for engineers evaluating the system's fallback routing.

---

## 9. Accessibility Considerations

The frontend uses native and semantic browser controls where possible so core interactions remain keyboard-accessible without custom interaction models.

Implemented accessibility details include:

- Interactive actions use native `<button>` elements rather than clickable non-semantic containers.
- Icon-only controls provide `aria-label` attributes to communicate their purpose.
- Pending chat messages expose `aria-busy` so assistive technology can identify loading state.
- Error messages use `role="alert"` where appropriate so failures are announced.
- HTML artifact iframes include descriptive `title` attributes.
- The responsive navigation preserves explicit controls for opening and closing the session sidebar instead of relying only on gestures.

Accessibility is treated as an implementation constraint rather than a claim of full WCAG conformance. The current application has not undergone a formal accessibility audit.

---

## 10. Responsive Behavior

The frontend implements responsive CSS breakpoints to handle smaller screens gracefully:
- **Tablet (`< 1024px`):** The Artifact Viewer transitions from a side-by-side panel into a full-screen fixed modal overlay (with a high z-index), ensuring documents remain readable without squishing the layout.
- **Mobile (`< 768px`):** The session sidebar collapses into an off-canvas drawer that can be toggled via a mobile menu hamburger icon. The chat composer expands to take the full width of the screen, and provider labels are visually hidden to save space. Session deletion buttons, normally shown on hover, are persistently enabled on touch devices.

---

## 11. Future Improvements

*(Note: These are theoretical enhancements and are not implemented in the current repository).*

- **Streaming with Speculative Grounding:** Stream tokens to the UI immediately, but visually flag or redact them post-hoc if the synchronous validator catches a grounding error at the end of the generation.
- **Dedicated Vector Database:** Migrate from `pgvector` to Pinecone or Qdrant if the Lenny corpus grows exponentially and requires out-of-the-box sparse/dense hybrid search (BM25).
- **Interactive Artifact Editing:** Allow users to directly edit the generated Markdown in the side panel and save the changes back to the database.
- **User Document Uploads:** Allow users to upload their own internal company strategy docs to be chunked, embedded, and queried alongside the Lenny curriculum. 
