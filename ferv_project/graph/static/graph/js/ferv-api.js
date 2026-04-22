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

const MOCK_MODE = false;

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
function parseEdge(e) {
  return {
    from:   String(e.from_node),   // ID del GraphNode origen
    to:     String(e.to_node),     // ID del GraphNode destino
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

  const resp = await fetch("/graph/api/fetch_graph/", {
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


// ── addNodeToBackend ──────────────────────────────────────────
//  Promueve un GraphNode de "recommendation" a "in_graph".
//  POST /graph/add-node/ → { node_id: <int> }
//  Retorna { edge_ids: [...] }

async function addNodeToBackend(placeId) {
  if (MOCK_MODE) return;

  const nodeId = parseInt(allNodes[placeId]?.id);
  if (!nodeId) throw new Error(`No se encontró node_id para place_id=${placeId}`);

  console.log("add-node →", { node_id: nodeId, place_id: placeId });

  const resp = await fetch("/graph/add-node/", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrf() },
    body: JSON.stringify({ node_id: nodeId })
  });

  const body = await resp.json();
  console.log("add-node ←", resp.status, body);

  if (!resp.ok) throw new Error(`add-node error ${resp.status}: ${body.error}`);
  return body;
}


// ── removeNodeFromBackend ─────────────────────────────────────
//  Elimina un nodo del mapa personal del usuario.
//  DELETE /graph/api/delete_node/<node_id>
//
//  NOTA PARA EL COMPAÑERO DE BACK — este endpoint está vacío (pass).
//  Necesita implementarse así:
//
//    Recibe:  node_id en la URL
//    Debe:    1. Buscar GraphNode con id=node_id y user=request.user
//             2. Eliminar sus GraphEdges asociados (from_node o to_node)
//             3. Eliminar el GraphNode
//    Retorna: { "status": "ok" }
//    Errores: 404 si no existe, 403 si no pertenece al usuario

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