// ══════════════════════════════════════════════════════════════
//  ferv-state.js  — Estado global compartido
//
//  DEPENDE DE: nada (debe cargarse antes que api, search, map, panel, ui)
//
//  Todos los demás módulos leen y escriben estas variables directamente.
//  No hay getters/setters — es estado mutable compartido, apropiado
//  para una app vanilla JS de este tamaño.
// ══════════════════════════════════════════════════════════════

let allNodes      = {};        // place_id → node object (con x, y)
let savedSet      = new Set(); // place_ids guardados en el mapa personal
let suggestIds    = new Set(); // place_ids de la búsqueda actual
let discoveredSet = new Set(); // place_ids en la lista de descubrimiento
let mapEdges      = [];        // edges entre nodos guardados (persistentes, cyan)
let searchEdges   = [];        // edges de la búsqueda actual (temporales, morado)
let queries       = [];        // historial de queries para los chips del canvas
let simulation    = null;      // instancia D3 forceSimulation activa
let svgG          = null;      // grupo SVG principal (para zoom)
let selectedD     = null;      // nodo seleccionado actualmente en el panel
