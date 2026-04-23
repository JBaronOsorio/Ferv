// ══════════════════════════════════════════════════════════════
//  ferv-filters.js  — Panel y lógica de filtros del mapa
//
//  DEPENDE DE: ferv-state.js, ferv-map.js (rerender), ferv-ui.js
// ══════════════════════════════════════════════════════════════

let activeFilters = { tags: [], neighborhood: null, minRating: 0 };

// Tags dinámicos — se leen de los nodos guardados, no hardcodeados
// Tags ya son strings planos porque parseNode los convierte: ["bar", "cafe"]
function getAvailableTags() {
  const saved = Object.values(allNodes).filter(n => savedSet.has(n.place_id));
  const tags = [...new Set(
    saved.flatMap(n => Array.isArray(n.tags) ? n.tags : []).filter(Boolean)
  )].sort();
  return tags;
}

function hasActiveFilters() {
  return activeFilters.tags.length > 0 || activeFilters.neighborhood || activeFilters.minRating > 0;
}

function matchesActiveFilters(node) {
  const nodeTags = Array.isArray(node.tags) ? node.tags : [];

  if (activeFilters.tags.length) {
    // tags son strings planos: ["bar", "cafe"]
    const tagMatch = activeFilters.tags.some(tag => nodeTags.includes(tag));
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
    if (title) title.textContent = "Sin lugares con estos filtros";
    if (hint) hint.textContent = "Limpia los filtros para volver a ver todos los lugares";
    emptyState.style.display = "flex";
    return;
  }

  if (title) title.textContent = "Tu mapa está vacío";
  if (hint) hint.textContent = "Busca algo para empezar a explorar";
  emptyState.style.display = "none";
}

function getFilteredVisibleNodes() {
  const visibleNodes = Object.values(allNodes).filter(node => {
    // Nunca mostrar nodos en la lista de descubrimiento en el canvas
    if (discoveredSet.has(node.place_id)) return false;

    if (!savedSet.has(node.place_id)) {
      return suggestIds.has(node.place_id);
    }

    return matchesActiveFilters(node);
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
      .filter(n => savedSet.has(n.place_id))  // ← solo guardados
      .map(n => n.neighborhood)
      .filter(Boolean)
  )].sort((a, b) => a.localeCompare(b, "es"));

  const currentValue = activeFilters.neighborhood || "";
  select.innerHTML = [
    `<option value="">Todos los barrios</option>`,
    ...neighborhoods.map(n => `<option value="${n}">${n}</option>`),
  ].join("");
  select.value = currentValue;
}

function renderTagButtons() {
  const wrap = document.getElementById("filters-tags");
  if (!wrap) return;

  const availableTags = getAvailableTags();

  if (!availableTags.length) {
    wrap.innerHTML = `<span style="color:rgba(255,255,255,0.3);font-size:11px">
      Agrega lugares al mapa para ver filtros
    </span>`;
    return;
  }

  wrap.innerHTML = availableTags.map(tag => {
    const active = activeFilters.tags.includes(tag) ? "active" : "";
    const label = tag.charAt(0).toUpperCase() + tag.slice(1);
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
  activeFilters = { tags: [], neighborhood: null, minRating: 0 };
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

  document.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      toggleFilterPanel(false);
    }
  });

  syncFilterUI();
});