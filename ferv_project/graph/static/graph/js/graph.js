const width = 600, height = 600;
const nodes = [
  { id: 1, label: "A"},
  { id: 2, label: "B"},
  { id: 3, label: "C"},
  { id: 4, label: "D"},
  { id: 5, label: "E"},
  { id: 6, label: "F"},
  { id: 7, label: "G"},
  { id: 8, label: "H"},
  { id: 9, label: "I"},
  { id: 10, label: "J"},
  { id: 11, label: "K"},
  { id: 12, label: "L"},
  { id: 13, label: "M"},
  { id: 14, label: "N"}
];

const edges = [
  { source: 0, target: 7 },
  { source: 1, target: 10 },
  { source: 2, target: 5 },
  { source: 3, target: 12 },
  { source: 4, target: 9 },
  { source: 6, target: 11 },
  { source: 8, target: 13 },
  { source: 5, target: 0 },
  { source: 7, target: 2 },
  { source: 9, target: 3 },
  { source: 10, target: 4 },
  { source: 11, target: 1 },
  { source: 12, target: 6 },
  { source: 13, target: 8 },
  { source: 2, target: 11 },
  { source: 4, target: 12 },
  { source: 0, target: 13 },
  { source: 6, target: 9 }
];


const svg = d3.select('#graph');
const g = svg.append('g');

const lines = g.selectAll("line")
.data(edges)
.enter()
.append("line")
.attr("stroke", "#999")
.attr("stroke-width", 2);

const circles = g.selectAll("circle")
  .data(nodes)
  .enter()
  .append("circle")
  .attr("r", 20)
  .attr("fill", "steelblue");

const labels = g.selectAll("text")
  .data(nodes)
  .enter()
  .append("text")
  .attr("text-anchor", "middle")   // horizontal center
  .attr("dominant-baseline", "middle")  // vertical center
  .attr("fill", "white")
  .text(d => d.label);

// --- DRAG BEHAVIOR ---
const drag = d3.drag()
  .on("start", (event, d) => {
    if (!event.active) simulation.alpha(0.5).restart(); // reheat gently
    d.fx = d.x;
    d.fy = d.y;
  })
  .on("drag", (event, d) => {
    d.fx = event.x;
    d.fy = event.y;
  })
  .on("end", (event, d) => {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
  });

  // --- ZOOM BEHAVIOR ---
const zoom = d3.zoom()
  .scaleExtent([0.3, 3])  // min and max zoom levels
  .on("zoom", (event) => {
    g.attr("transform", event.transform);
  });

// --- THE SIMULATION ---
const simulation = d3.forceSimulation(nodes)
  .force("link", d3.forceLink(edges).distance(100))
  .force("charge", d3.forceManyBody().strength(-100))
  .force("center", d3.forceCenter(width / 2, height / 2));

// --- THE TICK ---
simulation.on("tick", () => {
  svg.call(zoom);
  lines
    .attr("x1", d => d.source.x)
    .attr("y1", d => d.source.y)
    .attr("x2", d => d.target.x)
    .attr("y2", d => d.target.y);

  circles
    .attr("cx", d => d.x)
    .attr("cy", d => d.y)
    .on("click", (event, d) => {
        console.log(`Node ${d.label} clicked! x: ${d.x}, y: ${d.y}`);
    })
    .call(drag);

  labels
    .attr("x", d => d.x)
    .attr("y", d => d.y);
});