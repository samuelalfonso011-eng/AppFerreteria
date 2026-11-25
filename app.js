"use strict";

/* ---------- Ilustraciones (Fase 1) ---------- */
const shapes = {
  wrench: '<g transform="rotate(35 235 165)"><path d="M207 88q-30 38 10 63v87a23 23 0 1 0 34 0v-87q37-25 11-64l-12 36-29 2z" fill="url(#metal)" stroke="var(--art-metal-edge)" stroke-width="3"/><circle cx="234" cy="253" r="10" fill="var(--art-metal-fastener)"/></g>',
  roller: '<path d="M290 102h28v50l-78 19v42" fill="none" stroke="var(--art-roller-handle)" stroke-width="10" stroke-linejoin="round"/><rect x="222" y="197" width="35" height="88" rx="13" fill="url(#metal)"/><rect x="137" y="73" width="161" height="57" rx="15" fill="url(#orange)"/>',
  lamp: '<path d="M211 218q-1-30-21-53a61 61 0 1 1 98 0q-20 23-21 53z" fill="var(--art-lamp-glass)" stroke="var(--art-lamp-rim)" stroke-width="4"/><path d="M210 214h58l-7 45-20 12-24-13z" fill="url(#metal)"/><path d="m216 229 46-6m-45 18 44-6m-42 18 41-6" stroke="var(--art-lamp-thread)" stroke-width="5"/>',
  helmet: '<path d="M128 204q6-100 95-109l7-13h28l6 17q73 20 77 98l19 9v15l-230 9-14-12z" fill="url(#orange)"/><path d="m223 99 2 77m39-72-5 67" stroke="var(--art-helmet-highlight)" stroke-width="8"/><path d="m133 207 199-7" stroke="var(--art-helmet-crease)" stroke-width="7"/>'
};
const ARTS = new Set(["drill", "saw", "wrench", "roller", "lamp", "helmet"]);
const $ = selector => document.querySelector(selector);
const money = value => new Intl.NumberFormat("es-CO", {style:"currency", currency:"COP", maximumFractionDigits:0}).format(value);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const art = key => {
  const k = ARTS.has(key) ? key : "wrench";
  return '<svg viewBox="0 0 480 330" aria-hidden="true">' + (shapes[k] || '<use href="#' + k + '"/>') + '</svg>';
};
const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const normalize = value => String(value).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

/* ---------- Cliente de la API ---------- */
let csrfToken = null;
async function getCsrf(force) {
  if (!csrfToken || force) {
    const res = await fetch("/api/auth/csrf", {credentials:"same-origin", headers:{Accept:"application/json"}});
    if (!res.ok) throw new Error("No pudimos preparar una conexión segura. Recarga la página.");
    csrfToken = (await res.json()).csrf;
  }
  return csrfToken;
}
async function api(path, {method = "GET", body} = {}, retry = true) {
  const options = {method, credentials:"same-origin", headers:{Accept:"application/json"}};
  if (method !== "GET") {
    options.headers["Content-Type"] = "application/json";
    options.headers["X-CSRF-Token"] = await getCsrf();
    options.body = JSON.stringify(body || {});
  }
  let res;
  try { res = await fetch("/api" + path, options); }
  catch { throw Object.assign(new Error("Sin conexión con la tienda. Revisa tu internet."), {status:0, data:{}}); }
  const data = await res.json().catch(() => ({}));
  if (res.status === 403 && data.error === "csrf" && retry) {
    await getCsrf(true);
    return api(path, {method, body}, false);
  }
  if (!res.ok) throw Object.assign(new Error(data.message || "No pudimos completar la solicitud."), {status:res.status, data});
  return data;
}

/* ---------- Estado del catalogo ---------- */
const state = {products:[], byId:new Map(), bySlug:new Map(), categories:[], store:null, loaded:false};
async function loadCatalog() {
  const [p, c, s] = await Promise.all([api("/catalog/products"), api("/catalog/categories"), api("/store")]);
  state.products = p.products;
  state.byId = new Map(p.products.map(item => [item.id, item]));
  state.bySlug = new Map(p.products.map(item => [item.slug, item]));
  state.categories = c.categories;
  state.store = s.store;
  state.loaded = true;
}
const findProduct = ref => state.bySlug.get(ref) || state.byId.get(Number(ref));

function renderCategories() {
  const promos = state.categories.filter(c => c.headline).slice(0, 4);
  const section = $("#categorias");
  section.innerHTML = promos.map(c =>
    '<article class="tile">' + art(c.art) + '<h3>' + esc(c.headline) + '</h3><a href="#catalogo" data-filter="' + esc(c.name) + '">Explorar categoría ›</a></article>'
  ).join("");
  section.removeAttribute("aria-busy");
}

/* Catalogo progresivo: se pintan bloques de PAGE_SIZE tarjetas, no todo el DOM de golpe.
   Mas productos llegan con "Cargar mas" o al deslizar el carrusel hasta el final. */
const PAGE_SIZE = 12;
let catalogLimit = PAGE_SIZE, catalogTerm = null;
const matches = term => {
  const needle = normalize(term);
  return state.products.filter(p => normalize(p.name + " " + p.category).includes(needle));
};
function cardHTML(p) {
  const note = !p.available ? '<span class="stockNote out">Agotado</span>'
    : p.stock <= 5 ? '<span class="stockNote">Quedan ' + p.stock + ' unidades</span>' : "";
  const action = p.available
    ? '<button class="add" data-add="' + p.id + '">Agregar al carrito</button>'
    : '<button class="add" disabled>Agotado</button>';
  return '<article class="card">' + art(p.art) + '<small>' + esc(p.category) + '</small><h3>' + esc(p.name) + '</h3><p>' + money(p.price) + '</p>' + note + action + '</article>';
}
function catalog(term = "", {more = false} = {}) {
  const cards = $("#cards");
  if (!state.loaded) return;
  if (term !== catalogTerm) catalogLimit = PAGE_SIZE; // una busqueda nueva empieza por el primer bloque
  catalogTerm = term;
  const list = matches(term);
  if (more) {
    const start = cards.querySelectorAll(".card").length;
    catalogLimit = start + PAGE_SIZE;
    cards.insertAdjacentHTML("beforeend", list.slice(start, catalogLimit).map(cardHTML).join(""));
    reveal(".card");
  } else {
    cards.innerHTML = list.slice(0, catalogLimit).map(cardHTML).join("")
      || '<div class="catalogState"><p>Sin resultados. Prueba con otra herramienta.</p></div>';
    cards.scrollLeft = 0;
  }
  const remaining = list.length - catalogLimit;
  const loadMore = $("#loadMore");
  loadMore.hidden = remaining <= 0;
  loadMore.textContent = "Cargar más productos (" + Math.max(remaining, 0) + ")";
  cards.removeAttribute("aria-busy");
  $("#reset").hidden = !term;
  updateArrows();
  watchCatalogEnd(remaining > 0);
}
// Carga controlada al llegar al final del carrusel (solo si quedan productos)
const endObserver = "IntersectionObserver" in window ? new IntersectionObserver(entries => {
  if (entries.some(e => e.isIntersecting)) catalog(catalogTerm || "", {more:true});
}, {root:$("#cards"), rootMargin:"0px 320px 0px 0px"}) : null;
function watchCatalogEnd(hasMore) {
  if (!endObserver) return;
  endObserver.disconnect();
  const last = $("#cards .card:last-of-type");
  if (hasMore && last) endObserver.observe(last);
}
$("#loadMore").addEventListener("click", () => {
  const before = $("#cards").querySelectorAll(".card").length;
  catalog(catalogTerm || "", {more:true});
  const first = $("#cards").querySelectorAll(".card")[before];
  if (first) first.scrollIntoView({behavior:reducedMotion() ? "instant" : "smooth", block:"nearest", inline:"start"});
});
function catalogError() {
  const cards = $("#cards");
  cards.removeAttribute("aria-busy");
  cards.innerHTML = '<div class="catalogState"><p>No pudimos cargar el catálogo.</p><button class="pill" data-retry>Reintentar</button></div>';
  const tiles = $("#categorias");
  tiles.innerHTML = "";
  tiles.removeAttribute("aria-busy");
  $("#loadMore").hidden = true;
  updateArrows();
}
function updateArrows() {
  const cards = $("#cards");
  $("#prev").disabled = cards.scrollLeft < 2;
  $("#next").disabled = cards.scrollLeft + cards.clientWidth >= cards.scrollWidth - 2;
}
$("#cards").onscroll = updateArrows;
window.addEventListener("resize", updateArrows);
for (const [id, dir] of [["prev", -1], ["next", 1]]) {
  $("#" + id).onclick = () => $("#cards").scrollBy({left:dir * (($("#cards article")?.offsetWidth || 285) + 16), behavior:reducedMotion() ? "instant" : "smooth"});
}

/* ---------- Carrito ---------- */
const drawer = $("#drawer"), details = $("#details"), checkoutDialog = $("#checkoutDialog"), legalDialog = $("#legal");
const storageKey = "ferrepro.cart.v2";
let cart = {};
try {
  localStorage.removeItem("ferrepro.cart.v1"); // indices de la Fase 1, ya no corresponden a productos reales
  const saved = JSON.parse(localStorage.getItem(storageKey)) || {};
  for (const [id, qty] of Object.entries(saved)) if (Number.isSafeInteger(qty) && qty > 0) cart[id] = qty;
} catch {}
const saveCart = () => { try { localStorage.setItem(storageKey, JSON.stringify(cart)); } catch {} };

function reconcileCart() {
  const notes = [];
  for (const id of Object.keys(cart)) {
    const p = state.byId.get(Number(id));
    if (!p || !p.available) { delete cart[id]; if (p) notes.push(p.name + " se agotó"); }
    else if (cart[id] > p.stock) { cart[id] = p.stock; notes.push("Ajustamos " + p.name + " a " + p.stock + " unidades"); }
  }
  saveCart();
  return notes;
}
function totals() {
  let subtotal = 0, count = 0;
  for (const [id, qty] of Object.entries(cart)) {
    const p = state.byId.get(Number(id));
    if (p) { subtotal += p.price * qty; count += qty; }
  }
  const s = state.store;
  let shipping = 0;
  if (count && s) shipping = s.free_shipping_threshold && subtotal >= s.free_shipping_threshold ? 0 : s.shipping_cost;
  return {subtotal, count, shipping, total:subtotal + shipping};
}
function renderCart() {
  const rows = Object.entries(cart).map(([id, qty]) => {
    const p = state.byId.get(Number(id));
    if (!p) return "";
    const atMax = qty >= p.stock ? " disabled" : "";
    return '<div class="row"><strong>' + esc(p.name) + '</strong><p>' + money(p.price * qty) + '</p><button aria-label="Restar uno" data-minus="' + p.id + '">−</button>' + qty + '<button aria-label="Sumar uno" data-add="' + p.id + '"' + atMax + '>+</button><button data-remove="' + p.id + '">Eliminar</button></div>';
  }).join("");
  const t = totals();
  $("#items").innerHTML = rows || "<p>Tu carrito está vacío.</p>";
  $("#subtotal").textContent = money(t.subtotal);
  $("#badge").textContent = t.count;
  $("#bag").setAttribute("aria-label", "Abrir carrito, " + t.count + " artículos");
  $("#checkout").disabled = !t.count || !state.loaded;
  const s = state.store;
  $("#shipHint").textContent = !s || !t.count ? ""
    : s.free_shipping_threshold && t.subtotal < s.free_shipping_threshold
      ? "Te faltan " + money(s.free_shipping_threshold - t.subtotal) + " para el envío gratis."
      : s.free_shipping_threshold ? "Tu pedido tiene envío gratis." : "";
}
let toastTimer;
// Reinicia una animacion CSS aunque la clase ya este puesta
function replay(el, className) {
  el.classList.remove(className);
  void el.offsetWidth;
  el.classList.add(className);
}
function toast(message) {
  const status = $("#status");
  const showing = status.textContent !== "";
  status.textContent = message;
  if (showing) replay(status, "again"); // un aviso nuevo sobre otro visible se nota sin parpadear
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { status.textContent = ""; status.classList.remove("again"); }, 2400);
}
function change(id, delta) {
  const p = state.byId.get(Number(id));
  if (!p) return;
  const current = cart[p.id] || 0;
  let qty = current + delta;
  if (delta > 0 && qty > p.stock) {
    qty = p.stock;
    toast(p.stock ? "Solo hay " + p.stock + " unidades disponibles" : "Producto agotado");
  }
  if (qty > 0) cart[p.id] = qty; else delete cart[p.id];
  saveCart();
  renderCart();
  if (qty > current) replay($("#badge"), "bump"); // el contador del navbar late al entrar un producto
  if (delta > 0 && qty > current && !drawer.open && !details.open) toast("Agregaste " + p.name + " al carrito");
}
function showDetail(html) {
  $("#detailBody").innerHTML = html;
  if (!details.open) details.showModal();
}
function productDetail(p) {
  const specs = p.specs.length ? '<ul class="specs">' + p.specs.map(s => "<li>" + esc(s) + "</li>").join("") + "</ul>" : "";
  const availability = p.available ? (p.stock <= 5 ? "Quedan " + p.stock + " unidades" : "Disponible") : "Agotado";
  return art(p.art) + "<h2>" + esc(p.name) + "</h2><p>" + esc(p.description) + "</p>" + specs +
    "<p>" + money(p.price) + ' <span class="availability">· ' + availability + "</span></p>" +
    '<button class="primary" data-buy="' + p.id + '"' + (p.available ? "" : " disabled") + ">Comprar</button>";
}

/* ---------- Checkout ---------- */
const form = $("#checkoutForm");
let idempotencyKey = null;
const newKey = () => (crypto.randomUUID ? crypto.randomUUID() : Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, "0")).join(""));

function fillSummary() {
  const t = totals();
  $("#checkoutSummary").innerHTML =
    "<div><span>Subtotal</span><span>" + money(t.subtotal) + "</span></div>" +
    "<div><span>Envío</span><span>" + (t.shipping ? money(t.shipping) : "Gratis") + "</span></div>" +
    '<div class="grand"><span>Total</span><span>' + money(t.total) + "</span></div>";
}
function openCheckout() {
  if (!totals().count) return;
  drawer.close();
  idempotencyKey = newKey();
  clearErrors();
  // Con sesion iniciada, el nombre y el correo se rellenan (sin pisar lo que ya escribio)
  if (account.user) {
    if (!form.elements.name.value) form.elements.name.value = account.user.name;
    if (!form.elements.email.value) form.elements.email.value = account.user.email;
  }
  fillSummary();
  checkoutDialog.showModal();
}
// Errores por campo, reutilizables en checkout y en los formularios de cuenta
function clearErrors(f = form) {
  f.querySelectorAll(".fieldError").forEach(el => el.remove());
  f.querySelectorAll("[aria-invalid]").forEach(el => { el.removeAttribute("aria-invalid"); el.removeAttribute("aria-describedby"); });
  const general = f.querySelector(".formError");
  if (general) general.textContent = "";
}
function showErrors(fields, f = form) {
  let first = null;
  for (const [name, message] of Object.entries(fields)) {
    const input = f.elements[name];
    const target = input instanceof RadioNodeList ? input[0] : input;
    if (!target || !target.closest) continue;
    const holder = target.closest(".field, .check, fieldset");
    const id = "err-" + name;
    const error = document.createElement("span");
    error.className = "fieldError";
    error.id = id;
    error.textContent = message;
    holder.appendChild(error);
    target.setAttribute("aria-invalid", "true");
    target.setAttribute("aria-describedby", id);
    first = first || target;
  }
  const other = Object.keys(fields).filter(name => !f.elements[name]);
  const general = f.querySelector(".formError");
  if (other.length && general) general.textContent = fields[other[0]];
  if (first) first.focus();
}
function validateLocal(data) {
  const errors = {};
  const required = ["name", "email", "phone", "doc_number", "department", "city", "neighborhood", "street_address"];
  for (const name of required) if (!data[name]) errors[name] = "Este campo es obligatorio.";
  if (data.name && data.name.length < 3) errors.name = "Escribe tu nombre completo.";
  if (data.email && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(data.email)) errors.email = "Escribe un correo válido, por ejemplo nombre@dominio.com.";
  if (data.phone && !/^\+?[0-9 ]{7,20}$/.test(data.phone)) errors.phone = "Escribe un celular válido, solo números.";
  if (data.doc_number && !/^[0-9A-Za-z.-]{4,20}$/.test(data.doc_number)) errors.doc_number = "Escribe el número sin espacios.";
  if (data.street_address && data.street_address.length < 5) errors.street_address = "Escribe la dirección completa.";
  if (!data.accept_terms) errors.accept_terms = "Para continuar debes aceptar los Términos y la Política de devoluciones.";
  if (!data.accept_privacy) errors.accept_privacy = "Para continuar debes autorizar el tratamiento de tus datos personales.";
  return errors;
}
function setBusy(busy) {
  const button = $("#placeOrder");
  button.disabled = busy;
  button.setAttribute("aria-busy", String(busy));
  button.textContent = busy ? "Confirmando…" : "Confirmar pedido";
}
form.addEventListener("submit", async event => {
  event.preventDefault();
  clearErrors();
  const fd = new FormData(form);
  const text = name => String(fd.get(name) || "").trim();
  const data = {
    name:text("name"), email:text("email").toLowerCase(), phone:text("phone"), doc_type:text("doc_type") || "CC",
    doc_number:text("doc_number"), department:text("department"), city:text("city"), neighborhood:text("neighborhood"),
    street_address:text("street_address"), complement:text("complement"), notes:text("notes"),
    accept_terms:form.elements.accept_terms.checked, accept_privacy:form.elements.accept_privacy.checked
  };
  const errors = validateLocal(data);
  if (Object.keys(errors).length) { showErrors(errors); return; }
  const t = totals();
  if (!t.count) { $("#checkoutError").textContent = "Tu carrito está vacío."; return; }
  setBusy(true);
  try {
    const {order} = await api("/orders", {method:"POST", body:{
      ...data,
      items:Object.entries(cart).map(([id, quantity]) => ({product_id:Number(id), quantity})),
      idempotency_key:idempotencyKey,
      expected_total:t.total
    }});
    cart = {};
    saveCart();
    form.reset();
    checkoutDialog.close();
    showConfirmation(order);
    refreshCatalog();
  } catch (err) {
    if (err.status === 400 && err.data.fields) showErrors(err.data.fields);
    else if (err.status === 409) {
      await refreshCatalog();
      fillSummary();
      $("#checkoutError").textContent = err.message;
      if (!totals().count) checkoutDialog.close();
    } else $("#checkoutError").textContent = err.message;
  } finally {
    setBusy(false);
  }
});
function orderLines(order) {
  return '<ul class="orderLines">' + order.items.map(i => "<li><span>" + esc(i.name) + " × " + i.quantity + "</span><span>" + money(i.subtotal) + "</span></li>").join("") +
    "<li><span>Envío</span><span>" + (order.shipping_cost ? money(order.shipping_cost) : "Gratis") + "</span></li>" +
    "<li><strong>Total</strong><strong>" + money(order.total) + "</strong></li></ul>";
}
function showConfirmation(order) {
  showDetail("<h2>Pedido recibido</h2><p>Tu número de pedido es</p><p class=\"orderNumber\">" + esc(order.order_number) + "</p>" + orderLines(order) +
    "<p>Te llamaremos al celular registrado para coordinar el pago y la entrega. Consulta el estado cuando quieras en Soporte, Mi pedido.</p>" +
    '<button class="primary" data-close-dialog>Seguir comprando</button>');
}
function showLookup() {
  showDetail('<h2>Mi pedido</h2><p>Escribe el número de pedido y el correo con el que compraste.</p>' +
    '<form id="lookupForm" class="sheetForm" novalidate>' +
    '<label class="field"><span>Número de pedido</span><input name="order_number" required maxlength="20" placeholder="FP-261121-A1B2C3" autocomplete="off"></label>' +
    '<label class="field"><span>Correo electrónico</span><input name="email" type="email" required maxlength="254" autocomplete="email"></label>' +
    '<p class="formError" id="lookupError" role="alert"></p><button class="primary wide" type="submit">Consultar</button></form><div id="lookupResult"></div>');
}
async function submitLookup(lookup) {
  const number = lookup.elements.order_number.value.trim().toUpperCase();
  const email = lookup.elements.email.value.trim().toLowerCase();
  const error = $("#lookupError");
  error.textContent = "";
  if (!number || !email) { error.textContent = "Completa el número de pedido y el correo."; return; }
  const button = lookup.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    const {order} = await api("/orders/lookup", {method:"POST", body:{order_number:number, email}});
    $("#lookupResult").innerHTML = '<p><span class="statusChip">' + esc(order.status_label) + "</span></p>" + orderLines(order);
  } catch (err) {
    error.textContent = err.message;
  } finally {
    button.disabled = false;
  }
}
document.addEventListener("submit", event => {
  if (event.target.id === "lookupForm") { event.preventDefault(); submitLookup(event.target); }
});

/* ---------- Documentos legales ---------- */
const legalCache = new Map();
function renderLegal(doc) {
  return '<p class="eyebrow">' + esc(doc.kicker) + '</p><h2 id="legalTitle">' + esc(doc.title) + '</h2>' +
    '<p class="meta">Versión ' + esc(doc.version) + " · " + esc(doc.law) + "</p>" +
    doc.sections.map(s => "<section><h3>" + esc(s.heading) + "</h3>" +
      s.paragraphs.map(p => "<p>" + esc(p) + "</p>").join("") +
      (s.items.length ? "<ul>" + s.items.map(i => "<li>" + esc(i) + "</li>").join("") + "</ul>" : "") + "</section>").join("") +
    (doc.related.length ? '<div class="related">' + doc.related.map(r => '<button class="pill" data-legal="' + esc(r.slug) + '">' + esc(r.title) + "</button>").join("") + "</div>" : "");
}
async function openLegal(slug) {
  const body = $("#legalBody");
  if (!legalDialog.open) legalDialog.showModal();
  body.innerHTML = '<h2 id="legalTitle">Cargando…</h2>';
  try {
    if (!legalCache.has(slug)) legalCache.set(slug, (await api("/legal/" + encodeURIComponent(slug))).document);
    body.innerHTML = renderLegal(legalCache.get(slug));
  } catch (err) {
    body.innerHTML = '<h2 id="legalTitle">No disponible</h2><p>' + esc(err.message) + "</p>";
  }
  legalDialog.scrollTop = 0;
}

/* ---------- Eventos ---------- */
document.addEventListener("click", event => {
  const el = event.target.closest("button,a");
  if (!el) return;
  const d = el.dataset;
  if ("filter" in d) { $("#query").value = d.filter; catalog(d.filter); }
  if (el.closest("#links")) toggleMenu(false);
  if ("add" in d) change(d.add, 1);
  if ("minus" in d) change(d.minus, -1);
  if ("remove" in d) change(d.remove, -cart[d.remove]);
  if ("retry" in d) boot();
  if ("legal" in d) { event.preventDefault(); openLegal(d.legal); }
  if ("closeDialog" in d) el.closest("dialog").close();
  if ("buy" in d) {
    const p = findProduct(d.buy);
    if (!p) { toast(state.loaded ? "Este producto no está disponible por ahora" : "Cargando catálogo…"); return; }
    if (!p.available) { toast("Producto agotado"); return; }
    if (details.open) details.close();
    drawer.showModal();
    change(p.id, 1);
  }
  if ("info" in d) {
    const p = findProduct(d.info);
    if (p) showDetail(productDetail(p));
    else toast(state.loaded ? "Este producto no está disponible por ahora" : "Cargando catálogo…");
  }
  if ("help" in d) {
    if (d.help === "pedido") showLookup();
    else showDetail("<h2>Cómo comprar</h2><p>Agrega herramientas desde el catálogo y abre el carrito para ajustar las cantidades. Al finalizar, completa tus datos de entrega y facturación y acepta las políticas.</p><p>Reservamos el stock en ese momento y te llamamos para coordinar el pago y la entrega.</p>");
  }
  if (el.classList.contains("close")) el.closest("dialog").close();
});
$("#bag").onclick = () => drawer.showModal();
$("#checkout").onclick = openCheckout;
function toggleMenu(open) {
  $("#links").classList.toggle("open", open); $("#menu").setAttribute("aria-expanded", open);
}
$("#menu").onclick = () => { setSearch(false); toggleMenu(!$("#links").classList.contains("open")); };
function setSearch(open) {
  $("#searchBar").hidden = !open; $("#searchToggle").setAttribute("aria-expanded", open);
  if (open) { toggleMenu(false); $("#catalogo").scrollIntoView(); $("#query").focus({preventScroll:true}); }
}
$("#searchToggle").onclick = () => setSearch($("#searchBar").hidden);
$("#query").oninput = e => catalog(e.target.value);
$("#reset").onclick = () => { $("#query").value = ""; catalog(); };
document.addEventListener("keydown", e => {
  if (e.key !== "Escape") return;
  if (!$("#searchBar").hidden) { setSearch(false); $("#searchToggle").focus(); }
  if (!accountMenu.hidden) { toggleAccountMenu(false); accountBtn.focus(); }
  toggleMenu(false);
});

/* ---------- Cuenta: inicio de sesion, registro y recuperacion ---------- */
const authDialog = $("#authDialog"), accountMenu = $("#accountMenu"), accountBtn = $("#accountBtn");
const account = {user:null, resetToken:null};
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const EYE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>';
const MAIL = '<svg class="authIcon" viewBox="0 0 48 48" aria-hidden="true"><rect x="6" y="11" width="36" height="26" rx="5"/><path d="m8 14 16 12 16-12"/></svg>';
const MARK = '<svg class="authMark" viewBox="0 0 32 30" aria-hidden="true"><path d="M2 27 10 3h21l-2 6H15l-1 4h12l-2 6H12l-3 8z" fill="currentColor"/></svg>';

function passwordProblem(password, email) {
  if (password.length < 12) return "Usa al menos 12 caracteres.";
  if (password.length > 128) return "Usa como máximo 128 caracteres.";
  if (!/\p{L}/u.test(password) || !/\d/.test(password)) return "Combina letras y números.";
  const local = (email || "").split("@")[0].toLowerCase();
  if (local.length >= 4 && password.toLowerCase().includes(local)) return "No uses tu correo dentro de la contraseña.";
  return null;
}
const emailField = (autocomplete = "email") =>
  '<label class="field"><span>Correo electrónico</span><input name="email" type="email" autocomplete="' + autocomplete + '" required maxlength="254" spellcheck="false" autocapitalize="off"></label>';
const passwordField = (name, label, autocomplete, hint = "") =>
  '<label class="field"><span>' + label + '</span><span class="pwWrap"><input type="password" name="' + name + '" autocomplete="' + autocomplete + '" required maxlength="128"' + (hint ? ' aria-describedby="hint-' + name + '"' : "") + ">" +
  '<button type="button" class="pwToggle" aria-label="Mostrar contraseña" aria-pressed="false">' + EYE + "</button></span>" +
  (hint ? '<span class="fieldHint" id="hint-' + name + '">' + hint + "</span>" : "") + "</label>";
const submitRow = label => '<p class="formError" role="alert"></p><button class="primary wide" type="submit">' + label + "</button>";

const AUTH_VIEWS = {
  login: () => MARK + '<h2 id="authTitle">Inicia sesión en FerrePro</h2><p class="lead">Accede a tu cuenta para comprar más rápido.</p>' +
    '<form id="authForm" data-auth="login" novalidate>' + emailField("username") + passwordField("password", "Contraseña", "current-password") + submitRow("Iniciar sesión") + "</form>" +
    '<p class="authHint">¿Te registraste hace poco? Primero abre el enlace de activación que te enviamos por correo.</p>' +
    '<div class="authLinks"><button type="button" class="inline" data-auth-view="resend">Reenviar enlace de activación</button><button type="button" class="inline" data-auth-view="forgot">¿Olvidaste tu contraseña?</button>' +
    '<span>¿No tienes cuenta? <button type="button" class="inline" data-auth-view="register">Crea una</button></span></div>',
  register: () => MARK + '<h2 id="authTitle">Crea tu cuenta</h2><p class="lead">Te enviaremos un enlace para confirmar tu correo.</p>' +
    '<form id="authForm" data-auth="register" novalidate>' +
    '<label class="field"><span>Nombre completo</span><input name="name" autocomplete="name" required minlength="3" maxlength="150"></label>' +
    emailField() + passwordField("password", "Contraseña", "new-password", "Mínimo 12 caracteres, con letras y números.") +
    passwordField("confirm", "Repite la contraseña", "new-password") +
    '<fieldset class="consents"><legend class="sr">Autorizaciones</legend>' +
    '<label class="check"><input type="checkbox" name="accept_terms" required><span>Leí y acepto los <button type="button" class="inline" data-legal="terminos">Términos y condiciones</button>.</span></label>' +
    '<label class="check"><input type="checkbox" name="accept_privacy" required><span>Autorizo de forma previa, expresa e informada el tratamiento de mis datos personales según la <button type="button" class="inline" data-legal="datos">Política de tratamiento de datos</button> (Ley 1581 de 2012).</span></label></fieldset>' +
    submitRow("Crear cuenta") + "</form>" +
    '<div class="authLinks"><button type="button" class="inline" data-auth-view="resend">Reenviar enlace de activación</button></div>' +
    '<div class="authLinks"><span>¿Ya tienes cuenta? <button type="button" class="inline" data-auth-view="login">Inicia sesión</button></span></div>',
  resend: () => MARK + '<h2 id="authTitle">Reenvía tu enlace de activación</h2>' +
    '<form id="authForm" data-auth="resend" novalidate>' + emailField() + submitRow("Reenviar enlace") + "</form>" +
    '<div class="authLinks"><button type="button" class="inline" data-auth-view="login">Volver a iniciar sesión</button></div>',
  forgot: () => MARK + '<h2 id="authTitle">Recupera tu contraseña</h2><p class="lead">Escribe el correo de tu cuenta y te enviaremos un enlace para elegir una nueva.</p>' +
    '<form id="authForm" data-auth="forgot" novalidate>' + emailField() + submitRow("Enviar enlace") + "</form>" +
    '<div class="authLinks"><button type="button" class="inline" data-auth-view="login">Volver a iniciar sesión</button></div>',
  reset: () => MARK + '<h2 id="authTitle">Elige una contraseña nueva</h2><p class="lead">Al guardarla se cierran las sesiones abiertas en otros dispositivos.</p>' +
    '<form id="authForm" data-auth="reset" novalidate>' +
    passwordField("password", "Contraseña nueva", "new-password", "Mínimo 12 caracteres, con letras y números.") +
    passwordField("confirm", "Repite la contraseña", "new-password") + submitRow("Guardar contraseña") + "</form>",
  sent: ({message}) => MAIL + '<h2 id="authTitle">Revisa tu correo</h2><p class="lead">' + esc(message) + "</p>" +
    '<button type="button" class="primary wide" data-auth-view="login">Volver a iniciar sesión</button>'
};

function openAuth(view, options = {}) {
  if (view === "reset") account.resetToken = options.token;
  toggleAccountMenu(false);
  $("#authBody").innerHTML = AUTH_VIEWS[view](options);
  $("#authBody").dataset.view = view;
  if (!authDialog.open) authDialog.showModal();
  authDialog.scrollTop = 0;
  const first = authDialog.querySelector("#authBody input, #authBody .primary");
  if (first) first.focus();
  const email = authDialog.querySelector('[name="email"]');
  if (email && options.email) email.value = options.email;
  if (options.error) authDialog.querySelector(".formError").textContent = options.error;
}

function setAccount(user) {
  account.user = user;
  const avatar = $("#avatar");
  accountBtn.classList.toggle("signedIn", Boolean(user));
  avatar.hidden = !user;
  $("#adminLink").hidden = user?.role !== "admin";
  if (user) {
    avatar.textContent = (user.name.trim()[0] || "?").toUpperCase();
    accountBtn.setAttribute("aria-label", "Cuenta de " + user.name);
    accountBtn.setAttribute("aria-expanded", "false");
    accountBtn.setAttribute("aria-controls", "accountMenu");
    $("#accountName").textContent = user.name;
    $("#accountEmail").textContent = user.email;
  } else {
    accountBtn.setAttribute("aria-label", "Iniciar sesión");
    accountBtn.removeAttribute("aria-expanded");
    accountBtn.removeAttribute("aria-controls");
    toggleAccountMenu(false);
  }
}
function toggleAccountMenu(open) {
  if (!accountMenu) return;
  accountMenu.hidden = !open;
  if (account.user) accountBtn.setAttribute("aria-expanded", String(open));
  if (open) {
    setSearch(false);
    toggleMenu(false);
    accountMenu.querySelector(".menuItem:not([hidden])").focus();
  }
}
accountBtn.addEventListener("click", () => {
  if (!account.user) openAuth("login");
  else toggleAccountMenu(accountMenu.hidden);
});
document.addEventListener("click", event => {
  if (!accountMenu.hidden && !accountMenu.contains(event.target) && !accountBtn.contains(event.target)) toggleAccountMenu(false);
});
accountMenu.addEventListener("click", event => {
  if (event.target.closest(".menuItem")) toggleAccountMenu(false);
});

function signedIn(result, message) {
  csrfToken = result.csrf; // el servidor rota el token al iniciar sesion
  setAccount(result.user);
  if (authDialog.open) authDialog.close();
  if (result.user.role === "admin") {
    location.assign("/admin");
    return;
  }
  const first = result.user.name.split(" ")[0];
  toast(message || "Hola, " + first + ". Tu carrito sigue intacto.");
}
async function loadSession() {
  try {
    const me = await api("/auth/me");
    csrfToken = me.csrf;
    setAccount(me.user);
  } catch {
    setAccount(null);
  }
}
$("#logoutBtn").addEventListener("click", async () => {
  try {
    csrfToken = (await api("/auth/logout", {method:"POST"})).csrf;
  } catch (err) {
    toast(err.message);
    return;
  }
  setAccount(null);
  toast("Cerraste sesión.");
  accountBtn.focus();
});

function validateAuth(kind, f) {
  const errors = {};
  const value = name => (f.elements[name]?.value || "").trim();
  if (f.elements.name && value("name").length < 3) errors.name = "Escribe tu nombre completo.";
  if (f.elements.email) {
    if (!value("email")) errors.email = "Este campo es obligatorio.";
    else if (!EMAIL_RE.test(value("email"))) errors.email = "Escribe un correo válido, por ejemplo nombre@dominio.com.";
  }
  if (f.elements.password) {
    const password = f.elements.password.value;
    if (!password) errors.password = "Este campo es obligatorio.";
    else if (kind !== "login") {
      const problem = passwordProblem(password, value("email") || account.user?.email);
      if (problem) errors.password = problem;
    }
  }
  if (f.elements.confirm && !errors.password && f.elements.confirm.value !== f.elements.password.value) errors.confirm = "Las contraseñas no coinciden.";
  if (f.elements.accept_terms && !f.elements.accept_terms.checked) errors.accept_terms = "Para crear tu cuenta debes aceptar los Términos y condiciones.";
  if (f.elements.accept_privacy && !f.elements.accept_privacy.checked) errors.accept_privacy = "Para crear tu cuenta debes autorizar el tratamiento de tus datos personales.";
  return errors;
}
async function submitAuth(f) {
  const kind = f.dataset.auth;
  clearErrors(f);
  const errors = validateAuth(kind, f);
  if (Object.keys(errors).length) { showErrors(errors, f); return; }
  const email = (f.elements.email?.value || "").trim().toLowerCase();
  const button = f.querySelector("[type=submit]");
  const label = button.textContent;
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  button.textContent = "Un momento…";
  try {
    if (kind === "login") {
      signedIn(await api("/auth/login", {method:"POST", body:{email, password:f.elements.password.value}}));
    } else if (kind === "register") {
      const result = await api("/auth/register", {method:"POST", body:{
        name:f.elements.name.value.trim(), email, password:f.elements.password.value,
        accept_terms:true, accept_privacy:true
      }});
      openAuth("sent", {message:result.message});
    } else if (kind === "resend") {
      const result = await api("/auth/activation/resend", {method:"POST", body:{email}});
      openAuth("sent", {message:result.message});
    } else if (kind === "forgot") {
      const result = await api("/auth/password/forgot", {method:"POST", body:{email}});
      openAuth("sent", {message:result.message});
    } else if (kind === "reset") {
      const result = await api("/auth/password/reset", {method:"POST", body:{token:account.resetToken, password:f.elements.password.value}});
      account.resetToken = null;
      signedIn(result, "Listo. Tu contraseña nueva ya está activa.");
    }
  } catch (err) {
    if (err.data?.fields) showErrors(err.data.fields, f);
    else if (kind === "register" && err.data?.error === "mail_unavailable") openAuth("resend", {email, error:err.message});
    else if (err.data?.error === "invalid_link") openAuth("forgot", {error:err.message});
    else f.querySelector(".formError").textContent = err.message;
  } finally {
    if (button.isConnected) {
      button.disabled = false;
      button.removeAttribute("aria-busy");
      button.textContent = label;
    }
  }
}
async function activateAccount(token) {
  try {
    signedIn(await api("/auth/activate", {method:"POST", body:{token}}), "Tu cuenta está activa. Bienvenido a FerrePro.");
  } catch (err) {
    openAuth("resend", {error:err.message});
  }
}
document.addEventListener("submit", event => {
  if (event.target.id === "authForm") { event.preventDefault(); submitAuth(event.target); }
});
authDialog.addEventListener("click", event => {
  const viewButton = event.target.closest("[data-auth-view]");
  if (viewButton) openAuth(viewButton.dataset.authView, {email:authDialog.querySelector('[name="email"]')?.value});
  const eye = event.target.closest(".pwToggle");
  if (eye) {
    const input = eye.parentElement.querySelector("input");
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    eye.setAttribute("aria-pressed", String(show));
    eye.setAttribute("aria-label", show ? "Ocultar contraseña" : "Mostrar contraseña");
  }
});

/* Enlaces directos: #ingresar, #registro, #recuperar, #restablecer/<token>, #activar/<token>, #legal/<doc>.
   El token va en el fragmento (#): el navegador no lo envia al servidor ni queda en registros. */
function clearHash() { history.replaceState(null, "", location.pathname + location.search); }
function handleHash() {
  const hash = location.hash;
  let match;
  if ((match = hash.match(/^#legal\/([a-z]+)$/))) openLegal(match[1]);
  else if (hash === "#ingresar") { clearHash(); openAuth("login"); }
  else if (hash === "#registro") { clearHash(); openAuth("register"); }
  else if (hash === "#recuperar") { clearHash(); openAuth("forgot"); }
  else if ((match = hash.match(/^#restablecer\/([A-Za-z0-9._-]{20,300})$/))) { clearHash(); openAuth("reset", {token:match[1]}); }
  else if ((match = hash.match(/^#activar\/([A-Za-z0-9._-]{20,300})$/))) { clearHash(); activateAccount(match[1]); }
}
window.addEventListener("hashchange", handleHash);

/* ---------- Aviso de almacenamiento ---------- */
const NOTICE_KEY = "ferrepro.notice";
try { if (localStorage.getItem(NOTICE_KEY) !== "2026-11-21") $("#notice").hidden = false; } catch { $("#notice").hidden = false; }
$("#noticeOk").onclick = () => { try { localStorage.setItem(NOTICE_KEY, "2026-11-21"); } catch {} $("#notice").hidden = true; };

/* ---------- Animacion de entrada (Fase 1) ---------- */
const canReveal = "IntersectionObserver" in window && !reducedMotion();
// La entrada arranca cuando el elemento ya asoma (no al tocar el borde), para que se vea completa
const observer = canReveal ? new IntersectionObserver(entries => entries.forEach(({target, isIntersecting}) => {
  if (isIntersecting) { target.classList.remove("pending"); observer.unobserve(target); }
}), {rootMargin:"0px 0px -8% 0px"}) : null;

/* Render por viewport: una seccion se pinta cuando el usuario esta a ~400px de verla.
   Sin IntersectionObserver se pinta de inmediato, y si el observador nunca avisa (pestana
   en segundo plano, navegadores raros) se pinta igual tras unos segundos: el contenido
   nunca se queda en esqueleto. */
const NEAR_FALLBACK_MS = 3000;
function whenNear(element, callback) {
  if (!("IntersectionObserver" in window)) { callback(); return; }
  let done = false;
  const run = () => { if (done) return; done = true; watcher.disconnect(); clearTimeout(fallback); callback(); };
  const watcher = new IntersectionObserver(entries => { if (entries.some(e => e.isIntersecting)) run(); }, {rootMargin:"400px 0px"});
  const fallback = setTimeout(run, NEAR_FALLBACK_MS);
  watcher.observe(element);
}
function reveal(selector) {
  if (!observer) return;
  document.querySelectorAll(selector).forEach(el => {
    if (el.classList.contains("reveal")) return;
    el.classList.add("reveal", "pending"); observer.observe(el);
  });
}
reveal(".feature h2,.sawArt,.sectionHead");

/* ---------- Arranque ---------- */
async function refreshCatalog() {
  try {
    await loadCatalog();
    const notes = reconcileCart();
    renderCart();
    catalog($("#query").value);
    return notes;
  } catch {
    return [];
  }
}
async function boot() {
  $("#cards").setAttribute("aria-busy", "true");
  try {
    await loadCatalog();
  } catch {
    catalogError();
    renderCart();
    return;
  }
  const notes = reconcileCart();
  renderCart();
  whenNear($("#categorias"), () => { renderCategories(); reveal(".tile"); });
  // El catalogo se pinta al acercarse, o antes si una busqueda o un filtro lo necesita
  whenNear($("#catalogo"), () => { if (catalogTerm === null) catalog($("#query").value); reveal(".card"); });
  if (state.store) {
    $("#legalName").textContent = state.store.legal_name || state.store.store_name;
    $("#year").textContent = new Date().getFullYear();
  }
  if (notes.length) toast(notes[0]);
}
renderCart();
loadSession().then(handleHash);
boot();

/* ---------- Asistente FerrePro (chat flotante) ----------
   Contrato de POST /api/chat (backend de Codex, no se modifica aqui):
   pide {message: 1..500 caracteres, history: ultimos 6 turnos {role: "user"|"assistant", content}}
   y responde {reply, mode: "gemini"|"fallback", suggested_products: [{id, slug, name, category, price, stock}]}.
   Limite: 10 mensajes por minuto (429 con retry_after). Como todo POST, va con el token CSRF de api(). */
const CHAT_MAX = 500, CHAT_HISTORY = 6, CHAT_KEEP = 30, CHAT_KEY = "ferrepro.chat";
const CHAT_PROMPTS = ["¿Qué taladros tienen?", "Ver herramientas en stock", "Garantías y envíos"];
const chat = {open:false, pending:false, started:false, history:[], lastFailed:null};
const chatFab = $("#chatFab"), chatPanel = $("#chatPanel"), chatLog = $("#chatLog");
const chatText = $("#chatText"), chatSend = $("#chatSend"), chatCount = $("#chatCount");

// La conversacion sobrevive a recargar la pagina, solo dentro de la pestana (sessionStorage)
try {
  const saved = JSON.parse(sessionStorage.getItem(CHAT_KEY));
  if (Array.isArray(saved)) chat.history = saved.filter(t => t && (t.role === "user" || t.role === "assistant") && typeof t.content === "string").slice(-CHAT_KEEP);
} catch {}
const saveChat = () => { try { sessionStorage.setItem(CHAT_KEY, JSON.stringify(chat.history.slice(-CHAT_KEEP))); } catch {} };

// Respuesta del asistente: todo se escapa; solo se respeta **negrita**
const formatReply = text => esc(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

function scrollChat() {
  chatLog.scrollTo({top:chatLog.scrollHeight, behavior:reducedMotion() ? "instant" : "smooth"});
}
function addMessage(role, html, extra = "") {
  const bubble = document.createElement("div");
  bubble.className = "msg " + (role === "user" ? "user" : "bot") + (extra ? " " + extra : "");
  bubble.innerHTML = html;
  chatLog.appendChild(bubble);
  scrollChat();
  return bubble;
}
function renderConversation() {
  chatLog.innerHTML = "";
  addMessage("assistant", "Hola, soy el asistente de FerrePro. Te ayudo a encontrar herramientas, revisar precios y stock, o resolver dudas de envíos y garantías.");
  if (!chat.history.length) {
    const chips = document.createElement("div");
    chips.className = "chatChips";
    chips.setAttribute("role", "group");
    chips.setAttribute("aria-label", "Preguntas sugeridas");
    chips.innerHTML = CHAT_PROMPTS.map(p => '<button type="button" class="chatChip" data-chat-prompt="' + esc(p) + '">' + esc(p) + "</button>").join("");
    chatLog.appendChild(chips);
  }
  for (const turn of chat.history) addMessage(turn.role, turn.role === "user" ? esc(turn.content) : formatReply(turn.content));
}
function renderSuggestions(list) {
  const items = list.slice(0, 4).map(s => {
    const p = state.byId.get(Number(s.id));
    const name = p ? p.name : String(s.name || "");
    const price = p ? p.price : Number(s.price) || 0;
    const available = p ? p.available : false;
    const note = p && available && p.stock <= 5 ? " · Quedan " + p.stock : "";
    const action = p && available
      ? '<button type="button" class="add" data-chat-add="' + p.id + '" aria-label="Agregar ' + esc(name) + ' al carrito">Agregar</button>'
      : '<button type="button" class="add" disabled>' + (p ? "Agotado" : "No disponible") + "</button>";
    return '<li class="chatProduct">' + art(p ? p.art : "wrench") + "<div><strong>" + esc(name) + "</strong><span>" + money(price) + note + "</span></div>" + action + "</li>";
  });
  if (!items.length) return;
  const ul = document.createElement("ul");
  ul.className = "chatProducts";
  ul.setAttribute("aria-label", "Productos sugeridos");
  ul.innerHTML = items.join("");
  chatLog.appendChild(ul);
  scrollChat();
}

// Panel no modal: se abre y se cierra sin bloquear la tienda; Escape lo cierra
function updateChatViewport() {
  const vv = window.visualViewport;
  if (!vv) return;
  document.documentElement.style.setProperty("--chat-vh", vv.height + "px");
  document.documentElement.style.setProperty("--chat-top", vv.offsetTop + "px");
}
function openChat() {
  if (chat.open) return;
  chat.open = true;
  if (!chat.started) { renderConversation(); chat.started = true; }
  updateChatViewport();
  chatPanel.hidden = false;
  document.body.classList.add("chatOpen");
  chatFab.setAttribute("aria-expanded", "true");
  chatFab.setAttribute("aria-label", "Cerrar el asistente de FerrePro");
  updateChatInput();
  chatText.focus({preventScroll:true});
  scrollChat();
}
function closeChat(returnFocus = true) {
  if (!chat.open) return;
  chat.open = false;
  chatPanel.hidden = true;
  document.body.classList.remove("chatOpen");
  chatFab.setAttribute("aria-expanded", "false");
  chatFab.setAttribute("aria-label", "Abrir el asistente de FerrePro");
  if (returnFocus) chatFab.focus();
}
chatFab.addEventListener("click", () => (chat.open ? closeChat() : openChat()));
$("#chatClose").addEventListener("click", () => closeChat());
chatPanel.addEventListener("keydown", e => { if (e.key === "Escape") { e.stopPropagation(); closeChat(); } });
if (window.visualViewport) {
  // El teclado del movil encoge el area visible: el panel la sigue para no quedar tapado
  window.visualViewport.addEventListener("resize", () => { if (chat.open) { updateChatViewport(); scrollChat(); } });
  window.visualViewport.addEventListener("scroll", () => { if (chat.open) updateChatViewport(); });
}

// Entrada: 500 caracteres como el backend, contador visible desde el 80 %, crece hasta 4 lineas
function updateChatInput() {
  const length = chatText.value.length;
  const over = length > CHAT_MAX;
  chatSend.disabled = chat.pending || !chatText.value.trim() || over;
  chatCount.textContent = length >= CHAT_MAX * 0.8 ? length + " / " + CHAT_MAX : "";
  chatCount.classList.toggle("over", over);
  chatText.setAttribute("aria-invalid", String(over));
  chatText.style.height = "auto";
  chatText.style.height = Math.min(chatText.scrollHeight, 120) + "px";
  chatText.style.overflowY = chatText.scrollHeight > 120 ? "auto" : "hidden"; // barra solo pasadas 4 lineas
}
chatText.addEventListener("input", updateChatInput);
chatText.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    if (!chatSend.disabled) sendChat(chatText.value);
  }
});
$("#chatForm").addEventListener("submit", e => { e.preventDefault(); sendChat(chatText.value); });

async function sendChat(raw, retry = null) {
  const message = (retry ? retry.message : raw).trim();
  if (chat.pending || !message || message.length > CHAT_MAX) return;
  const history = retry ? retry.history : chat.history.slice(-CHAT_HISTORY);
  if (!retry) {
    chatLog.querySelector(".chatChips")?.remove();
    addMessage("user", esc(message));
    chat.history.push({role:"user", content:message});
    saveChat();
    chatText.value = "";
  }
  chat.pending = true;
  chatSend.setAttribute("aria-busy", "true");
  updateChatInput();
  const typing = addMessage("assistant", '<span class="typing" role="img" aria-label="El asistente está escribiendo"><i></i><i></i><i></i></span>');
  try {
    const data = await api("/chat", {method:"POST", body:{message, history}});
    typing.remove();
    const reply = typeof data.reply === "string" && data.reply.trim()
      ? data.reply.trim()
      : "No encontré una respuesta para eso. Prueba con el nombre de una herramienta.";
    addMessage("assistant", formatReply(reply));
    chat.history.push({role:"assistant", content:reply});
    saveChat();
    chat.lastFailed = null;
    if (Array.isArray(data.suggested_products)) renderSuggestions(data.suggested_products);
  } catch (err) {
    typing.remove();
    let text = "No pudimos conectar con el asistente. Revisa tu conexión e inténtalo de nuevo.";
    if (err.status === 429) text = "Enviaste muchos mensajes seguidos. Espera " + (err.data.retry_after || 60) + " segundos y vuelve a intentarlo.";
    else if (err.status === 400) text = err.message;
    chat.lastFailed = {message, history};
    const canRetry = err.status !== 400;
    addMessage("assistant", esc(text) + (canRetry ? '<div class="msgActions"><button type="button" class="pill" data-chat-retry>Reintentar</button></div>' : ""), "error");
  } finally {
    chat.pending = false;
    chatSend.removeAttribute("aria-busy");
    updateChatInput();
    if (chat.open && document.activeElement === document.body) chatText.focus({preventScroll:true});
  }
}

chatLog.addEventListener("click", e => {
  const prompt = e.target.closest("[data-chat-prompt]");
  if (prompt) { sendChat(prompt.dataset.chatPrompt); return; }
  const retry = e.target.closest("[data-chat-retry]");
  if (retry && chat.lastFailed) { retry.closest(".msg").remove(); sendChat("", chat.lastFailed); return; }
  const add = e.target.closest("[data-chat-add]");
  if (add) {
    const id = add.dataset.chatAdd;
    const before = cart[id] || 0;
    change(id, 1);
    if ((cart[id] || 0) > before) {
      add.textContent = "Agregado";
      add.dataset.done = "";
      setTimeout(() => { if (add.isConnected) { add.textContent = "Agregar"; delete add.dataset.done; } }, 1600);
    }
  }
});
