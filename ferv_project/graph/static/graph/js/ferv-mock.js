// ══════════════════════════════════════════════════════════════
//  ferv-mock.js  — Datos de prueba (eliminar cuando el back esté listo)
//
//  DEPENDE DE: nada
// ══════════════════════════════════════════════════════════════

const MOCK = {
  cafe: {
    nodes: [
      { id:"c1", place_id:"p001", name:"Pergamino Café",  neighborhood:"El Poblado", rating:4.8, tags:["especialidad","coworking","wifi"] },
      { id:"c2", place_id:"p002", name:"Café Velvet",     neighborhood:"Laureles",   rating:4.6, tags:["tercera ola","tranquilo","libros"] },
      { id:"c3", place_id:"p003", name:"Amor Perfecto",   neighborhood:"El Poblado", rating:4.7, tags:["origen","brunch","jardín"] },
      { id:"c4", place_id:"p004", name:"Azahar Café",     neighborhood:"Envigado",   rating:4.5, tags:["espresso","minimal","trabajo"] },
      { id:"c5", place_id:"p005", name:"Café Zeppelin",   neighborhood:"Laureles",   rating:4.4, tags:["música suave","lectura","plantas"] },
    ],
    edges: [
      { from:"c1", to:"c2", weight:0.88, reason:"Specialty coffee culture" },
      { from:"c1", to:"c3", weight:0.82, reason:"Single origin focus" },
      { from:"c2", to:"c5", weight:0.75, reason:"Quiet study atmosphere" },
      { from:"c3", to:"c4", weight:0.71, reason:"Poblado coffee scene" },
      { from:"c2", to:"c4", weight:0.60, reason:"Minimalist aesthetic" },
    ]
  },
  bar: {
    nodes: [
      { id:"b1", place_id:"p010", name:"El Social",       neighborhood:"El Poblado",  rating:4.5, tags:["cócteles","jazz","vivo"] },
      { id:"b2", place_id:"p011", name:"Son Havana",      neighborhood:"Laureles",    rating:4.7, tags:["salsa","cubano","bailar"] },
      { id:"b3", place_id:"p012", name:"La Octava",       neighborhood:"Envigado",    rating:4.3, tags:["rock","cervezas","indie"] },
      { id:"b4", place_id:"p013", name:"Envy Rooftop",    neighborhood:"El Poblado",  rating:4.6, tags:["vistas","electrónica","terraza"] },
      { id:"b5", place_id:"p014", name:"Vintrash",        neighborhood:"Laureles",    rating:4.4, tags:["punk","vinilo","underground"] },
    ],
    edges: [
      { from:"b1", to:"b2", weight:0.85, reason:"Live music scene" },
      { from:"b1", to:"b4", weight:0.79, reason:"Poblado nightlife" },
      { from:"b2", to:"b3", weight:0.72, reason:"Dance and music energy" },
      { from:"b3", to:"b5", weight:0.88, reason:"Alternative music lovers" },
    ]
  },
  sushi: {
    nodes: [
      { id:"s1", place_id:"p020", name:"Osaki Sushi",     neighborhood:"El Poblado", rating:4.7, tags:["omakase","sake","íntimo"] },
      { id:"s2", place_id:"p021", name:"Matsu",            neighborhood:"Laureles",   rating:4.5, tags:["ramen","izakaya","casual"] },
      { id:"s3", place_id:"p022", name:"Nori",             neighborhood:"Envigado",   rating:4.4, tags:["fusión","nikkei","moderno"] },
      { id:"s4", place_id:"p023", name:"Kai Robata",       neighborhood:"El Poblado", rating:4.6, tags:["parrilla","japonesa","barra"] },
      { id:"s5", place_id:"p024", name:"Tanuki",           neighborhood:"Laureles",   rating:4.3, tags:["ramen","dumplings","callejero"] },
    ],
    edges: [
      { from:"s1", to:"s4", weight:0.90, reason:"Premium Japanese experience" },
      { from:"s1", to:"s3", weight:0.75, reason:"Nikkei influence" },
      { from:"s2", to:"s5", weight:0.82, reason:"Casual ramen culture" },
      { from:"s3", to:"s4", weight:0.68, reason:"Modern Japanese fusion" },
    ]
  }
};

function getMock(q) {
  const lq = (q || "").toLowerCase();
  if (lq.includes("café") || lq.includes("cafe") || lq.includes("tranquilo") || lq.includes("trabajo")) return MOCK.cafe;
  if (lq.includes("bar") || lq.includes("noche") || lq.includes("música") || lq.includes("musica") || lq.includes("copa")) return MOCK.bar;
  if (lq.includes("sushi") || lq.includes("jap") || lq.includes("ramen")) return MOCK.sushi;
  return MOCK.bar;
}
