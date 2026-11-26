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
  dot:'<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="2.5"/></svg>',
  shield:'<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1.8 13 3.6v4c0 3-2.2 5.3-5 6.6-2.8-1.3-5-3.6-5-6.6v-4z"/></svg>',
  briefcase:'<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2" y="5" width="12" height="8.5" rx="1.5"/><path d="M5.5 5V3.5h5V5M2 9h12"/></svg>',
  person:'<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="5.5" r="2.6"/><path d="M3 14a5 5 0 0 1 10 0"/></svg>',
  store:'<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 6.5 3 3h10l1 3.5M3 6.5V13h10V6.5M6.5 13V9.5h3V13"/></svg>',
  globe:'<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6"/><path d="M2 8h12M8 2c1.8 1.8 1.8 10.2 0 12M8 2c-1.8 1.8-1.8 10.2 0 12"/></svg>',
  phone:'<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="4.5" y="1.5" width="7" height="13" rx="1.5"/><path d="M7 12.2h2"/></svg>',
  home:'<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 7.5 8 3l5.5 4.5M4 6.5V13h8V6.5"/></svg>'
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
async function api(path, {method = "GET", body, signal} = {}, retry = true) {
  const options = {method, signal, credentials:"same-origin", headers:{Accept:"application/json"}};
  if (method !== "GET") {
    if (!csrf) csrf = (await (await fetch("/api/auth/csrf", {signal, credentials:"same-origin"})).json()).csrf;
    options.headers["X-CSRF-Token"] = csrf;
    if (body instanceof FormData) {
      options.body = body; // multipart: el navegador pone el Content-Type con su boundary
    } else {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body || {});
    }
  }
  let res;
  try { res = await fetch("/api" + path, options); }
  catch { throw Object.assign(new Error(signal?.aborted ? "El servidor tardó demasiado. Vuelve a consultar la pestaña para ver el último resultado." : "Sin conexión con el servidor."), {status:0, data:{}}); }
  const data = await res.json().catch(() => ({}));
  if (res.status === 403 && data.error === "csrf" && retry) {
    csrf = null;
    return api(path, {method, body, signal}, false);
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
// La decision se resuelve en el mismo clic o tecla; no espera al evento "close", que algunos
// navegadores entregan solo al pintar el siguiente cuadro (pestanas en segundo plano).
function settleConfirm(value) {
  if (!confirmResolve) return;
  const resolve = confirmResolve;
  confirmResolve = null;
  resolve(value);
}
confirmDialog.addEventListener("click", e => {
  const b = e.target.closest("[data-confirm]");
  if (!b) return;
  settleConfirm(b.dataset.confirm === "yes");
  confirmDialog.close(b.dataset.confirm);
});
confirmDialog.addEventListener("cancel", () => { confirmDialog.returnValue = "no"; settleConfirm(false); });
confirmDialog.addEventListener("close", () => settleConfirm(confirmDialog.returnValue === "yes"));

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
const VIEWS = {resumen:renderDashboard, pedidos:renderOrders, clientes:renderCustomers, usuarios:renderUsers, productos:renderProducts,
  categorias:renderCategories, inventario:renderInventory, ajustes:renderSettings, benchmarks:renderBenchmarks, integridad:renderIntegrity};

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
const orderFilter = {status:"", q:"", page:1, channel:""};
function ordersTable(rows) {
  return '<table><thead><tr><th scope="col">Pedido</th><th scope="col">Cliente</th><th scope="col">Canal</th><th scope="col">Estado</th><th scope="col" class="right">Total</th></tr></thead><tbody>' +
    rows.map(o => {
      const employee = o.employee_id ? staffName(o.employee_id) : "";
      return '<tr><td><button class="linkBtn" data-order="' + o.id + '">' + esc(o.order_number) + '</button><span class="cellSub">' + fmtDate(o.created_at) + "</span></td>" +
        '<td><span class="cellMain">' + esc(o.customer_name) + '</span><span class="cellSub">' + esc(o.city || "Sin envío") + " · " + o.item_count + " u." +
        (employee ? " · Atendió " + esc(employee) : "") + "</span></td>" +
        "<td>" + channelBadge(o.channel) + "</td>" +
        "<td>" + statusBadge(o.status, o.status_label) + '</td><td class="right">' + money(o.total) + "</td></tr>";
    }).join("") +
    "</tbody></table>";
}
async function renderOrders(view) {
  const chips = [["", "Todos"], ...state.meta.statuses.map(s => [s.code, s.label])];
  try { await loadUsersCache(); } catch {} // solo para mostrar quien atendio; sin esto la lista igual carga
  view.innerHTML = head("Pedidos", "Confirma, prepara y despacha. Cancelar un pedido devuelve su stock al inventario.",
      '<button class="btn primary" data-new-order>Nuevo pedido</button>') +
    '<div class="toolbar"><label class="field search"><span class="sr">Buscar pedidos</span><input type="search" id="orderSearch" placeholder="Buscar por número, cliente o correo" value="' + esc(orderFilter.q) + '"></label></div>' +
    '<div class="chips" role="group" aria-label="Filtrar por estado">' +
    chips.map(([code, label]) => '<button class="chip" data-order-status="' + code + '" aria-pressed="' + (code === orderFilter.status) + '">' + esc(label) + "</button>").join("") +
    '</div><div class="segmentedFilter" role="group" aria-label="Filtrar por canal">' +
    [["", "Todos los canales"], ...CHANNEL_CHOICES.map(c => [c.value, c.label])].map(([code, label]) =>
      '<button class="segment" data-order-channel="' + code + '" aria-pressed="' + (code === orderFilter.channel) + '">' + esc(label) + "</button>").join("") +
    '</div><div class="card flush" id="ordersBox"></div>';
  $("#orderSearch").addEventListener("input", debounce(e => { orderFilter.q = e.target.value.trim(); orderFilter.page = 1; loadOrders(); }, 250));
  await loadOrders();
}
async function loadOrders() {
  const box = $("#ordersBox");
  if (!box) return;
  const params = new URLSearchParams({page:orderFilter.page});
  if (orderFilter.status) params.set("status", orderFilter.status);
  if (orderFilter.channel) params.set("channel", orderFilter.channel);
  if (orderFilter.q) params.set("q", orderFilter.q);
  box.setAttribute("aria-busy", "true");
  const d = await api("/admin/orders?" + params);
  box.removeAttribute("aria-busy");
  if (!d.orders.length) {
    const filtered = orderFilter.q || orderFilter.status || orderFilter.channel;
    box.innerHTML = emptyState(filtered ? "Ningún pedido coincide" : "Todavía no hay pedidos",
      filtered ? "Prueba con otro estado, canal o término de búsqueda." : "Los pedidos de la tienda aparecerán aquí al instante.");
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

/* ---------- Usuarios y roles ----------
   Contrato (backend de Codex): GET /admin/users?page (25 por pagina), POST /admin/users
   {name, email, password, role, is_active}, PATCH /admin/users/{id} {role?, is_active?}.
   Cambiar rol o estado revoca las sesiones; el admin autenticado no puede quitarse el rol. */
const ROLE_INFO = {
  admin:["info", ICON.shield, "Administrador"],
  employee:["", ICON.briefcase, "Empleado"],
  customer:["", ICON.person, "Cliente"]
};
const roleBadge = role => { const [tone, icon, label] = ROLE_INFO[role] || ["", ICON.dot, role]; return badge(tone, icon, label); };
const CHANNEL_INFO = {presencial:[ICON.store, "Presencial"], web:[ICON.globe, "Web"], app:[ICON.phone, "App"], domicilio:[ICON.home, "Domicilio"]};
const channelBadge = channel => { const [icon, label] = CHANNEL_INFO[channel] || CHANNEL_INFO.web; return badge("", icon, label); };
const userFilter = {q:"", role:"all"};
let usersCache = null;
async function loadUsersCache(force = false) {
  if (usersCache && !force) return usersCache;
  const all = [];
  let page = 1, pages = 1;
  do {
    const d = await api("/admin/users?page=" + page);
    all.push(...d.users);
    pages = d.pages;
    page += 1;
  } while (page <= pages && page <= 40);
  usersCache = all;
  return all;
}
const staffName = id => (usersCache || []).find(u => u.id === id)?.name || "empleado #" + id;
const isMe = u => state.me && u.email === state.me.email;
function accountState(u) {
  if (u.email_verification_pending) return badge("warn", ICON.clock, "Sin verificar");
  return u.is_active ? badge("ok", ICON.check, "Activa") : badge("", ICON.dot, "Inactiva");
}
async function renderUsers(view) {
  await loadUsersCache(true);
  view.innerHTML = head("Usuarios", "Equipo y clientes. Cambiar el rol o desactivar una cuenta cierra sus sesiones abiertas.",
      '<button class="btn primary" data-new-user>Nuevo usuario</button>') +
    '<div class="toolbar"><label class="field search"><span class="sr">Buscar usuarios</span><input type="search" id="userSearch" placeholder="Buscar por nombre o correo" value="' + esc(userFilter.q) + '" autocomplete="off"></label></div>' +
    '<div class="chips" role="group" aria-label="Filtrar por rol" id="userChips"></div><div class="card flush" id="usersBox"></div>';
  $("#userSearch").addEventListener("input", debounce(e => { userFilter.q = e.target.value.trim(); drawUsers(); }, 120));
  drawUsers();
}
function drawUsers() {
  const box = $("#usersBox");
  if (!box) return;
  const all = usersCache || [];
  const counts = {all:all.length};
  for (const role of Object.keys(ROLE_INFO)) counts[role] = all.filter(u => u.role === role).length;
  $("#userChips").innerHTML = [["all", "Todos"], ["admin", "Administradores"], ["employee", "Empleados"], ["customer", "Clientes"]]
    .map(([v, l]) => '<button class="chip" data-user-role="' + v + '" aria-pressed="' + (v === userFilter.role) + '">' + l + '<span class="count">' + counts[v] + "</span></button>").join("");
  const q = normalize(userFilter.q);
  const list = all.filter(u => (userFilter.role === "all" || u.role === userFilter.role) && (!q || normalize(u.name + " " + u.email).includes(q)));
  if (!list.length) {
    box.innerHTML = emptyState("Ningún usuario coincide", "Prueba con otro nombre, correo o rol.");
    return;
  }
  box.innerHTML = '<div class="tableWrap"><table><thead><tr><th scope="col">Usuario</th><th scope="col">Rol</th><th scope="col">Estado</th><th scope="col">Registro</th><th scope="col" class="right"><span class="sr">Acciones</span></th></tr></thead><tbody>' +
    list.map(u => {
      const me = isMe(u);
      const toggleBtn = me ? ""
        : u.is_active
          ? '<button class="btn dangerGhost small" data-user-toggle="' + u.id + '">Desactivar</button>'
          : '<button class="btn secondary small" data-user-toggle="' + u.id + '">Activar</button>';
      return '<tr><td><div class="customerHead"><span class="initial" aria-hidden="true">' + esc((u.name.trim()[0] || "?").toUpperCase()) + "</span>" +
        '<span><span class="cellMain">' + esc(u.name) + (me ? ' <span class="muted">(tú)</span>' : "") + '</span><span class="cellSub">' + esc(u.email) + "</span></span></div></td>" +
        "<td>" + roleBadge(u.role) + "</td><td>" + accountState(u) + "</td>" +
        "<td>" + fmtDate(u.created_at) + '<span class="cellSub">' + (u.last_login_at ? "Último acceso " + fmtDate(u.last_login_at) : "Aún no inicia sesión") + "</span></td>" +
        '<td><div class="rowActions"><button class="btn secondary small" data-edit-user="' + u.id + '">Editar</button>' + toggleBtn + "</div></td></tr>";
    }).join("") + '</tbody></table></div><div class="pager"><span>' + list.length + " de " + all.length + (all.length === 1 ? " cuenta" : " cuentas") + "</span></div>";
}
const ROLE_CHOICES = [{value:"admin", label:"Administrador"}, {value:"employee", label:"Empleado"}, {value:"customer", label:"Cliente"}];
function openUserForm(id) {
  const user = id ? (usersCache || []).find(u => u.id === Number(id)) : null;
  const me = user && isMe(user);
  openModal(
    '<form data-form="' + (user ? "userEdit" : "user") + '" data-id="' + (user ? user.id : "") + '" novalidate>' +
    '<div class="sheetHead"><h2 id="modalTitle">' + (user ? "Editar usuario" : "Nuevo usuario") + "</h2>" + closeButton + "</div>" +
    '<div class="sheetBody"><div class="formGrid">' +
      (user
        ? '<dl class="facts full">' + fact("Nombre", user.name) + fact("Correo", user.email) + "</dl>"
        : '<div class="full">' + field("name", "Nombre completo", "", 'required minlength="3" maxlength="150" autocomplete="off"') + "</div>" +
          field("email", "Correo electrónico", "", 'required type="email" maxlength="254" autocomplete="off"') +
          '<div>' + field("password", "Contraseña inicial", "", 'required type="password" minlength="12" maxlength="128" autocomplete="new-password"') +
          '<p class="hint">Mínimo 12 caracteres, con letras y números. Compártela por un canal seguro.</p></div>') +
      choices("role", "Rol", ROLE_CHOICES, user ? user.role : "employee") +
      toggle("is_active", "Cuenta activa", user ? user.is_active : true) +
      (me ? '<p class="hint full">Es tu cuenta: conserva el rol de administrador y queda activa.</p>' : "") +
    '</div><p class="formError" role="alert"></p><div class="sheetActions"><button class="btn secondary" type="button" data-close>Cancelar</button><button class="btn primary" type="submit"' + (me ? " disabled" : "") + ">" + (user ? "Guardar cambios" : "Crear usuario") + "</button></div></div></form>");
  if (me) $$("#modalBody input").forEach(input => { input.disabled = true; });
}
function mergeUser(user) {
  const i = (usersCache || []).findIndex(u => u.id === user.id);
  if (i >= 0) usersCache[i] = user; else (usersCache = usersCache || []).push(user);
}
async function submitUser(form) {
  const f = form.elements;
  const body = {name:f.name.value.trim(), email:f.email.value.trim().toLowerCase(), password:f.password.value, role:f.role.value, is_active:f.is_active.checked};
  const button = $("button[type=submit]", form);
  setBusy(button, true, "Creando…");
  try {
    const {user} = await api("/admin/users", {method:"POST", body});
    mergeUser(user);
    modal.close();
    toast("Usuario creado: " + user.name + ".");
    drawUsers();
  } catch (err) {
    setBusy(button, false);
    showFieldErrors(form, err.data.error === "email_taken" ? {email:err.message} : err.data.fields, err.message);
  }
}
async function patchUser(id, changes, button) {
  const user = (usersCache || []).find(u => u.id === Number(id));
  if (changes.is_active === false && user && user.is_active) {
    const ok = await confirmAction({title:"¿Desactivar a " + user.name + "?",
      text:"Se cerrarán sus sesiones y no podrá iniciar sesión hasta que reactives la cuenta. Sus pedidos y facturas se conservan.",
      action:"Desactivar cuenta"});
    if (!ok) return false;
  }
  setBusy(button, true, "Guardando…");
  try {
    const {user: updated} = await api("/admin/users/" + id, {method:"PATCH", body:changes});
    mergeUser(updated);
    toast(updated.is_active ? "Cambios guardados. Las sesiones de " + updated.name + " se cerraron." : updated.name + " quedó desactivado.");
    drawUsers();
    return true;
  } finally {
    if (button.isConnected) setBusy(button, false);
  }
}
async function submitUserEdit(form) {
  const user = (usersCache || []).find(u => u.id === Number(form.dataset.id));
  const changes = {};
  if (form.elements.role.value !== user.role) changes.role = form.elements.role.value;
  if (form.elements.is_active.checked !== user.is_active) changes.is_active = form.elements.is_active.checked;
  if (!Object.keys(changes).length) { modal.close(); return; }
  try {
    if (await patchUser(user.id, changes, $("button[type=submit]", form))) modal.close();
  } catch (err) {
    showFieldErrors(form, err.data.fields, err.message);
  }
}

/* ---------- Nuevo pedido con canal ----------
   POST /api/orders (el mismo checkout de la tienda): channel presencial|web|app|domicilio,
   customer_id opcional; presencial no exige direccion ni cobra envio. El operador queda
   registrado por la sesion. Los dos consentimientos son obligatorios tambien aqui. */
const CHANNEL_CHOICES = [{value:"presencial", label:"Presencial"}, {value:"web", label:"Web"}, {value:"app", label:"App"}, {value:"domicilio", label:"Domicilio"}];
const DOC_CHOICES = [{value:"CC", label:"CC"}, {value:"CE", label:"CE"}, {value:"NIT", label:"NIT"}, {value:"PAS", label:"Pasaporte"}];
const draft = {lines:new Map(), products:[], customers:[], key:null};
async function openNewOrder() {
  const [{products}, {customers}] = await Promise.all([api("/admin/products?status=active"), api("/admin/customers?status=verified")]);
  draft.products = products.filter(p => p.is_active && p.stock > 0);
  draft.customers = customers;
  draft.lines = new Map();
  draft.key = crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2);
  openModal(
    '<form data-form="order" novalidate>' +
    '<div class="sheetHead"><h2 id="modalTitle">Nuevo pedido</h2>' + closeButton + "</div>" +
    '<div class="sheetBody"><div class="formGrid">' +
      choices("channel", "Canal", CHANNEL_CHOICES, "presencial") +
      '<div class="full">' + listbox({name:"customer_id", label:"Cliente registrado (opcional)", value:"",
        options:[{value:"", label:"Sin cuenta"}, ...customers.map(c => ({value:c.id, label:c.name + " · " + c.email}))]}) + "</div>" +
      '<div class="full">' + field("name", "Nombre completo", "", 'required minlength="3" maxlength="150" autocomplete="off"') + "</div>" +
      field("email", "Correo electrónico", "", 'required type="email" maxlength="254" autocomplete="off"') +
      field("phone", "Celular", "", 'required inputmode="tel" maxlength="20" autocomplete="off"') +
      choices("doc_type", "Documento", DOC_CHOICES, "CC") +
      '<div class="full">' + field("doc_number", "Número de documento", "", 'required maxlength="20" autocomplete="off"') + "</div>" +
      '<fieldset class="full choiceSet orderAddress" hidden><legend>Dirección de entrega</legend><div class="formGrid">' +
        field("department", "Departamento", "", 'maxlength="100"') + field("city", "Ciudad", "", 'maxlength="100"') +
        field("neighborhood", "Barrio", "", 'maxlength="100"') + field("street_address", "Dirección", "", 'maxlength="255"') +
      "</div></fieldset>" +
      '<fieldset class="full choiceSet"><legend>Productos</legend><div class="lineAdd">' +
        listbox({name:"line_product", label:"Producto", value:"", placeholder:"Elige un producto",
          options:draft.products.map(p => ({value:p.id, label:p.name + " · " + money(p.price) + " · " + p.stock + " u."}))}) +
        field("line_qty", "Cantidad", "1", 'inputmode="numeric" maxlength="3" autocomplete="off"') +
        '<button class="btn secondary" type="button" data-add-line>Agregar</button></div>' +
        '<ul class="list orderLines" id="orderLines"></ul><input type="hidden" name="items"></fieldset>' +
      '<label class="check full"><input type="checkbox" name="accept_terms"><span>El cliente acepta los Términos y condiciones y la Política de devoluciones.</span></label>' +
      '<label class="check full"><input type="checkbox" name="accept_privacy"><span>El cliente autoriza el tratamiento de sus datos personales (Ley 1581 de 2012).</span></label>' +
    '</div><p class="formError" role="alert"></p><div class="sheetActions"><button class="btn secondary" type="button" data-close>Cancelar</button><button class="btn primary" type="submit">Registrar pedido</button></div></div></form>');
  drawLines();
}
function drawLines() {
  const ul = $("#orderLines");
  if (!ul) return;
  let total = 0;
  ul.innerHTML = [...draft.lines.entries()].map(([id, qty]) => {
    const p = draft.products.find(x => x.id === id);
    total += p.price * qty;
    return '<li><span><span class="cellMain">' + esc(p.name) + '</span><span class="cellSub">' + qty + " × " + money(p.price) + '</span></span><span class="lineEnd"><span class="num">' + money(p.price * qty) + '</span><button class="btn dangerGhost small" type="button" data-remove-line="' + id + '" aria-label="Quitar ' + esc(p.name) + '">Quitar</button></span></li>';
  }).join("") + (draft.lines.size ? '<li><strong>Subtotal</strong><strong class="num">' + money(total) + "</strong></li>" : '<li class="muted">Aún no agregas productos.</li>');
}
function addLine(form) {
  const id = Number(form.elements.line_product.value);
  const qty = Number(form.elements.line_qty.value);
  const p = draft.products.find(x => x.id === id);
  const errors = {};
  if (!p) errors.line_product = "Elige un producto.";
  if (!Number.isInteger(qty) || qty < 1) errors.line_qty = "Escribe una cantidad válida.";
  else if (p && (draft.lines.get(id) || 0) + qty > Math.min(p.stock, 99)) errors.line_qty = "Solo hay " + Math.min(p.stock, 99) + " unidades disponibles.";
  clearFieldErrors(form);
  if (Object.keys(errors).length) { showFieldErrors(form, errors); return; }
  draft.lines.set(id, (draft.lines.get(id) || 0) + qty);
  form.elements.line_qty.value = "1";
  drawLines();
}
async function submitOrder(form) {
  const f = form.elements;
  const channel = f.channel.value;
  const text = name => (f[name]?.value || "").trim();
  const body = {
    channel, name:text("name"), email:text("email").toLowerCase(), phone:text("phone"), doc_type:f.doc_type.value, doc_number:text("doc_number"),
    accept_terms:f.accept_terms.checked, accept_privacy:f.accept_privacy.checked, idempotency_key:draft.key,
    items:[...draft.lines.entries()].map(([product_id, quantity]) => ({product_id, quantity}))
  };
  if (f.customer_id.value) body.customer_id = Number(f.customer_id.value);
  if (channel !== "presencial") for (const k of ["department", "city", "neighborhood", "street_address"]) body[k] = text(k);
  const missing = {};
  if (!body.items.length) missing.items = "Agrega al menos un producto.";
  if (!body.accept_terms) missing.accept_terms = "El cliente debe aceptar los Términos.";
  if (!body.accept_privacy) missing.accept_privacy = "El cliente debe autorizar el tratamiento de sus datos.";
  if (Object.keys(missing).length) { showFieldErrors(form, missing, missing.items); return; }
  const button = $("button[type=submit]", form);
  setBusy(button, true, "Registrando…");
  try {
    const {order} = await api("/orders", {method:"POST", body});
    modal.close();
    toast("Pedido " + order.order_number + " registrado (" + (CHANNEL_INFO[order.channel] || CHANNEL_INFO.web)[1].toLowerCase() + ").");
    if (currentView() === "pedidos") await loadOrders();
    if (order.id) await openOrder(order.id);
  } catch (err) {
    setBusy(button, false);
    showFieldErrors(form, err.data.fields, err.message);
  }
}
// Canal presencial: sin direccion. El cliente registrado rellena nombre y correo.
$("#modalBody").addEventListener("change", e => {
  const form = e.target.form;
  if (!form || form.dataset.form !== "order") return;
  if (e.target.name === "channel") $(".orderAddress", form).hidden = e.target.value === "presencial";
  if (e.target.name === "customer_id") {
    const c = draft.customers.find(x => String(x.id) === e.target.value);
    if (c) { form.elements.name.value = c.name; form.elements.email.value = c.email; }
  }
});

const statusLabel = code => (state.meta.statuses.find(s => s.code === code) || {label:code}).label;
async function openOrder(id) {
  const [{order:o}, billing] = await Promise.all([
    api("/admin/orders/" + id),
    api("/orders/" + id + "/invoice").catch(() => null) // sin permiso o sin red: el pedido igual se muestra
  ]);
  const forward = o.allowed_transitions.filter(s => s !== "CANCELLED");
  const canCancel = o.allowed_transitions.includes("CANCELLED");
  const items = o.items.map(i => '<li><span><span class="cellMain">' + esc(i.name) + '</span><span class="cellSub">' + esc(i.sku) + " · " + i.quantity + " × " + money(i.unit_price) + '</span></span><span class="num">' + money(i.subtotal) + "</span></li>").join("");
  openModal(
    '<div class="sheetHead"><div><h2 id="modalTitle">' + esc(o.order_number) + '</h2><span class="muted">' + fmtDate(o.created_at) + "</span></div>" + closeButton + "</div>" +
    '<div class="sheetBody">' +
      '<div class="badgeRow">' + statusBadge(o.status, o.status_label) + (o.channel ? channelBadge(o.channel) : "") + "</div>" +
      invoiceSummary(o, billing) +
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
/* ---------- Factura y pagos ----------
   Contrato (backend de Codex):
   GET  /api/orders/{id}/invoice  -> {invoice | null, payments: [...], balance: numero COP}
   POST /api/orders/{id}/invoice  {discount_amount?: "1000.00"} -> {invoice, created} (idempotente)
   POST /api/invoices/{id}/payments  JSON {payment_method, amount} o FormData con receipt (PDF/PNG/JPEG, 5 MiB)
   balance solo descuenta pagos aprobados, pero al registrar el backend tambien cuenta los pendientes:
   el monto disponible para un pago nuevo es balance menos pendientes. */
const amountOf = v => Number(v) || 0; // los importes de factura llegan como "117810.00"
const METHOD_LABEL = {efectivo:"Efectivo", tarjeta:"Tarjeta", transferencia:"Transferencia", pse:"PSE", nequi:"Nequi"};
const METHOD_CHOICES = Object.entries(METHOD_LABEL).map(([value, label]) => ({value, label}));
const PAYMENT_STATUS = {pendiente:["warn", ICON.clock, "Pendiente"], aprobado:["ok", ICON.check, "Aprobado"], rechazado:["bad", ICON.x, "Rechazado"], anulado:["", ICON.dot, "Anulado"]};
const INVOICE_STATUS = {emitida:["ok", ICON.check, "Emitida"], anulada:["bad", ICON.x, "Anulada"]};
const statusPill = (map, key) => { const [tone, icon, label] = map[key] || ["", ICON.dot, key]; return badge(tone, icon, label); };
const RECEIPT_URL = /^\/api\/payments\/\d+\/receipt$/;
const RECEIPT_TYPES = {"application/pdf":"PDF", "image/png":"PNG", "image/jpeg":"JPEG"};
const RECEIPT_MAX = 5 * 1024 * 1024;
const pendingOf = payments => payments.filter(p => p.status === "pendiente").reduce((sum, p) => sum + amountOf(p.amount), 0);
const availableOf = billing => Math.max(0, amountOf(billing.balance) - pendingOf(billing.payments));
const fileSize = bytes => bytes < 1024 * 1024 ? Math.max(1, Math.round(bytes / 1024)) + " KB" : (bytes / 1024 / 1024).toFixed(1).replace(".", ",") + " MB";

function invoiceSummary(o, billing) {
  if (!billing) return "";
  const inv = billing.invoice;
  if (inv) {
    return '<section class="section"><h3>Factura</h3><div class="invoiceRow"><dl class="facts">' +
      fact("Número", "N.º " + inv.invoice_number) + fact("Total", money(amountOf(inv.total_amount))) + fact("Saldo por cobrar", money(amountOf(billing.balance))) +
      '</dl><button class="btn secondary" type="button" data-invoice-order="' + o.id + '">Ver factura</button></div></section>';
  }
  if (o.status === "CANCELLED") return '<section class="section"><h3>Factura</h3><p class="muted">Los pedidos cancelados no se facturan.</p></section>';
  return '<section class="section"><h3>Factura</h3><div class="invoiceRow"><p class="muted">Este pedido aún no tiene factura.</p>' +
    '<button class="btn secondary" type="button" data-invoice-order="' + o.id + '">Emitir factura</button></div></section>';
}

async function openInvoice(orderId) {
  const [{order:o}, billing] = await Promise.all([api("/admin/orders/" + orderId), api("/orders/" + orderId + "/invoice")]);
  if (!billing.invoice) return renderIssueForm(o);
  renderInvoice(o, billing);
}
const backToOrder = id => '<button class="btn secondary" type="button" data-back-order="' + id + '">Volver al pedido</button>';

function renderIssueForm(o) {
  const subtotal = o.items.reduce((sum, i) => sum + amountOf(i.subtotal), 0);
  openModal(
    '<form data-form="invoice" data-order-id="' + o.id + '" novalidate>' +
    '<div class="sheetHead"><div><h2 id="modalTitle">Emitir factura</h2><span class="muted">Pedido ' + esc(o.order_number) + "</span></div>" + closeButton + "</div>" +
    '<div class="sheetBody">' +
      '<section class="section"><h3>Resumen del pedido</h3><ul class="list">' +
        o.items.map(i => '<li><span><span class="cellMain">' + esc(i.name) + '</span><span class="cellSub">' + i.quantity + " × " + money(amountOf(i.unit_price)) + '</span></span><span class="num">' + money(amountOf(i.subtotal)) + "</span></li>").join("") +
        '<li><strong>Subtotal de productos</strong><strong class="num">' + money(subtotal) + "</strong></li></ul></section>" +
      '<div class="formGrid">' + field("discount_amount", "Descuento en pesos (opcional)", "", 'inputmode="numeric" autocomplete="off" placeholder="0"') +
      '<p class="hint full">El descuento se aplica al subtotal de productos. El impuesto lo calcula el servidor con la tarifa configurada y el envío se suma al final. La emisión confirma el pedido si estaba pendiente.</p></div>' +
      '<p class="formError" role="alert"></p><div class="sheetActions">' + backToOrder(o.id) + '<button class="btn primary" type="submit">Emitir factura</button></div>' +
    "</div></form>");
}
async function submitInvoice(form) {
  const orderId = form.dataset.orderId;
  const raw = numberValue(form.elements.discount_amount.value);
  if (raw !== null && (typeof raw !== "number" || raw < 0)) { showFieldErrors(form, {discount_amount:"Escribe un valor en pesos, por ejemplo 5000."}); return; }
  const body = raw ? {discount_amount:raw.toFixed(2)} : {};
  const button = $("button[type=submit]", form);
  setBusy(button, true, "Emitiendo…"); // el boton queda deshabilitado: no hay doble emision (y el backend es idempotente)
  try {
    const {invoice, created} = await api("/orders/" + orderId + "/invoice", {method:"POST", body});
    toast(created ? "Factura N.º " + invoice.invoice_number + " emitida." : "Este pedido ya tenía la factura N.º " + invoice.invoice_number + ".");
    await openInvoice(orderId);
    if (currentView() === "pedidos") loadOrders();
  } catch (err) {
    setBusy(button, false);
    const fields = err.data.error === "invalid_discount" ? {discount_amount:err.message} : err.data.fields;
    showFieldErrors(form, fields, err.message);
  }
}

function renderInvoice(o, billing) {
  const inv = billing.invoice;
  const available = availableOf(billing);
  const pending = pendingOf(billing.payments);
  const rows = [["Subtotal", amountOf(inv.subtotal)], ["Descuento", -amountOf(inv.discount_amount)], ["Impuestos", amountOf(inv.tax_amount)], ["Envío", amountOf(inv.shipping_cost)]];
  const payments = billing.payments.length
    ? '<ul class="list payments">' + billing.payments.map(p =>
        '<li><span><span class="cellMain">' + esc(METHOD_LABEL[p.payment_method] || p.payment_method) + " · " + money(amountOf(p.amount)) + "</span>" +
        '<span class="cellSub">' + fmtDate(p.paid_at || p.created_at) + "</span></span>" +
        '<span class="lineEnd">' + statusPill(PAYMENT_STATUS, p.status) +
        (p.receipt_url && RECEIPT_URL.test(p.receipt_url) ? '<a class="btn secondary small" href="' + esc(p.receipt_url) + '" download rel="noopener">Comprobante</a>' : "") +
        "</span></li>").join("") + "</ul>"
    : '<p class="muted">Aún no hay pagos registrados.</p>';
  const canPay = inv.status === "emitida" && available > 0;
  const payForm = canPay
    ? '<form data-form="payment" data-invoice-id="' + inv.id + '" data-order-id="' + o.id + '" data-available="' + available + '" novalidate class="formGrid">' +
        choices("payment_method", "Método de pago", METHOD_CHOICES, "efectivo") +
        '<div class="full">' + field("amount", "Monto en pesos", String(Math.round(available * 100) / 100), 'required inputmode="decimal" autocomplete="off"') +
        '<p class="hint">Disponible para registrar: ' + money(available) + ". Efectivo y tarjeta quedan aprobados; los demás métodos quedan pendientes de confirmar.</p></div>" +
        '<div class="full field dropField"><span class="dropLabel" id="receiptLabel">Comprobante (opcional)</span>' +
          '<label class="dropzone" id="dropzone" aria-labelledby="receiptLabel"><input type="file" name="receipt" accept="application/pdf,image/png,image/jpeg" class="sr">' +
          '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/></svg>' +
          '<span><strong>Arrastra el comprobante aquí</strong> o elige un archivo</span><span class="hint">PDF, PNG o JPEG de hasta 5 MB</span></label>' +
          '<div class="fileChip" id="fileChip" hidden><span id="fileInfo"></span><button type="button" class="btn secondary small" data-clear-receipt>Quitar</button></div></div>' +
        '<p class="formError full" role="alert"></p><div class="sheetActions full"><button class="btn primary" type="submit">Registrar pago</button></div></form>'
    : '<p class="muted">' + (inv.status !== "emitida" ? "La factura está anulada: no admite pagos."
        : pending > 0 ? "El saldo restante está en pagos pendientes de confirmar." : "La factura está pagada por completo.") + "</p>";
  openModal(
    '<div class="sheetHead"><div><h2 id="modalTitle">Factura N.º ' + esc(inv.invoice_number) + '</h2><span class="muted">' + fmtDate(inv.created_at) + " · Pedido " + esc(o.order_number) + "</span></div>" + closeButton + "</div>" +
    '<div class="sheetBody">' +
      '<div class="badgeRow">' + statusPill(INVOICE_STATUS, inv.status) + (o.channel ? channelBadge(o.channel) : "") + "</div>" +
      '<section class="section"><h3>Cliente</h3><dl class="facts">' + fact("Nombre", o.customer.name) + fact("Documento", o.customer.doc_type + " " + o.customer.doc_number) +
        (inv.employee_id ? fact("Emitió", staffName(inv.employee_id)) : "") + "</dl></section>" +
      '<section class="section"><h3>Detalle</h3><ul class="list">' +
        inv.items.map(i => '<li><span><span class="cellMain">' + esc(i.name) + '</span><span class="cellSub">' + esc(i.sku) + " · " + i.quantity + " × " + money(amountOf(i.unit_price)) + '</span></span><span class="num">' + money(amountOf(i.subtotal)) + "</span></li>").join("") +
        rows.map(([label, value]) => "<li><span>" + label + '</span><span class="num">' + (value < 0 ? "− " + money(-value) : money(value)) + "</span></li>").join("") +
        '<li class="totalRow"><strong>Total</strong><strong class="num">' + money(amountOf(inv.total_amount)) + "</strong></li></ul></section>" +
      '<section class="section"><h3>Pagos</h3><dl class="facts">' + fact("Saldo por cobrar", money(amountOf(billing.balance))) +
        (pending > 0 ? fact("Pendiente de confirmar", money(pending)) : "") + "</dl>" + payments + "</section>" +
      (inv.status === "emitida" ? '<section class="section"><h3>Registrar pago</h3>' + payForm + "</section>" : "") +
      '<div class="sheetActions">' + backToOrder(o.id) + "</div>" +
    "</div>");
  setupDropzone();
}

function receiptProblem(file) {
  if (!RECEIPT_TYPES[file.type]) return "Adjunta un archivo PDF, PNG o JPEG.";
  if (file.size > RECEIPT_MAX) return "El archivo pesa " + fileSize(file.size) + "; el máximo es 5 MB.";
  return null;
}
function showReceipt(form) {
  const file = form.elements.receipt.files[0];
  $("#fileChip").hidden = !file;
  $("#dropzone").hidden = Boolean(file);
  $("#fileInfo").textContent = file ? file.name + " · " + (RECEIPT_TYPES[file.type] || "formato no admitido") + " · " + fileSize(file.size) : "";
  $(".fieldError", form.querySelector(".dropField"))?.remove();
  if (file) {
    const problem = receiptProblem(file);
    if (problem) showFieldErrors(form, {receipt:problem});
  }
}
function setupDropzone() {
  const zone = $("#dropzone");
  if (!zone) return;
  const form = zone.closest("form");
  form.elements.receipt.addEventListener("change", () => showReceipt(form));
  ["dragenter", "dragover"].forEach(type => zone.addEventListener(type, e => { e.preventDefault(); zone.classList.add("over"); }));
  ["dragleave", "drop"].forEach(type => zone.addEventListener(type, () => zone.classList.remove("over")));
  zone.addEventListener("drop", e => {
    e.preventDefault();
    const files = e.dataTransfer?.files;
    if (!files || !files.length) return;
    const dt = new DataTransfer();
    dt.items.add(files[0]); // un solo comprobante por pago
    form.elements.receipt.files = dt.files;
    showReceipt(form);
  });
}
async function submitPayment(form) {
  const f = form.elements;
  const available = Number(form.dataset.available);
  const value = numberValue(f.amount.value);
  const file = f.receipt.files[0];
  const errors = {};
  if (typeof value !== "number" || value <= 0) errors.amount = "Escribe un monto mayor que cero.";
  else if (value > available + 0.001) errors.amount = "El monto supera lo disponible (" + money(available) + ").";
  if (file && receiptProblem(file)) errors.receipt = receiptProblem(file);
  if (Object.keys(errors).length) { showFieldErrors(form, errors); return; }
  let body = {payment_method:f.payment_method.value, amount:value.toFixed(2)};
  if (file) {
    const data = new FormData();
    data.append("payment_method", body.payment_method);
    data.append("amount", body.amount);
    data.append("receipt", file);
    body = data;
  }
  const button = $("button[type=submit]", form);
  setBusy(button, true, "Registrando…");
  try {
    const {payment} = await api("/invoices/" + form.dataset.invoiceId + "/payments", {method:"POST", body});
    toast("Pago de " + money(amountOf(payment.amount)) + " registrado: " + (PAYMENT_STATUS[payment.status] || [, , payment.status])[2].toLowerCase() + ".");
    await openInvoice(form.dataset.orderId);
  } catch (err) {
    setBusy(button, false);
    let fields = err.data.fields;
    if (err.data.error === "payment_exceeds_balance") fields = {amount:err.message};
    if (err.status === 413) fields = {receipt:"El archivo supera el máximo de 5 MB."};
    showFieldErrors(form, fields, err.message);
  }
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
    } else if ("invoiceOrder" in d) {
      setBusy(el, true, "Abriendo…");
      try { await openInvoice(d.invoiceOrder); } finally { if (el.isConnected) setBusy(el, false); }
    } else if ("backOrder" in d) {
      await openOrder(d.backOrder);
    } else if ("clearReceipt" in d) {
      const form = el.closest("form");
      form.elements.receipt.value = "";
      showReceipt(form);
      $("#dropzone").focus?.();
    } else if ("orderChannel" in d) {
      orderFilter.channel = d.orderChannel; orderFilter.page = 1;
      $$("[data-order-channel]").forEach(c => c.setAttribute("aria-pressed", String(c === el)));
      await loadOrders();
    } else if ("newUser" in d) {
      openUserForm(null);
    } else if ("editUser" in d) {
      openUserForm(d.editUser);
    } else if ("userToggle" in d) {
      const user = (usersCache || []).find(u => u.id === Number(d.userToggle));
      if (user) await patchUser(user.id, {is_active:!user.is_active}, el);
    } else if ("userRole" in d) {
      userFilter.role = d.userRole;
      drawUsers();
    } else if ("newOrder" in d) {
      await openNewOrder();
    } else if ("addLine" in d) {
      addLine(el.form);
    } else if ("removeLine" in d) {
      draft.lines.delete(Number(d.removeLine));
      drawLines();
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
  // Un formulario con una peticion en curso ignora nuevos envios (doble clic, Enter repetido).
  // Deshabilitar el boton no basta: Enter y requestSubmit envian igual. Clave en pagos, que no son idempotentes.
  if (form.dataset.busy) return;
  form.dataset.busy = "1";
  clearFieldErrors(form);
  const handler = ({product:submitProduct, category:submitCategory, adjust:submitAdjust, settings:submitSettings,
    user:submitUser, userEdit:submitUserEdit, order:submitOrder, invoice:submitInvoice, payment:submitPayment})[kind];
  Promise.resolve(handler(form)).catch(err => toast(err.message)).finally(() => { delete form.dataset.busy; });
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

/* Benchmarks del panel administrativo */
function benchNode(parent, tag, text, className) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  parent.append(node);
  return node;
}
const benchFormat = new Intl.NumberFormat("es-CO", {maximumFractionDigits:4});
const benchNum = value => value == null ? "Sin dato" : benchFormat.format(value);

function benchChart(parent, report) {
  const lines = [
    ["sum_sales", "Suma de ventas · O(n)", "var(--success-text)", ""],
    ["insertion_sort", "Insertion Sort · O(n²)", "var(--warning-text)", "5 3"],
    ["merge_sort", "Merge Sort · O(n log n)", "var(--link)", "2 2"]
  ];
  benchNode(parent, "h2", "Tiempo por volumen");
  const legend = benchNode(parent, "div", null, "benchLegend");
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  parent.append(svg);
  const hint = benchNode(parent, "p", "Selecciona un punto para consultar sus tiempos.", "benchHint");
  function shape(tag, attrs, label) {
    const element = document.createElementNS(svg.namespaceURI, tag);
    for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, value);
    if (label != null) element.textContent = label;
    svg.append(element);
    return element;
  }
  const points = report.measurements.filter(p => lines.some(([id]) => id === p.algorithm));
  if (!points.length) { hint.textContent = "Sin mediciones para graficar."; return; }
  const sizes = report.series.labels;
  const minN = Math.min(...sizes), maxN = Math.max(...sizes);
  const maxMs = Math.max(...points.map(p => p.median_ms), 0.0001);
  const width = Math.max(270, Math.min(850, parent.clientWidth - 48));
  svg.setAttribute("viewBox", "0 0 " + width + " 236");
  svg.setAttribute("aria-label", "Mediana en milisegundos por número de pedidos");
  const x = n => minN === maxN ? width / 2 : 52 + (width - 80) * (n - minN) / (maxN - minN);
  const minMs = Math.min(...points.map(p => p.median_ms));
  const logScale = minMs > 0 && maxMs / minMs >= 10;
  const low = logScale ? Math.floor(Math.log10(minMs)) : 0;
  const high = logScale ? Math.ceil(Math.log10(maxMs)) : maxMs;
  const y = ms => 184 - 155 * ((logScale ? Math.log10(ms) : ms) - low) / (high - low);
  shape("text", {x:4,y:15}, logScale ? "ms · escala logarítmica" : "ms");
  const ticks = logScale ? Array.from({length:high-low+1}, (_, i) => 10 ** (low+i)) : [0,maxMs/2,maxMs];
  for (const tick of ticks) {
    const height = y(tick);
    shape("line", {x1:51,x2:width-24,y1:height,y2:height,stroke:"var(--line)"});
    shape("text", {x:46,y:height+4,"text-anchor":"end"}, benchNum(Number(tick.toPrecision(3))));
  }
  let lastLabel = -Infinity;
  for (const n of sizes) {
    if (n !== maxN && (x(n)-lastLabel < 37 || x(maxN)-x(n)<37)) continue;
    shape("text", {x:x(n),y:206,"text-anchor":"middle"}, benchNum(n));
    lastLabel = x(n);
  }
  shape("text", {x:width/2,y:232,"text-anchor":"middle"}, "Volumen (N)");
  for (const [id, label, color, dash] of lines) {
    benchNode(legend, "span", label).style.color = color;
    const rows = points.filter(p => p.algorithm === id).sort((a,b) => a.n-b.n);
    shape("polyline", {points:rows.map(p => x(p.n)+","+y(p.median_ms)).join(" "), fill:"none",stroke:color,"stroke-width":2,"stroke-dasharray":dash});
    for (const p of rows) {
      const caption = label+" · N "+benchNum(p.n)+" · Media "+benchNum(p.avg_ms)+" ms · Mediana "+benchNum(p.median_ms)+" ms";
      const dot = shape("circle", {cx:x(p.n),cy:y(p.median_ms),r:5,fill:color,tabindex:0,"aria-label":caption});
      for (const event of ["pointerenter","focus","click"]) dot.addEventListener(event, () => { hint.textContent = caption; });
      const title = document.createElementNS(svg.namespaceURI,"title");
      title.textContent = caption;
      dot.append(title);
    }
  }
}

function benchReport(root, data) {
  root.replaceChildren();
  const {meta,timing,comparison,equivalence,results} = data;
  const largest = comparison.filter(row => row.before.algorithm === "insertion_sort").sort((a,b) => b.n-a.n)[0];
  benchNode(root,"p",(meta.source === "real" ? "Datos reales" : "Datos sintéticos")+" · "+fmtDate(meta.run_at),"muted");
  const kpis = benchNode(root,"div",null,"benchKpis");
  const metric = (label, value, note) => {
    const card = benchNode(kpis,"section",null,"benchCard");
    benchNode(card,"h2",label);
    benchNode(card,"strong",value);
    benchNode(card,"p",note);
    return card;
  };
  metric("Factor de mejora", largest?.speedup == null ? "Sin dato" : benchNum(largest.speedup)+"×",
    largest ? "Merge Sort frente a Insertion Sort con N = "+benchNum(largest.n) : "Sin comparación");
  metric("Tiempo de cómputo",benchNum(timing.compute_ms)+" ms",
    timing.db_fetch_ms == null ? "Lectura de BD sin medir" : "Lectura de BD por separado: "+benchNum(timing.db_fetch_ms)+" ms");
  const verified = metric("Equivalencia",equivalence.sort_by_date ? "Orden idéntico" : "Sin verificar","Insertion Sort y Merge Sort");
  if (equivalence.sort_by_date) verified.classList.add("benchVerified");
  const chart = benchNode(root,"section",null,"benchCard");
  benchChart(chart,data);
  let chartWidth = chart.clientWidth;
  const chartObserver = new ResizeObserver(() => {
    if (chart.isConnected && chart.clientWidth !== chartWidth) {
      chartWidth = chart.clientWidth;
      chart.replaceChildren();
      benchChart(chart,data);
    }
  });
  chartObserver.observe(chart);
  const section = benchNode(root,"section",null,"benchCard");
  benchNode(section,"h2","Antes y después");
  for (const operation of new Set(comparison.map(row => row.operation))) {
    benchNode(section,"h3",operation);
    const table = benchNode(section,"table");
    table.setAttribute("aria-label",operation);
    const heading = benchNode(benchNode(table,"thead"),"tr");
    for (const title of ["Tamaño (N)","Antes: O(n²) (ms)","Después: O(n log n) (ms)","Mejora"]) benchNode(heading,"th",title);
    const body = benchNode(table,"tbody");
    for (const row of comparison.filter(item => item.operation === operation)) {
      const tr = benchNode(body,"tr");
      for (const value of [row.n,row.before.median_ms,row.after.median_ms]) benchNode(tr,"td",benchNum(value));
      benchNode(benchNode(tr,"td"),"span",benchNum(row.speedup)+"× / "+benchNum(row.improvement_pct)+" %","benchBadge");
    }
  }
  const business = benchNode(root,"section",null,"benchCard");
  benchNode(business,"h2","Resultados de pedidos reales");
  if (results) {
    benchNode(business,"strong",money(results.total_sales));
    benchNode(business,"p","Ventas confirmadas · "+benchNum(results.orders_count)+" pedidos analizados");
    for (const [title,items] of [
      ["Productos más vendidos",results.top_products.map(p => p.name+" · "+benchNum(p.units)+" unidades")],
      ["Pedidos por cliente",results.orders_by_customer.map(c => c.customer+" · "+benchNum(c.orders)+" pedidos")]
    ]) {
      benchNode(business,"h3",title);
      const list = benchNode(business,"ul");
      for (const item of items.length ? items : ["Sin registros"]) benchNode(list,"li",item);
    }
  } else benchNode(business,"p","La lectura de datos reales no estuvo disponible.");
  benchNode(root,"footer","Python "+meta.python+" · "+meta.os+" · Semilla "+meta.seed+" · "+meta.repetitions+" repeticiones","muted");
  for (const note of meta.notes || []) benchNode(root,"p",note,"muted");
}

async function renderBenchmarks(view) {
  if (state.me?.role !== "admin") return;
  view.replaceChildren($("#bench-template").content.cloneNode(true));
  const form = $(".benchControls",view), run = $("button",form);
  const report = $(".benchReport",view), status = $(".benchStatus",view);
  form.onchange = () => { $(".benchSizes",form).hidden = form.elements.source.value === "real"; };
  async function load(execute) {
    run.disabled = true;
    run.setAttribute("aria-busy","true");
    status.textContent = execute ? "Midiendo algoritmos. La ejecución puede tardar unos segundos." : "Consultando la última ejecución…";
    try {
      const source = form.elements.source.value;
      const body = {source};
      if (source === "synthetic") body.sizes = [100,500,1000,2500,5000].filter(n => n <= Number(form.elements.volume.value));
      const signal = AbortSignal.timeout(45000);
      const result = execute ? await api("/admin/benchmarks/run",{method:"POST",body,signal}) : await api("/admin/benchmarks/latest",{signal});
      if (report.isConnected) benchReport(report,result);
      status.textContent = "";
    } catch (error) {
      status.textContent = error.data?.error === "no_benchmark" ? "Todavía no hay mediciones. Ejecuta el primer benchmark para comparar los algoritmos." : error.data?.fields?.sizes || error.message;
    } finally {
      run.disabled = false;
      run.removeAttribute("aria-busy");
    }
  }
  form.onsubmit = event => { event.preventDefault(); if (!run.disabled) load(true); };
  await load(false);
}

/* ---------- Integridad: cadena SHA-256 de facturas y pagos (contrato en backend/PHASE3_API.md) ----------
   GET /admin/integrity/status, POST /admin/integrity/verify {}, GET /admin/integrity/chain?page&per_page.
   Todo valor que llega del servidor se escribe con textContent: aqui no se arma HTML con datos. */
const INTEGRITY_PAGE_SIZE = 10;
const INTEGRITY_STATUS = {
  valid:["ok", "check", "Cadena íntegra", "Cada eslabón coincide con su hash y con el documento que protege."],
  compromised:["bad", "alert", "Alteración detectada", "Un documento o un eslabón cambió después de registrarse."],
  unverified:["warn", "clock", "Sin verificar", "La cadena tiene eslabones que aún no se han auditado."]
};
const INTEGRITY_REASON = {
  payload_mismatch:"El documento cambió después de registrarse en la cadena.",
  hash_mismatch:"El hash SHA-256 recalculado no coincide con el almacenado.",
  prev_hash_broken:"El eslabón apunta a un hash anterior incorrecto: la cadena está rota.",
  missing_entity:"El documento que protegía este eslabón ya no existe.",
  missing_event:"Existe un documento que nunca se registró en la cadena.",
  sequence_gap:"Falta una posición en la secuencia o la cadena se acortó.",
  checkpoint_mismatch:"Cambió el hash de una posición que ya se había auditado."
};
const INTEGRITY_EVENT = {issued:"Emisión", voided:"Anulación", payment_recorded:"Pago registrado", adjustment:"Ajuste"};
const INTEGRITY_FIELD = {
  created_at:"Fecha de registro", discount_amount:"Descuento", employee_id:"Empleado", invoice_number:"Número de factura",
  items_sha256:"Resumen de ítems (SHA-256)", order_id:"Pedido", shipping_cost:"Envío", status:"Estado", subtotal:"Subtotal",
  tax_amount:"Impuesto", total_amount:"Total", invoice_id:"Factura", amount:"Monto", payment_method:"Método de pago",
  paid_at:"Fecha de pago", receipt_path:"Comprobante", receipt_type:"Tipo de comprobante", receipt_sha256:"SHA-256 del comprobante",
  value:"Valor"
};
const INTEGRITY_MONEY = new Set(["discount_amount", "shipping_cost", "subtotal", "tax_amount", "total_amount", "amount"]);
const moneyExact = new Intl.NumberFormat("es-CO", {style:"currency", currency:"COP", minimumFractionDigits:2, maximumFractionDigits:2});
const INTEGRITY_ICON = {
  copy:'<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="5.5" y="5.5" width="8" height="8" rx="1.5"/><path d="M10.5 5.5V3.8A1.3 1.3 0 0 0 9.2 2.5H3.8a1.3 1.3 0 0 0-1.3 1.3v5.4a1.3 1.3 0 0 0 1.3 1.3h1.7"/></svg>',
  link:'<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6.8 9.2a2.6 2.6 0 0 0 3.7 0l2.2-2.2a2.6 2.6 0 0 0-3.7-3.7l-.8.8"/><path d="M9.2 6.8a2.6 2.6 0 0 0-3.7 0L3.3 9a2.6 2.6 0 0 0 3.7 3.7l.8-.8"/></svg>'
};

/* Crea un nodo: las cadenas hijas se vuelven nodos de texto, nunca HTML */
function dom(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null || value === false) continue;
    if (key === "className") el.className = value;
    else if (key === "text") el.textContent = value;
    else el.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) if (child != null && child !== false) el.append(child);
  return el;
}
/* Iconos: solo constantes del propio archivo (sin datos del servidor) */
function svgIcon(markup) {
  const tpl = document.createElement("template");
  tpl.innerHTML = markup;
  return tpl.content.firstElementChild;
}
const iconOf = name => svgIcon(INTEGRITY_ICON[name] || ICON[name]);
const pillBadge = (tone, icon, text) => dom("span", {className:"badge " + tone}, iconOf(icon), text);
const shortHash = hash => hash.length > 16 ? hash.slice(0, 6) + "…" + hash.slice(-6) : hash;
const documentLabel = (type, id) => id == null ? "Sin referencia" : (type === "payment" ? "Pago" : type === "invoice" ? "Factura" : "Documento") + " #" + id;

const integrity = {status:null, page:1, pages:1, total:0, broken:null, view:null};

function checkedByLabel(value) {
  if (!value) return "Sin registro";
  if (value === "system") return "Tarea programada del sistema";
  const id = Number(String(value).split(":")[1]);
  if (state.me && state.me.id === id) return (state.me.name || state.me.full_name || "Tú") + " (tú)";
  const user = (usersCache || []).find(u => u.id === id);
  return user ? user.name : "Administrador #" + id;
}

/* Botón para copiar el hash completo, con confirmación breve en el propio botón */
function copyButton(hash, label) {
  const button = dom("button", {type:"button", className:"copyHash", "aria-label":"Copiar " + label, title:"Copiar hash completo"}, iconOf("copy"));
  button.dataset.hash = hash;
  button.dataset.label = label;
  return button;
}
/* API del portapapeles y, si el navegador la niega (sin foco o sin HTTPS), el método clásico con un textarea temporal */
async function writeClipboard(text) {
  try { await navigator.clipboard.writeText(text); return true; } catch {}
  const area = dom("textarea", {className:"sr", readonly:true, "aria-hidden":"true"});
  area.value = text;
  document.body.append(area);
  area.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch {}
  area.remove();
  return ok;
}
async function copyHash(button) {
  if (!(await writeClipboard(button.dataset.hash))) {
    toast("No se pudo copiar. Selecciona el hash y cópialo manualmente.");
    return;
  }
  clearTimeout(button._copyTimer);
  button.replaceChildren(iconOf("check"));
  button.dataset.copied = "true";
  button.setAttribute("aria-label", "Copiado: " + button.dataset.label);
  toast("Hash copiado al portapapeles.");
  button._copyTimer = setTimeout(() => {
    button.replaceChildren(iconOf("copy"));
    delete button.dataset.copied;
    button.setAttribute("aria-label", "Copiar " + button.dataset.label);
  }, 1600);
}
function hashCell(hash, label) {
  if (!hash) return dom("span", {className:"muted", text:"Sin hash"});
  if (hash === "GENESIS") return pillBadge("", "dot", "Génesis");
  return dom("span", {className:"hashCell"}, dom("code", {className:"hash", title:hash, text:shortHash(hash)}), copyButton(hash, label));
}

/* ---------- 1. Estado de la cadena ---------- */
function renderIntegrityHero(box, data) {
  const status = INTEGRITY_STATUS[data.status] ? data.status : "unverified";
  const [tone, icon, label, text] = INTEGRITY_STATUS[status];
  const last = data.last_verification;
  const checked = last ? last.total_records_checked : 0;
  let note = text;
  if (status === "unverified") note = last ? "La cadena creció desde la última auditoría. Verifícala para incluir los eslabones nuevos." : "Todavía no se ha ejecutado ninguna verificación.";
  const headHash = last?.details?.head_hash;
  box.dataset.status = status;
  box.replaceChildren(
    dom("div", {className:"integrityLead"},
      pillBadge(tone, icon, label),
      dom("p", {className:"integrityFigure"},
        dom("strong", {text:new Intl.NumberFormat("es-CO").format(checked)}),
        dom("span", {text:status === "compromised"
          ? (checked === 1 ? "eslabón revisado hasta la divergencia" : "eslabones revisados hasta la divergencia")
          : (checked === 1 ? "eslabón verificado" : "eslabones verificados")})),
      dom("p", {className:"muted", text:note})),
    dom("dl", {className:"integrityFacts"},
      dom("div", {}, dom("dt", {text:"Eslabones en la cadena"}), dom("dd", {text:new Intl.NumberFormat("es-CO").format(data.total_records)})),
      dom("div", {}, dom("dt", {text:"Última verificación"}), dom("dd", {text:last ? fmtDate(last.checked_at) : "Nunca"})),
      dom("div", {}, dom("dt", {text:"Ejecutada por"}), dom("dd", {text:last ? checkedByLabel(last.checked_by) : "Sin registro"})),
      headHash ? dom("div", {}, dom("dt", {text:"Hash de cabeza"}), dom("dd", {}, hashCell(headHash, "hash de cabeza de la cadena"))) : null));
}

/* ---------- 2. Alerta del primer eslabón comprometido ---------- */
function parseDetail(value) {
  if (typeof value !== "string") return value;
  try { const parsed = JSON.parse(value); return parsed; } catch { return value; }
}
function formatFieldValue(key, value) {
  if (value == null || value === "") return dom("span", {className:"muted", text:"Sin valor"});
  if (typeof value === "object") return dom("code", {className:"hash", text:JSON.stringify(value)});
  const text = String(value);
  if (/^[0-9a-f]{64}$/i.test(text)) return dom("span", {className:"hashCell"}, dom("code", {className:"hash", title:text, text:shortHash(text)}), copyButton(text, INTEGRITY_FIELD[key] || key));
  if (INTEGRITY_MONEY.has(key) && !Number.isNaN(Number(text))) return dom("span", {className:"num", text:moneyExact.format(Number(text))});
  if (/^\d{4}-\d{2}-\d{2}T/.test(text)) return dom("span", {text:fmtDate(text)});
  return dom("span", {text});
}
function changedFields(expected, actual) {
  const isObj = v => v && typeof v === "object" && !Array.isArray(v);
  if (!isObj(expected) || !isObj(actual)) return [["value", expected, actual]];
  const keys = [...new Set([...Object.keys(expected), ...Object.keys(actual)])];
  return keys.filter(k => JSON.stringify(expected[k]) !== JSON.stringify(actual[k])).map(k => [k, expected[k], actual[k]]);
}
function renderIntegrityAlert(box, last) {
  box.replaceChildren();
  box.hidden = !last || last.status !== "compromised";
  if (box.hidden) return;
  const reason = last.failure_reason;
  const details = last.details || {};
  const facts = dom("dl", {className:"alertFacts"},
    dom("div", {}, dom("dt", {text:"Secuencia"}), dom("dd", {className:"num", text:last.first_broken_seq_no == null ? "Desconocida" : "#" + last.first_broken_seq_no})),
    dom("div", {}, dom("dt", {text:"Documento"}), dom("dd", {text:documentLabel(last.first_broken_entity_type, last.first_broken_entity_id)})),
    dom("div", {}, dom("dt", {text:"Motivo"}), dom("dd", {}, dom("code", {className:"reasonCode", text:reason || "desconocido"}))));
  const actions = dom("div", {className:"alertActions"});
  if (last.first_broken_seq_no != null) {
    actions.append(dom("button", {type:"button", className:"btn secondary small", "data-goto-broken":""}, iconOf("link"), "Ver eslabón en la cadena"));
  }
  box.append(
    dom("div", {className:"alertHead"},
      dom("span", {className:"alertIcon"}, iconOf("alert")),
      dom("div", {},
        dom("h2", {id:"integrityAlertTitle", text:"Primer eslabón comprometido"}),
        dom("p", {text:INTEGRITY_REASON[reason] || "La verificación encontró una divergencia en la cadena."}))),
    facts);
  if ("expected" in details || "actual" in details) {
    const rows = changedFields(parseDetail(details.expected), parseDetail(details.actual));
    if (rows.length) {
      const table = dom("table", {className:"diffTable", "aria-label":"Campos alterados"},
        dom("thead", {}, dom("tr", {},
          dom("th", {scope:"col", text:"Campo"}),
          dom("th", {scope:"col", text:"Valor registrado en la cadena"}),
          dom("th", {scope:"col", text:"Valor actual en la base de datos"}))),
        dom("tbody", {}, rows.map(([key, before, after]) => dom("tr", {},
          dom("td", {}, dom("span", {className:"cellMain", text:INTEGRITY_FIELD[key] || key})),
          dom("td", {className:"diffBefore"}, formatFieldValue(key, before)),
          dom("td", {className:"diffAfter"}, formatFieldValue(key, after))))));
      box.append(dom("h3", {className:"diffTitle", text:rows.length === 1 ? "1 campo no coincide" : rows.length + " campos no coinciden"}), table);
    }
  }
  if (actions.childElementCount) box.append(actions);
}

/* ---------- 3. Explorador de la cadena ---------- */
function renderChainTable(box, data) {
  integrity.page = data.page;
  integrity.pages = Math.max(1, data.pages);
  integrity.total = data.total;
  if (!data.entries.length) {
    box.replaceChildren(dom("div", {className:"emptyState compact"},
      dom("h2", {text:data.total ? "Esta página está vacía" : "La cadena está vacía"}),
      dom("p", {className:"muted", text:data.total ? "Vuelve a la primera página." : "Cada factura emitida y cada pago registrado agregan un eslabón."})));
    return;
  }
  const brokenSeq = integrity.broken;
  const table = dom("table", {className:"ledger"},
    dom("caption", {className:"sr", text:"Eslabones de la cadena de hashes, del más reciente al más antiguo"}),
    dom("thead", {}, dom("tr", {}, ["# Secuencia", "Documento", "Evento", "Fecha", "Hash anterior", "Hash actual"].map(t => dom("th", {scope:"col", text:t})))),
    dom("tbody", {}, data.entries.map(entry => {
      const broken = brokenSeq != null && entry.seq_no === brokenSeq;
      return dom("tr", {className:broken ? "rowBroken" : null, id:"seq-" + entry.seq_no, "aria-current":broken ? "true" : null},
        dom("td", {}, dom("span", {className:"seqNo", text:"#" + entry.seq_no}), broken ? pillBadge("bad", "alert", "Comprometido") : null),
        dom("td", {}, dom("span", {className:"cellMain", text:documentLabel(entry.entity_type, entry.entity_id)})),
        dom("td", {text:INTEGRITY_EVENT[entry.event_type] || entry.event_type}),
        dom("td", {}, dom("time", {datetime:entry.created_at, text:fmtDate(entry.created_at)})),
        dom("td", {}, hashCell(entry.prev_hash, "hash anterior de la secuencia " + entry.seq_no)),
        dom("td", {}, hashCell(entry.current_hash, "hash actual de la secuencia " + entry.seq_no)));
    })));
  const fmt = new Intl.NumberFormat("es-CO");
  box.replaceChildren(dom("div", {className:"tableWrap"}, table),
    dom("div", {className:"pager"},
      dom("span", {text:fmt.format(data.total) + (data.total === 1 ? " eslabón" : " eslabones") + " · página " + data.page + " de " + integrity.pages}),
      dom("span", {className:"pagerButtons"},
        dom("button", {type:"button", className:"btn secondary small", "data-chain-page":data.page - 1, disabled:data.page <= 1, text:"Anterior"}),
        dom("button", {type:"button", className:"btn secondary small", "data-chain-page":data.page + 1, disabled:data.page >= integrity.pages, text:"Siguiente"}))));
}
async function loadChain(page, focusSeq) {
  const box = $("#chainBox");
  if (!box) return;
  box.setAttribute("aria-busy", "true");
  try {
    const data = await api("/admin/integrity/chain?page=" + page + "&per_page=" + INTEGRITY_PAGE_SIZE);
    if (!box.isConnected) return;
    renderChainTable(box, data);
    if (focusSeq != null) {
      const row = $("#seq-" + focusSeq, box);
      if (row) { row.scrollIntoView({block:"center", behavior:matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"}); row.tabIndex = -1; row.focus({preventScroll:true}); }
    }
  } catch (err) {
    if (!box.isConnected || err.status === 401) return;
    box.replaceChildren(dom("div", {className:"emptyState compact"},
      dom("h2", {text:"No pudimos cargar la cadena"}),
      dom("p", {className:"muted", text:err.message}),
      dom("button", {type:"button", className:"btn secondary", "data-chain-page":page, text:"Reintentar"})));
  } finally {
    box.removeAttribute("aria-busy");
  }
}

/* ---------- Pantalla y verificación ---------- */
function applyIntegrityStatus(data) {
  integrity.status = data;
  const last = data.last_verification;
  integrity.broken = last && last.status === "compromised" ? last.first_broken_seq_no : null;
  renderIntegrityHero($("#integrityHero"), data);
  renderIntegrityAlert($("#integrityAlert"), last);
}
async function verifyIntegrity(button) {
  if (button.disabled) return;
  setBusy(button, true, "Verificando…");
  const live = $("#integrityLive");
  live.textContent = "Verificando la cadena de hashes.";
  try {
    const result = await api("/admin/integrity/verify", {method:"POST", body:{}});
    let status;
    try { status = await api("/admin/integrity/status"); }
    catch { status = {...integrity.status, status:result.status, last_verification:result}; }
    if (!$("#integrityHero")) return;
    applyIntegrityStatus(status);
    const message = result.status === "valid"
      ? "Cadena íntegra: " + result.total_records_checked + " eslabones verificados."
      : "Alteración detectada en " + documentLabel(result.first_broken_entity_type, result.first_broken_entity_id) + ".";
    live.textContent = message;
    toast(message);
    await loadChain(1);
    if (result.status === "compromised") $("#integrityAlert")?.focus({preventScroll:false});
  } catch (err) {
    if (err.status === 401) return;
    live.textContent = "";
    toast(err.message || "No pudimos completar la verificación.");
  } finally {
    setBusy(button, false);
  }
}
async function renderIntegrity(view) {
  if (state.me?.role !== "admin") return;
  const [status] = await Promise.all([api("/admin/integrity/status"), loadUsersCache().catch(() => null)]);
  const verify = dom("button", {type:"button", className:"btn primary", id:"verifyIntegrity"}, "Verificar integridad ahora");
  view.replaceChildren(dom("div", {className:"integrity"},
    dom("div", {className:"viewHead"},
      dom("div", {},
        dom("h1", {text:"Integridad"}),
        dom("p", {text:"Cada factura y cada pago se encadenan con SHA-256. Si alguien cambia un documento o un eslabón, la verificación lo señala."})),
      dom("div", {}, verify)),
    dom("p", {id:"integrityLive", className:"sr", role:"status", "aria-live":"polite"}),
    dom("section", {className:"card integrityHero", id:"integrityHero", "aria-label":"Estado de la cadena"}),
    dom("section", {className:"integrityAlert", id:"integrityAlert", tabindex:"-1", "aria-labelledby":"integrityAlertTitle", hidden:true}),
    dom("section", {className:"card flush", "aria-labelledby":"chainTitle"},
      dom("div", {className:"cardHead chainHead"},
        dom("h2", {id:"chainTitle", text:"Cadena de hashes"}),
        dom("span", {className:"muted", text:"Del más reciente al más antiguo"})),
      dom("div", {id:"chainBox"}))));
  applyIntegrityStatus(status);
  verify.addEventListener("click", () => verifyIntegrity(verify));
  const root = $(".integrity", view);
  root.addEventListener("click", event => {
    const copy = event.target.closest(".copyHash");
    if (copy) { copyHash(copy); return; }
    const pageBtn = event.target.closest("[data-chain-page]");
    if (pageBtn && !pageBtn.disabled) { loadChain(Number(pageBtn.dataset.chainPage)); return; }
    if (event.target.closest("[data-goto-broken]") && integrity.broken != null) {
      const total = integrity.status?.total_records || integrity.total;
      const page = Math.max(1, Math.ceil((total - integrity.broken + 1) / INTEGRITY_PAGE_SIZE));
      loadChain(page, integrity.broken);
    }
  });
  await loadChain(1);
}
