// ferv-favorites.js — Drawer para lista de favoritos

async function openFavoritesDrawer() {
  const drawer = document.getElementById("favorites-drawer");
  if (!drawer) return;
  drawer.classList.add("open");
  drawer.setAttribute("aria-hidden", "false");
  await loadFavoritesList();
}

function closeFavoritesDrawer() {
  const drawer = document.getElementById("favorites-drawer");
  if (!drawer) return;
  drawer.classList.remove("open");
  drawer.setAttribute("aria-hidden", "true");
}

async function loadFavoritesList() {
  const listEl = document.getElementById("favorites-list");
  if (!listEl) return;
  listEl.innerHTML = '<div class="favorites-loading">Cargando...</div>';

  try {
    const data = await fetchFavoritesList();
    const items = data.nodes || [];
    renderFavoritesList(items);
  } catch (_err) {
    listEl.innerHTML = `
      <div class="favorites-error">
        <p>No se pudo cargar la lista</p>
        <button class="favorites-retry-btn" onclick="loadFavoritesList()">Reintentar</button>
      </div>`;
  }
}

function renderFavoritesList(items) {
  const listEl = document.getElementById("favorites-list");
  const countEl = document.getElementById("favorites-header-count");
  if (!listEl) return;

  const count = items.length;
  if (countEl) countEl.textContent = count;

  if (!count) {
    listEl.innerHTML = '<div class="favorites-empty">Todavía no marcaste lugares como favoritos.</div>';
    return;
  }

  listEl.innerHTML = items.map((n, i) => {
    const tagsHtml = (n.tags || []).slice(0, 3).map(t => `<span class="favorites-tag">${t}</span>`).join("");
    const rating = n.rating ? `★ ${Number(n.rating).toFixed(1)}` : "";
    const meta = [n.neighborhood, rating].filter(Boolean).join(" · ");
    const statusLabel = n.status === "visited" ? "Visitado" : n.status === "in_graph" ? "En tu mapa" : "";

    return `
      <div class="favorites-item" data-idx="${i}">
        <div class="favorites-item__info">
          <div class="favorites-item__name">${n.name}</div>
          ${meta ? `<div class="favorites-item__meta">${meta}</div>` : ""}
          ${statusLabel ? `<div class="favorites-item__meta">${statusLabel}</div>` : ""}
          ${tagsHtml ? `<div class="favorites-item__tags">${tagsHtml}</div>` : ""}
        </div>
        <div class="favorites-item__actions">
          <button class="favorites-btn-open" data-idx="${i}" title="Abrir detalle">Abrir</button>
        </div>
      </div>`;
  }).join("");

  listEl.querySelectorAll(".favorites-btn-open").forEach(btn => {
    btn.addEventListener("click", () => {
      const idx = parseInt(btn.dataset.idx, 10);
      const node = items[idx];
      if (!node) return;
      openPanel(node, []);
      closeFavoritesDrawer();
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("favorites-list-btn");
  const closeBtn = document.getElementById("favorites-drawer-close");
  if (btn) btn.addEventListener("click", openFavoritesDrawer);
  if (closeBtn) closeBtn.addEventListener("click", closeFavoritesDrawer);

  document.addEventListener("keydown", e => {
    if (e.key === "Escape") closeFavoritesDrawer();
  });
});
