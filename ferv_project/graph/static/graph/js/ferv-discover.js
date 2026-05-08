// ══════════════════════════════════════════════════════════════
//  ferv-discover.js  — Lista de descubrimiento (drawer + modal)
//
//  DEPENDE DE: ferv-config.js, ferv-state.js, ferv-api.js,
//              ferv-map.js (rerender, mapEdges, updateHUD),
//              ferv-ui.js (showToast)
// ══════════════════════════════════════════════════════════════

let discoveryItems = [];
let visitedModalTarget = null;

// ── Drawer ────────────────────────────────────────────────────

function openDiscoveryDrawer() {
  const drawer = document.getElementById("discovery-drawer");
  drawer.classList.add("open");
  drawer.setAttribute("aria-hidden", "false");
  loadDiscoveryList();
}

function closeDiscoveryDrawer() {
  const drawer = document.getElementById("discovery-drawer");
  drawer.classList.remove("open");
  drawer.setAttribute("aria-hidden", "true");
}

async function loadDiscoveryList() {
  const listEl = document.getElementById("discovery-list");
  listEl.innerHTML = '<div class="discovery-loading">Cargando...</div>';

  try {
    const data = await fetchDiscoveryList();
    discoveryItems = data.nodes;
    renderDiscoveryList();
  } catch (_err) {
    listEl.innerHTML = `
      <div class="discovery-error">
        <p>No se pudo cargar la lista</p>
        <button class="discovery-retry-btn" onclick="loadDiscoveryList()">Reintentar</button>
      </div>`;
  }
}

function renderDiscoveryList() {
  const listEl   = document.getElementById("discovery-list");
  const countEl  = document.getElementById("discovery-header-count");
  const badgeEl  = document.getElementById("discover-count-badge");

  const count = discoveryItems.length;
  if (countEl) countEl.textContent = count;
  if (badgeEl) {
    badgeEl.textContent = count;
    badgeEl.style.display = count > 0 ? "flex" : "none";
  }

  if (!count) {
    listEl.innerHTML = '<div class="discovery-empty">Tu lista está vacía.<br>Guarda lugares del mapa para visitarlos.</div>';
    return;
  }

  listEl.innerHTML = discoveryItems.map((n, i) => {
    const tagsHtml = (n.tags || []).slice(0, 3).map(t =>
      `<span class="discovery-tag">${t}</span>`
    ).join("");
    const rating = n.rating ? `★ ${Number(n.rating).toFixed(1)}` : "";
    const meta   = [n.neighborhood, rating].filter(Boolean).join(" · ");
    return `
      <div class="discovery-item" data-idx="${i}">
        <div class="discovery-item__info">
          <div class="discovery-item__name">${n.name}</div>
          ${meta ? `<div class="discovery-item__meta">${meta}</div>` : ""}
          ${tagsHtml ? `<div class="discovery-item__tags">${tagsHtml}</div>` : ""}
        </div>
        <div class="discovery-item__actions">
          <button class="discovery-btn-visited" data-idx="${i}" title="Ya fui">Ya fui</button>
          <button class="discovery-btn-delete" data-idx="${i}" title="Eliminar de la lista">×</button>
        </div>
      </div>`;
  }).join("");

  listEl.querySelectorAll(".discovery-btn-visited").forEach(btn => {
    btn.addEventListener("click", () => {
      const n = discoveryItems[parseInt(btn.dataset.idx)];
      if (n) openVisitedModal(n.id, n.place_id, n.name);
    });
  });

  listEl.querySelectorAll(".discovery-btn-delete").forEach(btn => {
    btn.addEventListener("click", () => {
      const n = discoveryItems[parseInt(btn.dataset.idx)];
      if (n) deleteDiscoveryItem(n.id, n.place_id);
    });
  });
}

// ── Modal "Ya fui" ────────────────────────────────────────────

function openVisitedModal(nodeId, placeId, name) {
  visitedModalTarget = { id: String(nodeId), place_id: placeId, name };
  document.getElementById("visited-modal-name").textContent = name;
  const modal = document.getElementById("visited-modal");
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
}

function closeVisitedModal() {
  const modal = document.getElementById("visited-modal");
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
  visitedModalTarget = null;
}

async function handleVisitedChoice(choice) {
  if (!visitedModalTarget) return;
  const { id: nodeId, place_id: placeId, name } = visitedModalTarget;
  closeVisitedModal();

  if (choice === "keep") return;

  if (choice === "remove") {
    await deleteDiscoveryItem(nodeId, placeId);
    return;
  }

  if (choice === "map") {
    showMapLoading("Agregando a tu mapa...");
    try {
      const result = await markVisitedAPI(parseInt(nodeId));

      discoveryItems = discoveryItems.filter(n => String(n.id) !== String(nodeId));
      renderDiscoveryList();

      const parsed = parseNode(result.node);
      const W = document.querySelector(".canvas-wrap").clientWidth;
      const H = document.querySelector(".canvas-wrap").clientHeight;

      const mapNodes = Object.values(allNodes).filter(
        n => (n.status === "in_graph" || n.status === "visited") && n.x != null
      );
      const cx = mapNodes.length ? mapNodes.reduce((s, n) => s + n.x, 0) / mapNodes.length : W / 2;
      const cy = mapNodes.length ? mapNodes.reduce((s, n) => s + n.y, 0) / mapNodes.length : H / 2;

      allNodes[parsed.place_id] = {
        ...parsed,
        x: cx + (Math.random() - 0.5) * 160,
        y: cy + (Math.random() - 0.5) * 160,
        vx: 0, vy: 0,
      };

      (result.edges || []).forEach(e => {
        const src = Object.values(allNodes).find(n => n.id === String(e.source_id));
        const tgt = Object.values(allNodes).find(n => n.id === String(e.target_id));
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
      showToast(`"${trunc(name, 22)}" marcado como visitado`);

    } catch (_err) {
      showToast("Error al marcar como visitado. El lugar sigue en tu lista.");
      loadDiscoveryList();
    } finally {
      hideMapLoading();
    }
  }
}

// ── Eliminar de la lista ──────────────────────────────────────

async function deleteDiscoveryItem(nodeId, placeId) {
  try {
    await deleteNodeById(parseInt(nodeId));
    discoveryItems = discoveryItems.filter(n => String(n.id) !== String(nodeId));
    renderDiscoveryList();
    showToast("Lugar eliminado de tu lista");
  } catch (_err) {
    showToast("Error al eliminar el lugar de la lista");
  }
}

// ── Inicialización ────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("discover-fab").addEventListener("click", openDiscoveryDrawer);
  document.getElementById("discovery-drawer-close").addEventListener("click", closeDiscoveryDrawer);

  document.getElementById("visited-modal-keep").addEventListener("click", () => handleVisitedChoice("keep"));
  document.getElementById("visited-modal-map").addEventListener("click", () => handleVisitedChoice("map"));
  document.getElementById("visited-modal-remove").addEventListener("click", () => handleVisitedChoice("remove"));

  document.getElementById("visited-modal").addEventListener("click", e => {
    if (e.target.id === "visited-modal" || e.target.classList.contains("visited-modal__backdrop")) {
      closeVisitedModal();
    }
  });

  document.addEventListener("keydown", e => {
    if (e.key === "Escape") closeVisitedModal();
  });
});
