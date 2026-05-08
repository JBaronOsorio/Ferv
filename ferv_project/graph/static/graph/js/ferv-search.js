// ══════════════════════════════════════════════════════════════
//  ferv-search.js  — Lógica de búsqueda
//
//  DEPENDE DE: ferv-config.js, ferv-state.js, ferv-api.js,
//              ferv-map.js (rerender), ferv-ui.js (showToast, updateHUD, updateQueryTags)
// ══════════════════════════════════════════════════════════════

async function runSearch() {
  const q = document.getElementById("q-input").value.trim();
  if (!q) return;

  document.getElementById("spinner").classList.add("show");
  document.getElementById("search-btn").disabled = true;
  document.getElementById("empty-state").style.display = "none";
  closePanel();

  try {
    const data = await fetchRecommendations(q);

    const W = document.querySelector(".canvas-wrap").clientWidth;
    const H = document.querySelector(".canvas-wrap").clientHeight;

    // Limpiar solo nodos recommendation (preservar in_graph, visited; discovery no está en allNodes)
    Object.keys(allNodes).forEach(pid => {
      if (allNodes[pid].status === "recommendation") delete allNodes[pid];
    });

    data.nodes.forEach(n => {
      if (!allNodes[n.place_id]) {
        allNodes[n.place_id] = {
          ...n,
          x: W / 2 + (Math.random() - 0.5) * 200,
          y: H / 2 + (Math.random() - 0.5) * 200,
          vx: 0, vy: 0,
        };
      } else if (allNodes[n.place_id].status === "in_graph") {
        getSavedColor(n.neighborhood);
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

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("q-input").addEventListener("keydown", e => {
    if (e.key === "Enter") runSearch();
  });
});