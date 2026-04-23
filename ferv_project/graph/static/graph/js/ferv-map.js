// ══════════════════════════════════════════════════════════════
//  ferv-map.js  — Renderizado D3 y gestión de nodos del mapa
//
//  DEPENDE DE: ferv-config.js, ferv-state.js, ferv-api.js, ferv-ui.js
// ══════════════════════════════════════════════════════════════

async function saveNode(placeId) {
  if (savedSet.has(placeId)) return;
  const node = allNodes[placeId];
  if (!node) return;

  getSavedColor(node.neighborhood); // asignar color de barrio antes de renderizar

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

  mapEdges = mapEdges.filter(e =>
    e.source.place_id !== placeId && e.target.place_id !== placeId
  );

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

  const visibleNodes = getFilteredVisibleNodes();

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
      ? getSavedColor(d.neighborhood) + "28"
      : SUGGESTED_COLOR.fill
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
    .attr("fill", d => isSaved(d) ? getSavedColor(d.neighborhood) : SUGGESTED_COLOR.text)
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
