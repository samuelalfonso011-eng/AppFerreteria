"use strict";

/* ---------- Utilidades ---------- */
const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => Array.from(root.querySelectorAll(s));
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const money = v => new Intl.NumberFormat("es-CO", {style:"currency", currency:"COP", maximumFractionDigits:0}).format(v || 0);
const dateFmt = new Intl.DateTimeFormat("es-CO", {dateStyle:"medium", timeStyle:"short", timeZone:"America/Bogota"});
const fmtDate = iso => iso ? dateFmt.format(new Date(iso)) : "Sin registro";
const normalize = v => String(v).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

const ART_LABELS = {drill:"Taladro", saw:"Sierra", wrench:"Llave", roller:"Rodillo", lamp:"Bombilla", helmet:"Casco"};
const ICON = {
  clock:'<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6"/><path d="M8 5v3l2 1.5"/></svg>',
  check:'<svg viewBox="0 0 16 16" aria-hidden="true"><path d="m3.5 8.5 3 3 6-7"/></svg>',
  box:'<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 5 8 2.5 13.5 5v6L8 13.5 2.5 11z"/><path d="M2.5 5 8 7.5 13.5 5M8 7.5v6"/></svg>',
  truck:'<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M1.5 4h8v7h-8zM9.5 6.5h3l2 2.5v2h-5"/><circle cx="4.5" cy="12" r="1.3"/><circle cx="11.5" cy="12" r="1.3"/></svg>',
  x:'<svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4.5 4.5 7 7m0-7-7 7"/></svg>',
  alert:'<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2 14.5 13.5h-13z"/><path d="M8 6.5v3M8 11.5v.2"/></svg>',
  dot:'<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="2.5"/></svg>'
};
const CHEVRON = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4"/></svg>';
const STATUS_STYLE = {
  PENDING_CONFIRMATION:["warn", ICON.clock], CONFIRMED:["info", ICON.check], PREPARING:["info", ICON.box],
  SHIPPED:["info", ICON.truck], DELIVERED:["ok", ICON.check], CANCELLED:["bad", ICON.x]
};
const statusBadge = (code, label) => {
  const [tone, icon] = STATUS_STYLE[code] || ["", ICON.dot];
  return '<span class="badge ' + tone + '">' + icon + esc(label) + "</span>";
};
const badge = (tone, icon, text) => '<span class="badge ' + tone + '">' + icon + esc(text) + "</span>";

/* ---------- API ---------- */
let csrf = null;
const state = {me:null, meta:null};
async function api(path, {method = "GET", body} = {}, retry = true) {
  const options = {method, credentials:"same-origin", headers:{Accept:"application/json"}};
  if (method !== "GET") {
    if (!csrf) csrf = (await (await fetch("/api/auth/csrf", {credentials:"same-origin"})).json()).csrf;
    options.headers["Content-Type"] = "application/json";
    options.headers["X-CSRF-Token"] = csrf;
    options.body = JSON.stringify(body || {});
  }
  let res;
  try { res = await fetch("/api" + path, options); }
  catch { throw Object.assign(new Error("Sin conexión con el servidor."), {status:0, data:{}}); }
  const data = await res.json().catch(() => ({}));
  if (res.status === 403 && data.error === "csrf" && retry) {
    csrf = null;
    return api(path, {method, body}, false);
  }
  if (!res.ok) {
    const err = Object.assign(new Error(data.message || "No pudimos completar la operación."), {status:res.status, data});
    if (res.status === 401 && path.startsWith("/admin")) showLogin("Tu sesión terminó. Vuelve a iniciar sesión.");
    throw err;
  }
  return data;
}

/* ---------- Avisos, modal y confirmacion ---------- */
let toastTimer;
function toast(message) {
  $("#toast").textContent = message;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $("#toast").textContent = "", 2600);
}
const modal = $("#modal");
const closeButton = '<button class="closeBtn" type="button" data-close aria-label="Cerrar">×</button>';
function openModal(html) {
  $("#modalBody").innerHTML = html;
  initListboxes($("#modalBody"));
  if (!modal.open) modal.showModal();
  const first = $("#modalBody input:not([type=hidden]), #modalBody textarea, #modalBody .lbBtn");
  if (first) first.focus();
}
const confirmDialog = $("#confirm");
let confirmResolve = null;
function confirmAction({title, text, action}) {
  $("#confirmTitle").textContent = title;
  $("#confirmText").textContent = text;
  $("#confirmYes").textContent = action;
  confirmDialog.showModal();
  $("[data-confirm=no]", confirmDialog).focus();
  return new Promise(resolve => { confirmResolve = resolve; });
}
confirmDialog.addEventListener("close", () => { if (confirmResolve) { confirmResolve(confirmDialog.returnValue === "yes"); confirmResolve = null; } });
confirmDialog.addEventListener("click", e => {
  const b = e.target.closest("[data-confirm]");
  if (b) confirmDialog.close(b.dataset.confirm);
});
confirmDialog.addEventListener("cancel", () => { confirmDialog.returnValue = "no"; });

function setBusy(button, busy, busyText) {
  if (!button) return;
  if (busy) { button.dataset.label = button.textContent; button.textContent = busyText || "Guardando…"; }
  else if (button.dataset.label) button.textContent = button.dataset.label;
  button.disabled = busy;
  button.setAttribute("aria-busy", String(busy));
}
function clearFieldErrors(form) {
  $$(".fieldError", form).forEach(e => e.remove());
  $$("[aria-invalid]", form).forEach(e => { e.removeAttribute("aria-invalid"); e.removeAttribute("aria-describedby"); });
  const general = $(".formError", form);
  if (general) general.textContent = "";
}
function showFieldErrors(form, fields, fallback) {
  let first = null;
  const leftovers = [];
  for (const [name, message] of Object.entries(fields || {})) {
    const input = form.elements[name];
    const el = input instanceof RadioNodeList ? input[0] : input;
    if (!el) { leftovers.push(message); continue; }
    const holder = el.closest(".lb, .field, .switch, fieldset") || el.parentElement;
    const focusable = el.type === "hidden" ? $(".lbBtn", holder) : el;
    const id = "err-" + name;
    const msg = document.createElement("span");
    msg.className = "fieldError";
    msg.id = id;
    msg.textContent = message;
    holder.appendChild(msg);
    focusable.setAttribute("aria-invalid", "true");
    focusable.setAttribute("aria-describedby", id);
    first = first || focusable;
  }
  const general = $(".formError", form);
  if (general && (leftovers.length || fallback)) general.textContent = leftovers[0] || fallback;
  if (first) first.focus();
}

/* ---------- Listbox accesible (reemplaza al select nativo) ---------- */
let lbSeq = 0;
function listbox({name, label, options, value, placeholder = "Elige una opción"}) {
  const id = "lb" + (++lbSeq);
  const selected = options.find(o => String(o.value) === String(value));
  return '<div class="lb" data-lb><span id="' + id + '-label">' + esc(label) + "</span>" +
    '<input type="hidden" name="' + esc(name) + '" value="' + (selected ? esc(selected.value) : "") + '">' +
    '<button type="button" class="lbBtn" id="' + id + '-btn" aria-haspopup="listbox" aria-expanded="false" aria-controls="' + id + '-list" aria-labelledby="' + id + "-label " + id + '-btn">' +
    '<span class="lbValue">' + esc(selected ? selected.label : placeholder) + "</span>" + CHEVRON + "</button>" +
    '<ul class="lbList" id="' + id + '-list" role="listbox" tabindex="-1" aria-labelledby="' + id + '-label" hidden>' +
    options.map((o, i) => '<li role="option" id="' + id + "-o" + i + '" data-value="' + esc(o.value) + '" aria-selected="' + (o === selected) + '">' + esc(o.label) + "</li>").join("") +
    "</ul></div>";
}
function initListboxes(root) { $$("[data-lb]", root).forEach(setupListbox); }
function setupListbox(box) {
  const btn = $(".lbBtn", box), list = $(".lbList", box), input = $("input[type=hidden]", box);
  const opts = $$("[role=option]", list);
  let active = -1, typed = "", typedTimer;
  const setActive = (i, scroll = true) => {
    if (!opts.length) return;
    active = (i + opts.length) % opts.length;
    opts.forEach((o, j) => o.classList.toggle("active", j === active));
    list.setAttribute("aria-activedescendant", opts[active].id);
    if (scroll) opts[active].scrollIntoView({block:"nearest"});
  };
  const open = () => {
    list.hidden = false;
    btn.setAttribute("aria-expanded", "true");
    const current = opts.findIndex(o => o.getAttribute("aria-selected") === "true");
    setActive(current >= 0 ? current : 0);
    list.focus();
  };
  const close = (focusButton = true) => {
    list.hidden = true;
    btn.setAttribute("aria-expanded", "false");
    list.removeAttribute("aria-activedescendant");
    if (focusButton) btn.focus();
  };
  const choose = i => {
    const option = opts[i];
    if (!option) return;
    opts.forEach(o => o.setAttribute("aria-selected", String(o === option)));
    input.value = option.dataset.value;
    $(".lbValue", btn).textContent = option.textContent;
    btn.removeAttribute("aria-invalid");
    $(".fieldError", box)?.remove();
    close();
    input.dispatchEvent(new Event("change", {bubbles:true}));
  };
  btn.addEventListener("click", () => (list.hidden ? open() : close()));
  btn.addEventListener("keydown", e => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); open(); }
  });
  list.addEventListener("keydown", e => {
    switch (e.key) {
      case "ArrowDown": e.preventDefault(); setActive(active + 1); break;
      case "ArrowUp": e.preventDefault(); setActive(active - 1); break;
      case "Home": e.preventDefault(); setActive(0); break;
      case "End": e.preventDefault(); setActive(opts.length - 1); break;
      case "Enter": case " ": e.preventDefault(); choose(active); break;
      case "Escape": e.preventDefault(); e.stopPropagation(); close(); break;
      case "Tab": close(false); break;
      default:
        if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
          typed += e.key;
          clearTimeout(typedTimer);
          typedTimer = setTimeout(() => { typed = ""; }, 600);
          const i = opts.findIndex(o => normalize(o.textContent).startsWith(normalize(typed)));
          if (i >= 0) setActive(i);
        }
    }
  });
  list.addEventListener("click", e => {
    const li = e.target.closest("[role=option]");
    if (li) choose(opts.indexOf(li));
  });
  list.addEventListener("mousemove", e => {
    const li = e.target.closest("[role=option]");
    if (li) setActive(opts.indexOf(li), false);
  });
  box.addEventListener("focusout", e => { if (!list.hidden && !box.contains(e.relatedTarget)) close(false); });
}
document.addEventListener("pointerdown", e => {
  $$(".lbList:not([hidden])").forEach(list => {
    const box = list.closest("[data-lb]");
    if (!box.contains(e.target)) { list.hidden = true; $(".lbBtn", box).setAttribute("aria-expanded", "false"); }
  });
});

/* ---------- Plantillas comunes ---------- */
const head = (title, text, actions = "") =>
  '<div class="viewHead"><div><h1>' + esc(title) + "</h1><p>" + esc(text) + "</p></div>" + (actions ? "<div>" + actions + "</div>" : "") + "</div>";
const emptyState = (title, text, action = "") =>
  '<div class="emptyState"><h2>' + esc(title) + '</h2><p class="muted">' + esc(text) + "</p>" + action + "</div>";
const fact = (k, v) => "<div><dt>" + esc(k) + "</dt><dd>" + esc(v) + "</dd></div>";
const field = (name, label, value = "", attrs = "") =>
  '<label class="field"><span>' + esc(label) + '</span><input name="' + name + '" value="' + esc(value) + '" ' + attrs + "></label>";
const area = (name, label, value = "", attrs = "") =>
  '<label class="field full"><span>' + esc(label) + '</span><textarea name="' + name + '" ' + attrs + ">" + esc(value) + "</textarea></label>";
const toggle = (name, label, checked) =>
  '<label class="switch full"><span>' + esc(label) + '</span><input type="checkbox" role="switch" name="' + name + '"' + (checked ? " checked" : "") + "></label>";
const choices = (name, label, options, value) =>
  '<fieldset class="full choiceSet"><legend>' + esc(label) + '</legend><div class="choiceGrid">' +
  options.map(o => '<label class="choice"><input type="radio" name="' + name + '" value="' + esc(o.value) + '"' + (String(o.value) === String(value) ? " checked" : "") + "><span>" + esc(o.label) + "</span></label>").join("") +
  "</div></fieldset>";
// Acepta "489900", "489.900" (miles con punto) y "1234,50"; lo demas se envia tal cual para que el backend lo rechace
const numberValue = raw => {
  let v = String(raw ?? "").replace(/\s/g, "");
  if (v === "") return null;
  if (/^\d{1,3}(\.\d{3})+(,\d+)?$/.test(v)) v = v.replace(/\./g, "").replace(",", ".");
  else v = v.replace(",", ".");
  return /^\d+(\.\d+)?$/.test(v) ? Number(v) : v;
};

/* ---------- Router por pestañas ---------- */
const VIEWS = {resumen:renderDashboard, pedidos:renderOrders, clientes:renderCustomers, productos:renderProducts,
  categorias:renderCategories, inventario:renderInventory, ajustes:renderSettings};

/* Tablas que se apilan en el telefono: cada celda recibe la etiqueta de su columna (data-label),
   la primera es la principal (cellLead) y la de botones va aparte (cellActions). El CSS de
   admin.css (table.stack) las muestra como tarjetas hasta 640px y como tabla desde ahi.
   Un observador lo aplica a toda tabla nueva del panel y del modal, sin tocar cada plantilla. */
function stackTables(root) {
  $$("table:not(.stack)", root).forEach(table => {
    const labels = $$("thead th", table).map(th => th.textContent.trim());
    table.classList.add("stack");
    $$("tbody tr", table).forEach(row => {
      Array.from(row.cells).forEach((cell, i) => {
        if (labels[i]) cell.dataset.label = labels[i];
        if (i === 0) cell.classList.add("cellLead");
        if (cell.querySelector(".rowActions")) cell.classList.add("cellActions");
        // Celdas de varias partes (valor + texto secundario): se agrupan para apilarse a la derecha de la etiqueta
        if (i > 0 && !cell.classList.contains("cellActions") && cell.childNodes.length > 1) {
          const value = document.createElement("span");
          value.className = "cellValue";
          value.append(...cell.childNodes);
          cell.append(value);
        }
      });
    });
  });
}
const tableWatcher = new MutationObserver(records => records.forEach(r => {
  if (r.target instanceof Element) stackTables(r.target);
}));
tableWatcher.observe($("#view"), {childList:true, subtree:true});
tableWatcher.observe($("#modalBody"), {childList:true, subtree:true});
const currentView = () => { const v = location.hash.slice(1); return VIEWS[v] ? v : "resumen"; };
async function route() {
  if (!state.me) return;
  const name = currentView();
  $$("#tabs [role=tab]").forEach(tab => {
    const on = tab.dataset.view === name;
    tab.setAttribute("aria-selected", String(on));
    tab.tabIndex = on ? 0 : -1;
  });
  const view = $("#view");
  view.setAttribute("aria-labelledby", "tab-" + name);
  view.hidden = false;
  view.setAttribute("aria-busy", "true");
  view.innerHTML = '<div class="grid"><div class="skeleton"></div><div class="skeleton"></div></div>';
  try {
    await VIEWS[name](view);
  } catch (err) {
    if (err.status !== 401) view.innerHTML = emptyState("No pudimos cargar esta sección", err.message, '<button class="btn secondary" data-reload>Reintentar</button>');
  } finally {
    view.removeAttribute("aria-busy");
  }
}
window.addEventListener("hashchange", route);
$("#tabs").addEventListener("keydown", e => {
  const tabs = $$("#tabs [role=tab]");
  const i = tabs.indexOf(document.activeElement);
  if (i < 0) return;
  const next = {ArrowRight:i + 1, ArrowLeft:i - 1, Home:0, End:tabs.length - 1}[e.key];
  if (next === undefined) return;
  e.preventDefault();
  const tab = tabs[(next + tabs.length) % tabs.length];
  tab.focus();
  location.hash = tab.dataset.view;
});

/* ---------- Resumen ---------- */
async function renderDashboard(view) {
  const d = await api("/admin/dashboard");
  const max = Math.max(1, ...d.trend.map(t => t.total));
  const chartLabel = "Ventas por día: " + d.trend.map(t => t.label + " " + money(t.total)).join(", ");
  view.innerHTML = head("Resumen", "Ventas confirmadas, pedidos y stock al minuto.") +
    '<div class="grid dash">' +
      '<article class="card lead"><p class="eyebrow">Ventas del mes</p><p class="display">' + money(d.sales.month) + "</p>" +
        '<div class="kpis"><div class="kpi"><span>Hoy</span><strong>' + money(d.sales.today) + "</strong></div>" +
        '<div class="kpi"><span>Últimos 7 días</span><strong>' + money(d.sales.week) + "</strong></div>" +
        '<div class="kpi"><span>Por confirmar</span><strong>' + d.pending_orders + "</strong></div></div></article>" +
      '<article class="card"><h2>Pedidos por estado</h2><ul class="list">' +
        d.status_counts.map(s => "<li>" + statusBadge(s.status, s.label) + '<span class="num">' + s.count + "</span></li>").join("") + "</ul></article>" +
      '<article class="card span2"><div class="cardHead"><h2>Ventas por día</h2><span class="muted">Últimos 7 días</span></div>' +
        '<div class="bars" role="img" aria-label="' + esc(chartLabel) + '">' +
        d.trend.map((t, i) => '<div class="barCol' + (i === d.trend.length - 1 ? " today" : "") + '"><div class="barTrack"><div class="barFill" data-h="' + Math.round(t.total / max * 100) + '"></div></div><small>' + esc(t.label) + "</small></div>").join("") +
        "</div></article>" +
      '<article class="card"><h2>Más vendidos</h2>' + (d.top_products.length
        ? '<ul class="list">' + d.top_products.map(p => "<li><span>" + esc(p.name) + '</span><span class="num">' + p.units + " u.</span></li>").join("") + "</ul>"
        : '<p class="empty">Aún no hay ventas confirmadas.</p>') + "</article>" +
      '<article class="card flush span2"><div class="cardHead"><h2>Pedidos recientes</h2><a href="#pedidos">Ver todos</a></div>' +
        (d.recent_orders.length ? '<div class="tableWrap">' + ordersTable(d.recent_orders) + "</div>" : '<p class="empty">Todavía no hay pedidos.</p>') + "</article>" +
      '<article class="card"><div class="cardHead"><h2>Stock bajo</h2><a href="#inventario">Inventario</a></div>' + (d.low_stock.length
        ? '<ul class="list">' + d.low_stock.map(p => '<li><span><span class="cellMain">' + esc(p.name) + '</span><span class="cellSub">Mínimo ' + p.min_stock_alert + '</span></span><button class="btn secondary small" data-adjust="' + p.id + '" data-name="' + esc(p.name) + '" data-stock="' + p.stock + '">' + p.stock + " u. Ajustar</button></li>").join("") + "</ul>"
        : '<p class="empty">Todo el inventario está por encima del mínimo.</p>') + "</article>" +
    "</div>";
  $$(".barFill", view).forEach(bar => bar.style.setProperty("--h", bar.dataset.h + "%"));
}

/* ---------- Pedidos ---------- */
const orderFilter = {status:"", q:"", page:1};
function ordersTable(rows) {
  return '<table><thead><tr><th scope="col">Pedido</th><th scope="col">Cliente</th><th scope="col">Estado</th><th scope="col" class="right">Total</th></tr></thead><tbody>' +
    rows.map(o => '<tr><td><button class="linkBtn" data-order="' + o.id + '">' + esc(o.order_number) + '</button><span class="cellSub">' + fmtDate(o.created_at) + "</span></td>" +
      '<td><span class="cellMain">' + esc(o.customer_name) + '</span><span class="cellSub">' + esc(o.city) + " · " + o.item_count + " u.</span></td>" +
      "<td>" + statusBadge(o.status, o.status_label) + '</td><td class="right">' + money(o.total) + "</td></tr>").join("") +
    "</tbody></table>";
}
async function renderOrders(view) {
  const chips = [["", "Todos"], ...state.meta.statuses.map(s => [s.code, s.label])];
  view.innerHTML = head("Pedidos", "Confirma, prepara y despacha. Cancelar un pedido devuelve su stock al inventario.") +
    '<div class="toolbar"><label class="field search"><span class="sr">Buscar pedidos</span><input type="search" id="orderSearch" placeholder="Buscar por número, cliente o correo" value="' + esc(orderFilter.q) + '"></label></div>' +
    '<div class="chips" role="group" aria-label="Filtrar por estado">' +
    chips.map(([code, label]) => '<button class="chip" data-order-status="' + code + '" aria-pressed="' + (code === orderFilter.status) + '">' + esc(label) + "</button>").join("") +
    '</div><div class="card flush" id="ordersBox"></div>';
  $("#orderSearch").addEventListener("input", debounce(e => { orderFilter.q = e.target.value.trim(); orderFilter.page = 1; loadOrders(); }, 250));
  await loadOrders();
}
async function loadOrders() {
  const box = $("#ordersBox");
  if (!box) return;
  const params = new URLSearchParams({page:orderFilter.page});
  if (orderFilter.status) params.set("status", orderFilter.status);
  if (orderFilter.q) params.set("q", orderFilter.q);
  box.setAttribute("aria-busy", "true");
  const d = await api("/admin/orders?" + params);
  box.removeAttribute("aria-busy");
  if (!d.orders.length) {
    box.innerHTML = emptyState(orderFilter.q || orderFilter.status ? "Ningún pedido coincide" : "Todavía no hay pedidos",
      orderFilter.q || orderFilter.status ? "Prueba con otro estado o término de búsqueda." : "Los pedidos de la tienda aparecerán aquí al instante.");
    return;
  }
  box.innerHTML = '<div class="tableWrap">' + ordersTable(d.orders) + "</div>" +
    '<div class="pager"><span>' + d.total + " pedidos · página " + d.page + " de " + d.pages + "</span><span>" +
    '<button class="btn secondary small" data-page="' + (d.page - 1) + '"' + (d.page <= 1 ? " disabled" : "") + ">Anterior</button> " +
    '<button class="btn secondary small" data-page="' + (d.page + 1) + '"' + (d.page >= d.pages ? " disabled" : "") + ">Siguiente</button></span></div>";
}
/* ---------- Clientes ---------- */
const customerFilter = {status:"all", q:"", page:1};
const CUSTOMER_STATUS = {
  verified:["ok", ICON.check, "Verificado"],
  pending:["warn", ICON.clock, "Pendiente"],
  disabled:["", ICON.dot, "Desactivado"]
};
async function renderCustomers(view) {
  view.innerHTML = head("Clientes", "Cuentas registradas en la tienda. Solo lectura: nunca se muestran contraseñas ni datos de sesión.") +
    '<div class="toolbar"><label class="field search"><span class="sr">Buscar clientes</span><input type="search" id="customerSearch" placeholder="Buscar por nombre o correo" value="' + esc(customerFilter.q) + '" autocomplete="off"></label></div>' +
    '<div class="chips" role="group" aria-label="Filtrar clientes" id="customerChips"></div>' +
    '<div class="card flush" id="customersBox"></div>';
  $("#customerSearch").addEventListener("input", debounce(e => { customerFilter.q = e.target.value.trim(); customerFilter.page = 1; loadCustomers(); }, 200));
  await loadCustomers();
}
function renderCustomerChips(counts) {
  const chips = [["all", "Todos"], ["verified", "Verificados"], ["pending", "Pendientes"]];
  $("#customerChips").innerHTML = chips.map(([v, l]) =>
    '<button class="chip" data-customer-status="' + v + '" aria-pressed="' + (v === customerFilter.status) + '">' + l +
    '<span class="count">' + (counts ? counts[v] : "") + "</span></button>").join("");
}
async function loadCustomers() {
  const box = $("#customersBox");
  if (!box) return;
  const params = new URLSearchParams({status:customerFilter.status, page:customerFilter.page});
  if (customerFilter.q) params.set("q", customerFilter.q);
  box.setAttribute("aria-busy", "true");
  if (!box.querySelector("table")) box.innerHTML = '<p class="sr">Cargando clientes…</p>' + '<div class="skeleton skeletonRow"></div>'.repeat(4);
  const d = await api("/admin/customers?" + params);
  box.removeAttribute("aria-busy");
  renderCustomerChips(d.counts);
  if (!d.customers.length) {
    const filtered = customerFilter.q || customerFilter.status !== "all";
    box.innerHTML = emptyState(filtered ? "Ningún cliente coincide" : "Todavía no hay clientes",
      filtered ? "Prueba con otro nombre, correo o filtro." : "Las cuentas que se registren en la tienda aparecerán aquí.");
    return;
  }
  box.innerHTML = '<div class="tableWrap"><table><thead><tr><th scope="col">Cliente</th><th scope="col">Estado</th><th scope="col">Registro</th><th scope="col" class="right">Pedidos</th><th scope="col">Habeas Data</th></tr></thead><tbody>' +
    d.customers.map(c => {
      const [tone, icon, label] = CUSTOMER_STATUS[c.status] || CUSTOMER_STATUS.disabled;
      const consent = c.habeas_data.accepted
        ? badge("ok", ICON.check, "Aceptada") + '<span class="cellSub">' + fmtDate(c.habeas_data.accepted_at) + " · v" + esc(c.habeas_data.policy_version) + "</span>"
        : badge("bad", ICON.x, "Sin registro");
      return '<tr><td><div class="customerHead"><span class="initial" aria-hidden="true">' + esc((c.name.trim()[0] || "?").toUpperCase()) + "</span>" +
        '<span><span class="cellMain">' + esc(c.name) + '</span><span class="cellSub">' + esc(c.email) + "</span></span></div></td>" +
        "<td>" + badge(tone, icon, label) + "</td>" +
        "<td>" + fmtDate(c.created_at) + '<span class="cellSub">' + (c.last_login_at ? "Último acceso " + fmtDate(c.last_login_at) : "Aún no inicia sesión") + "</span></td>" +
        '<td class="right">' + c.orders + "</td><td>" + consent + "</td></tr>";
    }).join("") + "</tbody></table></div>" +
    (d.pages > 1 ? '<div class="pager"><span>' + d.total + " clientes · página " + d.page + " de " + d.pages + "</span><span>" +
      '<button class="btn secondary small" data-customer-page="' + (d.page - 1) + '"' + (d.page <= 1 ? " disabled" : "") + ">Anterior</button> " +
      '<button class="btn secondary small" data-customer-page="' + (d.page + 1) + '"' + (d.page >= d.pages ? " disabled" : "") + ">Siguiente</button></span></div>"
      : '<div class="pager"><span>' + d.total + (d.total === 1 ? " cliente" : " clientes") + "</span></div>");
}

const statusLabel = code => (state.meta.statuses.find(s => s.code === code) || {label:code}).label;
async function openOrder(id) {
  const {order:o} = await api("/admin/orders/" + id);
  const forward = o.allowed_transitions.filter(s => s !== "CANCELLED");
  const canCancel = o.allowed_transitions.includes("CANCELLED");
  const items = o.items.map(i => '<li><span><span class="cellMain">' + esc(i.name) + '</span><span class="cellSub">' + esc(i.sku) + " · " + i.quantity + " × " + money(i.unit_price) + '</span></span><span class="num">' + money(i.subtotal) + "</span></li>").join("");
  openModal(
    '<div class="sheetHead"><div><h2 id="modalTitle">' + esc(o.order_number) + '</h2><span class="muted">' + fmtDate(o.created_at) + "</span></div>" + closeButton + "</div>" +
    '<div class="sheetBody">' +
      "<div>" + statusBadge(o.status, o.status_label) + "</div>" +
      '<section class="section"><h3>Cliente</h3><dl class="facts">' + fact("Nombre", o.customer.name) + fact("Correo", o.customer.email) + fact("Celular", o.customer.phone) + fact("Documento", o.customer.doc_type + " " + o.customer.doc_number) + "</dl></section>" +
      '<section class="section"><h3>Entrega</h3><dl class="facts">' + fact("Dirección", o.shipping.line) + (o.notes ? fact("Indicaciones", o.notes) : "") + "</dl></section>" +
      '<section class="section"><h3>Productos</h3><ul class="list">' + items +
        '<li><span>Envío</span><span class="num">' + (o.shipping_cost ? money(o.shipping_cost) : "Gratis") + "</span></li>" +
        '<li><strong>Total</strong><strong class="num">' + money(o.total) + "</strong></li></ul></section>" +
      '<section class="section"><h3>Autorizaciones del cliente</h3><dl class="facts">' +
        fact("Términos", fmtDate(o.consent.terms_accepted_at)) + fact("Habeas Data", fmtDate(o.consent.privacy_accepted_at)) + fact("Versión", o.consent.policy_version) + "</dl></section>" +
      '<section class="section"><h3>Historial</h3><ol class="timeline">' +
        o.history.map(h => "<li><strong>" + esc(h.new_status_label) + "</strong>" + (h.comment ? "<span>" + esc(h.comment) + "</span>" : "") + "<time>" + fmtDate(h.created_at) + " · " + esc(h.changed_by) + "</time></li>").join("") + "</ol></section>" +
      (o.allowed_transitions.length
        ? '<section class="section"><h3>Actualizar estado</h3><label class="field"><span>Nota para el historial (opcional)</span><textarea id="statusComment" maxlength="500"></textarea></label>' +
          '<div class="sheetActions">' +
          (canCancel ? '<button class="btn dangerGhost" data-cancel-order="' + o.id + '" data-number="' + esc(o.order_number) + '">Cancelar pedido</button>' : "") +
          forward.map((s, i) => '<button class="btn ' + (i === 0 ? "primary" : "secondary") + '" data-set-status="' + s + '" data-order-id="' + o.id + '">Marcar como ' + esc(statusLabel(s).toLowerCase()) + "</button>").join("") +
          "</div></section>"
        : "") +
    "</div>");
}
async function changeStatus(orderId, status, button) {
  const comment = ($("#statusComment")?.value || "").trim();
  setBusy(button, true, "Actualizando…");
  try {
    await api("/admin/orders/" + orderId + "/status", {method:"POST", body:{status, comment}});
    toast("Pedido actualizado: " + statusLabel(status).toLowerCase());
    await openOrder(orderId);
    if (currentView() === "pedidos") loadOrders(); else if (currentView() === "resumen") route();
  } catch (err) {
    toast(err.message);
    setBusy(button, false);
  }
}

/* ---------- Productos ---------- */
const productFilter = {q:"", status:"all"};
let categoriesCache = null;
async function categoryOptions() {
  categoriesCache = (await api("/admin/categories")).categories;
  return categoriesCache.map(c => ({value:c.id, label:c.name + (c.is_active ? "" : " (inactiva)")}));
}
async function renderProducts(view) {
  view.innerHTML = head("Productos", "Precio, ficha y visibilidad en la tienda. El stock se mueve desde Inventario para que quede en el kárdex.",
      '<button class="btn primary" data-new-product>Nuevo producto</button>') +
    '<div class="toolbar"><label class="field search"><span class="sr">Buscar productos</span><input type="search" id="productSearch" placeholder="Buscar por nombre o SKU" value="' + esc(productFilter.q) + '"></label></div>' +
    '<div class="chips" role="group" aria-label="Filtrar productos">' +
    [["all", "Todos"], ["active", "Activos"], ["inactive", "Inactivos"], ["low", "Stock bajo"]].map(([v, l]) => '<button class="chip" data-product-status="' + v + '" aria-pressed="' + (v === productFilter.status) + '">' + l + "</button>").join("") +
    '</div><div class="card flush" id="productsBox"></div>';
  $("#productSearch").addEventListener("input", debounce(e => { productFilter.q = e.target.value.trim(); loadProducts(); }, 250));
  await loadProducts();
}
async function loadProducts() {
  const box = $("#productsBox");
  if (!box) return;
  const params = new URLSearchParams({status:productFilter.status});
  if (productFilter.q) params.set("q", productFilter.q);
  const {products} = await api("/admin/products?" + params);
  if (!products.length) {
    box.innerHTML = emptyState("No hay productos aquí", productFilter.q || productFilter.status !== "all" ? "Prueba con otro filtro." : "Crea el primero para que aparezca en la tienda.",
      '<button class="btn primary" data-new-product>Nuevo producto</button>');
    return;
  }
  box.innerHTML = '<div class="tableWrap"><table><thead><tr><th scope="col">Producto</th><th scope="col">Categoría</th><th scope="col" class="right">Precio</th><th scope="col" class="right">Stock</th><th scope="col">Estado</th><th scope="col" class="right"><span class="sr">Acciones</span></th></tr></thead><tbody>' +
    products.map(p => '<tr><td><span class="cellMain">' + esc(p.name) + '</span><span class="cellSub">' + esc(p.sku) + "</span></td><td>" + esc(p.category) + '</td><td class="right">' + money(p.price) + '</td>' +
      '<td class="right">' + (p.is_low_stock ? badge("warn", ICON.alert, p.stock + " bajo") : p.stock) + "</td>" +
      "<td>" + (p.is_active ? badge("ok", ICON.check, "Visible") : badge("", ICON.dot, "Oculto")) + "</td>" +
      '<td><div class="rowActions"><button class="btn secondary small" data-edit-product="' + p.id + '">Editar</button>' +
      '<button class="btn secondary small" data-toggle-product="' + p.id + '">' + (p.is_active ? "Ocultar" : "Publicar") + "</button>" +
      '<button class="btn dangerGhost small" data-delete-product="' + p.id + '" data-name="' + esc(p.name) + '">Eliminar</button></div></td></tr>').join("") +
    "</tbody></table></div>";
}
async function openProductForm(id) {
  const [options, product] = await Promise.all([
    categoryOptions(),
    id ? api("/admin/products?status=all").then(d => d.products.find(p => p.id === Number(id))) : Promise.resolve(null)
  ]);
  const p = product || {name:"", sku:"", category_id:"", price:"", min_stock_alert:5, art:"wrench", description:"", specs_text:"", is_active:true};
  const arts = state.meta.art_keys.map(k => ({value:k, label:ART_LABELS[k] || k}));
  openModal(
    '<form data-form="product" data-id="' + (product ? product.id : "") + '" novalidate>' +
    '<div class="sheetHead"><h2 id="modalTitle">' + (product ? "Editar producto" : "Nuevo producto") + "</h2>" + closeButton + "</div>" +
    '<div class="sheetBody"><div class="formGrid">' +
      '<div class="full">' + field("name", "Nombre", p.name, 'required maxlength="200" autocomplete="off"') + "</div>" +
      field("sku", "SKU", p.sku, 'required maxlength="50" autocomplete="off" placeholder="FP-0007"') +
      listbox({name:"category_id", label:"Categoría", options, value:p.category_id}) +
      field("price", "Precio en pesos", p.price, 'required inputmode="numeric" autocomplete="off" placeholder="89900"') +
      field("min_stock_alert", "Alerta de stock mínimo", p.min_stock_alert, 'inputmode="numeric" autocomplete="off"') +
      (product ? "" : field("initial_stock", "Stock inicial", "0", 'inputmode="numeric" autocomplete="off"')) +
      choices("art", "Ilustración en la tienda", arts, p.art) +
      area("description", "Descripción", p.description, 'maxlength="2000" rows="3"') +
      area("specs_text", "Características técnicas (una por línea)", p.specs_text, 'maxlength="2000" rows="4"') +
      toggle("is_active", "Visible en la tienda", p.is_active) +
    '</div><p class="formError" role="alert"></p><div class="sheetActions"><button class="btn secondary" type="button" data-close>Cancelar</button><button class="btn primary" type="submit">' + (product ? "Guardar cambios" : "Crear producto") + "</button></div></div></form>");
}
async function submitProduct(form) {
  const id = form.dataset.id;
  const f = form.elements;
  const body = {
    name:f.name.value, sku:f.sku.value.trim().toUpperCase(), category_id:numberValue(f.category_id.value),
    price:numberValue(f.price.value), min_stock_alert:numberValue(f.min_stock_alert.value), art:f.art.value,
    description:f.description.value, specs_text:f.specs_text.value, is_active:f.is_active.checked
  };
  if (!id) body.initial_stock = numberValue(f.initial_stock.value) ?? 0;
  const button = $("button[type=submit]", form);
  setBusy(button, true);
  try {
    await api(id ? "/admin/products/" + id : "/admin/products", {method:id ? "PUT" : "POST", body});
    modal.close();
    toast(id ? "Producto actualizado. La tienda ya muestra los cambios." : "Producto creado.");
    loadProducts();
  } catch (err) {
    setBusy(button, false);
    showFieldErrors(form, err.data.fields, err.message);
  }
}

/* ---------- Categorias ---------- */
async function renderCategories(view) {
  const {categories} = await api("/admin/categories");
  view.innerHTML = head("Categorías", "Las categorías con titular aparecen en el mosaico de la portada, en el orden indicado (máximo cuatro).",
      '<button class="btn primary" data-new-category>Nueva categoría</button>') +
    '<div class="card flush">' + (categories.length
      ? '<div class="tableWrap"><table><thead><tr><th scope="col">Categoría</th><th scope="col">Titular en portada</th><th scope="col" class="right">Productos</th><th scope="col" class="right">Orden</th><th scope="col">Estado</th><th scope="col" class="right"><span class="sr">Acciones</span></th></tr></thead><tbody>' +
        categories.map(c => '<tr><td><span class="cellMain">' + esc(c.name) + '</span><span class="cellSub">/' + esc(c.slug) + "</span></td><td>" + (c.headline ? esc(c.headline) : '<span class="muted">No aparece</span>') + '</td><td class="right">' + c.product_count + '</td><td class="right">' + c.sort_order + "</td>" +
          "<td>" + (c.is_active ? badge("ok", ICON.check, "Activa") : badge("", ICON.dot, "Inactiva")) + "</td>" +
          '<td><div class="rowActions"><button class="btn secondary small" data-edit-category="' + c.id + '">Editar</button><button class="btn secondary small" data-toggle-category="' + c.id + '">' + (c.is_active ? "Desactivar" : "Activar") + "</button></div></td></tr>").join("") +
        "</tbody></table></div>"
      : emptyState("Sin categorías", "Crea la primera para organizar el catálogo.")) + "</div>";
  categoriesCache = categories;
}
function openCategoryForm(id) {
  const c = (categoriesCache || []).find(x => x.id === Number(id)) || {name:"", headline:"", art:"wrench", sort_order:0, is_active:true};
  const arts = state.meta.art_keys.map(k => ({value:k, label:ART_LABELS[k] || k}));
  openModal(
    '<form data-form="category" data-id="' + (id || "") + '" novalidate>' +
    '<div class="sheetHead"><h2 id="modalTitle">' + (id ? "Editar categoría" : "Nueva categoría") + "</h2>" + closeButton + "</div>" +
    '<div class="sheetBody"><div class="formGrid">' +
      field("name", "Nombre", c.name, 'required maxlength="80" autocomplete="off"') +
      field("sort_order", "Orden", c.sort_order, 'inputmode="numeric" autocomplete="off"') +
      '<div class="full">' + field("headline", "Titular en la portada (opcional)", c.headline || "", 'maxlength="120" autocomplete="off" placeholder="Pinturas y Acabados"') + "</div>" +
      choices("art", "Ilustración del mosaico", arts, c.art) +
      toggle("is_active", "Activa en la tienda", c.is_active) +
    '</div><p class="formError" role="alert"></p><div class="sheetActions"><button class="btn secondary" type="button" data-close>Cancelar</button><button class="btn primary" type="submit">' + (id ? "Guardar cambios" : "Crear categoría") + "</button></div></div></form>");
}
async function submitCategory(form) {
  const id = form.dataset.id;
  const f = form.elements;
  const body = {name:f.name.value, headline:f.headline.value, art:f.art.value, sort_order:numberValue(f.sort_order.value) ?? 0, is_active:f.is_active.checked};
  const button = $("button[type=submit]", form);
  setBusy(button, true);
  try {
    await api(id ? "/admin/categories/" + id : "/admin/categories", {method:id ? "PUT" : "POST", body});
    modal.close();
    toast(id ? "Categoría actualizada." : "Categoría creada.");
    route();
  } catch (err) {
    setBusy(button, false);
    showFieldErrors(form, err.data.fields, err.message);
  }
}

/* ---------- Inventario ---------- */
async function renderInventory(view) {
  const {products} = await api("/admin/inventory");
  const low = products.filter(p => p.is_low_stock && p.is_active);
  view.innerHTML = head("Inventario", "Kárdex auditado: cada entrada, salida y ajuste queda registrado con su motivo y responsable.") +
    '<div class="grid">' +
    (low.length ? '<article class="card"><div class="cardHead"><h2>' + low.length + (low.length === 1 ? " producto necesita" : " productos necesitan") + ' reposición</h2></div><ul class="list">' +
      low.map(p => '<li><span><span class="cellMain">' + esc(p.name) + '</span><span class="cellSub">Stock ' + p.stock + " · mínimo " + p.min_stock_alert + '</span></span><button class="btn primary small" data-adjust="' + p.id + '" data-name="' + esc(p.name) + '" data-stock="' + p.stock + '">Registrar entrada</button></li>').join("") +
      "</ul></article>" : "") +
    '<article class="card flush"><div class="tableWrap"><table><thead><tr><th scope="col">Producto</th><th scope="col" class="right">Stock</th><th scope="col" class="right">Mínimo</th><th scope="col">Estado</th><th scope="col" class="right"><span class="sr">Acciones</span></th></tr></thead><tbody>' +
      products.map(p => '<tr><td><span class="cellMain">' + esc(p.name) + '</span><span class="cellSub">' + esc(p.sku) + " · " + esc(p.category || "") + '</span></td><td class="right">' + p.stock + '</td><td class="right">' + p.min_stock_alert + "</td>" +
        "<td>" + (p.stock === 0 ? badge("bad", ICON.x, "Agotado") : p.is_low_stock ? badge("warn", ICON.alert, "Bajo") : badge("ok", ICON.check, "Suficiente")) + "</td>" +
        '<td><div class="rowActions"><button class="btn secondary small" data-adjust="' + p.id + '" data-name="' + esc(p.name) + '" data-stock="' + p.stock + '">Ajustar</button><button class="btn secondary small" data-kardex="' + p.id + '">Kárdex</button></div></td></tr>').join("") +
    "</tbody></table></div></article></div>";
}
function openAdjust(id, name, stock) {
  const types = state.meta.movement_types.map(m => ({value:m.code, label:m.label}));
  openModal(
    '<form data-form="adjust" data-id="' + id + '" novalidate>' +
    '<div class="sheetHead"><div><h2 id="modalTitle">Movimiento de inventario</h2><span class="muted">' + esc(name) + " · stock actual " + esc(stock) + "</span></div>" + closeButton + "</div>" +
    '<div class="sheetBody"><div class="formGrid">' +
      choices("movement_type", "Tipo de movimiento", types, "PURCHASE_ENTRY") +
      field("quantity", "Cantidad", "", 'required inputmode="numeric" autocomplete="off"') +
      field("reason", "Motivo", "", 'required minlength="5" maxlength="255" autocomplete="off" placeholder="Factura de proveedor 1234"') +
    '</div><p class="formError" role="alert"></p><div class="sheetActions"><button class="btn secondary" type="button" data-close>Cancelar</button><button class="btn primary" type="submit">Registrar movimiento</button></div></div></form>');
}
async function submitAdjust(form) {
  const f = form.elements;
  const body = {movement_type:f.movement_type.value, quantity:numberValue(f.quantity.value), reason:f.reason.value};
  const button = $("button[type=submit]", form);
  setBusy(button, true);
  try {
    const {product} = await api("/admin/inventory/" + form.dataset.id + "/adjust", {method:"POST", body});
    modal.close();
    toast("Stock de " + product.name + ": " + product.stock + " unidades.");
    route();
  } catch (err) {
    setBusy(button, false);
    showFieldErrors(form, err.data.fields, err.message);
  }
}
async function openKardex(id) {
  const {product, movements} = await api("/admin/inventory/" + id + "/movements");
  openModal(
    '<div class="sheetHead"><div><h2 id="modalTitle">Kárdex</h2><span class="muted">' + esc(product.name) + " · " + esc(product.sku) + " · stock " + product.stock + "</span></div>" + closeButton + "</div>" +
    (movements.length
      ? '<div class="tableWrap"><table><thead><tr><th scope="col">Fecha</th><th scope="col">Movimiento</th><th scope="col" class="right">Cantidad</th><th scope="col" class="right">Stock</th><th scope="col">Motivo</th></tr></thead><tbody>' +
        movements.map(m => {
          const sign = m.new_stock >= m.previous_stock ? "+" : "−";
          return "<tr><td>" + fmtDate(m.created_at) + '</td><td><span class="cellMain">' + esc(m.type_label) + '</span><span class="cellSub">' + esc(m.user || "Tienda en línea") + '</span></td><td class="right">' + sign + m.quantity + '</td><td class="right">' + m.previous_stock + " → " + m.new_stock + "</td><td>" + esc(m.reason) + (m.reference ? '<span class="cellSub">' + esc(m.reference) + "</span>" : "") + "</td></tr>";
        }).join("") + "</tbody></table></div>"
      : '<div class="sheetBody">' + emptyState("Sin movimientos", "Este producto todavía no tiene registros.") + "</div>"));
}

/* ---------- Ajustes ---------- */
async function renderSettings(view) {
  const {settings:s} = await api("/admin/settings");
  view.innerHTML = head("Ajustes", "Estos datos identifican al responsable del tratamiento en los textos legales y definen el envío.") +
    '<form class="card" data-form="settings" novalidate><div class="formGrid">' +
      field("store_name", "Nombre comercial", s.store_name, 'required maxlength="150"') +
      field("legal_name", "Razón social", s.legal_name, 'required maxlength="150"') +
      field("nit", "NIT", s.nit, 'maxlength="30" placeholder="900123456-7"') +
      field("phone", "Teléfono", s.phone, 'required maxlength="50" inputmode="tel"') +
      '<div class="full">' + field("email", "Correo para datos personales y soporte", s.email, 'required type="email" maxlength="254"') + "</div>" +
      '<div class="full">' + field("address", "Dirección del domicilio", s.address, 'required maxlength="255"') + "</div>" +
      '<div class="full">' + field("business_hours", "Horario de atención", s.business_hours, 'required maxlength="255"') + "</div>" +
      field("shipping_cost", "Costo de envío", s.shipping_cost, 'required inputmode="numeric"') +
      field("free_shipping_threshold", "Envío gratis desde (vacío para desactivar)", s.free_shipping_threshold ?? "", 'inputmode="numeric"') +
      '<p class="hint full">Al guardar, la tienda y las políticas legales se actualizan de inmediato.</p>' +
    '</div><p class="formError" role="alert"></p><div class="sheetActions"><button class="btn primary" type="submit">Guardar ajustes</button></div></form>';
}
async function submitSettings(form) {
  const f = form.elements;
  const body = {
    store_name:f.store_name.value, legal_name:f.legal_name.value, nit:f.nit.value, phone:f.phone.value, email:f.email.value,
    address:f.address.value, business_hours:f.business_hours.value,
    shipping_cost:numberValue(f.shipping_cost.value), free_shipping_threshold:numberValue(f.free_shipping_threshold.value)
  };
  const button = $("button[type=submit]", form);
  clearFieldErrors(form);
  setBusy(button, true);
  try {
    await api("/admin/settings", {method:"PUT", body});
    toast("Ajustes guardados.");
  } catch (err) {
    showFieldErrors(form, err.data.fields, err.message);
  } finally {
    setBusy(button, false);
  }
}

/* ---------- Eventos globales ---------- */
document.addEventListener("click", async event => {
  const el = event.target.closest("button, a");
  if (!el || el.disabled) return;
  const d = el.dataset;
  try {
    if (el.getAttribute("role") === "tab") {
      if (location.hash.slice(1) === d.view) route(); else location.hash = d.view;
    } else if ("close" in d) {
      el.closest("dialog").close();
    } else if ("reload" in d) {
      route();
    } else if ("order" in d) {
      await openOrder(d.order);
    } else if ("setStatus" in d) {
      await changeStatus(d.orderId, d.setStatus, el);
    } else if ("cancelOrder" in d) {
      const ok = await confirmAction({title:"¿Cancelar el pedido " + d.number + "?",
        text:"El stock de sus productos vuelve al inventario y queda registrado en el kárdex. Un pedido cancelado no se puede reactivar.",
        action:"Cancelar pedido"});
      if (ok) await changeStatus(d.cancelOrder, "CANCELLED", el);
    } else if ("orderStatus" in d) {
      orderFilter.status = d.orderStatus; orderFilter.page = 1;
      $$("[data-order-status]").forEach(c => c.setAttribute("aria-pressed", String(c === el)));
      await loadOrders();
    } else if ("page" in d) {
      orderFilter.page = Number(d.page); await loadOrders();
    } else if ("customerStatus" in d) {
      customerFilter.status = d.customerStatus; customerFilter.page = 1;
      $$("[data-customer-status]").forEach(c => c.setAttribute("aria-pressed", String(c === el)));
      await loadCustomers();
    } else if ("customerPage" in d) {
      customerFilter.page = Number(d.customerPage); await loadCustomers();
    } else if ("productStatus" in d) {
      productFilter.status = d.productStatus;
      $$("[data-product-status]").forEach(c => c.setAttribute("aria-pressed", String(c === el)));
      await loadProducts();
    } else if ("newProduct" in d) {
      await openProductForm(null);
    } else if ("editProduct" in d) {
      await openProductForm(d.editProduct);
    } else if ("toggleProduct" in d) {
      const {product} = await api("/admin/products/" + d.toggleProduct + "/toggle", {method:"POST"});
      toast(product.is_active ? product.name + " ya es visible en la tienda." : product.name + " se ocultó de la tienda.");
      await loadProducts();
    } else if ("deleteProduct" in d) {
      const ok = await confirmAction({title:"¿Eliminar " + d.name + "?",
        text:"Se borran el producto y su kárdex. Si ya aparece en pedidos no se puede eliminar; en ese caso ocúltalo.",
        action:"Eliminar producto"});
      if (ok) {
        await api("/admin/products/" + d.deleteProduct, {method:"DELETE"});
        toast("Producto eliminado.");
        await loadProducts();
      }
    } else if ("newCategory" in d) {
      openCategoryForm(null);
    } else if ("editCategory" in d) {
      openCategoryForm(d.editCategory);
    } else if ("toggleCategory" in d) {
      await api("/admin/categories/" + d.toggleCategory + "/toggle", {method:"POST"});
      toast("Categoría actualizada.");
      route();
    } else if ("adjust" in d) {
      openAdjust(d.adjust, d.name, d.stock);
    } else if ("kardex" in d) {
      await openKardex(d.kardex);
    }
  } catch (err) {
    if (err.status !== 401) toast(err.message);
  }
});
document.addEventListener("submit", event => {
  const form = event.target;
  const kind = form.dataset.form;
  if (!kind) return;
  event.preventDefault();
  clearFieldErrors(form);
  ({product:submitProduct, category:submitCategory, adjust:submitAdjust, settings:submitSettings})[kind](form);
});

/* ---------- Sesion ---------- */
function showLogin(message, signedInWithoutRole = false) {
  state.me = null;
  if (modal.open) modal.close();
  $("#tabs").hidden = true;
  $("#view").hidden = true;
  $("#view").innerHTML = "";
  $("#logout").hidden = !signedInWithoutRole;
  $("#loginView").hidden = false;
  $("#loginError").textContent = message || "";
  $("#loginForm").elements.email.focus();
}
async function start(user) {
  state.me = user;
  state.meta = await api("/admin/meta");
  $("#loginView").hidden = true;
  $("#tabs").hidden = false;
  $("#logout").hidden = false;
  await route();
  $("#view").focus({preventScroll:true});
}
$("#loginForm").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.target;
  clearFieldErrors(form);
  const email = form.elements.email.value.trim();
  const password = form.elements.password.value;
  const missing = {};
  if (!email) missing.email = "Escribe tu correo.";
  if (!password) missing.password = "Escribe tu contraseña.";
  if (Object.keys(missing).length) { showFieldErrors(form, missing); return; }
  const button = $("button[type=submit]", form);
  setBusy(button, true, "Entrando…");
  try {
    const res = await api("/auth/login", {method:"POST", body:{email, password}});
    csrf = res.csrf;
    form.reset();
    if (res.user.role !== "admin") { location.assign("/"); return; }
    await start(res.user);
  } catch (err) {
    $("#loginError").textContent = err.message;
  } finally {
    setBusy(button, false);
  }
});
$("#logout").addEventListener("click", async () => {
  try {
    csrf = (await api("/auth/logout", {method:"POST"})).csrf;
  } catch (err) {
    toast(err.message);
    return;
  }
  showLogin("Cerraste sesión.");
});
async function boot() {
  try {
    const me = await api("/auth/me");
    csrf = me.csrf;
    if (me.user && me.user.role === "admin") await start(me.user);
    else showLogin(me.user ? "Tu cuenta no tiene permisos de administrador." : "", Boolean(me.user));
  } catch {
    showLogin("No pudimos conectar con el servidor. Verifica que el backend esté en ejecución.");
  }
}
boot();
