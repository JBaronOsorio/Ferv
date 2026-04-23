// ══════════════════════════════════════════════════════════════
//  ferv-config.js  — Constantes visuales y helpers de color
//
//  DEPENDE DE: nada (debe cargarse primero)
// ══════════════════════════════════════════════════════════════

// Color de nodo cuando está SUGERIDO (no guardado)
const SUGGESTED_COLOR = {
  stroke: "rgba(255,255,255,0.18)",
  fill:   "rgba(255,255,255,0.04)",
  text:   "rgba(255,255,255,0.35)",
};

// Paleta de colores para nodos GUARDADOS
// Se asigna dinámicamente por barrio la primera vez que se guarda un nodo de ese barrio.
const SAVED_PALETTE = [
  "#9b6bfa",  // purple
  "#fa6b8a",  // pink
  "#6bfac8",  // mint
];

// Mapa dinámico: neighborhood → color asignado
const neighborhoodColorMap = {};
let paletteIndex = 0;

function getSavedColor(neighborhood) {
  if (!neighborhood) return SAVED_PALETTE[0];
  if (!neighborhoodColorMap[neighborhood]) {
    neighborhoodColorMap[neighborhood] = SAVED_PALETTE[paletteIndex % SAVED_PALETTE.length];
    paletteIndex++;
  }
  return neighborhoodColorMap[neighborhood];
}

// Devuelve el color correcto según el estado del nodo
function nodeColor(d) {
  if (savedSet.has(d.place_id)) return getSavedColor(d.neighborhood);
  return null; // null = usar SUGGESTED_COLOR
}

// Trunca un string a n caracteres
function trunc(s, n) {
  return s && s.length > n ? s.slice(0, n) + "…" : (s || "");
}
