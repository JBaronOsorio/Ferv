// ══════════════════════════════════════════════════════════════
//  ferv-filters.js  — Panel y lógica de filtros del mapa
//
//  DEPENDE DE: ferv-state.js, ferv-map.js (rerender), ferv-ui.js
// ══════════════════════════════════════════════════════════════

let activeFilters = { tags: [], neighborhood: null, minRating: 0, onlyFavorites: false };

function hasActiveFilters() {
  return activeFilters.tags.length > 0 || activeFilters.neighborhood || activeFilters.minRating > 0 || activeFilters.onlyFavorites;
}

function matchesActiveFilters(node) {
  if (activeFilters.onlyFavorites && !node.is_favorite) return false;

  const nodeTags = Array.isArray(node.tags) ? node.tags : [];

  if (activeFilters.tags.length) {
    const tagMatch = activeFilters.tags.some(tag => nodeTags.some(t => t === tag));
    if (!tagMatch) return false;
  }

  if (activeFilters.neighborhood && node.neighborhood !== activeFilters.neighborhood) {
    return false;
  }

  if (activeFilters.minRating > 0 && Number(node.rating || 0) < activeFilters.minRating) {
    return false;
  }

  return true;
}

function setEmptyState(isFilteredEmpty) {
  const emptyState = document.getElementById("empty-state");
  if (!emptyState) return;

  const title = emptyState.querySelector("p");
  const hint = emptyState.querySelector(".hint");

  if (isFilteredEmpty) {
    if (activeFilters.onlyFavorites) {
      if (title) title.textContent = "Sin lugares favoritos aún";
      if (hint) hint.textContent = "Abre un lugar en tu mapa y márcalo como favorito con ☆";
    } else {
      if (title) title.textContent = "Sin lugares con estos filtros";
      if (hint) hint.textContent = "Limpia los filtros para volver a ver todos los lugares";
    }
    emptyState.style.display = "flex";
    return;
  }

  if (title) title.textContent = "Tu mapa está vacío";
  if (hint) hint.textContent = "Busca algo para empezar a explorar";
  emptyState.style.display = "none";
}

function getFilteredVisibleNodes() {
  const visibleNodes = Object.values(allNodes).filter(node => {
    if (node.status === "in_graph") return matchesActiveFilters(node);
    if (node.status === "visited") return matchesActiveFilters(node);
    if (node.status === "recommendation") return true;
    return false;
  });

  setEmptyState(visibleNodes.length === 0 && hasActiveFilters());
  return visibleNodes;
}

function updateFilterButtonState() {
  const fab = document.getElementById("filters-fab");
  if (!fab) return;
  fab.classList.toggle("active", hasActiveFilters());
}

function populateNeighborhoodOptions() {
  const select = document.getElementById("filters-neighborhood");
  if (!select) return;

  const neighborhoods = [...new Set(
    Object.values(allNodes)
      .map(node => node.neighborhood)
      .filter(Boolean)
  )].sort((a, b) => a.localeCompare(b, "es"));

  const currentValue = activeFilters.neighborhood || "";
  select.innerHTML = [
    `<option value="">Todos los barrios</option>`,
    ...neighborhoods.map(neighborhood => `<option value="${neighborhood}">${neighborhood}</option>`),
  ].join("");
  select.value = currentValue;
}

function getAvailableTags() {
  const tagSet = new Set();
  Object.values(allNodes).forEach(node => {
    (node.tags || []).forEach(t => tagSet.add(t));
  });
  return [...tagSet].sort((a, b) => a.localeCompare(b, "es"));
}

function renderTagButtons() {
  const wrap = document.getElementById("filters-tags");
  if (!wrap) return;

  const tags = getAvailableTags();
  if (!tags.length) {
    wrap.innerHTML = '<span class="filters-tags-empty">Sin etiquetas disponibles</span>';
    return;
  }

  activeFilters.tags = activeFilters.tags.filter(t => tags.includes(t));

  wrap.innerHTML = tags.map(tag => {
    const label = tag.charAt(0).toUpperCase() + tag.slice(1);
    const active = activeFilters.tags.includes(tag) ? "active" : "";
    return `<button type="button" class="filters-tag ${active}" data-tag="${tag}">${label}</button>`;
  }).join("");
}

function syncFilterUI() {
  renderTagButtons();
  populateNeighborhoodOptions();

  const ratingInput = document.getElementById("filters-rating");
  const ratingValue = document.getElementById("filters-rating-value");
  const neighborhoodSelect = document.getElementById("filters-neighborhood");

  if (ratingInput) ratingInput.value = String(activeFilters.minRating);
  if (ratingValue) ratingValue.textContent = activeFilters.minRating > 0 ? `${activeFilters.minRating}+` : "Cualquiera";
  if (neighborhoodSelect) neighborhoodSelect.value = activeFilters.neighborhood || "";

  updateFilterButtonState();
}

function applyFilters() {
  const ratingInput = document.getElementById("filters-rating");
  const neighborhoodSelect = document.getElementById("filters-neighborhood");

  if (ratingInput) {
    activeFilters.minRating = Number(ratingInput.value || 0);
  }

  if (neighborhoodSelect) {
    activeFilters.neighborhood = neighborhoodSelect.value || null;
  }

  updateFilterButtonState();
  rerender();
}

function clearFilters() {
  activeFilters = { tags: [], neighborhood: null, minRating: 0, onlyFavorites: false };
  const favToggle = document.getElementById("filters-favorites");
  if (favToggle) favToggle.classList.remove("active");
  syncFilterUI();
  rerender();
}

function toggleFilterPanel(forceOpen) {
  const panel = document.getElementById("filters-panel");
  const fab = document.getElementById("filters-fab");
  if (!panel || !fab) return;

  const shouldOpen = typeof forceOpen === "boolean" ? forceOpen : !panel.classList.contains("open");
  panel.classList.toggle("open", shouldOpen);
  panel.setAttribute("aria-hidden", shouldOpen ? "false" : "true");
  fab.setAttribute("aria-expanded", shouldOpen ? "true" : "false");

  if (shouldOpen) {
    syncFilterUI();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const fab = document.getElementById("filters-fab");
  const panel = document.getElementById("filters-panel");
  const closeBtn = document.getElementById("filters-panel-close");
  const clearBtn = document.getElementById("filters-clear");
  const applyBtn = document.getElementById("filters-apply");
  const ratingInput = document.getElementById("filters-rating");
  const ratingValue = document.getElementById("filters-rating-value");
  const neighborhoodSelect = document.getElementById("filters-neighborhood");

  if (!fab || !panel) return;

  fab.addEventListener("click", () => toggleFilterPanel());
  closeBtn?.addEventListener("click", () => toggleFilterPanel(false));
  clearBtn?.addEventListener("click", clearFilters);
  applyBtn?.addEventListener("click", applyFilters);

  ratingInput?.addEventListener("input", () => {
    if (ratingValue) {
      ratingValue.textContent = Number(ratingInput.value) > 0 ? `${Number(ratingInput.value)}+` : "Cualquiera";
    }
  });

  const tagWrap = document.getElementById("filters-tags");
  tagWrap?.addEventListener("click", event => {
    const button = event.target.closest(".filters-tag");
    if (!button) return;

    const tag = button.dataset.tag;
    if (!tag) return;

    if (activeFilters.tags.includes(tag)) {
      activeFilters.tags = activeFilters.tags.filter(value => value !== tag);
      button.classList.remove("active");
      return;
    }

    activeFilters.tags.push(tag);
    button.classList.add("active");
  });

  neighborhoodSelect?.addEventListener("change", () => {
    activeFilters.neighborhood = neighborhoodSelect.value || null;
  });

  document.getElementById("filters-favorites")?.addEventListener("click", () => {
    activeFilters.onlyFavorites = !activeFilters.onlyFavorites;
    document.getElementById("filters-favorites").classList.toggle("active", activeFilters.onlyFavorites);
    updateFilterButtonState();
    rerender();
  });

  document.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      toggleFilterPanel(false);
    }
  });

  syncFilterUI();
});