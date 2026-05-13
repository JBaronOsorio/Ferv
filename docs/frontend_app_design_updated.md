# Ferv — Frontend Architecture Design (Actualizado)

**Status:** Documento de referencia activo — sprint actual
**Scope:** Graph view frontend (`ferv_project/graph/static/graph/js/`)
**Anterior:** `frontend_app_design.md` (versión draft original — conservado sin modificar)
**Companion doc:** `recommendation_pipelines.md` (backend pipelines)

---

## 1. Objetivos

Definir los límites de módulos del frontend del mapa para que:

- Cada módulo tenga una responsabilidad única y nombrable.
- El estado tenga una única fuente de verdad, derivable del backend.
- Nuevos tipos de recomendación (chat, contextual, exploratoria) puedan agregarse sin reestructurar.
- Rendering, orquestación y chrome de UI no estén entrelazados.

Este documento refleja el estado **actual** del código después del sprint de HU03, HU08, HU11 y HU12, incluyendo las correcciones realizadas durante la implementación.

---

## 2. Módulos — tabla completa (estado actual)

Trece módulos activos en producción:

| Módulo | Responsabilidad | Escribe estado? |
|---|---|---|
| `ferv-config.js` | Constantes visuales: paletas, mapa barrio→color, helper `trunc` | No — puramente declarativo |
| `ferv-state.js` | Globals mutables compartidos: `allNodes`, `mapEdges`, `searchEdges`, `queries`, handles D3 (`simulation`, `svgG`, `selectedD`) | Declara; los demás leen/escriben |
| `ferv-api.js` | Capa HTTP: fetch al backend, CSRF, `parseNode`/`parseEdge`, `fetchNodeBasedRecommendations`, `fetchExploratoryRecommendations` | No |
| `ferv-recommendations.js` | Dispatcher del pipeline de recomendación one-shot. Merge de resultados en `allNodes`, trigger de redraw | Sí (`allNodes`, `searchEdges`, `queries`) |
| `ferv-controller.js` | Orquestación de mutaciones del grafo: `loadUserMap`, `saveNode`, `removeNode` | Sí (`allNodes`, `mapEdges`) |
| `ferv-map.js` | Rendering puro + D3 force simulation. `rerender()`. También expone `runExploratoryMode(heat)` y `exploreFromNode(placeId)` | No (solo handles D3) |
| `ferv-filters.js` | Estado del panel de filtros + `getFilteredVisibleNodes`. Tags extraídas dinámicamente de `allNodes` | Sí (propio `activeFilters`) |
| `ferv-panel.js` | Componente panel de detalle. Lógica de display, botones add/remove/explore, modal de confirmación. Delega mutaciones al controller | Sí (`selectedD`) |
| `ferv-chat.js` | Componente chat. Estado de mensajes, botón send, dispatch a recommendations | Sí (estado conversación propio) |
| `ferv-ui.js` | Chrome de la app: contadores HUD, toasts, chips de query, menú de usuario. Utilidades UI compartidas | No |
| `ferv-explore.js` | Componente panel exploratorio (HU11). FAB, slider de calor, `toggleExplorePanel`, `closeExplorePanel` | No — delega a `ferv-map.js` |
| `ferv-export.js` | Exportar mapa (HU08). SVG→Canvas→PNG, descarga automática | No |
| `ferv-stats.js` | Modal de estadísticas (HU12). Fetch, render de tarjetas y barras, retry | No |

### Principios de diseño

- **Única fuente de verdad: `node.status`.** Cada nodo lleva `status: "recommendation" | "in_graph" | "visited" | "discovery"`. No hay Sets paralelos. `allNodes` está indexado por `place_id` para lookup O(1).
- **Rendering por pull.** Mutaciones de estado nunca re-dibujan solas. Toda operación que muta estado termina con `rerender()` explícito.
- **Módulo por responsabilidad, componente para UI autocontenida.** Chrome compartido en `ferv-ui.js`. Superficies autocontenidas con su propio estado (panel, chat, explore, stats) son sus propios componentes.
- **El controller posee las mutaciones.** Cualquier cambio en `allNodes` o `mapEdges` coordinado con el backend va por `ferv-controller.js`.
- **Las recomendaciones se despachan, no se buscan.** El input del usuario es una petición de recomendación.

---

## 3. Estructuras compartidas y convenciones

### 3.1 Shape del estado (`ferv-state.js`)

```js
let allNodes    = {};   // place_id → node object (con x, y, status)
let mapEdges    = [];   // edges persistentes entre nodos in_graph/visited (cyan)
let searchEdges = [];   // edges transitorios de recomendaciones (purple)
let queries     = [];   // historial de prompts (chips)
let simulation  = null; // D3 forceSimulation activo
let svgG        = null; // grupo SVG raíz para zoom transform
let selectedD   = null; // nodo actualmente en el panel de detalle
```

### 3.2 Shape del nodo

Después de `parseNode` (en `ferv-api.js`):

```js
{
  id:           "<GraphNode.id>",
  place_id:     "<Place.place_id>",
  name:         "<Place.name>",
  neighborhood: "<Place.neighborhood>",
  rating:       <float>,
  tags:         ["tag1", "tag2"],   // strings planos
  status:       "recommendation" | "in_graph" | "visited" | "discovery",
  x: <number>, y: <number>, vx: 0, vy: 0,
}
```

Los nodos retornados por Pipeline B node-based y Pipeline C exploratorio usan un parser específico en `ferv-api.js` (no `parseNode`) porque el backend devuelve `node_id` (no `id`) y sin `tags`.

### 3.3 Shape del edge

```js
{
  source: <node ref>,   // hidratado al objeto nodo real
  target: <node ref>,
  weight: <float 0–1>,
  reason: "<texto corto>",
  type:   "map" | "search",
}
```

### 3.4 Convenciones de status

| Status | Dónde aparece | Visible en mapa |
|---|---|---|
| `recommendation` | Resultado de Pipeline A/B/C | Sí (gris/púrpura) |
| `in_graph` | Guardado por el usuario | Sí (color de barrio) |
| `visited` | Marcado como visitado desde discovery | Sí (color de barrio + borde verde) |
| `discovery` | Lista de pendientes | **No** en el mapa SVG — solo en panel lateral |

### 3.5 Orden de carga (HTML)

```
ferv-config.js → ferv-state.js → ferv-api.js
  → ferv-map.js → ferv-filters.js → ferv-recommendations.js
  → ferv-controller.js → ferv-panel.js → ferv-chat.js → ferv-ui.js
  → ferv-explore.js → ferv-export.js → ferv-stats.js
```

Los tres módulos nuevos van al final porque dependen de state + controller + map.

### 3.6 Convención de loading overlay

Todas las operaciones async que pueden durar >300ms usan el overlay de carga global:

```js
showMapLoading("Texto descriptivo...");
try {
  await operacionAsync();
} finally {
  hideMapLoading();
}
```

`showMapLoading` / `hideMapLoading` están en `ferv-ui.js`. El overlay es un `<div id="map-loading-overlay">` con spinner y texto, absoluto sobre el SVG con `z-index: 35`.

---

## 4. Pipelines de operación

Seis pipelines cubren todo lo que hace el frontend:

### 4.1 Carga inicial

**Trigger:** `DOMContentLoaded` en `ferv-ui.js` llama `loadUserMap()`.
**Owner:** `ferv-controller.js`.

1. Controller llama `fetchUserGraph()` → `GET /graph/api/fetch-graph/`.
2. Backend retorna nodos `in_graph` + `visited` + edges persistentes.
3. Controller hidrata `allNodes` (indexado por `place_id`) y `mapEdges`.
4. Controller llama `updateHUD()` y `rerender()`.

Si el grafo está vacío, se muestra estado vacío y se salta el rendering.

### 4.2 Recomendación one-shot (Pipeline A)

**Trigger:** Usuario envía prompt via input de recomendación.
**Owner:** `ferv-recommendations.js`.

1. Dispatcher recibe `(promptText)`. Llama `fetchRecommendations(promptText)` → `GET /graph/api/one_shot_recommendation/<query>`.
2. Nodos `recommendation` anteriores se eliminan de `allNodes`.
3. Nuevos nodos se mergean en `allNodes` con coordenadas cerca del centro.
4. `searchEdges` se reconstruye (actualmente siempre vacío desde el backend).
5. Dispatcher pushea prompt a `queries`, llama `updateQueryTags()`, `updateHUD()`, `rerender()`.

### 4.3 Agregar nodo al mapa (Pipeline B — add)

**Trigger:** Usuario hace clic en "Agregar" en `ferv-panel.js`.
**Owner:** `ferv-controller.js`.

1. Panel llama `saveNode(placeId)`. El panel no muta estado.
2. Controller llama `addNodeToBackend(placeId)` → `POST /graph/add-node/`.
3. Backend crea edges (Pipeline B) y retorna `edge_ids + reasons + weights`.
4. Controller setea `node.status = "in_graph"` y pushea los edges a `mapEdges`.
5. Controller llama `updateHUD()` y `rerender()`.

### 4.4 Explorar similares desde nodo (Pipeline B — node-based, HU03)

**Trigger:** Usuario hace clic en "↗ Explorar similares" en el panel de un nodo `in_graph` o `visited`.
**Owner:** `ferv-map.js` (función `exploreFromNode`).

1. Panel llama `exploreFromNode(placeId)`. Cierra panel, muestra loading overlay.
2. Map clears nodos `recommendation` y `searchEdges` anteriores.
3. Llama `fetchNodeBasedRecommendations(nodeId)` → `POST /api/recommendation/node_based/` con `{ node_ids: [nodeId] }`.
4. Posiciona nuevos nodos ±260px alrededor del nodo ancla.
5. Mergea en `allNodes`, llama `rerender()`. `finally`: `hideMapLoading()`.

**Botón visible:** solo si `status === "in_graph"` o `status === "visited"`.

### 4.5 Recomendaciones exploratorias (Pipeline C, HU11)

**Trigger:** Usuario ajusta slider de calor y hace clic en "Explorar" en el panel lateral del FAB.
**Owner:** `ferv-map.js` (función `runExploratoryMode`).

1. Valida que el usuario tenga ≥1 nodo guardado (`in_graph` o `visited`).
2. Muestra loading overlay. Clears nodos `recommendation` y `searchEdges`.
3. Llama `fetchExploratoryRecommendations(heat)` → `POST /api/recommendation/exploratory/` con `{ heat: <float 0–1> }`.
4. Posiciona nuevos nodos cerca del centroide de nodos guardados ±300px.
5. Mergea en `allNodes`, llama `rerender()`. `finally`: `hideMapLoading()`.

**Slider de calor:** 4 niveles con label dinámico:
- ≤ 0.2 → "Cercano a ti"
- ≤ 0.5 → "Moderado"
- ≤ 0.8 → "Aventurero"
- > 0.8 → "Sorpréndeme"

### 4.6 Eliminar nodo del mapa

**Trigger:** Usuario confirma eliminación en el modal de confirmación del panel.
**Owner:** `ferv-controller.js`.

1. Panel llama `removeNode(placeId)`.
2. Controller filtra `mapEdges` para eliminar edges que tocan este nodo.
3. Llama `removeNodeFromBackend(placeId)` → `DELETE /graph/api/delete_node/<id>`.
4. En éxito, elimina el nodo de `allNodes`. Cierra panel, llama `updateHUD()` y `rerender()`.

### 4.7 Filtrado

**Trigger:** Usuario activa tags, barrio o rating en el panel de filtros.
**Owner:** `ferv-filters.js`.

Filtrado se aplica en tiempo de render, no de mutación. `getFilteredVisibleNodes()` es llamado por `rerender()`:
- Nodos `in_graph`/`visited` pasan `matchesActiveFilters` (tags, barrio, minRating).
- Nodos `recommendation` siempre pasan — la petición actual no se filtra.

**Tags dinámicas:** `getAvailableTags()` extrae tags únicas de `allNodes` ordenadas alfabéticamente. Tags stale en `activeFilters` se podan al re-renderizar los botones.

---

## 5. Contratos de componentes

### 5.1 Panel (`ferv-panel.js`)

- **Público:** `openPanel(d, edges)`, `closePanel()`.
- **Lee:** `selectedD`, status del nodo pasado.
- **Muta:** solo `selectedD`.
- **Delega:** `saveNode` y `removeNode` al controller; `exploreFromNode` a `ferv-map.js`.
- **Botón explorar:** visible (`display: "block"`) solo para `in_graph` y `visited`. Oculto (`display: "none"`) para `recommendation`.

### 5.2 Chat (`ferv-chat.js`)

- **Público:** `chatAddMsg(text, type)`, `chatSend()`.
- **Posee:** estado de mensajes DOM dentro de `#chatMessages`.
- **Delega:** dispatch de mensajes a `ferv-recommendations.js`.

### 5.3 Panel exploratorio (`ferv-explore.js`)

- **Público:** `toggleExplorePanel(forceOpen)`, `closeExplorePanel()`.
- **Posee:** estado del slider de calor, label dinámico del nivel.
- **Delega:** la ejecución a `runExploratoryMode(heat)` en `ferv-map.js`.
- **FAB:** esquina inferior derecha (`right: 20px; bottom: 80px`), gradiente ámbar-naranja.

### 5.4 Exportar mapa (`ferv-export.js`)

- **Público:** `exportMap()`.
- **Flujo:** serializa SVG con `XMLSerializer`, inyecta `xmlns` + dimensiones, dibuja en Canvas 2× (retina) con fondo `#0a0a0a`, descarga como `ferv-mapa-YYYY-MM-DD.png`.
- **Limitación conocida:** fuentes de Google Fonts no se incrustan por CORS — el texto exportado usa fallback del sistema.

### 5.5 Modal de estadísticas (`ferv-stats.js`)

- **Público:** `openStatsModal()`, `closeStatsModal()`.
- **Flujo:** fetch → `GET /graph/api/stats/` cada vez que se abre el modal.
- **Renderiza:**
  - Estado vacío (total === 0): mensaje motivacional con ícono ✦.
  - Estado error: mensaje de error + botón "Reintentar".
  - Estado normal: 3 tarjetas (en mapa / visitados / en lista) + barras proporcionales de tags + barras de barrios + timestamp.
- **Endpoint backend:** `user_stats` view en `graph/views.py` usando `Counter` para tags y `annotate(count=Count('id'))` para barrios.

---

## 6. Endpoints del backend (referencia rápida)

| Método | URL | Descripción |
|---|---|---|
| GET | `/graph/api/fetch-graph/` | Nodos `in_graph`+`visited` + edges del usuario |
| GET | `/graph/api/one_shot_recommendation/<query>` | Pipeline A — recomendación por texto |
| POST | `/graph/add-node/` | Guarda nodo en mapa (Pipeline B add) |
| DELETE | `/graph/api/delete_node/<id>` | Elimina nodo del mapa |
| GET | `/graph/api/discovery-list/` | Lista de nodos en `discovery` |
| POST | `/graph/api/add-to-discovery/` | Mueve nodo a lista de descubrimiento |
| PATCH | `/graph/api/mark-visited/<id>/` | Marca nodo discovery como visitado |
| GET | `/graph/api/stats/` | Estadísticas del usuario |
| POST | `/api/recommendation/node_based/` | Pipeline B seeded by node — explorar similares |
| POST | `/api/recommendation/exploratory/` | Pipeline C — recomendación exploratoria por calor |

---

## 7. Issues resueltos (vs. documento original)

| Issue original | Resolución |
|---|---|
| Tag filter nunca matcheaba (`t.tag === tag`) | Corregido: tags son strings planos → `t === tag`. Tags ahora dinámicas desde `allNodes` |
| Pinning `fx`/`fy` en `loadUserMap` | Eliminado |
| `crossReason()` dead code | Eliminado |
| `nodeColor()` dead code | Eliminado |
| `graph.js` dead code | Eliminado |
| Comentario stale sobre `delete_node` | Actualizado |
| `MOCK_MODE` sin documentar | Documentado como flag de testing local, nunca en producción |
| `GraphNode.rationale` no surfaceado | Pendiente (ver §8) |
| Status `visited` no habilitaba botón "↗ Explorar similares" | Fix en `ferv-panel.js` (`display: "block"`) y en `recommendation_service.py` (`status__in=["in_graph", "visited"]`) |

---

## 8. Issues pendientes / trabajo restante

### Críticos

- **`GraphNode.rationale` sin surfacear.** El backend produce un campo de rationale por nodo. `parseNode` no lo extrae, el panel no lo muestra. Wiring pendiente cuando el campo esté poblado consistentemente.
- **`searchEdges` siempre vacíos.** El backend de recomendación one-shot no retorna edges entre recomendaciones. Si se decide agregar clustering visual, esta lane ya está reservada en state y render.

### UX / mejoras menores

- **Discovery list en el mapa.** Los nodos `discovery` no aparecen en el mapa SVG. Podrían mostrarse como marcadores semi-transparentes o en una capa separada.
- **Persistencia de posición de nodos.** Las posiciones x/y se recalculan en cada sesión. Guardar las posiciones en `localStorage` mejoraría la experiencia de usuarios con mapas grandes.
- **Animación al agregar nodo.** Al promover un `recommendation` a `in_graph`, el nodo podría animarse (escala + cambio de color) para feedback visual.
- **Panel de discovery en mobile.** El panel lateral de discovery no está optimizado para pantallas < 768px.

### Post-MVP — exportación con fuentes

El PNG exportado usa fuentes fallback del sistema porque Google Fonts bloquea el canvas por CORS. Tres opciones para corregirlo:

1. **Hostear fuentes localmente** (recomendado para producción): servir el `.woff2` desde `/static/`, inyectarlo como `@font-face` base64 en el blob SVG antes de rasterizar. Sin CORS, canvas lo acepta.
2. **`html2canvas`**: librería que snapshots el DOM completo incluyendo fuentes aplicadas. Drop-in más simple, genera PNG del área visible (no solo el SVG). Trade-off: dependencia externa ~45 KB.
3. **`opentype.js` + paths vectoriales**: parsear el `.woff2` y convertir texto a `<path>` antes de exportar. Máxima fidelidad, máxima complejidad.

---

## 9. Historias de usuario — estado

| HU | Descripción | Estado |
|---|---|---|
| HU01 | Ver mapa propio | ✅ Completo |
| HU02 | Agregar lugar al mapa | ✅ Completo |
| HU03 | Explorar similares desde nodo | ✅ Completo (Pipeline B) |
| HU04 | Recomendación por texto (one-shot) | ✅ Completo (Pipeline A) |
| HU05 | Eliminar lugar del mapa | ✅ Completo |
| HU06 | Filtrar mapa | ✅ Completo (tags dinámicas) |
| HU07 | Lista de descubrimiento | ✅ Completo (panel lateral) |
| HU08 | Exportar mapa como imagen | ✅ Completo (PNG, limitación de fuentes documentada) |
| HU09 | Marcar lugar como visitado | ✅ Completo |
| HU10 | Ver detalle de lugar | ✅ Completo (panel) |
| HU11 | Recomendaciones exploratorias | ✅ Completo (Pipeline C + slider calor) |
| HU12 | Estadísticas de usuario | ✅ Completo (modal con tarjetas + barras) |
| HU13 | Chat conversacional | 🔲 Pendiente — stub presente, endpoint backend aún no definido |

---

## 10. Posibles mejoras futuras (no MVP)

- **Service Worker / cache offline:** permitir ver el mapa guardado sin conexión.
- **Zoom to fit al cargar:** centrar automáticamente el grafo al abrir el mapa.
- **Modo oscuro toggle:** actualmente fijo en tema oscuro; variable CSS permite cambio.
- **Clustering visual por barrio:** agrupar nodos del mismo barrio con un hull visual.
- **Tooltips en edges:** mostrar `reason` del edge al hacer hover sobre la línea.
- **Búsqueda de nodos en el mapa:** highlight de nodo por nombre sin navegar por el grafo.
- **Export a PDF:** extender `ferv-export.js` con `jsPDF` para documentos multipage.
- **Modo presentación:** ocultar chrome de UI y solo mostrar el grafo, para demos.
