// ══════════════════════════════════════════════════════════════
//  ferv-explore.js  — Panel de modo exploración (Pipeline C)
//
//  DEPENDE DE: ferv-state.js, ferv-map.js (runExploratoryMode),
//              ferv-ui.js (showToast)
// ══════════════════════════════════════════════════════════════

function toggleExplorePanel(forceOpen) {
  const panel = document.getElementById("explore-panel");
  const fab   = document.getElementById("explore-fab");
  if (!panel || !fab) return;

  const shouldOpen = typeof forceOpen === "boolean"
    ? forceOpen
    : !panel.classList.contains("open");

  panel.classList.toggle("open", shouldOpen);
  panel.setAttribute("aria-hidden", shouldOpen ? "false" : "true");
  fab.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
}

function closeExplorePanel() {
  toggleExplorePanel(false);
}

function heatLabel(v) {
  if (v <= 0.2) return "Cercano a ti";
  if (v <= 0.5) return "Moderado";
  if (v <= 0.8) return "Aventurero";
  return "Sorpréndeme";
}

document.addEventListener("DOMContentLoaded", () => {
  const fab       = document.getElementById("explore-fab");
  const closeBtn  = document.getElementById("explore-panel-close");
  const runBtn    = document.getElementById("explore-run-btn");
  const heatInput = document.getElementById("explore-heat");
  const heatValue = document.getElementById("explore-heat-value");

  if (!fab) return;

  if (heatValue && heatInput) {
    heatValue.textContent = heatLabel(Number(heatInput.value));
  }

  fab.addEventListener("click", () => toggleExplorePanel());
  closeBtn?.addEventListener("click", () => closeExplorePanel());

  heatInput?.addEventListener("input", () => {
    if (heatValue) heatValue.textContent = heatLabel(Number(heatInput.value));
  });

  runBtn?.addEventListener("click", () => {
    const heat = Number(heatInput?.value ?? 0.5);
    runExploratoryMode(heat);
  });

  document.addEventListener("keydown", e => {
    if (e.key === "Escape") closeExplorePanel();
  });
});
