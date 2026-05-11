// ══════════════════════════════════════════════════════════════
//  ferv-panel.js  — Panel lateral de detalle de nodo
//
//  DEPENDE DE: ferv-config.js, ferv-state.js,
//              ferv-map.js (saveNode, removeNode)
// ══════════════════════════════════════════════════════════════

function openPanel(d, edges) {
  selectedD = d;
  const isSaved = d.status === "in_graph";

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
      const other      = e.source.place_id === d.place_id ? e.target : e.source;
      const otherSaved = other?.status === "in_graph";
      const col        = otherSaved ? getSavedColor(other?.neighborhood) : "rgba(255,255,255,0.25)";
      return `<div class="conn-item">
        <div class="conn-dot" style="background:${col};opacity:${otherSaved ? 1 : 0.5}"></div>
        <span style="color:${col}">${trunc(other?.name || "", 17)}</span>
        <span style="color:#444;font-size:10px"> · ${trunc(e.reason, 20)}</span>
      </div>`;
    }).join("");
  } else {
    connEl.style.display = "none";
  }

  const addBtn      = document.getElementById("panel-add-btn");
  const discoverBtn = document.getElementById("panel-discover-btn");
  const removeBtn   = document.getElementById("panel-remove-btn");
  const isVisited   = d.status === "visited";

  if (isVisited) {
    addBtn.textContent  = "✓ Visitado";
    addBtn.className    = "btn-add saved";
    addBtn.disabled     = true;
    discoverBtn.style.display = "none";
    removeBtn.classList.add("visible");
  } else if (isSaved) {
    addBtn.textContent  = "✓ En tu mapa";
    addBtn.className    = "btn-add saved";
    addBtn.disabled     = true;
    discoverBtn.textContent  = "♡ Guardar en lista";
    discoverBtn.className    = "btn-discover-panel";
    discoverBtn.disabled     = false;
    discoverBtn.style.display = "";
    removeBtn.classList.add("visible");
  } else {
    addBtn.textContent  = "+ Agregar a mi mapa";
    addBtn.className    = "btn-add";
    addBtn.disabled     = false;
    discoverBtn.textContent  = "♡ Guardar en lista";
    discoverBtn.className    = "btn-discover-panel";
    discoverBtn.disabled     = false;
    discoverBtn.style.display = "";
    removeBtn.classList.remove("visible");
  }

  document.getElementById("detail-panel").classList.add("open");
}

function closePanel() {
  document.getElementById("detail-panel").classList.remove("open");
  selectedD = null;
}

function openRemoveModal() {
  if (!selectedD) return;

  const modal = document.getElementById("remove-confirm-modal");
  const nameEl = document.getElementById("remove-confirm-name");
  if (!modal || !nameEl) return;

  nameEl.textContent = selectedD.name || "este lugar";
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
}

function closeRemoveModal() {
  const modal = document.getElementById("remove-confirm-modal");
  if (!modal) return;

  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("panel-add-btn").addEventListener("click", () => {
    if (!selectedD || selectedD.status === "in_graph" || selectedD.status === "visited") return;
    saveNode(selectedD.place_id);
    closePanel();
  });

  document.getElementById("panel-discover-btn").addEventListener("click", () => {
    if (!selectedD || selectedD.status === "discovery") return;
    addToDiscovery(selectedD.place_id);
  });

  document.getElementById("panel-remove-btn").addEventListener("click", () => {
    if (!selectedD) return;
    openRemoveModal();
  });

  document.getElementById("remove-confirm-cancel").addEventListener("click", () => {
    closeRemoveModal();
  });

  document.getElementById("remove-confirm-accept").addEventListener("click", () => {
    if (!selectedD) return;
    removeNode(selectedD.place_id);
    closeRemoveModal();
    closePanel();
  });

  document.getElementById("remove-confirm-modal").addEventListener("click", (event) => {
    if (event.target.id === "remove-confirm-modal" || event.target.classList.contains("remove-modal__backdrop")) {
      closeRemoveModal();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeRemoveModal();
    }
  });
});