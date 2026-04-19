# Ferv — Recommendation Service & RAG Architecture

**Status:** Draft for team review
**Scope:** MVP sprint — one-shot prompt recommendation + add-to-graph edge building
**Out of scope this sprint:** chat-based recommendation, feedback-driven profile updates, async execution, rejection analysis

---

## 1. Goals

Build the recommendation service and supporting RAG infrastructure that powers two user workflows:

1. **One-shot recommendation** — user submits a free-text prompt, receives a ranked set of places as `recommendation`-status graph nodes.
2. **Add-to-graph** — user promotes a recommendation node to `in_graph`, triggering personalized edge construction between the new node and existing graph members.

Both workflows must satisfy the product requirements:

- Recommendations reflect the user's profile, not just their prompt.
- Edges are personalized — two users saving the same pair of places may get different edges, with rationales that reflect each user's own profile.
- All inputs, prompts, and outputs are logged as substrate for a future feedback pipeline.

## 2. Non-goals

- This document does not design the chat agent (Recommendation Type 3). Chat will be a separate service layered on top of the one-shot primitives, with its own state management.
- This document does not design the feedback pipeline or profile auto-update workflow.
- This document does not design fallback strategies for LLM failures. Current policy: fail loudly.

---

## 3. Module overview

Seven modules, each with a single responsibility:

| Module | Responsibility | Writes to DB? |
|---|---|---|
| `EmbeddingService` | Generate embeddings; persist place embeddings; expose ad-hoc embedding for query text | Yes (pgvector, write-side only) |
| `Retriever` | Vector similarity queries over pgvector. Takes a query vector + filters, returns ranked candidates | No |
| `PromptBuilder` | Load versioned prompt templates, inject data, return fully-formed prompt strings | No |
| `LlmClient` | Send prompts to the LLM, parse and validate responses against a caller-specified schema, return structured data or raise | No |
| `GraphBuilder` | Orchestrate add-to-graph workflow. Owns `GraphEdge` writes and `GraphNode` status transitions | Yes (edges, node status) |
| `RecommendationService` | Orchestrate one-shot recommendation workflow. Owns `GraphNode` creation in `recommendation` status | Yes (nodes) |
| `User.get_profile_as_prompt_text()` | Pure method on the User model. Aggregates `in_graph` node characteristics on-the-fly and combines with free-form profile text. Returns a prompt-ready string | No |

### Design principles

- **Read/write separation on pgvector.** `EmbeddingService` is the only module that writes embeddings. `Retriever` is read-only. This prevents the vector-store module from becoming a god-object as retrieval logic grows.
- **The LLM returns data, not database rows.** `LlmClient` parses and validates but never persists. Persistence always goes through the orchestrator that owns the domain (GraphBuilder for edges, RecommendationService for nodes). This preserves the ability to add validation, review, or dry-run steps between the LLM output and the DB.
- **Prompts are versioned.** Templates live in files (e.g., `edge_building_v1.txt`, `recommendation_v1.txt`). Every LLM call logs the prompt version used. Lets us iterate on prompts without deploying code and lets us debug "why did edges from March look different."
- **Validation failures fail fast.** No retry, no fallback, no partial success. If the LLM returns malformed or invalid data, the user-facing operation raises. We will revisit once we have real usage data.

---

## 4. Data model additions & assumptions

### Existing (assumed present)

- `User` — standard Django user, plus a `profile_text` field (free-form, hand-written for MVP).
- `Place` — place corpus with embeddings already populated in pgvector.
- `GraphNode` — links a user to a place with a `status` field: `recommendation | in_graph | discarded | removed`.
- `GraphEdge` — as specified:
  ```python
  class GraphEdge(models.Model):
      user = ForeignKey(User, related_name='graph_edges')
      from_node = ForeignKey(GraphNode, related_name='outgoing_edges')
      to_node = ForeignKey(GraphNode, related_name='incoming_edges')
      weight = FloatField(default=1.0)
      reason = CharField(max_length=255, blank=True)
      reason_type = CharField(max_length=60, blank=True)
      created_at = DateTimeField(auto_now_add=True)
      updated_at = DateTimeField(auto_now=True)
  ```

### Proposed additions

- **`GraphNode.rationale`** (optional, `TextField(blank=True)`) — stores the LLM's per-place rationale from the recommendation step. Useful for UI ("why was this recommended?") and for future feedback extraction.
- **Log table or structured log stream** — prompt version, user ID, input payload, raw LLM response, parsed output, outcome. Append-only. Exact shape is a team decision; simplest MVP is a dedicated `LlmInteractionLog` model.

### Open model questions

- `reason_type` is free-form at the DB level. Prompt will instruct the LLM to pick from a small enum (e.g., `food | ambiance | activity | neighborhood | social`), but we are not enforcing at the DB level yet. Expect some drift; revisit if it becomes a problem.
- `weight` is a float produced by the LLM. Values will be poorly calibrated. Do not rely on fine-grained weight differences for any downstream logic in MVP.

---

## 5. Pipeline A: One-shot recommendation

### Trigger
User submits a free-text prompt via the recommendation endpoint.

### Inputs
- `user_id`
- `prompt_text` (free text)

### Steps

1. **Request entry.** `RecommendationService` receives the request and orchestrates.
2. **Prompt embedding.** `EmbeddingService` embeds `prompt_text` using the same model used for place embeddings. Not persisted.
3. **Candidate retrieval.** `Retriever` returns top-K places (default K=20) from the corpus by vector similarity to the prompt embedding. SQL-level filter excludes places already linked to this user in any `GraphNode` status. If fewer than K places remain after filtering, return what's available.
4. **Profile fetch.** Call `user.get_profile_as_prompt_text()`.
5. **Prompt assembly.** `PromptBuilder` loads `recommendation_v1.txt`, injects `prompt_text`, `profile_text`, and candidate descriptors. Template instructs the LLM to select top N (default N=5), rank them, and return structured JSON with `place_id` and `rationale` per pick.
6. **LLM call.** `LlmClient` sends the prompt, parses the JSON, validates against the schema (N items, valid `place_id` from candidate set, non-empty rationale within length limits). On failure: raise.
7. **GraphNode creation.** `RecommendationService` creates N `GraphNode` rows with status `recommendation`, attaches rationale, returns nodes + place data to the API layer.
8. **Log.** Prompt version, user ID, prompt text, prompt embedding (or hash), retrieved candidate IDs, candidates passed to LLM, profile snapshot, raw LLM response, parsed output, created node IDs.

### Key parameters (tunable)

- `K` (retrieval breadth) — default 20. Log LLM-selected rank positions within vector-search ordering to tune later.
- `N` (recommendations returned) — default 5.

### Known risks

- **Query/description asymmetry in embedding space.** Prompt embeddings and place-description embeddings may not cluster well together even when semantically related. If recommendation quality feels off, HyDE (LLM generates a hypothetical place description, we embed that for retrieval) is the first mitigation to try. Not implementing for MVP.
- **Sync latency.** Entire pipeline is sync. Users wait 3–10s per request. Acceptable for MVP; revisit with async + optimistic UI after real usage.

---

## 6. Pipeline B: Add node to graph

### Trigger
User promotes a `recommendation`-status `GraphNode` to `in_graph`.

### Inputs
- `user_id`
- `new_node_id`

### Steps

1. **Request entry.** `GraphBuilder` receives the transition request.
2. **Candidate retrieval.** `Retriever` returns top-N existing `in_graph` nodes for this user, ranked by vector similarity between the new node's embedding and existing nodes' embeddings (default N=5–8). If user has fewer than N `in_graph` nodes, use all. If zero, skip to step 6 — status transition only, no edges.
3. **Profile fetch.** Call `user.get_profile_as_prompt_text()`.
4. **Prompt assembly.** `PromptBuilder` loads `edge_building_v1.txt`, injects profile text, candidate node descriptors, new node descriptor. Template instructs the LLM to produce 0–N edges as structured JSON, each with `from_node_id`, `to_node_id`, `weight` (float 0–1), `reason` (short text, ≤255 chars), `reason_type` (from enum: `food | ambiance | activity | neighborhood | social | other`).
5. **LLM call.** `LlmClient` sends, parses, validates (edge count within bounds, all `from_node_id`/`to_node_id` values from the candidate set or equal to the new node ID, fields within length/range limits). On failure: raise.
6. **Edge persistence.** `GraphBuilder` re-verifies node IDs belong to this user's graph (defense against schema-valid but unauthorized IDs). Creates `GraphEdge` rows in a transaction with the status transition. Returns created edge IDs.
7. **Commit.** New node status moves to `in_graph`. If any prior step raised, transition is rolled back and error surfaces to user.
8. **Log.** Prompt version, user ID, profile snapshot, candidate node IDs, new node ID, raw LLM response, parsed output, created edge IDs, outcome.

### Key parameters (tunable)

- `N` (candidate breadth for edge-building) — default 5–8. Determines both LLM context size and maximum edges produced per add.

### Known risks

- **Thin profiles produce weak edges.** Cold-start users with little profile signal will get generic rationales. Hand-authored MVP profiles should be written at "realistic auto-generated quality," not "pristine human quality," to avoid masking this.
- **Reason-type drift.** LLM will occasionally invent categories outside the enum. We log and accept for MVP.

---

## 7. Cross-pipeline concerns

### Profile assembly

`User.get_profile_as_prompt_text()` returns a string with two parts:

- **Part 1 (derived):** Top-K most frequent characteristics across the user's `in_graph` nodes, grouped by dimension (types, activities, ambiance). Computed on-the-fly. No caching for MVP.
- **Part 2 (authored):** The user's `profile_text` field, hand-written by the team for MVP. Will be auto-generated by the feedback pipeline in a later sprint.

The method must be pure: no side effects, no logging, no caching. Callers (`GraphBuilder`, `RecommendationService`) must never bypass it to access profile fields directly. This keeps the migration to a dedicated `ProfileService` mechanical when the write-side arrives.

### Prompt versioning

- Templates live at `prompts/<workflow>_v<N>.txt`.
- Every LLM call logs the exact template version used.
- Never edit a versioned template in place. Create `_v2`, route new calls to it, keep `_v1` available for comparison.

### Logging

Every LLM-touching operation logs, at minimum:
- Prompt version
- Full input payload (user data, candidates, user prompt text where applicable)
- Raw LLM response
- Parsed/validated output (or validation error)
- Resulting DB writes (IDs)
- Timestamp and user ID

This is load-bearing infrastructure for the feedback pipeline. It is not optional and not deferrable.

### Failure handling

Single policy across both pipelines: **validation failures raise, the user-facing operation fails.** No retries, no fallbacks, no partial success. Revisit after real usage data.

---

## 8. Sequence diagrams

### Pipeline A — one-shot recommendation

```
User        API               RecService     EmbedSvc    Retriever    User(model)   PromptBuilder    LlmClient       DB
 |           |                     |              |           |             |              |               |          |
 |--prompt-->|                     |              |           |             |              |               |          |
 |           |-recommend_one_shot->|              |           |             |              |               |          |
 |           |                     |--embed------>|           |             |              |               |          |
 |           |                     |<---vector----|           |             |              |               |          |
 |           |                     |---top-K w/ exclusion---->|             |              |               |          |
 |           |                     |<------candidates---------|             |              |               |          |
 |           |                     |--profile_text()----------------------->|              |               |          |
 |           |                     |<-----string----------------------------|              |               |          |
 |           |                     |---build(prompt, profile, candidates)----------------->|               |          |
 |           |                     |<---formatted prompt-----------------------------------|               |          |
 |           |                     |---send(prompt, schema)------------------------------->|               |          |
 |           |                     |                                                       |--LLM API----->|          |
 |           |                     |                                                       |<--response----|          |
 |           |                     |<---parsed & validated output--------------------------|               |          |
 |           |                     |---create GraphNodes (status=recommendation)------------------------------------->|
 |           |                     |---log interaction--------------------------------------------------------------->|
 |           |<---nodes ID's-------|              |           |             |              |               |          |
 |<--results-|                     |              |           |             |              |               |          |
```

### Pipeline B — add to graph

```
User        API           GraphBuilder                  Retriever    User(model)   PromptBuilder    LlmClient     DB
 |           |                 |                              |             |              |               |          |
 |--add----->|                 |                              |             |              |               |          |
 |           |---add_to_graph->|                              |             |              |               |          |
 |           |                 |---top-N in_graph, new_node-->|             |              |               |          |
 |           |                 |<----candidates---------------|             |              |               |          |
 |           |                 |--profile_text()--------------------------->|              |               |          |
 |           |                 |<-----string--------------------------------|              |               |          |
 |           |                 |---build(profile, candidates, new_node)------------------->|               |          |
 |           |                 |<---formatted prompt---------------------------------------|               |          |
 |           |                 |---send(prompt, schema)----------------------------------->|               |          |
 |           |                 |                                                           |--LLM API----->|          |
 |           |                 |                                                           |<--response----|          |
 |           |                 |<---parsed & validated output------------------------------|               |          |
 |           |                 |---verify node IDs belong to user---------------------------------------------------->|
 |           |                 |---create GraphEdges + transition status (transaction)------------------------------->|
 |           |                 |---log interaction------------------------------------------------------------------->|
 |           |<---edge IDs-----|                              |             |              |               |          |
 |<--ok------|                 |                              |             |              |               |          |
```

---

## 9. Build order for the sprint

Suggested order of implementation, each step gated by the previous:

1. **`EmbeddingService` + `Retriever`** — shared infrastructure. Verify with smoke tests against the existing place corpus (query → candidates that look plausible).
2. **`PromptBuilder` + `LlmClient` + template loading** — also shared. Build with a stub template, verify the round-trip (prompt → LLM → validated JSON) works end-to-end on a dummy schema.
3. **`User.get_profile_as_prompt_text()`** — plus hand-author 3–5 test user profiles at "realistic auto-generated quality."
4. **Pipeline A — RecommendationService** — end-to-end one-shot recommendation. Start with synthetic prompts against real test users.
5. **Pipeline B — GraphBuilder** — edge building. Depends on A because you need `in_graph` nodes to test against; either add them manually or run Pipeline A first to produce recommendations, then promote.
6. **Logging** — ideally layered in from step 2, not bolted on at the end.

---

## 10. Open questions for team discussion

- **Log storage.** Dedicated `LlmInteractionLog` model, structured logs to a log aggregator, or both?
- **`reason_type` enum enforcement.** Loose (prompt-only) vs. strict (DB constraint) — the tradeoff is flexibility for iteration vs. cleanliness of downstream queries.
- **Rationale persistence on `GraphNode`.** Add the field now, or defer until we know whether we surface it in the UI?
- **K and N defaults.** Chosen based on intuition. Should we instrument and tune during sprint, or pick now and revisit?
- **Test user profiles.** Who authors them, and how many do we need to feel confident edges and recommendations are working?
- **Weight assignment by Llm.** Llm are bad at estimated continuous numeric values, most weights assigned by Llm will be around 0.7 to 0.9 (Noisy data).

---

## 11. What this doc doesn't answer (deferred)

- Chat recommendation (Type 3). Separate design doc when that sprint lands.
- Feedback pipeline (profile auto-updates, rejection analysis, cleanup). Separate design doc.
- Async execution. Revisit after measuring real latency under load.
- HyDE / query expansion. Revisit if recommendation quality suggests retrieval asymmetry is a real problem.
- Caching strategy for profile derivation. Revisit if on-the-fly aggregation becomes a bottleneck.
