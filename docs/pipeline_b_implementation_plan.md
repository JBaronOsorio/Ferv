# Pipeline B (Node-based recommendation) — implementation plan

## Context

The recommendation app on branch `feat/recommendations` already implements Pipeline A (one-shot, free-text prompt) and Pipeline C (exploratory, profile-perturbation). Pipeline B (node-based) is specified in [docs/recommendation_pipelines.md](../../U/5to%20semestre/Proyecto%202/Ferv/docs/recommendation_pipelines.md) §2 but has no implementation yet.

Pipeline B lets a user request recommendations seeded by a list of nodes they already have in their graph: the system runs one similarity query per anchor node, fuses the ranked lists with Reciprocal Rank Fusion (RRF), and asks the LLM to pick the best N from the fused candidate block. The intended outcome: fill the third slot in the recommendation surface so the frontend can offer "give me places like these ones I already have" alongside free-text and exploratory.

> **Branch note:** the `recommendation` app and `docs/` only exist on `feat/recommendations` (not on `main`, where this worktree was created). Implementation must happen on `feat/recommendations` (or a branch off it). All file paths below are relative to that branch.

---

## Modules touched / created

| File | Change |
|---|---|
| `ferv_project/recommendation/recommendation_service.py` | Add `recommend_node_based(user, node_list)` method + constants `NODE_BASED_K_PRIME`, `NODE_BASED_K`, `NODE_BASED_N`, `RRF_C` |
| `ferv_project/recommendation/vector_utils.py` | Add pure helper `reciprocal_rank_fusion(ranked_lists, c=60)` |
| `ferv_project/recommendation/views.py` | Add `node_based_recommend` view (sibling of `recommend` / `exploratory_recommend`) |
| `ferv_project/recommendation/urls.py` | Register `path('node_based/', views.node_based_recommend, name='node_based')` |
| `ferv_project/prompts/node_based_recommendation_v1.txt` | New versioned template |
| `ferv_project/recommendation/tests/test_node_based.py` | New test module (RRF unit tests + service + endpoint) |
| `docs/recommendation_system_architecture.md` | Add the new endpoint to §5 (HTTP surface) |

No model migrations. No changes to providers, `EmbeddingService`, `PromptBuilder`, `LlmClient`, or `LlmInteractionLog`.

---

## Reused (do not duplicate)

- `Retriever.get_candidates(query_vector, top_k, exclude_user)` — exact API needed for each per-anchor query; SQL-level user-node exclusion already implemented.
- `_candidates_block(candidates)` in `recommendation_service.py` — promote the module-level helper as-is for the new method.
- `LlmClient.send(prompt, RecommendationOutput)` and `RecommendationOutput` schema — Pipeline B's LLM output shape (`{recommendations: [{place_id, rationale}]}`) is identical to Pipeline A.
- `PromptBuilder.build(template_name, **context)` — versioned template loader, returns `(filled, version)`.
- `EmbeddingService` — only used to read `model_name` for the log row; no new embeddings produced.
- `user.get_profile_as_prompt_text()` — same as the other pipelines.
- `LlmInteractionLog.objects.create(...)` — same shape; new `workflow="node_based_recommendation"`.
- `transaction.atomic()` block for multi-row `GraphNode` writes (mirrors Pipeline C).

---

## New helper: RRF fusion

In `vector_utils.py`:

```python
def reciprocal_rank_fusion(
    ranked_lists: list[list[str]], c: int = 60
) -> list[tuple[str, float]]:
    """
    Reciprocal Rank Fusion across n ranked lists of place_ids.
    Returns (place_id, score) pairs sorted by score desc. c=60 is the
    Cormack/Buettcher/Clarke default.
    """
```

Pure, no DB access, easy to unit-test (deterministic ordering, single-list pass-through, missing items, empty input).

---

## New service method shape

```python
NODE_BASED_K_PRIME = 50   # per-anchor retrieval breadth
NODE_BASED_K = 20         # distilled candidates after RRF
NODE_BASED_N = 5          # final picks
RRF_C = 60                # RRF constant

def recommend_node_based(self, user, node_ids: list[int]) -> list[GraphNode]:
    # 1. Validate: non-empty list[int]. Fetch GraphNodes via
    #    GraphNode.objects.filter(id__in=node_ids, user=user, status="in_graph")
    #    .select_related("place"). Raise ValueError if the count differs
    #    (covers wrong owner, wrong status, missing IDs in one shot).
    # 2. Resolve each anchor place's embedding vector via PlaceEmbedding +
    #    the configured VectorClass (use Retriever's vector_class, or factor
    #    a small _vectors_for_places(places) helper). Anchor missing an
    #    embedding raises ValueError before any LLM call.
    # 3. For each anchor vector, call retriever.get_candidates(vec, K', exclude_user=user).
    #    The user-node exclusion already drops the anchors themselves and any
    #    other GraphNode the user owns.
    # 4. Build n ranked lists of place_ids; reciprocal_rank_fusion(...)
    #    returns top-K (place_id, score) pairs.
    # 5. Materialize the K candidate dicts (place + score) by joining back
    #    against the per-anchor result sets (use the dict that was already
    #    in memory; no extra DB round-trip).
    # 6. profile_text = user.get_profile_as_prompt_text() or "No profile available."
    # 7. anchors_block = _anchors_block(anchor_nodes)  # new local helper,
    #    same shape as _candidates_block but for the anchor set.
    # 8. PromptBuilder.build("node_based_recommendation_v1",
    #        anchors_block=..., profile_text=..., candidates_block=...,
    #        candidate_count=K, n=N)
    # 9. LlmClient.send(prompt, RecommendationOutput) — fail fast on validation,
    #    log validation_error row before re-raising.
    # 10. Validate picks ⊆ fused candidate set; on miss, log validation_error
    #     row and raise.
    # 11. transaction.atomic(): create N GraphNode rows status="recommendation",
    #     rationale truncated to [:255] (mirror Pipeline A/C).
    # 12. LlmInteractionLog row: input_payload includes anchor node_ids,
    #     anchor place_ids, per-anchor retrieved candidate IDs with their
    #     ranks, fused top-K IDs with RRF scores, profile snapshot.
```

---

## New prompt template

`ferv_project/prompts/node_based_recommendation_v1.txt` mirrors the structure of `recommendation_v1.txt` but the request side describes the anchor places (the user's `in_graph` seeds) instead of free text. **No `{prompt_text}` slot.** Slots: `{anchors_block}`, `{profile_text}`, `{candidates_block}`, `{candidate_count}`, `{n}`. Template instructs the LLM to pick N places that extend the pattern set by the anchors while staying coherent with the profile. Output contract identical to Pipeline A so we can reuse `RecommendationOutput`.

---

## HTTP surface

`POST /api/recommendation/node_based/` body `{"node_ids": [<int>, ...]}` →
`{"nodes": [_serialize_node(n), ...]}`. Same auth (`@login_required`) and error envelope as the existing two views. `_serialize_node` already exists in `views.py` — reuse.

---

## Tests (new file `tests/test_node_based.py`)

**Unit:** `reciprocal_rank_fusion` — single list, two overlapping lists with known ranks, place appearing in all lists, empty list, deterministic tie-break.

**Service (`@pytest.mark.django_db`, mock Retriever / LlmClient as in `test_exploratory.py`):**
- Happy path: 3 `in_graph` anchors → 3 ranked lists → RRF merges → LLM picks → N nodes created, then `log = LlmInteractionLog.objects.latest()` and assert `log.workflow == "node_based_recommendation"`, `log.outcome == "success"`, anchor IDs and per-anchor retrieved IDs present in `log.input_payload`.
- Anchor without an embedding raises before any LLM call, no log row written.
- Anchor not owned by user raises before any work (no log row).
- Anchor with status `recommendation` (not `in_graph`) raises before any work.
- LLM picks outside fused candidate set raises; assert via `LlmInteractionLog.objects.latest()` that the most recent log has `workflow == "node_based_recommendation"` and `outcome == "validation_error"`.
- Empty `node_ids` raises immediately.

> **Test pattern (apply consistently across this file and any future log assertions):** use `LlmInteractionLog.objects.latest()` then assert the `workflow` field on the returned row, instead of `LlmInteractionLog.objects.get(workflow=...)`. The latter raises `MultipleObjectsReturned` once any test (or fixture, or earlier subtest) writes more than one row with the same workflow, masking the real failure. `latest()` resolves by `Meta.get_latest_by = 'created_at'` already set on the model.

**Endpoint:**
- Requires authentication (302 to login when anonymous).
- Invalid JSON → 400.
- Empty / non-list / non-int `node_ids` → 400.
- Happy path → 200 with serialized nodes (mirror `test_exploratory.py::TestExploratoryEndpoint::test_happy_path_endpoint`).

Reuse fixtures from `tests/conftest.py` (`test_user_with_profile`, `authenticated_client`) and the `_make_place` / `_patch_pipeline_c` helper pattern from `test_exploratory.py` (adapt for Pipeline B's per-anchor `get_candidates` call sequence).

---

## Verification

1. `cd ferv_project && python manage.py test recommendation.tests.test_node_based` (or `pytest`).
2. Run the existing suite to confirm no regressions: `pytest ferv_project/recommendation/tests/`.
3. End-to-end manual: log in as a test user with ≥3 `in_graph` nodes (each with an embedded place), `POST /api/recommendation/node_based/` with `{"node_ids": [...]}`, confirm the response contains up to N=5 new `GraphNode` rows in `recommendation` status and that one `LlmInteractionLog` row with `workflow="node_based_recommendation"` was written. Try a payload mixing in a non-`in_graph` node ID and confirm it 500s with a `ValueError` from the service.
4. Confirm provider config — `settings.RECOMMENDATION_CONFIGS["default"]` is reused; no new env vars or settings.

---

## Postman walkthrough (manual smoke test as user `ferv`)

Confirmed against the local Postgres dev DB: user `ferv` exists with `id=2` and has 11 `in_graph` GraphNodes (IDs **53, 62, 69, 72, 78, 82, 85, 88, 92, 93, 98** — all places in / around El Poblado / Envigado: A LA FIJA, Cafetería Apolo LA 6ta, Social Club Academia, Tres Helenas Coffee Bar, Burg-co Hamburguesas, Parque Santa María de Los Ángeles I, Bermellón, PERGAMINO Wake Biohotel El Tesoro, Tentación Comidas Rápidas, De Lolita La Frontera, NUEVE CERO TRES). Pick 3–5 of these as the seed for the smoke test.

Server assumed at `http://localhost:8000`. Auth is session-based (Django `@login_required`) and CSRF-enforced (the recommendation views are not `@csrf_exempt`).

### Postman setup, one-time

1. Create a Postman environment with variables `base_url = http://localhost:8000`, `csrftoken = ` (empty), `sessionid = ` (empty).
2. In the workspace settings, enable **automatic cookie management** for `localhost`. (Postman will then carry `csrftoken` and `sessionid` across requests; you only need to lift the CSRF value into a header.)

### Step 1 — Prime the CSRF cookie

`GET {{base_url}}/`

Django's `CsrfViewMiddleware` sets a `csrftoken` cookie on this response. In Postman's **Tests** tab on this request, paste:

```javascript
const cookie = pm.cookies.get("csrftoken");
if (cookie) pm.environment.set("csrftoken", cookie);
```

### Step 2 — Log in as `ferv`

`POST {{base_url}}/`
- Headers: `X-CSRFToken: {{csrftoken}}`, `Content-Type: application/x-www-form-urlencoded`
- Body (x-www-form-urlencoded):
  - `username = ferv`
  - `password = <ferv's password>`  ← supply locally; not in this plan
  - `csrfmiddlewaretoken = {{csrftoken}}`

A successful login redirects to `/graph/welcome/` and sets the `sessionid` cookie. Postman's cookie jar holds it for subsequent requests. (If you prefer, log in once via the browser at `http://localhost:8000/`, copy the `csrftoken` and `sessionid` cookies into Postman's cookie editor for `localhost`, and skip steps 1–2.)

### Step 3 — Call Pipeline B

`POST {{base_url}}/api/recommendation/node_based/`

Headers:
- `Content-Type: application/json`
- `X-CSRFToken: {{csrftoken}}`

Body (raw JSON) — five of ferv's in_graph nodes as anchors:

```json
{
  "node_ids": [53, 62, 69, 72, 78]
}
```

### Expected response (200)

```json
{
  "nodes": [
    {
      "node_id": <new id>,
      "status": "recommendation",
      "rationale": "<5–10 word LLM rationale>",
      "place": {
        "place_id": "ChIJ…",
        "name": "<place name>",
        "neighborhood": "<…>",
        "rating": <float>,
        "price_level": <int|null>,
        "editorial_summary": "<…>"
      }
    }
    /* …up to N=5 entries… */
  ]
}
```

### Negative cases worth running

| Body | Expected | Why |
|---|---|---|
| `{}` or `{"node_ids": []}` | `400` `{"error":"node_ids is required."}` | View-level validation. |
| `{"node_ids": [40]}` | `500` `{"error":"…"}` (service `ValueError`) | Node 40 is a `recommendation`, not `in_graph` — fails the in-graph filter. |
| `{"node_ids": [99999]}` | `500` `{"error":"…"}` | Not ferv's node — fails the owner+status filter. |
| `{"node_ids": [53]}` (single anchor) | `200` with N=5 nodes | Single-list RRF degenerates to plain ranking; should still work. |

### Post-call DB check

```sql
SELECT id, status, rationale, created_at
FROM graph_graphnode
WHERE user_id = 2 AND status = 'recommendation'
ORDER BY created_at DESC LIMIT 5;

SELECT id, workflow, outcome, prompt_version, created_at
FROM recommendation_llminteractionlog
ORDER BY created_at DESC LIMIT 1;
```

The latest log row should have `workflow = 'node_based_recommendation'`, `outcome = 'success'`, and an `input_payload` JSON containing the anchor `node_ids`, `anchor_place_ids`, per-anchor candidate ID lists, and the fused top-K IDs.

---

## Out of scope

- Frontend wiring (separate ticket).
- The Pipeline-A optimization to dedupe the `excluded_place_ids` query across anchors (correctness-equivalent, premature).
- Auto-selecting anchor nodes from the user's graph (caller supplies `node_ids` explicitly).
- A new `EmbeddingVector` subclass or any provider work.