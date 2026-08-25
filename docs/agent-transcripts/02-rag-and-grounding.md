# 02 — RAG and Grounding

This record documents the knowledge ingestion, hybrid retrieval, conversational retrieval behavior, source traceability, and grounding controls used by the Lenny Growth Assistant.

## 1. Knowledge Ingestion

The Lenny Podcast and Newsletter corpus is transformed into structured documents and chunks before retrieval.

Document metadata is preserved so retrieved evidence can be traced back to its original source. Depending on the source, this includes fields such as:

- title
- guest
- source type
- source URL
- YouTube URL
- timestamps
- chunk content

Podcast and newsletter content use different chunking strategies because their source structures differ.

Podcast chunks preserve conversational and timestamp context, while newsletter chunks are segmented around prose structure.

Each chunk is embedded using `nomic-embed-text` through Ollama and stored in PostgreSQL with a 768-dimensional `pgvector` embedding.

The ingestion pipeline is designed so the knowledge base can be refreshed without treating every run as an entirely new corpus.

## 2. Initial Retrieval Approach

Retrieval began with semantic similarity over the stored embeddings.

This worked well for broad conceptual questions, but testing exposed an important weakness: semantic similarity alone was not always enough for queries containing exact names, acronyms, episode titles, or other lexical signals.

For a grounded product assistant, retrieving a conceptually similar episode is not sufficient when the user is clearly asking about a particular company, guest, or case study.

## 3. Hybrid Retrieval

The retrieval pipeline was expanded to combine semantic and lexical search.

Semantic candidates are ranked using cosine distance over the vector embeddings.

Lexical candidates use PostgreSQL full-text search with:

- `to_tsvector`
- `to_tsquery`
- `ts_rank_cd`

The two candidate sets are combined using Reciprocal Rank Fusion with:

`RRF_K = 60`

This allows exact lexical matches and semantic similarity to contribute independently instead of forcing both signals into a single scoring scale.

A metadata reranking step was also added.

`ENTITY_MATCH_BOOST` increases the final score when the query explicitly matches useful document metadata such as a guest name or distinctive title tokens.

This became particularly useful for company- and guest-specific questions.

## 4. Retrieval Evaluation: Duolingo

Retrieval quality was tested directly against the knowledge base rather than relying only on generated answers.

For the query about how Duolingo reignited user growth, the retrieved results included chunks covering:

- the retention model,
- CURR,
- leaderboards,
- push notifications,
- streaks,
- and the resulting growth impact.

After metadata reranking improvements, Duolingo-specific chunks ranked ahead of semantically related but less relevant retention discussions.

This test was important because the generated answer can look plausible even when retrieval quality is poor. Inspecting chunk IDs, titles, similarity scores, lexical scores, and previews made retrieval behavior observable independently of generation.

## 5. Conversational Retrieval Bug

A later artifact test exposed a more subtle retrieval problem.

The conversation had moved from Duolingo to Anthropic. The user then issued a new, self-contained Ship 30 request explicitly asking for an essay about Duolingo.

The artifact retrieval query automatically included previous user turns.

As a result, unrelated Anthropic conversation context leaked into retrieval and Anthropic chunks appeared among the sources for the Duolingo artifact.

This was not primarily a generation problem. It was a retrieval-query construction problem.

## 6. First Fix and Regression

The first attempted fix disabled conversation-history contribution for artifact and Ship 30 retrieval.

That solved the contamination problem for self-contained prompts, but it broke an existing behavior.

A test using:

`Turn the Duolingo discussion into an essay.`

expected the earlier user turn:

`Tell me about Duolingo growth.`

to participate in retrieval because the current instruction depends on conversational context.

The Ship 30 test failed because retrieval now received only the current referential instruction.

This showed that globally removing conversation history was too aggressive.

## 7. Context-Aware Retrieval Fix

The retrieval-query design was changed to distinguish between two cases:

1. self-contained requests that already contain enough topic information;
2. referential requests that depend on earlier conversation context.

`build_retrieval_query` retained its normal bounded-history behavior.

Artifact and Ship 30 workflows decide whether to include that history based on whether the current instruction requires conversational context.

This preserved follow-up behavior such as:

`Turn the Duolingo discussion into an essay.`

while preventing an explicit request such as:

`Create a Ship 30 for 30 essay about how Duolingo reignited user growth...`

from inheriting unrelated Anthropic turns.

A regression test was added specifically to verify that a self-contained Duolingo Ship 30 request does not include earlier Anthropic context in its retrieval query.

After the fix:

`5 passed`

for the Ship 30 tests, followed by:

`61 passed`

for the complete backend test suite at that stage.

The final Duolingo artifact retrieval returned only Duolingo newsletter sources in the demonstrated result.

## 8. Grounding Controls

Retrieved chunks are formatted into numbered source context before generation.

The assistant prompt instructs the model to:

- use the supplied Lenny knowledge as factual evidence,
- cite factual claims with source numbers,
- avoid unsupported acronym expansions,
- and avoid presenting unsupported text as direct quotations.

Prompt instructions alone are not treated as sufficient.

The backend also performs deterministic grounding checks for specific failure modes.

These checks include validating quoted text against retrieved source content and detecting unsupported acronym-expansion patterns.

If grounding issues are detected, the application can perform a correction pass using the identified issues and the same retrieved evidence.

If acceptable grounded output still cannot be produced, the workflow returns a controlled failure/refusal rather than silently presenting the problematic output.

These controls reduce unsupported claims but are not presented as proof that every possible factual error can be detected.

## 9. Source Traceability

Retrieved chunks remain associated with the generated response.

The API exposes source metadata so the frontend can show the evidence used for an answer.

Source cards can include information such as:

- document title
- source type
- guest
- timestamps
- source URL
- YouTube URL

This allows users to inspect where an answer came from instead of receiving an uncited model response.

Artifact and Ship 30 workflows also retain the retrieved sources used during generation.

## 10. Result

At the end of this phase, the system had:

- local vector embeddings,
- semantic retrieval,
- PostgreSQL lexical retrieval,
- Reciprocal Rank Fusion,
- metadata-aware reranking,
- context-aware retrieval queries,
- numbered source grounding,
- deterministic checks for selected grounding failure modes,
- correction behavior,
- and source traceability through the API and UI.

The retrieval contamination bug also produced an important design rule for the project: conversation history should improve genuinely contextual requests, but should not automatically override the explicit subject of a new self-contained request.
