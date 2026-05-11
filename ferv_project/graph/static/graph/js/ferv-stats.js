// ══════════════════════════════════════════════════════════════
//  ferv-stats.js  — Modal de estadísticas del usuario
//
//  DEPENDE DE: ferv-ui.js (showToast)
// ══════════════════════════════════════════════════════════════

function openStatsModal() {
  const modal = document.getElementById("stats-modal");
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
  loadStats();
}

function closeStatsModal() {
  const modal = document.getElementById("stats-modal");
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
}

async function loadStats() {
  const container = document.getElementById("stats-content");
  container.innerHTML = '<div class="stats-loading">Cargando estadísticas...</div>';

  try {
    const resp = await fetch("/graph/api/stats/", {
      headers: { "Accept": "application/json" }
    });
    if (!resp.ok) throw new Error(`stats error ${resp.status}`);
    const data = await resp.json();
    renderStats(data);
  } catch (_err) {
    container.innerHTML = `
      <div class="stats-error">
        <p>No se pudieron cargar las estadísticas</p>
        <button class="stats-retry-btn" onclick="loadStats()">Reintentar</button>
      </div>`;
  }
}

function renderStats(data) {
  const { counts, top_tags, top_neighborhoods, updated_at } = data;
  const container = document.getElementById("stats-content");
  const total = counts.in_graph + counts.visited + counts.discovery;

  if (total === 0) {
    container.innerHTML = `
      <div class="stats-empty">
        <div class="stats-empty__icon">✦</div>
        <p class="stats-empty__msg">Tu mapa está esperando por ti</p>
        <p class="stats-empty__hint">Explora y guarda lugares para ver tu actividad aquí</p>
      </div>`;
    return;
  }

  const cardsHtml = `
    <div class="stats-cards">
      <div class="stats-card stats-card--map">
        <div class="stats-card__num">${counts.in_graph}</div>
        <div class="stats-card__label">En mi mapa</div>
      </div>
      <div class="stats-card stats-card--visited">
        <div class="stats-card__num">${counts.visited}</div>
        <div class="stats-card__label">Visitados</div>
      </div>
      <div class="stats-card stats-card--discovery">
        <div class="stats-card__num">${counts.discovery}</div>
        <div class="stats-card__label">En mi lista</div>
      </div>
    </div>`;

  const maxTag = top_tags[0]?.count || 1;
  const tagsHtml = top_tags.length ? `
    <div class="stats-section">
      <div class="stats-section__label">Categorías frecuentes</div>
      ${top_tags.map(t => `
        <div class="stats-bar-row">
          <span class="stats-bar-name">${t.tag}</span>
          <div class="stats-bar-track">
            <div class="stats-bar-fill stats-bar-fill--tag"
              style="width:${(t.count / maxTag * 100).toFixed(1)}%"></div>
          </div>
          <span class="stats-bar-count">${t.count}</span>
        </div>`).join("")}
    </div>` : "";

  const maxNeigh = top_neighborhoods[0]?.count || 1;
  const neighHtml = top_neighborhoods.length ? `
    <div class="stats-section">
      <div class="stats-section__label">Barrios frecuentes</div>
      ${top_neighborhoods.map(n => `
        <div class="stats-bar-row">
          <span class="stats-bar-name">${n.neighborhood}</span>
          <div class="stats-bar-track">
            <div class="stats-bar-fill stats-bar-fill--neigh"
              style="width:${(n.count / maxNeigh * 100).toFixed(1)}%"></div>
          </div>
          <span class="stats-bar-count">${n.count}</span>
        </div>`).join("")}
    </div>` : "";

  const date = new Date(updated_at);
  const updatedStr = date.toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" });

  container.innerHTML = cardsHtml + tagsHtml + neighHtml +
    `<div class="stats-footer">Actualizado: ${updatedStr}</div>`;
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("open-stats-btn")?.addEventListener("click", () => {
    document.getElementById("userMenu")?.classList.remove("open");
    openStatsModal();
  });

  document.getElementById("stats-modal-close")?.addEventListener("click", closeStatsModal);

  document.getElementById("stats-modal")?.addEventListener("click", e => {
    if (e.target.id === "stats-modal") closeStatsModal();
  });

  document.addEventListener("keydown", e => {
    if (e.key === "Escape") closeStatsModal();
  });
});
