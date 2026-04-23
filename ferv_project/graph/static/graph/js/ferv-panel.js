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

  const addBtn      = document.getElementById("panel-add-btn");
  const removeBtn   = document.getElementById("panel-remove-btn");
  const discoverBtn = document.getElementById("panel-discover-btn");

  if (isSaved) {
    addBtn.textContent  = "✓ En tu mapa";
    addBtn.className    = "btn-add saved";
    addBtn.disabled     = true;
    removeBtn.classList.add("visible");
    discoverBtn.style.display = "none";
  } else {
    addBtn.textContent  = "+ Agregar a mi mapa";
    addBtn.className    = "btn-add";
    addBtn.disabled     = false;
    removeBtn.classList.remove("visible");
    discoverBtn.style.display = "block";
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
    if (!selectedD || savedSet.has(selectedD.place_id)) return;
    saveNode(selectedD.place_id);
    closePanel();
  });

  document.getElementById("panel-remove-btn").addEventListener("click", () => {
    if (!selectedD) return;
    openRemoveModal();
  });

  document.getElementById("panel-discover-btn").addEventListener("click", () => {
    if (!selectedD || savedSet.has(selectedD.place_id)) return;
    discoverNode(selectedD.place_id);
    closePanel();
  });

  document.getElementById("remove-confirm-cancel").addEventListener("click", () => {
    closeRemoveModal();
  });

  document.getElementById("remove-confirm-accept").addEventListener("click", () => {
    if (!selectedD) return;
    removeNode(selectedD.place_id);
    closeRemoveModal();
  });

  document.getElementById("remove-confirm-modal").addEventListener("click", (event) => {
    if (event.target.id === "remove-confirm-modal" || event.target.classList.contains("remove-modal__backdrop")) {
      closeRemoveModal();
    }
  });

  // ── Discovery drawer ──
  const discoveryFab   = document.getElementById("discovery-fab");
  const discoveryClose = document.getElementById("discovery-panel-close");

  discoveryFab?.addEventListener("click", () => toggleDiscoveryDrawer());
  discoveryClose?.addEventListener("click", () => toggleDiscoveryDrawer(false));

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeRemoveModal();
      toggleDiscoveryDrawer(false);
    }
  });
});


// ── Discovery functions ───────────────────────────────────────

async function discoverNode(placeId) {
  const node = allNodes[placeId];
  if (!node) return;

  try {
    await discoverNodeBackend(placeId);
  } catch (err) {
    showToast("Error: " + err.message);
    return;
  }

  discoveredSet.add(placeId);
  suggestIds.delete(placeId);
  updateHUD();
  rerender();
  renderDiscoveryList();
  showToast(`"${trunc(node.name, 22)}" guardado en descubrimientos`);
}

function toggleDiscoveryDrawer(forceOpen) {
  const panel = document.getElementById("discovery-panel");
  const fab   = document.getElementById("discovery-fab");
  if (!panel || !fab) return;

  const shouldOpen = typeof forceOpen === "boolean" ? forceOpen : !panel.classList.contains("open");
  panel.classList.toggle("open", shouldOpen);

  if (shouldOpen) renderDiscoveryList();
}

async function renderDiscoveryList() {
  const listEl = document.getElementById("discovery-list");
  if (!listEl) return;

  try {
    const data = await fetchDiscoveryList();

    if (!data.nodes.length) {
      listEl.innerHTML = `<div class="discovery-empty">No tienes descubrimientos aún</div>`;
      updateDiscoveryBadge(0);
      return;
    }

    updateDiscoveryBadge(data.nodes.length);

    listEl.innerHTML = data.nodes.map(n => {
      const place = n.place || {};
      const tags  = (place.tags || []).map(t => `<span class="tag">${t.tag}</span>`).join("");
      const rating = place.rating ? `★ ${place.rating.toFixed(1)}` : "";
      return `<div class="discovery-card" data-node-id="${n.id}" data-place-id="${place.place_id}">
        <div class="discovery-card__header">
          <div class="discovery-card__name">${place.name || "Lugar"}</div>
          <div class="discovery-card__neighborhood">${place.neighborhood || ""}</div>
        </div>
        <div class="discovery-card__tags">${tags}</div>
        ${rating ? `<div class="discovery-card__rating">${rating}</div>` : ""}
        <div class="discovery-card__actions">
          <button class="discovery-btn discovery-btn--add" data-action="add" data-node-id="${n.id}" data-place-id="${place.place_id}">+ Mi mapa</button>
          <button class="discovery-btn discovery-btn--release" data-action="release" data-node-id="${n.id}" data-place-id="${place.place_id}">Soltar</button>
        </div>
      </div>`;
    }).join("");

    // Event delegation para los botones de cada tarjeta
    listEl.querySelectorAll(".discovery-btn").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        const action  = e.target.dataset.action;
        const nodeId  = parseInt(e.target.dataset.nodeId);
        const placeId = e.target.dataset.placeId;
        const name    = trunc(allNodes[placeId]?.name || "Lugar", 22);

        try {
          if (action === "add") {
            await restoreNodeBackend(nodeId, "in_graph");
            if (allNodes[placeId]) {
              savedSet.add(placeId);
              getSavedColor(allNodes[placeId].neighborhood);
              allNodes[placeId].fx = allNodes[placeId].x;
              allNodes[placeId].fy = allNodes[placeId].y;
            }
            discoveredSet.delete(placeId);
            showToast(`"${name}" agregado a tu mapa`);
          } else {
            await restoreNodeBackend(nodeId, "recommendation");
            discoveredSet.delete(placeId);
            if (allNodes[placeId]) suggestIds.add(placeId);
            showToast(`"${name}" suelto de nuevo`);
          }
          updateHUD();
          rerender();
          renderDiscoveryList();
        } catch (err) {
          showToast("Error: " + err.message);
        }
      });
    });

  } catch (err) {
    listEl.innerHTML = `<div class="discovery-empty">Error cargando lista</div>`;
    console.error(err);
  }
}

function updateDiscoveryBadge(count) {
  const badge = document.getElementById("discovery-badge");
  if (!badge) return;
  badge.textContent    = count;
  badge.style.display  = count > 0 ? "flex" : "none";
}