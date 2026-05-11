# Ferv — Recommendation System Architecture (current state)

**Scope:** Structural view of [ferv_project/recommendation/](../ferv_project/recommendation/) — modules, dependencies, and read/write ownership. Pipeline-specific flows (one-shot recommendation, add-to-graph edge building, future variants) are documented separately per pipeline.

---

## 1. Module map

| Module | File | Role | DB access |
|---|---|---|---|
| `EmbeddingService` | [embedding_service.py](../ferv_project/recommendation/embedding_service.py) | Text → vector via a provider. Persists `PlaceEmbedding` rows | **Write** (vectors, place embeddings) |
| `Retriever` | [retriever.py](../ferv_project/recommendation/retriever.py) | pgvector similarity queries (L2). Resolves the vector class for the configured provider | **Read-only** |
| `PromptBuilder` | [prompt_builder.py](../ferv_project/recommendation/prompt_builder.py) | Loads versioned templates from `ferv_project/prompts/` and injects context | None |
| `LlmClient` | [llm_client.py](../ferv_project/recommendation/llm_client.py) | Sends prompts via a provider, parses JSON, validates against a caller-supplied pydantic schema | None |
| `RecommendationService` | [recommendation_service.py](../ferv_project/recommendation/recommendation_service.py) | Orchestrator. Owns `GraphNode` creation in `recommendation` status | **Write** (`GraphNode`, `LlmInteractionLog`) |
| `GraphBuilder` | [graph_builder.py](../ferv_project/recommendation/graph_builder.py) | Orchestrator. Owns `GraphEdge` writes and node status transitions to `in_graph` | **Write** (`GraphEdge`, `GraphNode.status`, `LlmInteractionLog`) |

Provider abstractions:

- [embedding_providers/](../ferv_project/recommendation/embedding_providers/) — `base.EmbeddingProvider`, plus Gemini and OpenAI implementations and a `vector_class_for(cfg)` registry.
- [llm_providers/](../ferv_project/recommendation/llm_providers/) — `base.LlmProvider`, plus Gemini and OpenAI implementations.

Selection is driven by `settings.RECOMMENDATION_CONFIGS[config_key]`. All shared modules accept an injected provider for tests.

---

## 2. Dependency graph

```
                ┌──────────────────────────┐
   HTTP / API ──▶  RecommendationService    │   ┌──▶  GraphBuilder
                └──┬───────┬───────┬────────┘   │     (orchestrator)
                   │       │       │            │
                   ▼       ▼       ▼            │
          EmbeddingService Retriever PromptBuilder LlmClient
                   │            │                    │
                   ▼            ▼                    ▼
          embedding_providers/  pgvector       llm_providers/
          (Gemini, OpenAI)      (PlaceEmbedding,  (Gemini, OpenAI)
                                EmbeddingVector*)
```

Rules enforced by the layout:

- **Read/write split on pgvector.** `EmbeddingService` is the only writer of vectors and `PlaceEmbedding`; `Retriever` is read-only. Keeps the vector store from becoming a god-object as retrieval logic grows.
- **The LLM returns data, not DB rows.** `LlmClient` parses and validates; persistence happens only in the orchestrator that owns the domain. This preserves the ability to add validation, dry-run, or review steps between LLM output and the DB.
- **Providers are swappable.** Orchestrators depend on `EmbeddingService` / `LlmClient` interfaces, not on a specific provider. Adding a third provider = adding a file under `*_providers/` and registering it.

---

## 3. Data model (current)

Defined in [models.py](../ferv_project/recommendation/models.py):

- `EmbeddingVector` — abstract metadata (model_name, timestamps).
  - `GeminiEmbeddingVector` (768d), `GeminiEmbeddingVectorLarge` (3072d), `OpenAIEmbeddingVector` (1536d). New providers add their own subclass with the appropriate `VectorField` dimension.
- `PlaceEmbedding` — `Place` ↔ vector via `GenericForeignKey(content_type, object_id)`. Lets a single place point at any `EmbeddingVector` subclass without forcing a fixed dimension on the schema.
- `LlmInteractionLog` — append-only audit row: `workflow`, `prompt_version`, `embedding_model`, `language_model`, `input_payload` (JSON), `raw_llm_response`, `parsed_output` (JSON), `outcome`, `created_at`.

Domain models touched by orchestrators (defined in the `graph` app):

- `GraphNode` — written by `RecommendationService` (creation in `recommendation` status, with `rationale`) and by `GraphBuilder` (status transition to `in_graph`).
- `GraphEdge` — written exclusively by `GraphBuilder`.

---

## 4. Cross-cutting concerns

- **Provider config.** Every module that needs a provider reads `settings.RECOMMENDATION_CONFIGS[config_key]`. Tests inject providers directly.
- **Prompt versioning.** Templates live at [ferv_project/prompts/](../ferv_project/prompts/) as `<name>.txt`. `PromptBuilder.build` returns `(filled, template_name)`; the name is logged as `prompt_version`. Templates are never edited in place — new versions are added as `_v2`, `_v3`, etc.
- **Logging.** Every LLM-touching orchestration writes an `LlmInteractionLog` row on both success and validation failure. This is load-bearing infrastructure for the future feedback pipeline.
- **Failure policy.** Validation errors raise; no retries, no fallback. Orchestrators that perform multi-row writes (e.g. `GraphBuilder`) wrap them in `transaction.atomic()` so partial state is impossible.

---

## 5. HTTP surface

Routed in [urls.py](../ferv_project/recommendation/urls.py) and handled by [views.py](../ferv_project/recommendation/views.py):

- `POST /api/recommendation/recommend/` → `RecommendationService.recommend_one_shot` (Pipeline A).
- `POST /api/recommendation/node_based/` → `RecommendationService.recommend_node_based` (Pipeline B). Body: `{"node_ids": [<int>, ...]}` — the user's `in_graph` GraphNode IDs to seed retrieval.
- `POST /api/recommendation/exploratory/` → `RecommendationService.recommend_exploratory` (Pipeline C). Body: `{"heat": <float in [0,1]>}`.

`GraphBuilder` is callable in code; an HTTP route will be added when the add-to-graph workflow is exposed.

---

## 6. Extension points

- **New Recommendation Pipeline:** extend `recommendation_service` with new dispatcher functions that orchestrate all other modules.
- **New LLM or embedding provider:** implement the `base` interface, register in the corresponding `_providers/` package, add a new `EmbeddingVector` subclass if the dimension differs.
- **New retrieval strategy:** extend `Retriever` with a new query method; keep it read-only.

## 7. File structure (current)
recommendation/
├── __init__.py
├── admin.py
├── apps.py
├── models.py
├── urls.py
├── views.py
├── prompt_builder.py
├── llm_client.py
├── recommendation_service.py
├── graph_builder.py
├── embedding_service.py
├── retriever.py
├── llm_providers/
│   ├── __init__.py        # PROVIDER_REGISTRY, build_provider
│   ├── base.py            # LlmProvider ABC
│   ├── gemini.py          # GeminiProvider
│   └── openai.py          # OpenAIProvider
├── embedding_providers/
│   ├── __init__.py        # PROVIDER_REGISTRY, build_embedding_provider, vector_class_for
│   ├── base.py            # EmbeddingProvider ABC
│   ├── gemini.py          # GeminiEmbeddingProvider
│   └── openai.py          # OpenAIEmbeddingProvider
├── migrations/
│   ├── __init__.py
│   ├── 0001_initial.py
│   ├── 0002_geminiembeddingvectorlarge.py
│   └── 0003_merge_20260419_2237.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_recommendation.py
└── versions/              # empty
