// ══════════════════════════════════════════════════════════════
//  ferv-map.js  — Lógica del mapa de nodos
//
//  SECCIONES:
//    1. CONFIG — constantes visuales y helpers
//    2. MOCK DATA — datos de prueba (reemplazar con API real)
//    3. ESTADO GLOBAL — allNodes, savedSet, edges, etc.
//    4. API — aquí conectas el backend Django
//    5. BÚSQUEDA — runSearch()
//    6. MAPA — saveNode(), removeNode(), rerender()
//    7. PANEL — openPanel(), closePanel()
//    8. HUD & UI helpers
// ══════════════════════════════════════════════════════════════


// ── 1. CONFIG ────────────────────────────────────────────────

// Color de nodo cuando está SUGERIDO (no guardado)
// Un solo color neutro para todos — sin importar el barrio
const SUGGESTED_COLOR = {
  stroke: "rgba(255,255,255,0.18)",
  fill:   "rgba(255,255,255,0.04)",
  text:   "rgba(255,255,255,0.35)",
};

// Paleta de colores para nodos GUARDADOS
// Se asigna dinámicamente por barrio la primera vez que se guarda un nodo de ese barrio.
// Si llegan barrios nuevos del backend, automáticamente toman el siguiente color disponible.
const SAVED_PALETTE = [
  // "#3dd6c8",  // cyan  
  "#9b6bfa",  // purple
  "#fa6b8a",  // pink  
  "#6bfac8",  // mint  
  // "#fac86b",  // amber 
  // "#6baafa",  // blue
  // "#fa9b6b",  // orange
  // "#c8fa6b",  // lime
  // "#fa6bfa",  // fuchsia
  // "#6bfafa",  // sky
];

// Mapa dinámico: neighborhood → color asignado
// Se puebla automáticamente en saveNode() la primera vez que se guarda un nodo de ese barrio.
const neighborhoodColorMap = {};
let paletteIndex = 0;

function getSavedColor(neighborhood) {
  if (!neighborhood) return SAVED_PALETTE[0];
  if (!neighborhoodColorMap[neighborhood]) {
    neighborhoodColorMap[neighborhood] = SAVED_PALETTE[paletteIndex % SAVED_PALETTE.length];
    paletteIndex++;
  }
  return neighborhoodColorMap[neighborhood];
}

// Devuelve el color correcto según el estado del nodo:
//   - Sugerido → color neutro
//   - Guardado → color del barrio (asignado dinámicamente)
function nodeColor(d) {
  if (savedSet.has(d.place_id)) return getSavedColor(d.neighborhood);
  return null; // null = usar SUGGESTED_COLOR
}

function trunc(s, n) { return s && s.length > n ? s.slice(0, n) + "…" : (s || ""); }


// ── 2. MOCK DATA ─────────────────────────────────────────────
//
//  TODO: Eliminar esta sección cuando conectes el backend.
//  La función fetchGraph() (sección 4) ya tiene la estructura
//  para llamar a /graph/api/?q=...

const MOCK = {
  cafe: {
    nodes: [
      { id:"c1", place_id:"p001", name:"Pergamino Café",  neighborhood:"El Poblado", rating:4.8, tags:["especialidad","coworking","wifi"] },
      { id:"c2", place_id:"p002", name:"Café Velvet",     neighborhood:"Laureles",   rating:4.6, tags:["tercera ola","tranquilo","libros"] },
      { id:"c3", place_id:"p003", name:"Amor Perfecto",   neighborhood:"El Poblado", rating:4.7, tags:["origen","brunch","jardín"] },
      { id:"c4", place_id:"p004", name:"Azahar Café",     neighborhood:"Envigado",   rating:4.5, tags:["espresso","minimal","trabajo"] },
      { id:"c5", place_id:"p005", name:"Café Zeppelin",   neighborhood:"Laureles",   rating:4.4, tags:["música suave","lectura","plantas"] },
    ],
    edges: [
      { from:"c1", to:"c2", weight:0.88, reason:"Specialty coffee culture" },
      { from:"c1", to:"c3", weight:0.82, reason:"Single origin focus" },
      { from:"c2", to:"c5", weight:0.75, reason:"Quiet study atmosphere" },
      { from:"c3", to:"c4", weight:0.71, reason:"Poblado coffee scene" },
      { from:"c2", to:"c4", weight:0.60, reason:"Minimalist aesthetic" },
    ]
  },
  bar: {
    nodes: [
      { id:"b1", place_id:"p010", name:"El Social",       neighborhood:"El Poblado",  rating:4.5, tags:["cócteles","jazz","vivo"] },
      { id:"b2", place_id:"p011", name:"Son Havana",      neighborhood:"Laureles",    rating:4.7, tags:["salsa","cubano","bailar"] },
      { id:"b3", place_id:"p012", name:"La Octava",       neighborhood:"Envigado",    rating:4.3, tags:["rock","cervezas","indie"] },
      { id:"b4", place_id:"p013", name:"Envy Rooftop",    neighborhood:"El Poblado",  rating:4.6, tags:["vistas","electrónica","terraza"] },
      { id:"b5", place_id:"p014", name:"Vintrash",        neighborhood:"Laureles",    rating:4.4, tags:["punk","vinilo","underground"] },
    ],
    edges: [
      { from:"b1", to:"b2", weight:0.85, reason:"Live music scene" },
      { from:"b1", to:"b4", weight:0.79, reason:"Poblado nightlife" },
      { from:"b2", to:"b3", weight:0.72, reason:"Dance and music energy" },
      { from:"b3", to:"b5", weight:0.88, reason:"Alternative music lovers" },
    ]
  },
  sushi: {
    nodes: [
      { id:"s1", place_id:"p020", name:"Osaki Sushi",     neighborhood:"El Poblado", rating:4.7, tags:["omakase","sake","íntimo"] },
      { id:"s2", place_id:"p021", name:"Matsu",            neighborhood:"Laureles",   rating:4.5, tags:["ramen","izakaya","casual"] },
      { id:"s3", place_id:"p022", name:"Nori",             neighborhood:"Envigado",   rating:4.4, tags:["fusión","nikkei","moderno"] },
      { id:"s4", place_id:"p023", name:"Kai Robata",       neighborhood:"El Poblado", rating:4.6, tags:["parrilla","japonesa","barra"] },
      { id:"s5", place_id:"p024", name:"Tanuki",           neighborhood:"Laureles",   rating:4.3, tags:["ramen","dumplings","callejero"] },
    ],
    edges: [
      { from:"s1", to:"s4", weight:0.90, reason:"Premium Japanese experience" },
      { from:"s1", to:"s3", weight:0.75, reason:"Nikkei influence" },
      { from:"s2", to:"s5", weight:0.82, reason:"Casual ramen culture" },
      { from:"s3", to:"s4", weight:0.68, reason:"Modern Japanese fusion" },
    ]
  }
};

function getMock(q) {
  const lq = (q || "").toLowerCase();
  if (lq.includes("café") || lq.includes("cafe") || lq.includes("tranquilo") || lq.includes("trabajo")) return MOCK.cafe;
  if (lq.includes("bar") || lq.includes("noche") || lq.includes("música") || lq.includes("musica") || lq.includes("copa")) return MOCK.bar;
  if (lq.includes("sushi") || lq.includes("jap") || lq.includes("ramen")) return MOCK.sushi;
  return MOCK.bar;
}


// ── 3. ESTADO GLOBAL ─────────────────────────────────────────

let allNodes    = {};        // place_id → node object (con x, y)
let savedSet    = new Set(); // place_ids guardados en el mapa personal
let suggestIds  = new Set(); // place_ids de la búsqueda actual
let mapEdges    = [];        // edges entre nodos guardados (persistentes, cyan)
let searchEdges = [];        // edges de la búsqueda actual (temporales, morado)
let queries     = [];        // historial de queries para los chips del canvas
let simulation  = null;
let svgG        = null;
let selectedD   = null;      // nodo seleccionado en el panel


// ── 4. API ───────────────────────────────────────────────────
//
//  Cambiar MOCK_MODE = false cuando el backend esté listo.
//  fetchGraph() y addNodeToBackend() ya tienen la estructura correcta.

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

  // LOG TEMPORAL ***************************************************
  console.log("Enviando place_id:", placeId);
  
  const nodeId = parseInt(allNodes[placeId]?.id);  


  const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] || "";
  const resp = await fetch("/graph/add-node/", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
    body: JSON.stringify({ node_id: nodeId })
  });

  // LOG TEMPORAL
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


// ── 5. BÚSQUEDA ──────────────────────────────────────────────

async function runSearch() {
  const q = document.getElementById("q-input").value.trim();
  if (!q) return;

  document.getElementById("spinner").classList.add("show");
  document.getElementById("search-btn").disabled = true;
  document.getElementById("empty-state").style.display = "none";
  closePanel();

  try {
    const data = await fetchGraph(q);

    const W = document.querySelector(".canvas-wrap").clientWidth;
    const H = document.querySelector(".canvas-wrap").clientHeight;

    suggestIds = new Set();
    data.nodes.forEach(n => {
      suggestIds.add(n.place_id);
      if (!allNodes[n.place_id]) {
        allNodes[n.place_id] = {
          ...n,
          x: W / 2 + (Math.random() - 0.5) * 200,
          y: H / 2 + (Math.random() - 0.5) * 200,
          vx: 0, vy: 0,
        };
      }
      if (n.status === 'in_graph') {
        getSavedColor(n.neighborhood); // asignar color al barrio
        savedSet.add(n.place_id);
        allNodes[n.place_id].fx = allNodes[n.place_id].x;
        allNodes[n.place_id].fy = allNodes[n.place_id].y;
      }

    });

    searchEdges = data.edges
      .map(e => {
        const srcNode = data.nodes.find(n => n.id === e.from);
        const tgtNode = data.nodes.find(n => n.id === e.to);
        return {
          source: srcNode ? allNodes[srcNode.place_id] : null,
          target: tgtNode ? allNodes[tgtNode.place_id] : null,
          weight: e.weight,
          reason: e.reason,
          type: "search",
        };
      })
      .filter(e => e.source && e.target);

    if (!queries.includes(q)) queries.push(q);
    updateQueryTags();
    rerender();
    document.getElementById("hud").style.display = "flex";
    updateHUD();

  } catch (err) {
    showToast("Error al buscar: " + err.message);
    console.error(err);
  }

  document.getElementById("spinner").classList.remove("show");
  document.getElementById("search-btn").disabled = false;
}

document.getElementById("q-input").addEventListener("keydown", e => {
  if (e.key === "Enter") runSearch();
});


// ── 6. MAPA ──────────────────────────────────────────────────

async function saveNode(placeId) {
  if (savedSet.has(placeId)) return;
  const node = allNodes[placeId];
  if (!node) return;

  // Asignar color de barrio ANTES de renderizar
  // Si el barrio ya tiene color asignado no hace nada, si es nuevo toma el siguiente de la paleta
  getSavedColor(node.neighborhood);

  savedSet.add(placeId);
  node.fx = node.x;
  node.fy = node.y;

  // Crear edges cruzados con todos los ya guardados
  const savedArr = [...savedSet].filter(id => id !== placeId);
  savedArr.forEach(otherId => {
    const other = allNodes[otherId];
    if (!other) return;
    const exists = mapEdges.some(e =>
      (e.source.place_id === placeId && e.target.place_id === otherId) ||
      (e.source.place_id === otherId && e.target.place_id === placeId)
    );
    if (!exists) {
      mapEdges.push({
        source: node,
        target: other,
        weight: 0.7,
        reason: crossReason(node, other),
        type: "map",
      });
    }
  });

  try {
    await addNodeToBackend(placeId);
  } catch (err) {
    console.warn("No se pudo guardar en el backend:", err);
  }

  updateHUD();
  rerender();
  showToast(`"${trunc(node.name, 22)}" fijado en tu mapa`);
}

async function removeNode(placeId) {
  if (!savedSet.has(placeId)) return;
  const node = allNodes[placeId];
  if (!node) return;

  savedSet.delete(placeId);
  node.fx = null;
  node.fy = null;

  // Eliminar edges de mapa que involucren este nodo
  mapEdges = mapEdges.filter(e =>
    e.source.place_id !== placeId && e.target.place_id !== placeId
  );

  // Nota: NO borramos el color del barrio en neighborhoodColorMap.
  // Si el usuario vuelve a guardar otro nodo del mismo barrio, mantiene el mismo color.

  try {
    await removeNodeFromBackend(placeId);
  } catch (err) {
    console.warn("No se pudo eliminar en el backend:", err);
  }

  closePanel();
  updateHUD();
  rerender();
  showToast(`"${trunc(node.name, 22)}" eliminado del mapa`);
}

function crossReason(a, b) {
  if (a.neighborhood === b.neighborhood) return `Ambos en ${a.neighborhood}`;
  const shared = (a.tags || []).filter(t => (b.tags || []).includes(t));
  if (shared.length) return shared[0];
  return "En tu mapa";
}

function rerender() {
  const svg = d3.select("#ferv-svg");
  svg.selectAll("*").remove();

  const W = document.querySelector(".canvas-wrap").clientWidth;
  const H = document.querySelector(".canvas-wrap").clientHeight;

  svg.append("defs").html(`
    <marker id="arr-s" markerWidth="5" markerHeight="5" refX="4" refY="2.5" orient="auto">
      <path d="M0,0 L0,5 L5,2.5 z" fill="rgba(155,107,250,0.35)"/>
    </marker>
    <marker id="arr-m" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
      <path d="M0,0 L0,7 L7,3.5 z" fill="#3dd6c8"/>
    </marker>
  `);

  svgG = svg.append("g");
  svg.call(
    d3.zoom().scaleExtent([0.15, 4]).on("zoom", e => svgG.attr("transform", e.transform))
  );

  const isSaved = d => savedSet.has(d.place_id);

  const visibleNodes = Object.values(allNodes).filter(n =>
    isSaved(n) || suggestIds.has(n.place_id)
  );

  const visiblePids = new Set(visibleNodes.map(n => n.place_id));
  const allEdges = [...searchEdges, ...mapEdges];
  const visibleEdges = allEdges.filter(e =>
    visiblePids.has(e.source?.place_id) && visiblePids.has(e.target?.place_id)
  );

  // ── Simulación de fuerzas ──
  if (simulation) simulation.stop();
  simulation = d3.forceSimulation(visibleNodes)
    .force("link", d3.forceLink(visibleEdges)
      .id(d => d.place_id)
      .distance(d => d.type === "map" ? 100 : 130 - d.weight * 50)
      .strength(d => d.type === "map" ? 0.8 : 0.4)
    )
    .force("charge", d3.forceManyBody().strength(-260))
    .force("center", d3.forceCenter(W / 2, H / 2).strength(0.04))
    .force("collision", d3.forceCollide(56))
    .alphaDecay(0.025);

  visibleNodes.forEach(n => {
    if (isSaved(n)) { n.fx = n.fx ?? n.x; n.fy = n.fy ?? n.y; }
    else            { n.fx = null; n.fy = null; }
  });

  // ── Edges de mapa (cyan, entre guardados) ──
  const mapEdgeEls = svgG.append("g").selectAll("line")
    .data(visibleEdges.filter(e => e.type === "map")).join("line")
    .attr("stroke", "#3dd6c8")
    .attr("stroke-width", 2.5)
    .attr("stroke-opacity", 0.55)
    .attr("marker-end", "url(#arr-m)");

  const mapEdgeLabelEls = svgG.append("g").selectAll("text")
    .data(visibleEdges.filter(e => e.type === "map")).join("text")
    .attr("fill", "#3dd6c8").attr("fill-opacity", 0.55)
    .attr("font-size", "9.5").attr("font-family", "'DM Mono', monospace")
    .attr("text-anchor", "middle").attr("pointer-events", "none")
    .text(d => trunc(d.reason, 26));

  // ── Edges de búsqueda (morado tenue) ──
  const searchEdgeEls = svgG.append("g").selectAll("line")
    .data(visibleEdges.filter(e => e.type === "search")).join("line")
    .attr("stroke", d => `rgba(155,107,250,${0.10 + d.weight * 0.25})`)
    .attr("stroke-width", d => 0.7 + d.weight * 1.4)
    .attr("stroke-dasharray", d => d.weight > 0.78 ? "none" : "4,5")
    .attr("marker-end", "url(#arr-s)");

  const searchEdgeLabelEls = svgG.append("g").selectAll("text")
    .data(visibleEdges.filter(e => e.type === "search" && e.weight > 0.72)).join("text")
    .attr("fill", "rgba(155,107,250,0.38)")
    .attr("font-size", "9").attr("font-family", "'DM Mono', monospace")
    .attr("text-anchor", "middle").attr("pointer-events", "none")
    .text(d => trunc(d.reason, 24));

  // ── Nodos ──
  const nodeEls = svgG.append("g").selectAll("g")
    .data(visibleNodes, d => d.place_id).join("g")
    .style("cursor", "pointer")
    .call(d3.drag()
      .on("start", (ev, d) => { if (!ev.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on("drag",  (ev, d) => { d.fx = ev.x; d.fy = ev.y; })
      .on("end",   (ev, d) => { if (!ev.active) simulation.alphaTarget(0); if (!isSaved(d)) { d.fx = null; d.fy = null; } })
    )
    .on("click", (ev, d) => { ev.stopPropagation(); openPanel(d, visibleEdges); });

  // Anillo exterior punteado — solo guardados
  nodeEls.filter(isSaved).append("circle")
    .attr("r", 50).attr("fill", "none")
    .attr("stroke", d => getSavedColor(d.neighborhood))
    .attr("stroke-width", 0.7).attr("stroke-opacity", 0.25)
    .attr("stroke-dasharray", "3,6");

  // Círculo principal
  nodeEls.append("circle")
    .attr("r", d => isSaved(d) ? 40 : 36)
    .attr("fill", d => isSaved(d)
      ? getSavedColor(d.neighborhood) + "28"   // color del barrio con alpha bajo
      : SUGGESTED_COLOR.fill                   // gris neutro
    )
    .attr("stroke", d => isSaved(d)
      ? getSavedColor(d.neighborhood)
      : SUGGESTED_COLOR.stroke
    )
    .attr("stroke-width", d => isSaved(d) ? 2.2 : 0.8)
    .attr("stroke-opacity", d => isSaved(d) ? 1 : 1);

  // Estrella — guardados
  nodeEls.filter(isSaved).append("text")
    .attr("y", -30).attr("text-anchor", "middle")
    .attr("font-size", "11").attr("fill", "#fac86b")
    .attr("pointer-events", "none").text("★");

  // Nombre
  nodeEls.append("text")
    .attr("y", 3).attr("text-anchor", "middle")
    .attr("font-size", "11.5").attr("font-weight", "500")
    .attr("font-family", "'DM Sans', sans-serif")
    .attr("fill", d => isSaved(d)
      ? getSavedColor(d.neighborhood)   // color vivo del barrio
      : SUGGESTED_COLOR.text            // blanco tenue
    )
    .attr("pointer-events", "none")
    .text(d => trunc(d.name, 13));

  // Barrio
  nodeEls.append("text")
    .attr("y", 17).attr("text-anchor", "middle").attr("font-size", "9.5")
    .attr("fill", d => isSaved(d) ? "#666" : "#333")
    .attr("font-family", "'DM Mono', monospace")
    .attr("pointer-events", "none")
    .text(d => trunc(d.neighborhood, 13));

  // Label "en mi mapa" — solo guardados
  nodeEls.filter(isSaved).append("text")
    .attr("y", 29).attr("text-anchor", "middle")
    .attr("font-size", "8.5").attr("fill", "#3dd6c8").attr("fill-opacity", "0.7")
    .attr("font-family", "'DM Mono', monospace")
    .attr("pointer-events", "none").text("en mi mapa");

  // ── Tick de simulación ──
  function edgeEnd(d, r = 44) {
    const dx = d.target.x - d.source.x;
    const dy = d.target.y - d.source.y;
    const dist = Math.hypot(dx, dy) || 1;
    return { x2: d.target.x - (dx / dist) * r, y2: d.target.y - (dy / dist) * r };
  }

  simulation.on("tick", () => {
    mapEdgeEls
      .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
      .each(function(d) { const e = edgeEnd(d, 44); d3.select(this).attr("x2", e.x2).attr("y2", e.y2); });

    mapEdgeLabelEls
      .attr("x", d => (d.source.x + d.target.x) / 2)
      .attr("y", d => (d.source.y + d.target.y) / 2 - 6);

    searchEdgeEls
      .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
      .each(function(d) { const e = edgeEnd(d, 40); d3.select(this).attr("x2", e.x2).attr("y2", e.y2); });

    searchEdgeLabelEls
      .attr("x", d => (d.source.x + d.target.x) / 2)
      .attr("y", d => (d.source.y + d.target.y) / 2 - 5);

    nodeEls.attr("transform", d => `translate(${d.x},${d.y})`);
  });

  svg.on("click", () => closePanel());
}


// ── 7. PANEL ─────────────────────────────────────────────────

function openPanel(d, edges) {
  selectedD = d;
  const isSaved = savedSet.has(d.place_id);

  // Color del badge: si está guardado usa el color del barrio, si no un neutro
  const badgeColor = isSaved ? getSavedColor(d.neighborhood) : "rgba(255,255,255,0.35)";

  const badge = document.getElementById("panel-badge");
  badge.textContent = `• ${d.neighborhood || "Medellín"}`;
  badge.style.color = badgeColor;
  badge.style.background = badgeColor + "15";
  badge.style.borderColor = badgeColor + "33";

  document.getElementById("panel-name").textContent = d.name;
  document.getElementById("panel-neighborhood").textContent = d.neighborhood || "Medellín";

  const tagsEl = document.getElementById("panel-tags");
  tagsEl.innerHTML = "";
  (d.tags || []).forEach(t => {
    const s = document.createElement("span");
    s.className = "tag";
    s.textContent = t;
    tagsEl.appendChild(s);
  });

  document.getElementById("panel-rating").textContent = d.rating ? `★ ${d.rating.toFixed(1)}` : "";

  // Conexiones
  const conns = edges.filter(e =>
    e.source?.place_id === d.place_id || e.target?.place_id === d.place_id
  );
  const connEl   = document.getElementById("panel-connections");
  const connList = document.getElementById("conn-list");
  if (conns.length) {
    connEl.style.display = "block";
    connList.innerHTML = conns.map(e => {
      const other     = e.source.place_id === d.place_id ? e.target : e.source;
      const otherSaved = savedSet.has(other?.place_id);
      const col       = otherSaved ? getSavedColor(other?.neighborhood) : "rgba(255,255,255,0.25)";
      return `<div class="conn-item">
        <div class="conn-dot" style="background:${col};opacity:${otherSaved ? 1 : 0.5}"></div>
        <span style="color:${col}">${trunc(other?.name || "", 17)}</span>
        <span style="color:#444;font-size:10px"> · ${trunc(e.reason, 20)}</span>
      </div>`;
    }).join("");
  } else {
    connEl.style.display = "none";
  }

  const addBtn    = document.getElementById("panel-add-btn");
  const removeBtn = document.getElementById("panel-remove-btn");

  if (isSaved) {
    addBtn.textContent  = "✓ En tu mapa";
    addBtn.className    = "btn-add saved";
    addBtn.disabled     = true;
    removeBtn.classList.add("visible");
  } else {
    addBtn.textContent  = "+ Agregar a mi mapa";
    addBtn.className    = "btn-add";
    addBtn.disabled     = false;
    removeBtn.classList.remove("visible");
  }

  document.getElementById("detail-panel").classList.add("open");
}

function closePanel() {
  document.getElementById("detail-panel").classList.remove("open");
  selectedD = null;
}

document.getElementById("panel-add-btn").addEventListener("click", () => {
  if (!selectedD || savedSet.has(selectedD.place_id)) return;
  saveNode(selectedD.place_id);
  closePanel();
});

document.getElementById("panel-remove-btn").addEventListener("click", () => {
  if (!selectedD) return;
  removeNode(selectedD.place_id);
});


// ── 8. HUD & UI HELPERS ──────────────────────────────────────

function updateHUD() {
  document.getElementById("hud-suggested").textContent = Object.keys(allNodes).length - savedSet.size;
  document.getElementById("hud-saved").textContent = savedSet.size;
}

function updateQueryTags() {
  const el = document.getElementById("query-tags");
  el.innerHTML = queries.map(q => `<div class="q-tag">${q}</div>`).join("");
}

function showToast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2800);
}


// ── Chat ─────────────────────────────────────────────────────
const chatBubble = document.getElementById("chatBubble");
const chatPanel  = document.getElementById("chatPanel");
const chatInput  = document.getElementById("chatInput");
const chatMsgs   = document.getElementById("chatMessages");

chatBubble.addEventListener("click", () => {
  const isOpen = chatPanel.classList.toggle("open");
  chatBubble.classList.toggle("open", isOpen);
  if (isOpen) setTimeout(() => chatInput.focus(), 250);
});

function chatAddMsg(text, type) {
  const d = document.createElement("div");
  d.className = "chat-msg " + type;
  d.textContent = text;
  chatMsgs.appendChild(d);
  chatMsgs.scrollTop = chatMsgs.scrollHeight;
}

async function chatSend() {
  const txt = chatInput.value.trim();
  if (!txt) return;
  chatAddMsg(txt, "user");
  chatInput.value = "";
  // TODO: reemplazar con llamada real al endpoint de chat
  // const resp = await fetch("/chat/", { method:"POST", body: JSON.stringify({message: txt}), ... })
  chatAddMsg("Buscando lugares para ti...", "bot");
}

document.getElementById("chatSendBtn").addEventListener("click", chatSend);
chatInput.addEventListener("keydown", e => { if (e.key === "Enter") chatSend(); });


// ── User menu ─────────────────────────────────────────────────

const userMenu      = document.getElementById("userMenu");
const userAvatarBtn = document.getElementById("userAvatarBtn");

userAvatarBtn.addEventListener("click", e => {
  e.stopPropagation();
  userMenu.classList.toggle("open");
});

document.addEventListener("click", () => {
  userMenu.classList.remove("open");
});

// ── Carga inicial del mapa ────────────────────────────────────
async function loadUserMap() {
  try {
    const data = await fetchGraph(null); // null = sin query, solo carga el mapa
    if (!data.nodes.length) return;     // mapa vacío, mostrar empty state

    const W = document.querySelector(".canvas-wrap").clientWidth;
    const H = document.querySelector(".canvas-wrap").clientHeight;

    // Registrar todos los nodos
    data.nodes.forEach(n => {
      if (!allNodes[n.place_id]) {
        allNodes[n.place_id] = {
          ...n,
          x: W / 2 + (Math.random() - 0.5) * 300,
          y: H / 2 + (Math.random() - 0.5) * 300,
          vx: 0, vy: 0,
        };
      }
      if (n.status === "in_graph") {
        getSavedColor(n.neighborhood);
        savedSet.add(n.place_id);
        allNodes[n.place_id].fx = allNodes[n.place_id].x;
        allNodes[n.place_id].fy = allNodes[n.place_id].y;
        suggestIds.add(n.place_id); // para que sean visibles sin búsqueda
      }
    });

    // Cargar edges reales del backend
    data.edges.forEach(e => {
      console.log("Edge:", e);  

      const src = Object.values(allNodes).find(n => n.id === e.from);
      const tgt = Object.values(allNodes).find(n => n.id === e.to);

      console.log("src:", src, "tgt:", tgt);  // ← y aquí

      if (!src || !tgt) return;
      const exists = mapEdges.some(me =>
        (me.source.place_id === src.place_id && me.target.place_id === tgt.place_id) ||
        (me.source.place_id === tgt.place_id && me.target.place_id === src.place_id)
      );
      if (!exists) {
        mapEdges.push({ source: src, target: tgt, weight: e.weight, reason: e.reason, type: "map" });
      }
    });

    document.getElementById("empty-state").style.display = "none";
    document.getElementById("hud").style.display = "flex";
    updateHUD();
    rerender();

  } catch (err) {
    console.error("Error cargando mapa:", err);
  }
}

// Ejecutar al cargar la página
loadUserMap();