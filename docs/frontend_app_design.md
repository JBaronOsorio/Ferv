# Ferv — Frontend Architecture Design

**Status:** Draft for team review
**Scope:** Graph view frontend (`ferv_project/graph/static/graph/js/`)
**Companion doc:** `recommendation_service_design.md` (backend pipelines)

---

## 1. Goals

Define a clear module boundary for the graph view frontend so that:

- Each module has a single, nameable responsibility.
- State has one source of truth, derivable from backend data.
- New recommendation types (chat, context-based) can be added without restructuring.
- Rendering, orchestration, and UI chrome are not entangled.

The current code works, but several modules grew into catch-alls during the MVP sprint. This document captures the structure we're moving to.

---

## 2. Module overview

Ten modules, each with one job:

| Module | Responsibility | Writes state? |
|---|---|---|
| `ferv-config.js` | Static visual constants (palettes, neighborhood→color mapping, suggested-node styling, `trunc` helper) | No — purely declarative |
| `ferv-state.js` | Shared mutable globals: `allNodes`, `mapEdges`, `searchEdges`, `queries`, D3 handles (`simulation`, `svgG`, `selectedD`) | Declares; all other modules read/write |
| `ferv-api.js` | HTTP layer. Backend fetch, CSRF, and `parseNode`/`parseEdge` translation to D3-compatible shapes | No |
| `ferv-recommendations.js` | Recommendation pipeline dispatcher. Owns `requestRecommendations` (one-shot today; chat/context later). Merges results into `allNodes` and triggers redraw | Yes (`allNodes`, `searchEdges`, `queries`) |
| `ferv-controller.js` | Orchestration of graph mutations: `loadUserMap`, `saveNode`, `removeNode`. Coordinates backend call → state mutation → rerender | Yes (`allNodes`, `mapEdges`) |
| `ferv-map.js` | Pure rendering. `rerender()` + D3 force simulation setup. Reads from state, writes to the SVG | No (only D3 handles) |
| `ferv-filters.js` | Filter panel state + `getFilteredVisibleNodes`. Filters by `node.status` and active filter values | Yes (own `activeFilters`) |
| `ferv-panel.js` | Detail panel **component**. Owns its display logic and event wiring (add/remove buttons, confirmation modal). Delegates mutations to the controller | Yes (`selectedD`) |
| `ferv-chat.js` | Chat **component**. Owns message state, display, send button, and dispatch to recommendations | Yes (its own conversation state) |
| `ferv-ui.js` | App-level chrome: HUD counts, toasts, query chips, user menu. Shared UI utilities — not a catch-all | No |

### Design principles

- **Single source of truth: `node.status`.** Each node carries `status: "recommendation" | "in_graph"` from the backend. There are no parallel Sets shadowing this state. `allNodes` is keyed by `place_id` for O(1) lookup; `node.status` is what every visibility, color, and HUD decision reads.
- **Pull rendering.** State changes never auto-redraw. Every operation that mutates state ends with an explicit `rerender()` call. This keeps the data flow legible: callers know they triggered a render.
- **Module-per-concern, component for self-contained UI.** Shared utilities (toasts, HUD, user menu) live in `ferv-ui.js`. Self-contained UI surfaces with their own state and event wiring (panel, chat) are their own components. The UI module is *not* "all DOM" — it's the shared chrome layer.
- **Controller owns mutations.** Anything that changes `allNodes` or `mapEdges` based on backend coordination goes through `ferv-controller.js`. Components delegate to the controller; they do not call the API directly.
- **Recommendations are dispatched, not searched.** The user's text input is a recommendation request, not a search. The module is named after the pipeline (`ferv-recommendations.js`), and the public function (`requestRecommendations`) takes a recommendation type so future types layer in cleanly.

---

## 3. Shared structures and conventions

### 3.1 State shape

All defined in `ferv-state.js`, all globals:

```js
let allNodes    = {};   // place_id → node object (with x, y, status)
let mapEdges    = [];   // persistent edges between in_graph nodes (cyan)
let searchEdges = [];   // transient edges from recommendations (purple)
let queries     = [];   // history of recommendation prompts (chips)
let simulation  = null; // active D3 forceSimulation
let svgG        = null; // root SVG group for zoom transform
let selectedD   = null; // node currently shown in detail panel
```

### 3.2 Node shape

After `parseNode` (in `ferv-api.js`):

```js
{
  id:           "<GraphNode.id as string>",
  place_id:     "<Place.place_id>",
  name:         "<Place.name>",
  neighborhood: "<Place.neighborhood>",
  rating:       <Place.rating>,
  tags:         ["tag1", "tag2", ...],   // plain strings
  status:       "recommendation" | "in_graph",
  // populated at insertion time:
  x: <number>, y: <number>, vx: 0, vy: 0,
}
```

Node pinning (`fx`/`fy`) is **not** part of this design. Any existing pinning attempts in the code (e.g., the `fx = x` lines in `loadUserMap`) are to be removed during the refactor.

### 3.3 Edge shape

After `parseEdge`:

```js
{
  source: <node ref>,    // hydrated to actual node object on insertion
  target: <node ref>,
  weight: <float 0–1>,
  reason: "<short text>",
  type:   "map" | "search",
}
```

`type: "map"` edges are persistent (between `in_graph` nodes, returned by Pipeline B). `type: "search"` edges come from recommendation responses; the backend currently returns none, so this lane is reserved infrastructure.

### 3.4 Status conventions

Two values are observed in the frontend: `recommendation` and `in_graph`. The backend may also produce `discarded` and `removed` per the recommendation service design — those are filtered out at the API layer (or by the controller after a remove operation). The frontend never renders nodes in those states; they should not appear in `allNodes`.

### 3.5 Load order

No module system. Files must be loaded in this order so globals exist when referenced:

```
ferv-config.js → ferv-state.js → ferv-api.js
  → ferv-map.js → ferv-filters.js → ferv-recommendations.js
  → ferv-controller.js → ferv-panel.js → ferv-chat.js → ferv-ui.js
```

Rule of thumb: anything reading state loads after `ferv-state.js`; anything that may be called from `DOMContentLoaded` (controller, components) loads before `ferv-ui.js`.

### 3.6 Rendering convention

Any function that mutates `allNodes`, `mapEdges`, or `searchEdges` must call `rerender()` before returning (or before completing its async work). The render function reads filtered visible nodes from `getFilteredVisibleNodes()` — filter state is applied at render time, not at mutation time.

### 3.7 Color assignment

`ferv-config.js` exposes a static neighborhood→color map. Color assignment is deterministic by neighborhood and stable across sessions. `getSavedColor(neighborhood)` is the only public access; callers do not read the map directly.

---

## 4. Operation pipelines

Five pipelines cover everything the frontend does. Each names the entry point, the modules it touches, and the state it changes.

### 4.1 Initial load

**Trigger:** `DOMContentLoaded` in `ferv-ui.js` calls `loadUserMap()`.
**Owner:** `ferv-controller.js`.

1. Controller calls `fetchUserGraph()` → `GET /graph/api/fetch-graph/`.
2. Backend returns `in_graph` nodes + persistent edges for the user.
3. Controller hydrates `allNodes` (keyed by `place_id`) and `mapEdges` (with hydrated source/target node refs).
4. Controller calls `updateHUD()` and `rerender()`.

If the user's graph is empty, the empty state is shown and rendering is skipped.

### 4.2 One-shot recommendation

**Trigger:** User submits prompt via the recommendation input (or future chat send).
**Owner:** `ferv-recommendations.js`.

1. Dispatcher receives `(promptText, recommendationType)`. For MVP, type is always `"one_shot"`.
2. Dispatcher calls `fetchRecommendations(promptText)` → `GET /graph/api/one_shot_recommendation/<query>`.
3. Stale `recommendation`-status nodes from the previous request are removed from `allNodes` (in_graph nodes survive).
4. New nodes from the response are merged into `allNodes` with random initial coordinates near the canvas center. `status` is set from the backend response.
5. `searchEdges` is rebuilt from the response (currently always empty).
6. Dispatcher pushes the prompt onto `queries`, calls `updateQueryTags()`, `updateHUD()`, `rerender()`.

This pipeline corresponds to **Pipeline A** in the recommendation service design.

### 4.3 Add node to graph

**Trigger:** User clicks the add button in `ferv-panel.js`.
**Owner:** `ferv-controller.js`.

1. Panel calls `saveNode(placeId)`. Panel itself does not mutate state.
2. Controller calls `addNodeToBackend(placeId)` → `POST /graph/add-node/`.
3. Backend runs Pipeline B (edge construction) and returns created edge IDs + reasons + weights.
4. Controller sets `node.status = "in_graph"` and pushes the new edges into `mapEdges` (with hydrated source/target node refs).
5. Controller calls `updateHUD()` and `rerender()`.

If the backend call fails, the controller logs and aborts; node status stays `"recommendation"`.

This pipeline corresponds to **Pipeline B** in the recommendation service design.

### 4.4 Remove node from graph

**Trigger:** User confirms removal in the panel's confirmation modal.
**Owner:** `ferv-controller.js`.

1. Panel calls `removeNode(placeId)`.
2. Controller filters `mapEdges` to drop any edge touching this node.
3. Controller calls `removeNodeFromBackend(placeId)` → `DELETE /graph/api/delete_node/<id>`.
4. On success, controller deletes the node from `allNodes`.
5. Controller closes the panel, calls `updateHUD()` and `rerender()`.

### 4.5 Filtering

**Trigger:** User toggles tags, neighborhood, or rating in the filter panel.
**Owner:** `ferv-filters.js`.

Filtering is applied at render time, not at mutation time. `getFilteredVisibleNodes()` is called by `rerender()` and applies:

- `in_graph` nodes pass `matchesActiveFilters` (tags, neighborhood, minRating).
- `recommendation` nodes always pass — the user's current request is never filtered out.

`applyFilters` and `clearFilters` mutate `activeFilters` and call `rerender()` directly.

---

## 5. Component contracts

Components are self-contained UI surfaces with their own rendering and event wiring.

### 5.1 Panel (`ferv-panel.js`)

- **Public:** `openPanel(d, edges)`, `closePanel()`.
- **Reads:** `selectedD`, node status from the node passed in.
- **Mutates:** `selectedD` only.
- **Delegates:** `saveNode` and `removeNode` to the controller. Never calls the API.

### 5.2 Chat (`ferv-chat.js`)

- **Public:** `chatAddMsg(text, type)`, `chatSend()`.
- **Owns:** message DOM state inside `#chatMessages`, conversation history (when implemented).
- **Delegates:** message dispatch to `ferv-recommendations.js` once the chat backend lands.

Chat is currently a stub — splitting it now means the future chat endpoint slots in without touching `ferv-ui.js`.

---

## 6. Known issues to address

These exist in the current code and should be cleaned up as part of this refactor:

- **Pinning attempts must be removed.** `loadUserMap` currently assigns `fx`/`fy` on `in_graph` nodes. Pinning is not part of the design — drop these lines.
- **Tag filter never matches.** `ferv-filters.js:matchesActiveFilters` compares `t.tag === tag`, but tags are plain strings after `parseNode`. Fix: compare `t === tag`.
- **`crossReason()` is dead code** in `ferv-map.js`. Its caller is commented out and `searchEdges` arrives empty from the API. Remove.
- **`nodeColor()` is dead code** in `ferv-config.js`. Referenced removed `savedSet`. Remove.
- **`graph.js` is dead code.** Standalone D3 example, not loaded by the ferv system. Remove.
- **`MOCK_MODE` is a hardcoded flag** in `ferv-api.js`. Either gate behind a build/env mechanism or document its intended use clearly. Risk: silently ships fake data if toggled.
- **`GraphNode.rationale` is not surfaced.** The backend design proposes a per-node rationale field. `parseNode` does not extract it and the panel does not display it. Wire up when the field is populated.
- **Stale comment about `delete_node`** in `ferv-api.js` claims the backend is unimplemented. It is implemented. Update or remove the comment.

---

## 7. Open questions

- **Search edges (Pipeline A).** Should the recommendation response carry inter-recommendation edges (e.g., "these three are clustered because…")? If yes, the API and `ferv-recommendations.js` need to populate `searchEdges`. If no, drop the `type: "search"` infrastructure.
- **`recommendation` node lifetime.** Currently cleared on the next recommendation request. Should they instead persist across requests until explicitly dismissed?
- **Filter scope.** Filters apply to `in_graph` nodes only. Should they also apply to recommendations, or is "current request always visible" the intended behavior?
- **Color map persistence.** Static neighborhood→color mapping makes assignments stable. Do we author the full map up front, or fall back to a deterministic hash for unknown neighborhoods?

---

## 8. Build order for the refactor

1. **Move `saveNode`/`removeNode`/`loadUserMap` into `ferv-controller.js`.** Update load order. Update `ferv-ui.js` `DOMContentLoaded` to call `loadUserMap` from the controller. Drop the `fx`/`fy` pinning lines.
2. **Rename `ferv-search.js` → `ferv-recommendations.js`** and `runSearch` → `requestRecommendations(prompt, type="one_shot")`. Update HTML script tags and event listeners.
3. **Extract chat into `ferv-chat.js`.** Move `chatAddMsg`, `chatSend`, and the chat `DOMContentLoaded` block out of `ferv-ui.js`.
4. **Make `neighborhoodColorMap` static** in `ferv-config.js`. Remove `paletteIndex` mutation.
5. **Delete dead code** (§6).
6. **Fix the tag filter bug** (§6).

Each step is independently shippable; the refactor doesn't require a single big PR.
