// ══════════════════════════════════════════════════════════════
//  ferv-panel.js  — Panel lateral de detalle de nodo
//
//  DEPENDE DE: ferv-config.js, ferv-state.js,
//              ferv-map.js (saveNode, removeNode)
// ══════════════════════════════════════════════════════════════

function openPanel(d, edges) {
  selectedD = d;
  const isSaved = savedSet.has(d.place_id);

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
      const otherSaved = savedSet.has(other?.place_id);
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

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("panel-add-btn").addEventListener("click", () => {
    if (!selectedD || savedSet.has(selectedD.place_id)) return;
    saveNode(selectedD.place_id);
    closePanel();
  });

  document.getElementById("panel-remove-btn").addEventListener("click", () => {
    if (!selectedD) return;
    removeNode(selectedD.place_id);
  });
});