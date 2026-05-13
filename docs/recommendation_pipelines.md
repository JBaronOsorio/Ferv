# Ferv -- Recommendation pipelines

**Scope:** MVP - Definition of the following recommendation pipelines:
- One shot recommendation
- Node based recommendation
- Exploratory recommendation

---


## Design principles

- **Read/write separation on pgvector.** `EmbeddingService` is the only module that writes embeddings. `Retriever` is read-only. This prevents the vector-store module from becoming a god-object as retrieval logic grows.
- **The LLM returns data, not database rows.** `LlmClient` parses and validates but never persists. Persistence always goes through the orchestrator that owns the domain (GraphBuilder for edges, RecommendationService for nodes). This preserves the ability to add validation, review, or dry-run steps between the LLM output and the DB.
- **Prompts are versioned.** Templates live in files (e.g., `edge_building_v1.txt`, `recommendation_v1.txt`). Every LLM call logs the prompt version used. Lets us iterate on prompts without deploying code and lets us debug "why did edges from March look different."
- **Validation failures fail fast.** No retry, no fallback, no partial success. If the LLM returns malformed or invalid data, the user-facing operation raises. We will revisit once we have real usage data.

---

## 1. Pipeline A: One-shot recommendation

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

---

## 2. Pipeline B: Node-based recommendation

### Trigger
User submits a node based recommendation request via the recommendation endpoint.

### Inputs
- `user_id`
- `node_list` (List of n nodes on which the recommendation will be based)

### Steps
1. **Request entry.** `RecommendationService` receives the request and orchestrates.
2. **Candidate pool retrieval.** `Retriever` executes n independent vector similarity queries, one per node in node_list, each returning top-K' places (default K'=50) ranked by similarity. SQL-level filter excludes places already linked to this user in any GraphNode status across all n queries.
3. **Candidate pool distillation.** The n ranked lists are merged using Reciprocal Rank Fusion (RRF). Each candidate place receives an RRF score summing 1 / (rank + 60) across every list it appears in, rewarding both breadth of appearance and high rank position within individual lists. The top-K candidates by RRF score form the final candidate block passed to the LLM (default K=20).
4. **Profile fetch.** Call `user.get_profile_as_prompt_text()`.
5. **Prompt assembly.** `PromptBuilder` loads `node_based_recommendation_v1.txt`, injects `prompt_text`, `profile_text`, and candidate descriptors. Template instructs the LLM to select top N (default N=5), rank them, and return structured JSON with `place_id` and `rationale` per pick.
6. **LLM call.** `LlmClient` sends the prompt, parses the JSON, validates against the schema (N items, valid `place_id` from candidate set, non-empty rationale within length limits). On failure: raise.
7. **GraphNode creation.** `RecommendationService` creates N `GraphNode` rows with status `recommendation`, attaches rationale, returns nodes + place data to the API layer.
8. **Log.** Prompt version, user ID, prompt text, prompt embedding (or hash), retrieved candidate IDs, candidates passed to LLM with per-anchor rank positions, profile snapshot, raw LLM response, parsed output, created node IDs.

### Key paramenters (tunable)

- `K'` (subset retrieval breadth) — default 50.
- `K` (distilled candidates) - default 20.
- `N` (recommendations returned) — default 5.

--- 

## 3. Pipeline C: Exploratory recommendation

### Trigger
User requests an exploratory recommendation from their map view.

### Inputs
- `user_id`
- `heat` (float 0–1, user-controlled)

### Steps
1. **Request entry.** `RecommendationService` receives the request and orchestrates.
2. **Profile fetch.** Call `user.get_profile_as_prompt_text()`.
3. **Profile embedding.** `EmbeddingService` embeds the output of `user.get_profile_as_prompt_text()` 
into a profile vector. Not persisted.
4. **Direction perturbation.** A random unit vector of the same dimensionality as the profile 
embedding is sampled. The profile vector is shifted by `heat * scale` along this direction, 
producing a perturbed query vector. The direction vector and perturbation magnitude are retained 
for logging.
5. **Direction decoding.** `Retriever` finds the top-D nearest places to the raw direction vector 
alone (not the perturbed query vector). These place labels are stored as a human-readable proxy 
for the perturbation direction and are not used for candidate retrieval.
6. **Candidate pool retrieval.** `Retriever` executes a vector similarity querie from the 
perturbed query vector. SQL-level filter excludes places already linked to this user in any 
`GraphNode` status. First query returns a broad set of K places (default K=200). Second query 
returns a top set of K' places (default K'=20). Both queries exclude places already linked to 
this user in any `GraphNode` status.
7. **Margin sampling.** The top set is subtracted from the broad set, yielding a margin candidate 
block of K-K' places (default 20). These are candidates that relate to the perturbed profile 
vector but are not its closest matches, producing results that are recognizably non-random but 
outside the user's established map.
8. **Prompt assembly.** `PromptBuilder` loads `exploratory_recommendation_v1.txt`, injects 
`profile_text` and margin candidate descriptors. Template instructs the LLM to select top N 
(default N=5), rank them, and return structured JSON with `place_id` and `rationale` per pick. 
Template explicitly frames the task as selecting places that are surprising or outside the user's 
established pattern while remaining coherent choices.
9. **LLM call.** `LlmClient` sends the prompt, parses the JSON, validates against the schema 
(N items, valid `place_id` from margin candidate block, non-empty rationale within length limits). 
On failure: raise.
10. **GraphNode creation.** `RecommendationService` creates N `GraphNode` rows with status 
`recommendation`, attaches rationale, returns nodes + place data to the API layer.
11. **Log.** Prompt version, user ID, profile embedding hash, perturbation direction vector, 
perturbation magnitude, heat value, direction decoded place labels, broad candidate IDs, top 
candidate IDs, margin candidate IDs, profile snapshot, raw LLM response, parsed output, 
created node IDs.

### Key parameters (tunable)
- `heat` (perturbation intensity) — float 0–1, user-controlled. Scales the magnitude of the 
directional shift applied to the profile embedding.
- `scale` (perturbation magnitude scalar) — system-controlled. Converts the normalized heat 
value into an actual distance in embedding space. Requires empirical tuning against the 
embedding model in use.
- `D` (near perturbed vector set) — default 5. Defines how many places will be sampled to characterize the perturbed vector.
- `K` (broad retrieval set) — default 200.
- `K'` (top retrieval set) — default 180. Defines the exclusion zone; K-K' is the margin 
candidate block size.
- `N` (recommendations returned) — default 5.

## Cross pipeline concerns
### `User.get_profile_as_prompt_text()` returns a string with two parts:

- **Part 1 (derived):** Top-K most frequent characteristics across the user's `in_graph` nodes, grouped by dimension (types, activities, ambiance). Computed on-the-fly. No caching for MVP.
- **Part 2 (authored):** The user's `profile_text` field, hand-written by the team for MVP. Will be auto-generated by the feedback pipeline in a later sprint.

The method must be pure: no side effects, no logging, no caching. Callers (`GraphBuilder`, `RecommendationService`) must never bypass it to access profile fields directly. This keeps the migration to a dedicated `ProfileService` mechanical when the write-side arrives.