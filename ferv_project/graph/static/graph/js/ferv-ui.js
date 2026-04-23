// ══════════════════════════════════════════════════════════════
//  ferv-ui.js  — HUD, toasts, chat, user menu y carga inicial
//
//  DEPENDE DE: ferv-config.js, ferv-state.js, ferv-api.js,
//              ferv-map.js (rerender), ferv-panel.js (closePanel)
// ══════════════════════════════════════════════════════════════


// ── HUD ──────────────────────────────────────────────────────

function updateHUD() {
  document.getElementById("hud-suggested").textContent = Object.keys(allNodes).length - savedSet.size;
  document.getElementById("hud-saved").textContent = savedSet.size;
}

function updateQueryTags() {
  const el = document.getElementById("query-tags");
  el.innerHTML = queries.map(q => `<div class="q-tag">${q}</div>`).join("");
}

function showToast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2800);
}


// ── Chat ─────────────────────────────────────────────────────

// ── Chat ─────────────────────────────────────────────────────
// Las funciones se definen fuera del DOMContentLoaded para que
// puedan ser llamadas desde otros módulos si es necesario.

function chatAddMsg(text, type) {
  const chatMsgs = document.getElementById("chatMessages");
  const d = document.createElement("div");
  d.className = "chat-msg " + type;
  d.textContent = text;
  chatMsgs.appendChild(d);
  chatMsgs.scrollTop = chatMsgs.scrollHeight;
}

async function chatSend() {
  const chatInput = document.getElementById("chatInput");
  const txt = chatInput.value.trim();
  if (!txt) return;
  chatAddMsg(txt, "user");
  chatInput.value = "";
  // TODO: reemplazar con llamada real al endpoint de chat
  chatAddMsg("Buscando lugares para ti...", "bot");
}

document.addEventListener("DOMContentLoaded", () => {
  // ── Chat ──
  const chatBubble = document.getElementById("chatBubble");
  const chatPanel  = document.getElementById("chatPanel");
  const chatInput  = document.getElementById("chatInput");

  chatBubble.addEventListener("click", () => {
    const isOpen = chatPanel.classList.toggle("open");
    chatBubble.classList.toggle("open", isOpen);
    if (isOpen) setTimeout(() => chatInput.focus(), 250);
  });

  document.getElementById("chatSendBtn").addEventListener("click", chatSend);
  chatInput.addEventListener("keydown", e => { if (e.key === "Enter") chatSend(); });

  // ── User menu ──
  const userMenu      = document.getElementById("userMenu");
  const userAvatarBtn = document.getElementById("userAvatarBtn");

  userAvatarBtn.addEventListener("click", e => {
    e.stopPropagation();
    userMenu.classList.toggle("open");
  });

  document.addEventListener("click", () => {
    userMenu.classList.remove("open");
  });

  // ── Carga inicial del mapa ──
  loadUserMap();
});

async function loadUserMap() {
  try {
    const data = await fetchUserGraph();
    if (!data.nodes.length) return;      // mapa vacío, mostrar empty state

    const W = document.querySelector(".canvas-wrap").clientWidth;
    const H = document.querySelector(".canvas-wrap").clientHeight;

    data.nodes.forEach(n => {
      if (!allNodes[n.place_id]) {
        allNodes[n.place_id] = {
          ...n,
          x: W / 2 + (Math.random() - 0.5) * 300,
          y: H / 2 + (Math.random() - 0.5) * 300,
          vx: 0, vy: 0,
        };
      }
      if (n.status === "in_graph") {
        getSavedColor(n.neighborhood);
        savedSet.add(n.place_id);
        allNodes[n.place_id].fx = allNodes[n.place_id].x;
        allNodes[n.place_id].fy = allNodes[n.place_id].y;
        suggestIds.add(n.place_id);
      }
    });

    data.edges.forEach(e => {
      console.log("Edge:", e);
      const src = Object.values(allNodes).find(n => n.id === e.from);
      const tgt = Object.values(allNodes).find(n => n.id === e.to);
      console.log("src:", src, "tgt:", tgt);

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

  } catch (err) {
    console.error("Error cargando mapa:", err);
  }
}