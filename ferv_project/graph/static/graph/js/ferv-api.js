// ══════════════════════════════════════════════════════════════
//  ferv-api.js  — Comunicación con el backend Django
//
//  ENDPOINTS:
//    GET  /graph/api/fetch_graph/                     → mapa guardado del usuario
//    GET  /graph/api/one_shot_recommendation/<query>  → recomendaciones nuevas
//    POST /graph/add-node/                            → guardar nodo en mapa
//    DELETE /graph/api/delete_node/<node_id>          → eliminar nodo del mapa
//
//  DEPENDE DE: ferv-mock.js (getMock), ferv-state.js (allNodes)
// ══════════════════════════════════════════════════════════════

const MOCK_MODE = false; // set to true para usar datos mock y evitar llamadas al backend durante el desarrollo del frontend

// ── Helpers ──────────────────────────────────────────────────

function getCsrf() {
  return document.cookie.match(/csrftoken=([^;]+)/)?.[1] || "";
}

// Transforma un nodo del backend al formato que usa D3
function parseNode(n) {
  return {
    id:           String(n.id),
    place_id:     n.place?.place_id,
    name:         n.place?.name,
    neighborhood: n.place?.neighborhood,
    rating:       n.place?.rating,
    tags:         (n.place?.tags || []).map(t => t.tag),
    status:       n.status,   // "in_graph" | "recommendation"
  };
}

// Transforma un edge del backend al formato que usa D3
// El back retorna source y target como objetos completos, no IDs
function parseEdge(e) {
  return {
    from:   String(e.source?.id),
    to:     String(e.target?.id),
    weight: e.weight,
    reason: e.reason,
  };
}


// ── fetchUserGraph ────────────────────────────────────────────
//  Carga el mapa personal guardado del usuario (sin query).
//  Llama a GET /graph/api/fetch_graph/ sin parámetros.
//  Se usa en loadUserMap() al entrar al mapa.

async function fetchUserGraph() {
  if (MOCK_MODE) return { nodes: [], edges: [] };

  const resp = await fetch("/graph/api/fetch-graph/", {
    headers: { "Accept": "application/json" }
  });
  if (!resp.ok) throw new Error(`fetch_graph error ${resp.status}`);
  const data = await resp.json();

  return {
    nodes: data.nodes.map(parseNode),
    edges: data.edges.map(parseEdge),
  };
}


// ── fetchRecommendations ──────────────────────────────────────
//  Pide recomendaciones nuevas para una query de texto.
//  Llama a GET /graph/api/one_shot_recommendation/<query>
//  Se usa en runSearch() cuando el usuario escribe en el buscador.

async function fetchRecommendations(query) {
  if (MOCK_MODE) {
    await new Promise(r => setTimeout(r, 600));
    return getMock(query);
  }

  const resp = await fetch(
    `/graph/api/one_shot_recommendation/${encodeURIComponent(query)}`,
    { headers: { "Accept": "application/json" } }
  );
  if (!resp.ok) throw new Error(`one_shot_recommendation error ${resp.status}`);
  const data = await resp.json();

  // one_shot_recommendation retorna { query, results: [...nodes] }
  // No retorna edges — los edges de búsqueda los genera el front localmente
  return {
    nodes: data.results.map(parseNode),
    edges: [],
  };
}


// ── addNodeToMap ──────────────────────────────────────────────
//  Promueve un GraphNode de "recommendation" a "in_graph".
//  POST /graph/add-node/ → { node_id: <int> }
//  Retorna array de edges: [{ source_id, target_id, weight, reason }]

async function addNodeToMap(placeId) {
  if (MOCK_MODE) return [];

  const nodeId = parseInt(allNodes[placeId]?.id);
  if (!nodeId) throw new Error(`No se encontró node_id para place_id=${placeId}`);

  const resp = await fetch("/graph/add-node/", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrf() },
    body: JSON.stringify({ node_id: nodeId })
  });

  const body = await resp.json();
  if (!resp.ok) throw new Error(`add-node error ${resp.status}: ${body.error}`);
  return body.edges || [];
}


// ── fetchDiscoveryList ────────────────────────────────────────
//  Devuelve los nodos con status='discovery' del usuario.
//  GET /graph/api/discovery-list/

async function fetchDiscoveryList() {
  const resp = await fetch("/graph/api/discovery-list/", {
    headers: { "Accept": "application/json" }
  });
  if (!resp.ok) throw new Error(`discovery-list error ${resp.status}`);
  const data = await resp.json();
  return { nodes: data.nodes.map(parseNode) };
}


// ── addToDiscoveryAPI ─────────────────────────────────────────
//  Mueve un nodo a la lista de descubrimiento.
//  POST /graph/api/add-to-discovery/ → { node_id: <int> }
//  Lanza error con .status=409 si el lugar ya está en la lista.

async function addToDiscoveryAPI(nodeId) {
  const resp = await fetch("/graph/api/add-to-discovery/", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrf() },
    body: JSON.stringify({ node_id: nodeId })
  });
  const body = await resp.json().catch(() => ({}));
  if (resp.status === 409) {
    const err = new Error(body.error || "Ya en lista");
    err.status = 409;
    throw err;
  }
  if (!resp.ok) throw new Error(`add-to-discovery error ${resp.status}: ${body.error}`);
  return body;
}


// ── markVisitedAPI ────────────────────────────────────────────
//  Marca un nodo de discovery como visited y corre Pipeline B.
//  PATCH /graph/api/mark-visited/<nodeId>/
//  Retorna { status, node, edges: [{source_id, target_id, weight, reason}] }

async function markVisitedAPI(nodeId) {
  const resp = await fetch(`/graph/api/mark-visited/${nodeId}/`, {
    method: "PATCH",
    headers: { "X-CSRFToken": getCsrf() }
  });
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(`mark-visited error ${resp.status}: ${body.error}`);
  return body;
}


// ── deleteNodeById ────────────────────────────────────────────
//  Elimina un nodo directamente por su GraphNode ID.
//  Usado por la lista de descubrimiento (nodos no presentes en allNodes).
//  DELETE /graph/api/delete_node/<nodeId>

async function deleteNodeById(nodeId) {
  const resp = await fetch(`/graph/api/delete_node/${nodeId}`, {
    method: "DELETE",
    headers: { "X-CSRFToken": getCsrf() },
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(`delete_node error ${resp.status}: ${body.error || ""}`);
  }
}


// ── removeNodeFromBackend ─────────────────────────────────────
//  Elimina un nodo in_graph/visited del mapa personal (requiere que el nodo
//  esté en allNodes para resolver el node_id). Para nodos fuera del state
//  (discovery) usar deleteNodeById.
//  DELETE /graph/api/delete_node/<node_id>

async function removeNodeFromBackend(placeId) {
  if (MOCK_MODE) return;

  const nodeId = parseInt(allNodes[placeId]?.id);
  if (!nodeId) throw new Error(`No se encontró node_id para place_id=${placeId}`);

  const resp = await fetch(`/graph/api/delete_node/${nodeId}`, {
    method: "DELETE",
    headers: { "X-CSRFToken": getCsrf() },
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(`delete_node error ${resp.status}: ${body.error || ""}`);
  }
}