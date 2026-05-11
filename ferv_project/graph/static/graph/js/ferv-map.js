// ══════════════════════════════════════════════════════════════
//  ferv-map.js  — Renderizado D3 y gestión de nodos del mapa
//
//  DEPENDE DE: ferv-config.js, ferv-state.js, ferv-api.js, ferv-ui.js
// ══════════════════════════════════════════════════════════════

function showMapLoading(text = "Construyendo tu mapa...") {
  const el = document.getElementById("loading-overlay");
  if (!el) return;
  el.querySelector(".loading-overlay__text").textContent = text;
  el.classList.add("show");
}

function hideMapLoading() {
  document.getElementById("loading-overlay")?.classList.remove("show");
}

async function saveNode(placeId) {
  if (allNodes[placeId]?.status === "in_graph") return;
  const node = allNodes[placeId];
  if (!node) return;

  getSavedColor(node.neighborhood);
  showMapLoading();

  try {
    const newEdges = await addNodeToMap(placeId);
    node.status = "in_graph";

    const nodeList = Object.values(allNodes);
    newEdges.forEach(e => {
      const src = nodeList.find(n => n.id === String(e.source_id));
      const tgt = nodeList.find(n => n.id === String(e.target_id));
      if (src && tgt) {
        mapEdges.push({ source: src, target: tgt, weight: e.weight, reason: e.reason, type: "map" });
      }
    });

    showToast(`"${trunc(node.name, 22)}" fijado en tu mapa`);
  } catch (err) {
    showToast("Error al guardar en el mapa");
    console.error(err);
  } finally {
    hideMapLoading();
    updateHUD();
    rerender();
  }
}

async function addToDiscovery(placeId) {
  const node = allNodes[placeId];
  if (!node || node.status === "discovery") return;

  try {
    await addToDiscoveryAPI(parseInt(node.id));

    if (node.status === "in_graph" || node.status === "visited") {
      mapEdges = mapEdges.filter(e =>
        e.source.place_id !== placeId && e.target.place_id !== placeId
      );
    }
    const name = node.name;
    delete allNodes[placeId];

    closePanel();
    updateHUD();
    rerender();
    showToast(`"${trunc(name, 22)}" guardado en tu lista`);
  } catch (err) {
    if (err.status === 409) {
      showToast("Este lugar ya está en tu lista");
    } else {
      showToast("Error al guardar en la lista");
      console.error(err);
    }
  }
}

async function removeNode(placeId) {
  const node = allNodes[placeId];
  if (!node || (node.status !== "in_graph" && node.status !== "visited")) return;

  mapEdges = mapEdges.filter(e =>
    e.source.place_id !== placeId && e.target.place_id !== placeId
  );

  try {
    await removeNodeFromBackend(placeId);
    delete allNodes[placeId];
  } catch (err) {
    console.warn("No se pudo eliminar en el backend:", err);
  }

  closePanel();
  updateHUD();
  rerender();
  showToast(`"${trunc(node.name, 22)}" eliminado del mapa`);
}

async function runExploratoryMode(heat) {
  const savedCount = Object.values(allNodes).filter(
    n => n.status === "in_graph" || n.status === "visited"
  ).length;

  if (!savedCount) {
    showToast("Agrega lugares a tu mapa primero para usar el modo exploración.");
    return;
  }

  closeExplorePanel();
  showMapLoading("Explorando fuera de tu perfil...");

  try {
    const newNodes = await fetchExploratoryRecommendations(heat);

    Object.keys(allNodes).forEach(pid => {
      if (allNodes[pid].status === "recommendation") delete allNodes[pid];
    });
    searchEdges = [];

    if (!newNodes.length) {
      showToast("No encontramos sugerencias exploratorias. Intenta enriquecer tu perfil.");
      rerender();
      return;
    }

    const W = document.querySelector(".canvas-wrap").clientWidth;
    const H = document.querySelector(".canvas-wrap").clientHeight;
    const mapNodes = Object.values(allNodes).filter(
      n => (n.status === "in_graph" || n.status === "visited") && n.x != null
    );
    const cx = mapNodes.length ? mapNodes.reduce((s, n) => s + n.x, 0) / mapNodes.length : W / 2;
    const cy = mapNodes.length ? mapNodes.reduce((s, n) => s + n.y, 0) / mapNodes.length : H / 2;

    newNodes.forEach(n => {
      if (!allNodes[n.place_id]) {
        allNodes[n.place_id] = {
          ...n,
          x: cx + (Math.random() - 0.5) * 300,
          y: cy + (Math.random() - 0.5) * 300,
          vx: 0, vy: 0,
        };
      }
    });

    document.getElementById("hud").style.display = "flex";
    updateHUD();
    rerender();
    showToast(`${newNodes.length} lugares fuera de lo usual para ti`);

  } catch (_err) {
    showToast("Error al cargar sugerencias exploratorias. Puedes intentarlo de nuevo.");
  } finally {
    hideMapLoading();
  }
}

async function exploreFromNode(placeId) {
  const node = allNodes[placeId];
  if (!node) return;

  closePanel();
  showMapLoading("Buscando lugares similares...");

  try {
    const newNodes = await fetchNodeBasedRecommendations(parseInt(node.id));

    Object.keys(allNodes).forEach(pid => {
      if (allNodes[pid].status === "recommendation") delete allNodes[pid];
    });
    searchEdges = [];

    if (!newNodes.length) {
      showToast("No encontramos sugerencias desde este lugar. Prueba con otro.");
      rerender();
      return;
    }

    const anchorX = node.x ?? document.querySelector(".canvas-wrap").clientWidth / 2;
    const anchorY = node.y ?? document.querySelector(".canvas-wrap").clientHeight / 2;

    newNodes.forEach(n => {
      if (!allNodes[n.place_id]) {
        allNodes[n.place_id] = {
          ...n,
          x: anchorX + (Math.random() - 0.5) * 260,
          y: anchorY + (Math.random() - 0.5) * 260,
          vx: 0, vy: 0,
        };
      }
    });

    document.getElementById("hud").style.display = "flex";
    updateHUD();
    rerender();
    showToast(`${newNodes.length} sugerencias desde "${trunc(node.name, 18)}"`);

  } catch (_err) {
    showToast("Error al cargar sugerencias. Puedes intentarlo de nuevo.");
  } finally {
    hideMapLoading();
  }
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

  const isSaved   = d => d.status === "in_graph";
  const isVisited = d => d.status === "visited";
  const isOnMap   = d => d.status === "in_graph" || d.status === "visited";

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
      .distance(d => d.weight > 0.78 ? 380 : 200)
      .strength(d => Math.max(0.05, d.weight - 0.3))
    )
    .force("charge", d3.forceManyBody().strength(-600))
    .force("center", d3.forceCenter(W / 2, H / 2).strength(0.02))
    .force("collision", d3.forceCollide(80))
    .alphaDecay(0.018);

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
      .on("end",   (ev, d) => { if (!ev.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; })
    )
    .on("click", (ev, d) => { ev.stopPropagation(); openPanel(d, visibleEdges); });

  // Anillo exterior punteado — en mapa y visitados (estilo diferente)
  nodeEls.filter(isOnMap).append("circle")
    .attr("r", 50).attr("fill", "none")
    .attr("stroke", d => getSavedColor(d.neighborhood))
    .attr("stroke-width", d => isVisited(d) ? 0.5 : 0.7)
    .attr("stroke-opacity", d => isVisited(d) ? 0.14 : 0.25)
    .attr("stroke-dasharray", d => isVisited(d) ? "2,8" : "3,6");

  // Círculo principal
  nodeEls.append("circle")
    .attr("r", d => isOnMap(d) ? 40 : 36)
    .attr("fill", d => isOnMap(d)
      ? getSavedColor(d.neighborhood) + (isVisited(d) ? "18" : "28")
      : SUGGESTED_COLOR.fill
    )
    .attr("stroke", d => isOnMap(d)
      ? getSavedColor(d.neighborhood)
      : SUGGESTED_COLOR.stroke
    )
    .attr("stroke-width", d => isOnMap(d) ? 2.2 : 0.8)
    .attr("stroke-opacity", d => isVisited(d) ? 0.45 : 1);

  // Ícono: ★ guardados, ✓ visitados
  nodeEls.filter(isSaved).append("text")
    .attr("y", -30).attr("text-anchor", "middle")
    .attr("font-size", "11").attr("fill", "#fac86b")
    .attr("pointer-events", "none").text("★");

  nodeEls.filter(isVisited).append("text")
    .attr("y", -30).attr("text-anchor", "middle")
    .attr("font-size", "12").attr("fill", "#5bba6f")
    .attr("pointer-events", "none").text("✓");

  // Nombre
  nodeEls.append("text")
    .attr("y", 3).attr("text-anchor", "middle")
    .attr("font-size", "11.5").attr("font-weight", "500")
    .attr("font-family", "'DM Sans', sans-serif")
    .attr("fill", d => isOnMap(d) ? getSavedColor(d.neighborhood) : SUGGESTED_COLOR.text)
    .attr("fill-opacity", d => isVisited(d) ? 0.55 : 1)
    .attr("pointer-events", "none")
    .text(d => trunc(d.name, 13));

  // Barrio
  nodeEls.append("text")
    .attr("y", 17).attr("text-anchor", "middle").attr("font-size", "9.5")
    .attr("fill", d => isOnMap(d) ? "#666" : "#333")
    .attr("font-family", "'DM Mono', monospace")
    .attr("pointer-events", "none")
    .text(d => trunc(d.neighborhood, 13));

  // Label inferior: "en mi mapa" / "visitado"
  nodeEls.filter(isSaved).append("text")
    .attr("y", 29).attr("text-anchor", "middle")
    .attr("font-size", "8.5").attr("fill", "#3dd6c8").attr("fill-opacity", "0.7")
    .attr("font-family", "'DM Mono', monospace")
    .attr("pointer-events", "none").text("en mi mapa");

  nodeEls.filter(isVisited).append("text")
    .attr("y", 29).attr("text-anchor", "middle")
    .attr("font-size", "8.5").attr("fill", "#5bba6f").attr("fill-opacity", "0.6")
    .attr("font-family", "'DM Mono', monospace")
    .attr("pointer-events", "none").text("visitado");

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
