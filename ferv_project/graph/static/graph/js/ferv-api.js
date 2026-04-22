// ══════════════════════════════════════════════════════════════
//  ferv-api.js  — Comunicación con el backend Django
//
//  DEPENDE DE: ferv-mock.js (getMock)
// ══════════════════════════════════════════════════════════════

const MOCK_MODE = false; // ← Cambiar a false cuando el back esté listo

async function fetchGraph(query) {
  if (MOCK_MODE) {
    if (!query) return { nodes: [], edges: [] };
    await new Promise(r => setTimeout(r, 600));
    return getMock(query);
  }

  const url = query
    ? `/graph/api/fetch-graph/?q=${encodeURIComponent(query)}`
    : `/graph/api/fetch-graph/`;

  const resp = await fetch(url, {
    headers: { "Accept": "application/json" }
  });

  if (!resp.ok) throw new Error(`API error ${resp.status}`);
  const data = await resp.json();

  return {
    nodes: data.nodes.map(n => ({
      id:           String(n.id),
      place_id:     n.place?.place_id,
      name:         n.place?.name,
      neighborhood: n.place?.neighborhood,
      rating:       n.place?.rating,
      tags:         (n.place?.tags || []).map(t => t.tag),
      status:       n.status,
    })),
    edges: data.edges.map(e => ({
      from:   String(e.source?.id),
      to:     String(e.target?.id),
      weight: e.weight,
      reason: e.reason,
    }))
  };
}

async function addNodeToBackend(placeId) {
  if (MOCK_MODE) return;

  console.log("Enviando place_id:", placeId);

  const nodeId = parseInt(allNodes[placeId]?.id);
  const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] || "";
  const resp = await fetch("/graph/add-node/", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
    body: JSON.stringify({ node_id: nodeId })
  });

  const body = await resp.json();
  console.log("Respuesta add-node:", resp.status, body);

  if (!resp.ok) throw new Error(`add-node error ${resp.status}`);
}

async function removeNodeFromBackend(placeId) {
  if (MOCK_MODE) return;
  const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] || "";
  const resp = await fetch("/graph/remove-node/", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
    body: JSON.stringify({ place_id: placeId })
  });
  if (!resp.ok) throw new Error(`remove-node error ${resp.status}`);
}
