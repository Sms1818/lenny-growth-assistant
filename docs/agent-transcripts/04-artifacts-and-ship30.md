# 04 — Artifacts and Ship 30

This record documents Markdown and HTML artifact generation, the Artifact Viewer, HTML isolation, standalone artifact viewing, and the dedicated Ship 30 for 30 workflow.

## 1. General Artifact Generation

The assistant supports two general artifact formats:

- Markdown
- HTML/CSS

Artifact generation is separate from normal conversational answering.

The user's instruction is combined with retrieved Lenny knowledge and recent conversation context where appropriate, then sent through the configured artifact-generation provider.

Generated artifacts are persisted and linked to the assistant message that created them.

This allows an artifact to be reopened later when a persisted session is restored.

## 2. Artifact Viewer

Displaying large generated documents directly inside the chat made the conversation difficult to navigate.

A dedicated Artifact Viewer was therefore added beside the chat.

For Markdown artifacts, the frontend renders the generated Markdown as formatted content rather than displaying raw source text.

For HTML artifacts, the viewer renders the document inside an isolated iframe.

This keeps artifact content visually separate from the conversation while preserving the original chat context.

## 3. HTML Artifact Security

Generated HTML is treated as untrusted input.

Before an HTML artifact is persisted, backend validation checks for known executable or embedded contexts.

Rejected patterns include constructs such as:

- `<script>`
- inline event handlers such as `onclick=`
- `javascript:` URLs
- `<iframe>`
- `<object>`
- `<embed>`

The goal is to prevent generated artifacts from introducing obvious executable browser contexts.

This validation is a defense-in-depth measure, not a claim of complete HTML or network isolation.

## 4. In-App HTML Isolation

The in-app viewer renders generated HTML using:

`<iframe sandbox="">`

No sandbox permissions are granted.

This removes privileges including:

- script execution;
- same-origin access to the parent application;
- form submission;
- popup privileges;
- and top-level navigation privileges.

The sandbox does not inherently prevent every passive external resource request, so the security model should not be interpreted as complete network isolation.

The primary objective is to prevent generated HTML from receiving execution privileges inside the main application.

## 5. Standalone Artifact Viewing

Artifact testing showed that the side-panel viewer was useful for comparison with the chat, but long Markdown documents, Ship 30 essays, and HTML briefs were also easier to inspect at full browser width.

An "Open in new tab" action was added for generated artifacts.

HTML artifacts are opened through a transient Blob URL.

`window.open` uses:

`noopener,noreferrer`

so the opened document does not retain an opener relationship to the main application.

The iframe `sandbox=""` boundary applies only to the in-app viewer and does not carry over to the standalone Blob document.

The standalone HTML path therefore relies primarily on backend validation together with opener isolation rather than the iframe sandbox.

Markdown and Ship 30 artifacts are converted into a standalone rendered HTML document for the new-tab reading experience.

## 6. Dedicated Ship 30 for 30 Skill

Ship 30 generation is implemented as a separate workflow in:

`backend/app/assistant/skills/ship30.py`

rather than as an ordinary chat prompt.

The skill encodes writing requirements including:

- approximately 1,250 words;
- a strong hook;
- narrative progression;
- an H1 headline;
- skimmable formatting;
- selective emphasis;
- a concrete takeaway;
- and source citations.

The backend structural validator accepts an implemented word-count range of:

`1,000–1,500 words`

while the generation contract targets approximately 1,250 words.

The workflow also validates structural requirements before persisting the artifact.

A structural failure is returned as a controlled `422` artifact-generation error.

## 7. Ship 30 Retrieval Depth

Ship 30 uses more retrieved source material than normal conversational chat.

The workflow retrieves up to 8 chunks so the long-form model has enough evidence to construct a complete essay without relying only on a small number of excerpts.

This became particularly important for prompts covering multiple aspects of a case study, such as Duolingo's:

- CURR model;
- retention strategy;
- leaderboards;
- notifications;
- streaks;
- and measurable outcomes.

## 8. Retrieval Context Contamination

A real UI test exposed a retrieval problem.

The conversation included an unrelated Anthropic question immediately before a new, self-contained Ship 30 request explicitly asking about Duolingo.

Because prior user turns were automatically appended to the retrieval query, Anthropic chunks appeared among the sources for the Duolingo essay.

The generated essay could therefore receive irrelevant evidence even though the new request already contained a complete topic.

This was diagnosed as retrieval-query contamination rather than a model-generation failure.

## 9. First Retrieval Fix and Regression

The first attempted correction removed conversation history from Ship 30 and artifact retrieval entirely.

That fixed the self-contained Duolingo request but broke genuinely referential instructions.

The existing Ship 30 test used:

`Turn the Duolingo discussion into an essay.`

with an earlier user message:

`Tell me about Duolingo growth.`

The test expected that earlier context to participate in retrieval.

After history was disabled globally, the test failed because the current instruction alone did not contain the full topic.

This showed that artifact retrieval needed conditional context rather than either always including or always excluding conversation history.

## 10. Context-Aware Retrieval Correction

The final design preserved the normal bounded-history behavior in `build_retrieval_query`.

Artifact and Ship 30 workflows now decide whether retrieval history is necessary based on whether the current request depends on previous conversation context.

A self-contained request such as:

`Create a Ship 30 for 30 essay about how Duolingo reignited user growth...`

can retrieve using its explicit topic.

A referential request such as:

`Turn the Duolingo discussion into an essay.`

can still include recent user context.

A regression test was added to ensure that a previous Anthropic discussion does not contaminate a self-contained Duolingo Ship 30 retrieval query.

The Ship 30 test suite passed after the correction, followed by a green full backend suite.

A later UI test showed all 8 retrieved Ship 30 sources coming from the Duolingo newsletter.

## 11. Local Long-Form Generation

Normal local chat uses `llama3.2:3b`.

Long-form local artifact generation was tested with:

`qwen3:4b-instruct`

because the smaller conversational model was not a good fit for approximately 1,250-word structured essays and visual HTML generation.

Local Markdown and Ship 30 generation were successfully exercised through the UI.

Long-form local generation was slower than cloud generation, so the artifact timeout was configured separately from the normal chat timeout.

Auto mode uses the cloud path for artifacts, while explicit Local mode remains available to demonstrate fully local artifact generation.

## 12. Failed Grounding Refinement Attempt

After local Ship 30 generation was working, an additional semantic grounding-refinement pass was introduced.

The intended flow was:

1. generate the initial Ship 30 draft;
2. ask the model to rewrite the draft so unsupported claims were removed;
3. run the existing deterministic grounding checks;
4. persist the refined essay.

The change required a second long-form local model call.

Unit tests initially exposed the changed call contract because a Ship 30 test expected one agent invocation and now observed two.

The test was updated to verify the intended two-pass behavior.

However, the more important failure appeared during real UI testing.

The refinement pass produced an artifact that failed the existing structural validator:

`essay_too_short:755`

and:

`missing_h1`

The extra grounding pass improved neither the user experience nor the structural reliability. It degraded a previously working long-form workflow.

## 13. Refinement Revert

Rather than weakening the Ship 30 structural requirements or reducing the assignment's approximately 1,250-word target, the additional refinement pass was removed.

The revert was intentionally surgical.

The following improvements were retained:

- hybrid retrieval;
- metadata reranking;
- context-aware artifact retrieval;
- self-contained request isolation;
- 8-chunk Ship 30 retrieval;
- structural validation;
- deterministic quote/acronym grounding checks;
- and local `qwen3:4b-instruct` artifact generation.

Only the additional second long-form grounding rewrite was removed.

After reverting it, the local Ship 30 workflow again successfully produced a complete artifact with:

- an H1 headline;
- long-form structure;
- 8 Duolingo sources;
- and the expected Artifact Viewer experience.

This was a useful example of preferring a stable, validated workflow over adding another model pass simply because it appeared theoretically safer.

## 14. Result

At the end of this phase, the application supported:

- grounded Markdown artifacts;
- grounded HTML/CSS artifacts;
- persistent artifact records;
- an in-app Artifact Viewer;
- sandboxed HTML rendering;
- standalone new-tab viewing;
- a dedicated Ship 30 skill;
- approximately 1,250-word Ship 30 generation with structural validation;
- explicit Local and Cloud artifact execution;
- context-aware artifact retrieval;
- and regression coverage for retrieval isolation.

The main lesson from the artifact work was that long-form generation needs separate engineering constraints from normal chat. Retrieval depth, model capability, timeout limits, structure validation, security boundaries, and conversational context all had to be handled explicitly rather than treating artifacts as simply longer chat responses.
