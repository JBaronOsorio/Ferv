// ══════════════════════════════════════════════════════════════
//  ferv-export.js  — Exportación del mapa como imagen PNG
//
//  DEPENDE DE: ferv-state.js (allNodes), ferv-ui.js (showToast)
// ══════════════════════════════════════════════════════════════

function exportMap() {
  const hasNodes = Object.values(allNodes).some(n =>
    n.status === "in_graph" || n.status === "visited" || n.status === "recommendation"
  );

  if (!hasNodes) {
    showToast("Tu mapa está vacío. Agrega lugares antes de exportar.");
    return;
  }

  const svg = document.getElementById("ferv-svg");
  const W   = svg.clientWidth;
  const H   = svg.clientHeight;

  const serializer = new XMLSerializer();
  let svgStr = serializer.serializeToString(svg);

  if (!svgStr.includes('xmlns="http://www.w3.org/2000/svg"')) {
    svgStr = svgStr.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"');
  }
  svgStr = svgStr.replace(/<svg\s/, `<svg width="${W}" height="${H}" `);

  const blob = new Blob([svgStr], { type: "image/svg+xml;charset=utf-8" });
  const svgUrl = URL.createObjectURL(blob);

  const img = new Image();

  img.onload = () => {
    const scale  = 2;
    const canvas = document.createElement("canvas");
    canvas.width  = W * scale;
    canvas.height = H * scale;

    const ctx = canvas.getContext("2d");
    ctx.scale(scale, scale);
    ctx.fillStyle = "#0a0a0a";
    ctx.fillRect(0, 0, W, H);
    ctx.drawImage(img, 0, 0, W, H);
    URL.revokeObjectURL(svgUrl);

    canvas.toBlob(pngBlob => {
      if (!pngBlob) {
        showToast("Error al generar la imagen. Intenta de nuevo.");
        return;
      }
      const date = new Date().toISOString().slice(0, 10);
      const a    = document.createElement("a");
      a.href     = URL.createObjectURL(pngBlob);
      a.download = `ferv-mapa-${date}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(a.href);
      showToast("Mapa exportado correctamente");
    }, "image/png");
  };

  img.onerror = () => {
    URL.revokeObjectURL(svgUrl);
    showToast("Error al exportar el mapa. Intenta de nuevo.");
  };

  img.src = svgUrl;
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("export-btn")?.addEventListener("click", exportMap);
});
