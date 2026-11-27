"use strict";

/* ---------- Utilidades ---------- */
const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => Array.from(root.querySelectorAll(s));
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const money = v => new Intl.NumberFormat("es-CO", {style:"currency", currency:"COP", minimumFractionDigits:0, maximumFractionDigits:2}).format(v || 0);
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
let pendingInvoice = null;
async function api(path, {method = "GET", body, signal} = {}, retry = true) {
  const actor = state.me;
  const options = {method, signal, credentials:"same-origin", headers:{Accept:"application/json"}};
  if (method !== "GET") {
    if (!csrf) {
      const token = await api("/auth/csrf", {signal});
      if (!token.csrf) throw Object.assign(new Error("No se pudo preparar la sesión. Intenta de nuevo."), {status:0, data:{}});
      csrf = token.csrf;
    }
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
  if (actor && actor !== state.me && !path.startsWith("/auth/"))
    throw Object.assign(new Error("La sesión cambió."), {status:401, data:{}});
  if (res.status === 403 && data.error === "csrf" && retry) {
    csrf = null;
    return api(path, {method, body, signal}, false);
  }
  if (!res.ok) {
    const err = Object.assign(new Error(data.message || "No pudimos completar la operación."), {status:res.status, data});
    if (res.status === 401 && !path.startsWith("/auth/") && state.me) {
      const form = $("#modalBody form[data-order-id]");
      const order = path.match(/^\/orders\/(\d+)\/invoice$/);
      const orderId = order?.[1] || form?.dataset.orderId;
      pendingInvoice = orderId ? {email:state.me.email, orderId} : null;
      showLogin("Tu sesión terminó. Vuelve a iniciar sesión.");
    }
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
  categorias:renderCategories, inventario:renderInventory, ajustes:renderSettings, benchmarks:renderBenchmarks, integridad:renderIntegrity, analitica:renderAnalytics, modelos:renderModels};

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
const employeeMode = () => state.me?.role === "employee";
const ordersPath = () => employeeMode() ? "/staff/orders" : "/admin/orders";
function currentView() {
  const view = location.hash.slice(1);
  if (employeeMode()) return view === "usuarios" ? "usuarios" : "pedidos";
  return Object.hasOwn(VIEWS, view) ? view : "resumen";
}
async function route() {
  if (!state.me) return;
  const name = currentView();
  $$("#tabs [role=tab]").forEach(tab => {
    const on = tab.dataset.view === name;
    tab.setAttribute("aria-selected", String(on));
    tab.hidden = employeeMode() && !["pedidos", "usuarios"].includes(tab.dataset.view);
    tab.tabIndex = on ? 0 : -1;
  });
  const panel = $("#view");
  const view = document.createElement("div");
  panel.replaceChildren(view);
  panel.setAttribute("aria-labelledby", "tab-" + name);
  panel.hidden = false;
  panel.setAttribute("aria-busy", "true");
  view.innerHTML = '<div class="grid"><div class="skeleton"></div><div class="skeleton"></div></div>';
  try {
    await VIEWS[name](view);
  } catch (err) {
    if (err.status !== 401) view.innerHTML = emptyState("No pudimos cargar esta sección", err.message, '<button class="btn secondary" data-reload>Reintentar</button>');
  } finally {
    if (view.isConnected) panel.removeAttribute("aria-busy");
  }
}
window.addEventListener("hashchange", route);
$("#tabs").addEventListener("keydown", e => {
  const tabs = $$("#tabs [role=tab]:not([hidden])");
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
      if (o.employee_name) staffNames.set(o.employee_id, o.employee_name);
      const employee = o.employee_name || (o.employee_id ? staffName(o.employee_id) : "");
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
  view.innerHTML = head("Pedidos", employeeMode() ? "Consulta los pedidos de la tienda por cliente, número o canal." : "Confirma, prepara y despacha. Cancelar un pedido devuelve su stock al inventario.",
      employeeMode() ? "" : '<button class="btn primary" data-new-order>Nuevo pedido</button>') +
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
let orderRequest = 0;
async function loadOrders() {
  const request = ++orderRequest;
  const box = $("#ordersBox");
  if (!box) return;
  const params = new URLSearchParams({page:orderFilter.page});
  if (orderFilter.status) params.set("status", orderFilter.status);
  if (orderFilter.channel) params.set("channel", orderFilter.channel);
  if (orderFilter.q) params.set("q", orderFilter.q);
  box.setAttribute("aria-busy", "true");
  let d;
  try {
    d = await api(ordersPath() + "?" + params);
  } catch (err) {
    if (request === orderRequest && box.isConnected && err.status !== 401)
      box.innerHTML = emptyState("No pudimos cargar los pedidos", err.message, '<button class="btn secondary" data-reload>Reintentar</button>');
    return;
  } finally {
    if (request === orderRequest) box.removeAttribute("aria-busy");
  }
  if (request !== orderRequest || !box.isConnected) return;
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
const userFilter = {q:"", role:"all", page:1};
let usersCache = [], usersRequest = 0;
const staffNames = new Map();
async function loadAdminNames() {
  let page = 1;
  while (true) {
    const data = await api("/admin/users?role=admin&page=" + page);
    for (const u of data.users) staffNames.set(u.id, u.name);
    if (page >= data.pages) return;
    page++;
  }
}
const staffName = id => staffNames.get(id) || (usersCache || []).find(u => u.id === id)?.name || "empleado #" + id;
const isMe = u => state.me && u.email === state.me.email;
function accountState(u) {
  if (u.email_verification_pending) return badge("warn", ICON.clock, "Sin verificar");
  return u.is_active ? badge("ok", ICON.check, "Activa") : badge("", ICON.dot, "Inactiva");
}
async function renderUsers(view) {
  view.innerHTML = head("Usuarios", employeeMode() ? "Consulta las cuentas por nombre, correo o rol." : "Equipo y clientes. Cambiar el rol o desactivar una cuenta cierra sus sesiones abiertas.",
      employeeMode() ? "" : '<button class="btn primary" data-new-user>Nuevo usuario</button>') +
    '<div class="toolbar"><label class="field search"><span class="sr">Buscar usuarios</span><input type="search" id="userSearch" placeholder="Buscar por nombre o correo" value="' + esc(userFilter.q) + '" autocomplete="off"></label></div>' +
    '<div class="chips" role="group" aria-label="Filtrar por rol" id="userChips"></div><div class="card flush" id="usersBox"></div>';
  $("#userSearch").addEventListener("input", debounce(e => { userFilter.q = e.target.value.trim(); userFilter.page = 1; drawUsers(); }, 120));
  drawUsers();
}
async function drawUsers() {
  const box = $("#usersBox");
  if (!box) return;
  const request = ++usersRequest;
  const params = new URLSearchParams({page:userFilter.page, q:userFilter.q});
  if (userFilter.role !== "all") params.set("role", userFilter.role);
  $("#userChips").innerHTML = [["all", "Todos"], ["admin", "Administradores"], ["employee", "Empleados"], ["customer", "Clientes"]]
    .map(([v, label]) => '<button class="chip" data-user-role="' + v + '" aria-pressed="' + (v === userFilter.role) + '">' + label + '</button>').join("");
  let result;
  try {
    result = await api((employeeMode() ? "/staff/users?" : "/admin/users?") + params);
  } catch (err) {
    if (request === usersRequest && box.isConnected && err.status !== 401)
      box.innerHTML = emptyState("No pudimos cargar los usuarios", err.message, '<button class="btn secondary" data-reload>Reintentar</button>');
    return;
  }
  if (request !== usersRequest || !box.isConnected) return;
  if (userFilter.page > result.pages) { userFilter.page = result.pages; return drawUsers(); }
  const list = usersCache = result.users;
  if (!list.length) {
    box.innerHTML = emptyState("Ningún usuario coincide", "Prueba con otro nombre, correo o rol.");
    return;
  }
  box.innerHTML = '<div class="tableWrap"><table><thead><tr><th scope="col">Usuario</th><th scope="col">Rol</th><th scope="col">Estado</th><th scope="col">Registro</th>' + (employeeMode() ? "" : '<th scope="col" class="right"><span class="sr">Acciones</span></th>') + '</tr></thead><tbody>' +
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
        (employeeMode() ? "" : '<td><div class="rowActions"><button class="btn secondary small" data-edit-user="' + u.id + '">Editar</button>' + toggleBtn + "</div></td>") + "</tr>";
    }).join("") + '</tbody></table></div><div class="pager"><span>'  + result.total + (result.total === 1 ? ' cuenta' : ' cuentas') + ' · página ' + result.page + ' de ' + result.pages +
      '</span><span><button class="btn secondary small" data-user-page="' + (result.page - 1) + '"' + (result.page === 1 ? ' disabled' : '') + '>Anterior</button> ' +
      '<button class="btn secondary small" data-user-page="' + (result.page + 1) + '"' + (result.page >= result.pages ? ' disabled' : '') + '>Siguiente</button></span></div>';
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
    showFieldErrors(form, err.data?.error === "email_taken" ? {email:err.message} : err.data?.fields, err.message);
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
    showFieldErrors(form, err.data?.fields, err.message);
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
    showFieldErrors(form, err.data?.fields, err.message);
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
  if (employeeMode()) {
    const {order} = await api(ordersPath() + "/" + id);
    const lines = order.items.map(item => "<li><span>" + esc(item.name) + " × " + esc(item.quantity) +
      '</span><span class="num">' + money(item.subtotal) + "</span></li>").join("");
    openModal('<div class="sheetHead"><h2 id="modalTitle">' + esc(order.order_number) + "</h2>" + closeButton + '</div><div class="sheetBody"><dl class="facts">' +
      fact("Cliente", order.customer_name) + fact("Estado", order.status_label) + fact("Canal", order.channel) +
      fact("Fecha", fmtDate(order.created_at)) + '</dl><section class="section"><h3>Productos</h3><ul class="list">' + lines +
      '</ul><dl class="facts">' + fact("Envío", money(order.shipping_cost)) + fact("Total", money(order.total)) + "</dl></section></div>");
    return;
  }
  const [{order:o}, billing] = await Promise.all([
    api(ordersPath() + "/" + id),
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
   GET  /api/orders/{id}/invoice  -> {invoice | null, payments: [...], balance: "117810.00" (texto COP)}
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

/* POST /api/admin/payments/{id}/status {status:"aprobado"|"rechazado"}: resuelve un pago pendiente */
async function reviewPayment(paymentId, decision, orderId, button) {
  setBusy(button, true, decision === "aprobado" ? "Aprobando…" : "Rechazando…");
  try {
    const {payment} = await api("/admin/payments/" + paymentId + "/status", {method:"POST", body:{status:decision}});
    toast("Pago de " + money(amountOf(payment.amount)) + (decision === "aprobado" ? " aprobado." : " rechazado: el monto vuelve a estar disponible."));
    await openInvoice(orderId);
  } catch (err) {
    if (err.status !== 401) toast(err.message || "No pudimos actualizar el pago.");
  } finally {
    if (button.isConnected) setBusy(button, false);
  }
}
async function openInvoice(orderId) {
  const [{order:o}, billing] = await Promise.all([api(ordersPath() + "/" + orderId), api("/orders/" + orderId + "/invoice")]);
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
    const fields = err.data?.error === "invalid_discount" ? {discount_amount:err.message} : err.data?.fields;
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
        // Transferencia, PSE y Nequi quedan pendientes hasta que un administrador confirma el dinero recibido
        (p.status === "pendiente" && state.me?.role === "admin"
          ? '<button type="button" class="btn secondary small" data-review-payment="' + p.id + '" data-decision="aprobado" data-order-id="' + o.id + '">Aprobar</button>' +
            '<button type="button" class="btn dangerGhost small" data-review-payment="' + p.id + '" data-decision="rechazado" data-order-id="' + o.id + '" data-amount="' + esc(money(amountOf(p.amount))) + '">Rechazar</button>'
          : "") +
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
      '<div class="sheetActions">' + backToOrder(o.id) +
        (state.me?.role === "admin" && inv.status === "emitida" ? '<button class="btn dangerGhost" data-void-invoice="' + inv.id + '" data-order-id="' + o.id + '">Anular factura</button><p class="formError" role="alert" data-void-error></p>' : "") + "</div>" +
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
    let fields = err.data?.fields;
    if (err.data?.error === "payment_exceeds_balance") fields = {amount:err.message};
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
    showFieldErrors(form, err.data?.fields, err.message);
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
    showFieldErrors(form, err.data?.fields, err.message);
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
    showFieldErrors(form, err.data?.fields, err.message);
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
    showFieldErrors(form, err.data?.fields, err.message);
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
    if (el.getAttribute("role") === "tab" && d.view) { // solo pestañas principales; las sub-pestañas no tienen data-view
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
    } else if ("voidInvoice" in d) {
      if (!await confirmAction({title:"¿Anular la factura?", text:"La anulación queda registrada en el historial de integridad.", action:"Anular factura"})) return;
      setBusy(el, true, "Anulando…");
      try {
        await api("/admin/invoices/" + d.voidInvoice + "/void", {method:"POST", body:{}});
        await openInvoice(d.orderId);
        toast("Factura anulada.");
      } catch (err) {
        const alert = $("[data-void-error]");
        if (alert) alert.textContent = err.message;
      } finally { if (el.isConnected) setBusy(el, false); }
    } else if ("reviewPayment" in d) {
      if (d.decision === "rechazado") {
        const ok = await confirmAction({title:"¿Rechazar el pago de " + d.amount + "?",
          text:"Úsalo si el dinero no llegó. El monto vuelve a quedar disponible para cobrar y el rechazo queda registrado en la cadena de integridad.",
          action:"Rechazar pago"});
        if (!ok) return;
      }
      await reviewPayment(d.reviewPayment, d.decision, d.orderId, el);
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
    } else if ("userPage" in d) {
      userFilter.page = Number(d.userPage);
      await drawUsers();
    } else if ("userRole" in d) {
      userFilter.page = 1;
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
  usersCache = [];
  staffNames.clear();
  if (confirmDialog.open) { settleConfirm(false); confirmDialog.close(); }
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
  state.meta = employeeMode() ? {statuses:[]} : await api("/admin/meta");
  $(".brand .tag").textContent = employeeMode() ? "Trabajadores" : "Admin";
  $("#loginView").hidden = true;
  $("#tabs").hidden = false;
  $("#logout").hidden = false;
  await route();
  const invoice = pendingInvoice;
  pendingInvoice = null;
  if (invoice?.email === user.email) { await openInvoice(invoice.orderId); return; }
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
    if (!["employee", "admin"].includes(res.user.role)) { location.assign("/"); return; }
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
    if (me.user && ["employee", "admin"].includes(me.user.role)) await start(me.user);
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
      benchNode(benchNode(tr,"td"),"span",[row.speedup == null ? null : benchNum(row.speedup)+"×", row.improvement_pct == null ? null : benchNum(row.improvement_pct)+" %"].filter(Boolean).join(" / ") || "Sin dato","benchBadge");
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
  return staffNames.get(id) || user?.name || "Administrador #" + id;
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
  const [status] = await Promise.all([api("/admin/integrity/status"), loadAdminNames().catch(() => {})]);
  if (!view.isConnected) return;
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

/* ---------- Analitica: calidad de datos, perfiles con boxplot y demanda (contrato en backend/PHASE4_API.md) ----------
   POST /admin/data-quality/audit {}, GET /admin/data-quality/latest (null antes de la primera),
   GET /admin/analytics/users, GET /admin/analytics/demand?period&horizon.
   Reutiliza dom(), iconOf() y pillBadge() de Integridad: todo dato del servidor entra con textContent. */
const SVG_NS = "http://www.w3.org/2000/svg";
const ANALYTICS_VIEWS = [["calidad", "Calidad de datos"], ["perfiles", "Perfiles y anomalías"], ["demanda", "Demanda"]];
const QUALITY_MODULES = [["users", "Usuarios"], ["categories", "Categorías"], ["products", "Productos"], ["orders", "Pedidos"], ["invoices", "Facturas"], ["payments", "Pagos"]];
const QUALITY_STATUS = {auto_fixed:["ok", "check", "Auto-corregida"], pending_review:["warn", "clock", "Pendiente de revisión"], resolved:["info", "check", "Resuelta"]};
const QUALITY_SEVERITY = {low:["", "dot", "Baja"], medium:["warn", "alert", "Media"], high:["bad", "alert", "Alta"]};
const QUALITY_ISSUE = {
  malformed_string:"Texto con formato irregular", missing_field:"Campo obligatorio vacío", duplicate_candidate:"Posible duplicado",
  inconsistent_category:"Categoría inexistente", invalid_price:"Precio inválido"
};
const ALERT_TYPE = {
  high_amount_outlier:"Monto atípico", excessive_cancellations:"Cancelaciones excesivas",
  abusive_discounts:"Descuentos fuera de lo habitual", unusual_frequency:"Frecuencia inusual"
};
const SOURCE_LABEL = {order_ids:"Pedido", invoice_ids:"Factura", payment_ids:"Pago"};
const CHANNEL_NAME = {web:"Web", presencial:"Presencial", app:"App", domicilio:"Domicilio"};
const fmtInt = new Intl.NumberFormat("es-CO");
const fmtDec = new Intl.NumberFormat("es-CO", {maximumFractionDigits:2});
const fmtPct = v => v == null ? "Sin dato" : fmtDec.format(v) + " %";
const analytics = {sub:"calidad", role:"customer", focusUser:null, quality:null, qModule:"all", qStatus:"all", qShown:20,
  users:null, demand:null, period:"daily", product:"global"};
try { const saved = localStorage.getItem("ferrepro.analytics"); if (ANALYTICS_VIEWS.some(([k]) => k === saved)) analytics.sub = saved; } catch {}

function svgEl(tag, attrs = {}, text) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) el.setAttribute(k, v);
  if (text != null) el.textContent = text;
  return el;
}
/* Control segmentado: botones con aria-pressed, como el filtro de canal de Pedidos */
function segmented(label, options, value, onPick) {
  const group = dom("div", {className:"segmentedFilter", role:"group", "aria-label":label});
  for (const [key, text] of options) {
    const b = dom("button", {type:"button", className:"segment", "aria-pressed":String(key === value), text});
    b.addEventListener("click", () => {
      $$(".segment", group).forEach(s => s.setAttribute("aria-pressed", String(s === b)));
      onPick(key);
    });
    group.append(b);
  }
  return group;
}
/* Tooltip flotante compartido por las graficas; se posiciona en px dentro de su contenedor */
function chartTip(wrap) {
  const tip = dom("div", {className:"chartTip", role:"status", "aria-live":"polite", hidden:true});
  wrap.append(tip);
  return {
    show(x, y, title, lines) {
      tip.replaceChildren(dom("strong", {text:title}), ...lines.map(([k, v, swatch]) =>
        dom("span", {className:"tipRow"}, swatch ? dom("i", {className:"tipSwatch " + swatch, "aria-hidden":"true"}) : null, dom("span", {text:k}), dom("b", {text:v}))));
      tip.hidden = false;
      const w = wrap.clientWidth, tw = tip.offsetWidth;
      tip.style.left = Math.max(0, Math.min(w - tw, x - tw / 2)) + "px";
      const above = y - tip.offsetHeight - 12;
      tip.style.top = (above >= 0 ? above : y + 16) + "px"; // sin espacio arriba, va debajo y no tapa el punto
    },
    hide() { tip.hidden = true; }
  };
}
/* Redibuja una grafica cuando cambia el ancho de su tarjeta (sin re-pedir datos) */
function responsiveChart(box, draw) {
  let width = 0;
  const run = () => { if (!box.isConnected) { if (width) ro.disconnect(); return; } if (box.clientWidth && box.clientWidth !== width) { width = box.clientWidth; draw(width); } };
  const ro = new ResizeObserver(run);
  ro.observe(box);
  run();
}
const niceTicks = (min, max, count = 4) => {
  if (min === max) { const pad = Math.abs(min) || 1; min -= pad; max += pad; }
  const raw = (max - min) / count, mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map(f => f * mag).find(s => s >= raw);
  const start = Math.floor(min / step) * step, ticks = [];
  for (let v = start; v <= max + step * 0.001; v += step) ticks.push(Number(v.toFixed(10)));
  if (ticks[ticks.length - 1] < max) ticks.push(ticks[ticks.length - 1] + step);
  return ticks;
};

/* ======================= Pantalla y sub-vistas ======================= */
async function renderAnalytics(view) {
  if (state.me?.role !== "admin") return;
  const tabs = dom("div", {className:"segmentedFilter analyticsTabs", role:"tablist", "aria-label":"Secciones de analítica"});
  const panel = dom("section", {className:"analyticsPanel", id:"analyticsPanel", role:"tabpanel", tabindex:"-1"});
  ANALYTICS_VIEWS.forEach(([key, text]) => {
    const tab = dom("button", {type:"button", role:"tab", className:"segment", id:"atab-" + key, "aria-controls":"analyticsPanel",
      "aria-selected":String(key === analytics.sub), tabindex:key === analytics.sub ? "0" : "-1", text});
    tab.addEventListener("click", () => showAnalytics(key));
    tabs.append(tab);
  });
  tabs.addEventListener("keydown", e => {
    const list = $$("[role=tab]", tabs), i = list.indexOf(document.activeElement);
    const next = {ArrowRight:i + 1, ArrowLeft:i - 1, Home:0, End:list.length - 1}[e.key];
    if (i < 0 || next === undefined) return;
    e.preventDefault();
    const tab = list[(next + list.length) % list.length];
    tab.focus();
    showAnalytics(tab.id.slice(5));
  });
  view.replaceChildren(dom("div", {className:"analytics"},
    dom("div", {className:"viewHead"}, dom("div", {},
      dom("h1", {text:"Analítica"}),
      dom("p", {text:"Calidad de los datos, comportamiento de clientes y empleados, y demanda estimada con regresión lineal."}))),
    tabs, panel));
  await loadAdminNames().catch(() => {});
  if (view.isConnected) await showAnalytics(analytics.sub);
}
async function showAnalytics(key) {
  analytics.sub = key;
  try { localStorage.setItem("ferrepro.analytics", key); } catch {}
  $$(".analyticsTabs [role=tab]").forEach(t => {
    const on = t.id === "atab-" + key;
    t.setAttribute("aria-selected", String(on));
    t.tabIndex = on ? 0 : -1;
  });
  const panel = $("#analyticsPanel");
  if (!panel) return;
  panel.setAttribute("aria-labelledby", "atab-" + key);
  panel.setAttribute("aria-busy", "true");
  panel.replaceChildren(dom("div", {className:"grid"}, dom("div", {className:"skeleton"}), dom("div", {className:"skeleton"})));
  try {
    if (key === "calidad") await renderQuality(panel);
    else if (key === "perfiles") await renderProfiles(panel);
    else await renderDemand(panel);
  } catch (err) {
    if (err.status === 401 || analytics.sub !== key) return;
    const retry = dom("button", {type:"button", className:"btn secondary", text:"Reintentar"});
    retry.addEventListener("click", () => showAnalytics(key));
    panel.replaceChildren(dom("div", {className:"emptyState compact"},
      dom("h2", {text:"No pudimos cargar esta sección"}), dom("p", {className:"muted", text:err.message}), retry));
  } finally {
    panel.removeAttribute("aria-busy");
  }
}
const stale = (panel, key) => !panel.isConnected || analytics.sub !== key;

/* ======================= 1. Calidad de datos ======================= */
async function renderQuality(panel) {
  const data = analytics.quality = await api("/admin/data-quality/latest");
  if (stale(panel, "calidad")) return;
  const run = dom("button", {type:"button", className:"btn primary", id:"runAudit", text:"Ejecutar auditoría"});
  run.addEventListener("click", () => runAudit(run));
  const bar = dom("div", {className:"panelBar"},
    dom("p", {className:"muted", text:data ? "Última auditoría: " + fmtDate(data.executed_at) + " · " + staffLabel(data.executed_by) : "Revisa usuarios, categorías, productos, pedidos, facturas y pagos."}),
    run);
  if (!data) {
    panel.replaceChildren(bar, dom("div", {className:"card emptyState compact"},
      dom("h2", {text:"Todavía no hay auditorías"}),
      dom("p", {className:"muted", text:"Ejecuta la primera para medir la calidad de los datos y corregir lo que sea seguro corregir."})));
    return;
  }
  panel.replaceChildren(bar, qualityKpis(data), qualityModules(data), dom("section", {className:"card flush", id:"issuesCard", "aria-labelledby":"issuesTitle"}));
  drawIssues();
}
const staffLabel = id => {
  if (id == null) return "Sistema";
  const user = (usersCache || []).find(u => u.id === id);
  return staffNames.get(id) || user?.name || "Administrador #" + id;
};
function scoreTone(score) {
  if (score >= 90) return ["ok", "check", "Excelente"];
  if (score >= 70) return ["warn", "alert", "Aceptable"];
  return ["bad", "alert", "Requiere atención"];
}
function qualityKpis(d) {
  const score = Math.max(0, Math.min(100, Number(d.quality_score) || 0));
  const [tone, icon, label] = scoreTone(score);
  const r = 52, c = 2 * Math.PI * r;
  const ring = svgEl("svg", {viewBox:"0 0 120 120", class:"scoreRing " + tone, "aria-hidden":"true"});
  ring.append(svgEl("circle", {cx:60, cy:60, r, class:"ringTrack"}),
    svgEl("circle", {cx:60, cy:60, r, class:"ringValue", "stroke-dasharray":c, "stroke-dashoffset":c * (1 - score / 100), transform:"rotate(-90 60 60)"}));
  const lead = dom("section", {className:"card qualityScore", "aria-label":"Puntaje de calidad"},
    dom("div", {className:"scoreVisual"}, ring, dom("strong", {className:"scoreValue", text:new Intl.NumberFormat("es-CO", {maximumFractionDigits:1}).format(score)})),
    dom("div", {className:"scoreText"},
      pillBadge(tone, icon, label),
      dom("h2", {text:"Quality Score"}),
      dom("p", {className:"muted", text:"Porcentaje de registros sin incidencias pendientes después de las correcciones automáticas (de 0 a 100)."})));
  const kpi = (labelText, value, note) => dom("div", {className:"card kpiCard"},
    dom("span", {className:"kpiLabel", text:labelText}), dom("strong", {text:fmtInt.format(value)}), dom("span", {className:"muted", text:note}));
  return dom("div", {className:"qualityKpis"}, lead,
    dom("div", {className:"kpiStack"},
      kpi("Registros escaneados", d.total_records_scanned, "en seis módulos"),
      kpi("Auto-corregidas", d.auto_fixed_count, "normalizadas sin alterar importes"),
      kpi("Pendientes de revisión", d.pending_review_count, "requieren decisión humana")));
}
function qualityModules(d) {
  // Mosaicos compactos: seis módulos caben en dos columnas en el teléfono sin una tabla larga
  const tiles = QUALITY_MODULES.map(([key, label]) => {
    const m = d.summary_by_module?.[key] || {scanned:0, auto_fixed:0, pending_review:0};
    return dom("li", {className:"moduleTile"},
      dom("span", {className:"moduleName", text:label}),
      dom("strong", {className:"num", text:fmtInt.format(m.scanned)}),
      dom("span", {className:"muted moduleUnit", text:m.scanned === 1 ? "registro escaneado" : "registros escaneados"}),
      dom("span", {className:"moduleBadges"},
        m.auto_fixed ? pillBadge("ok", "check", fmtInt.format(m.auto_fixed) + (m.auto_fixed === 1 ? " corregida" : " corregidas")) : null,
        m.pending_review ? pillBadge("warn", "clock", fmtInt.format(m.pending_review) + (m.pending_review === 1 ? " pendiente" : " pendientes")) : null,
        !m.auto_fixed && !m.pending_review ? pillBadge("", "dot", "Sin incidencias") : null));
  });
  return dom("section", {className:"card", "aria-labelledby":"modulesTitle"},
    dom("div", {className:"cardHead"}, dom("h2", {id:"modulesTitle", text:"Resumen por módulo"})),
    dom("ul", {className:"moduleGrid"}, tiles));
}
function issueValue(text) {
  return text == null || text === "" ? dom("span", {className:"muted", text:"Vacío"}) : dom("code", {className:"valueCode", text:String(text)});
}
function drawIssues() {
  const card = $("#issuesCard"), d = analytics.quality;
  if (!card || !d) return;
  const list = (d.issues || []).filter(i => (analytics.qModule === "all" || i.module === analytics.qModule) && (analytics.qStatus === "all" || i.status === analytics.qStatus));
  const moduleName = key => (QUALITY_MODULES.find(([k]) => k === key) || [key, key])[1];
  const filters = dom("div", {className:"issueFilters"},
    segmented("Filtrar por módulo", [["all", "Todos los módulos"], ...QUALITY_MODULES], analytics.qModule, key => { analytics.qModule = key; analytics.qShown = 20; drawIssues(); }),
    segmented("Filtrar por estado", [["all", "Todos los estados"], ["auto_fixed", "Auto-corregidas"], ["pending_review", "Pendientes"], ["resolved", "Resueltas"]], analytics.qStatus,
      key => { analytics.qStatus = key; analytics.qShown = 20; drawIssues(); }));
  const head = dom("div", {className:"cardHead"}, dom("h2", {id:"issuesTitle", text:"Incidencias"}),
    dom("span", {className:"muted", text:fmtInt.format(list.length) + " de " + fmtInt.format(d.issues_found ?? (d.issues || []).length)}));
  let body;
  if (!list.length) {
    body = dom("div", {className:"emptyState compact"}, dom("h2", {text:(d.issues || []).length ? "Ninguna incidencia coincide" : "Sin incidencias"}),
      dom("p", {className:"muted", text:(d.issues || []).length ? "Prueba con otro módulo o estado." : "La última auditoría no encontró problemas."}));
  } else {
    const rows = list.slice(0, analytics.qShown).map(i => {
      const [st, sti, stl] = QUALITY_STATUS[i.status] || ["", "dot", i.status];
      const [sv, svi, svl] = QUALITY_SEVERITY[i.severity] || ["", "dot", i.severity];
      const related = i.details?.related_entity_ids;
      return dom("tr", {},
        dom("td", {}, dom("span", {className:"cellMain", text:moduleName(i.module)}), dom("span", {className:"cellSub", text:"Registro #" + i.entity_id + (i.details?.field ? " · " + i.details.field : "")})),
        dom("td", {}, dom("span", {text:QUALITY_ISSUE[i.issue_type] || i.issue_type}),
          related?.length ? dom("span", {className:"cellSub", text:"Relacionado con #" + related.join(", #")}) : null),
        dom("td", {}, pillBadge(sv, svi, svl)),
        dom("td", {className:"cellWide"}, dom("span", {className:"beforeAfter"},
          dom("span", {}, dom("span", {className:"baLabel", text:"Original"}), issueValue(i.original_value)),
          dom("span", {}, dom("span", {className:"baLabel", text:"Normalizado"}), i.normalized_value == null ? dom("span", {className:"muted", text:"Sin propuesta"}) : issueValue(i.normalized_value)))),
        dom("td", {}, dom("span", {className:"issueState"}, pillBadge(st, sti, stl),
          i.status === "pending_review"
            ? dom("button", {type:"button", className:"btn secondary small", "data-resolve-issue":i.id, text:"Marcar resuelta"})
            : null)));
    });
    body = dom("div", {className:"tableWrap"}, dom("table", {className:"issuesTable"},
      dom("thead", {}, dom("tr", {}, ["Módulo y origen", "Problema", "Severidad", "Valor original y normalizado", "Estado"].map(t => dom("th", {scope:"col", text:t})))),
      dom("tbody", {}, rows)));
  }
  const more = list.length > analytics.qShown
    ? dom("div", {className:"pager"}, dom("span", {text:"Mostrando " + analytics.qShown + " de " + list.length}),
        dom("button", {type:"button", className:"btn secondary small", "data-more-issues":"", text:"Mostrar más"}))
    : null;
  card.replaceChildren(...[head, dom("div", {className:"cardPad"}, filters), body, more].filter(Boolean));
  card.onclick = event => {
    const button = event.target.closest("[data-resolve-issue]");
    if (button && !button.disabled) resolveIssue(Number(button.dataset.resolveIssue), button);
  };
  more?.querySelector("button").addEventListener("click", () => { analytics.qShown += 20; drawIssues(); });
}
/* POST /admin/data-quality/issues/{id}/resolve: cierra una incidencia corregida a mano */
async function resolveIssue(issueId, button) {
  setBusy(button, true, "Guardando…");
  try {
    const {issue} = await api("/admin/data-quality/issues/" + issueId + "/resolve", {method:"POST", body:{}});
    const item = (analytics.quality?.issues || []).find(i => i.id === issue.id);
    if (item) item.status = issue.status;
    toast("Incidencia marcada como resuelta.");
    drawIssues();
  } catch (err) {
    if (err.status !== 401) toast(err.message || "No pudimos actualizar la incidencia.");
    if (button.isConnected) setBusy(button, false);
  }
}
async function runAudit(button) {
  if (button.disabled) return;
  setBusy(button, true, "Auditando…");
  try {
    const report = await api("/admin/data-quality/audit", {method:"POST", body:{}});
    analytics.qModule = "all"; analytics.qStatus = "all"; analytics.qShown = 20;
    toast("Auditoría lista: puntaje " + fmtDec.format(report.quality_score) + ", " + report.auto_fixed_count + " corregidas, " + report.pending_review_count + " pendientes.");
    const panel = $("#analyticsPanel");
    if (panel && analytics.sub === "calidad") await renderQuality(panel);
    $("#runAudit")?.focus();
  } catch (err) {
    if (err.status !== 401) toast(err.message || "No pudimos ejecutar la auditoría.");
  } finally {
    if (button.isConnected) setBusy(button, false);
  }
}

/* ======================= 2. Perfiles y anomalias ======================= */
async function renderProfiles(panel) {
  // POST recalcula y guarda las alertas para que tengan ID estable; GET quedó como lectura pura
  const data = analytics.users = await api("/admin/analytics/users", {method:"POST", body:{}});
  if (stale(panel, "perfiles")) return;
  panel.replaceChildren(
    dom("div", {className:"panelBar"},
      segmented("Rol", [["customer", "Clientes"], ["employee", "Empleados"]], analytics.role, role => { analytics.role = role; analytics.focusUser = null; drawProfiles(); }),
      dom("p", {className:"muted", text:"Cercas de Tukey a 1,5 × IQR. El puntaje describe magnitud relativa, no probabilidad de fraude."})),
    dom("div", {id:"profilesBody", className:"profilesBody"}));
  drawProfiles();
}
function drawProfiles() {
  const box = $("#profilesBody"), data = analytics.users;
  if (!box || !data) return;
  const role = analytics.role;
  const profiles = (data.profiles || []).filter(p => p.user_role === role);
  const focus = profiles.find(p => p.user_id === analytics.focusUser) || null;
  const plot = focus ? focus.amount_boxplot : data.global_boxplots?.[role];
  const who = focus ? focus.name : (role === "customer" ? "Todos los clientes" : "Todos los empleados");
  const alerts = (data.alerts || []).filter(a => a.user_role === role);
  // Orden por puntaje sin mutar la respuesta (merge sort del navegador es estable)
  const ranked = [...alerts].sort((a, b) => b.anomaly_score - a.anomaly_score || a.id - b.id);
  const chartCard = dom("section", {className:"card boxCard", "aria-labelledby":"boxTitle"},
    dom("div", {className:"cardHead"},
      dom("div", {}, dom("h2", {id:"boxTitle", text:"Distribución de montos"}), dom("p", {className:"muted", text:who + " · COP por operación"})),
      focus ? dom("button", {type:"button", className:"btn secondary small", "data-box-reset":"", text:"Ver todo el rol"}) : null));
  const plotBox = dom("div", {className:"plotBox"});
  chartCard.append(plotBox);
  if (plot) {
    responsiveChart(plotBox, w => drawBoxplot(plotBox, plot, w));
    chartCard.append(boxStats(plot));
  } else {
    plotBox.append(dom("p", {className:"muted chartEmpty", text:"Sin operaciones para graficar."}));
  }
  box.replaceChildren(
    dom("div", {className:"profilesGrid"}, chartCard, alertsPanel(ranked, data.profiles || [])),
    profilesTable(profiles, role));
  $("[data-box-reset]", box)?.addEventListener("click", () => { analytics.focusUser = null; drawProfiles(); $("#boxTitle")?.scrollIntoView({block:"nearest"}); });
}
function boxStats(p) {
  const min = Math.min(p.whisker_min, ...(p.outliers || []));
  const max = Math.max(p.whisker_max, ...(p.outliers || []));
  const items = [["Mínimo", money(min)], ["Q1", money(p.q1)], ["Mediana (Q2)", money(p.median)], ["Q3", money(p.q3)], ["Máximo", money(max)],
    ["IQR", money(p.iqr)], ["Cerca inferior", money(p.lower)], ["Cerca superior", money(p.upper)], ["Observaciones", fmtInt.format(p.n)], ["Atípicos", fmtInt.format((p.outliers || []).length)]];
  return dom("dl", {className:"boxStats"}, items.map(([k, v]) => dom("div", {}, dom("dt", {text:k}), dom("dd", {text:v}))));
}
function drawBoxplot(wrap, p, width) {
  wrap.replaceChildren();
  const outliers = p.outliers || [];
  const lo = Math.min(p.lower, p.whisker_min, ...outliers), hi = Math.max(p.upper, p.whisker_max, ...outliers);
  const ticks = niceTicks(lo, hi, width < 480 ? 3 : 5);
  const t0 = ticks[0], t1 = ticks[ticks.length - 1];
  const H = 168, padL = 16, padR = 16, top = 34, mid = 84, boxH = 40;
  const x = v => padL + (width - padL - padR) * (v - t0) / (t1 - t0 || 1);
  const svg = svgEl("svg", {viewBox:`0 0 ${width} ${H}`, width, height:H, class:"boxplot", role:"group",
    "aria-label":`Boxplot: mínimo ${money(Math.min(p.whisker_min, ...outliers))}, Q1 ${money(p.q1)}, mediana ${money(p.median)}, Q3 ${money(p.q3)}, máximo ${money(Math.max(p.whisker_max, ...outliers))}, ${outliers.length} atípicos`});
  for (const t of ticks) {
    svg.append(svgEl("line", {x1:x(t), x2:x(t), y1:top - 8, y2:H - 30, class:"gridLine"}),
      svgEl("text", {x:x(t), y:H - 10, "text-anchor":t === t0 ? "start" : t === t1 ? "end" : "middle", class:"axisText"}, compactMoney(t)));
  }
  for (const [v, label] of [[p.lower, "Cerca inf."], [p.upper, "Cerca sup."]]) {
    svg.append(svgEl("line", {x1:x(v), x2:x(v), y1:top - 6, y2:mid + boxH / 2 + 10, class:"fenceLine"}),
      svgEl("text", {x:x(v), y:top - 14, "text-anchor":x(v) < 60 ? "start" : x(v) > width - 60 ? "end" : "middle", class:"axisText"}, label));
  }
  svg.append(svgEl("line", {x1:x(p.whisker_min), x2:x(p.q1), y1:mid, y2:mid, class:"whisker"}),
    svgEl("line", {x1:x(p.q3), x2:x(p.whisker_max), y1:mid, y2:mid, class:"whisker"}),
    svgEl("line", {x1:x(p.whisker_min), x2:x(p.whisker_min), y1:mid - 10, y2:mid + 10, class:"whisker"}),
    svgEl("line", {x1:x(p.whisker_max), x2:x(p.whisker_max), y1:mid - 10, y2:mid + 10, class:"whisker"}),
    svgEl("rect", {x:x(p.q1), y:mid - boxH / 2, width:Math.max(2, x(p.q3) - x(p.q1)), height:boxH, rx:4, class:"boxBody"}),
    svgEl("line", {x1:x(p.median), x2:x(p.median), y1:mid - boxH / 2, y2:mid + boxH / 2, class:"medianLine"}));
  const tip = chartTip(wrap);
  const hit = svgEl("rect", {x:x(p.whisker_min) - 6, y:mid - boxH / 2 - 6, width:Math.max(12, x(p.whisker_max) - x(p.whisker_min) + 12), height:boxH + 12,
    class:"hitArea", tabindex:"0", role:"img", "aria-label":"Caja: Q1 " + money(p.q1) + ", mediana " + money(p.median) + ", Q3 " + money(p.q3)});
  const boxTip = () => tip.show(x(p.median), mid - boxH / 2, "Caja y bigotes", [["Mínimo", money(p.whisker_min)], ["Q1", money(p.q1)], ["Mediana", money(p.median)], ["Q3", money(p.q3)], ["Máximo", money(p.whisker_max)]]);
  hit.addEventListener("pointerenter", boxTip); hit.addEventListener("focus", boxTip);
  hit.addEventListener("pointerleave", tip.hide); hit.addEventListener("blur", tip.hide);
  svg.append(hit);
  outliers.forEach((v, i) => {
    const jitter = (i % 3 - 1) * 8;
    const dot = svgEl("circle", {cx:x(v), cy:mid + jitter, r:6, class:"outlierDot", tabindex:"0", role:"img", "aria-label":"Atípico " + money(v)});
    const show = () => tip.show(x(v), mid + jitter - 6, "Valor atípico", [["Monto", money(v)], ["Cerca superior", money(p.upper)], ["Exceso", money(Math.max(0, v - p.upper))]]);
    dot.addEventListener("pointerenter", show); dot.addEventListener("focus", show);
    dot.addEventListener("pointerleave", tip.hide); dot.addEventListener("blur", tip.hide);
    svg.append(dot);
  });
  wrap.prepend(svg);
}
const compactMoney = v => {
  const a = Math.abs(v), sign = v < 0 ? "-" : "";
  if (a >= 1e6) return sign + "$" + fmtDec.format(a / 1e6) + " M";
  if (a >= 1e3) return sign + "$" + fmtDec.format(a / 1e3) + " mil";
  return sign + "$" + fmtDec.format(a);
};
function alertsPanel(ranked, profiles) {
  const nameOf = a => profiles.find(p => p.user_id === a.user_id && p.user_role === a.user_role)?.name || "Usuario #" + a.user_id;
  const card = dom("section", {className:"card alertsCard", "aria-labelledby":"alertsTitle"},
    dom("div", {className:"cardHead"}, dom("h2", {id:"alertsTitle", text:"Alertas explicadas"}),
      ranked.length ? pillBadge("warn", "alert", fmtInt.format(ranked.length)) : pillBadge("ok", "check", "Sin alertas")));
  if (!ranked.length) {
    card.append(dom("p", {className:"muted", text:"Ninguna cuenta de este rol supera su cerca superior. Las alertas necesitan al menos cuatro observaciones."}));
    return card;
  }
  const list = dom("ol", {className:"alertList"});
  for (const a of ranked) {
    const t = a.threshold_info || {};
    const score = Math.max(0, Math.min(100, Number(a.anomaly_score) || 0));
    const meter = dom("div", {className:"scoreMeter", role:"meter", "aria-valuemin":"0", "aria-valuemax":"100", "aria-valuenow":String(score), "aria-label":"Puntaje de anomalía"},
      dom("span", {className:"meterFill " + (score >= 70 ? "bad" : score >= 40 ? "warn" : "info")}));
    meter.firstChild.style.width = score + "%";
    const sources = Object.entries(a.source_record_ids || {}).flatMap(([key, ids]) =>
      (ids || []).map(id => dom("span", {className:"sourceChip", text:(SOURCE_LABEL[key] || key) + " #" + id})));
    const isMoney = a.alert_type === "high_amount_outlier";
    const fmtT = v => v == null ? "Sin dato" : isMoney ? money(v) : fmtDec.format(v);
    list.append(dom("li", {className:"alertItem"},
      dom("div", {className:"alertTop"},
        dom("div", {}, dom("span", {className:"cellMain", text:nameOf(a)}), dom("span", {className:"cellSub", text:ALERT_TYPE[a.alert_type] || a.alert_type})),
        dom("div", {className:"alertScore"}, dom("strong", {className:"num", text:fmtDec.format(score)}), dom("span", {className:"muted", text:"/ 100"}))),
      meter,
      dom("p", {className:"alertWhy", text:a.explanation}),
      dom("dl", {className:"alertThresholds"},
        [["Q1", fmtT(t.q1)], ["Q3", fmtT(t.q3)], ["IQR", fmtT(t.iqr)], ["Cerca sup.", fmtT(t.upper)]].map(([k, v]) => dom("div", {}, dom("dt", {text:k}), dom("dd", {text:v})))),
      sources.length ? dom("div", {className:"sourceRow"}, dom("span", {className:"baLabel", text:"Registros de origen"}), dom("span", {className:"sourceChips"}, sources)) : null));
  }
  card.append(list);
  return card;
}
/* Solo cuentan las facturas con descuento real; la media se calcula sobre ellas */
function discountSummary(list) {
  const applied = list.filter(d => Number(d.amount) > 0);
  if (!applied.length) return "Ninguno";
  const avg = applied.reduce((s, d) => s + (Number(d.percent) || 0), 0) / applied.length;
  return fmtInt.format(applied.length) + " de " + fmtInt.format(list.length) + " · media " + fmtPct(avg);
}
function profilesTable(profiles, role) {
  const card = dom("section", {className:"card flush", "aria-labelledby":"profilesTitle"},
    dom("div", {className:"cardHead"}, dom("h2", {id:"profilesTitle", text:role === "customer" ? "Perfiles de clientes" : "Perfiles de empleados"}),
      dom("span", {className:"muted", text:fmtInt.format(profiles.length) + " cuentas"})));
  if (!profiles.length) {
    card.append(dom("div", {className:"emptyState compact"}, dom("h2", {text:"Sin cuentas con este rol"}), dom("p", {className:"muted", text:"Los perfiles aparecen cuando existen cuentas activas."})));
    return card;
  }
  const sum = list => list.reduce((s, v) => s + (Number(v) || 0), 0);
  const heads = role === "customer"
    ? ["Cliente", "Pedidos", "Pedidos por día", "Monto mediano", "Total", "Canal", "Cancelaciones", "Distribución"]
    : ["Empleado", "Facturas", "Monto mediano", "Total facturado", "Anulaciones", "Descuentos", "Distribución"];
  const rows = profiles.map(p => {
    const ops = p.operations || [];
    const median = p.amount_boxplot ? money(p.amount_boxplot.median) : "Sin dato";
    const view = dom("button", {type:"button", className:"btn secondary small", "data-focus-user":p.user_id, "aria-pressed":String(analytics.focusUser === p.user_id),
      disabled:!p.amount_boxplot, text:analytics.focusUser === p.user_id ? "En la gráfica" : "Ver"});
    const cells = role === "customer"
      ? [fmtInt.format(p.operations_count), p.orders_per_day == null ? "Sin dato" : fmtDec.format(p.orders_per_day), median, money(sum(ops.map(o => o.amount))),
         CHANNEL_NAME[p.predominant_channel] || p.predominant_channel || "Sin dato", fmtPct((p.cancellation_rate ?? 0) * 100)]
      : [fmtInt.format(p.invoices_issued ?? p.operations_count), median, money(sum(ops.map(o => o.amount))), fmtPct((p.cancellation_rate ?? 0) * 100),
         discountSummary(p.discounts || [])];
    return dom("tr", {className:analytics.focusUser === p.user_id ? "rowFocus" : null},
      dom("td", {}, dom("span", {className:"cellMain", text:p.name}), dom("span", {className:"cellSub", text:"Cuenta #" + p.user_id})),
      ...cells.map(v => dom("td", {className:"num", text:v})),
      dom("td", {}, dom("div", {className:"rowActions"}, view)));
  });
  card.append(dom("div", {className:"tableWrap"}, dom("table", {className:"profilesTable"},
    dom("thead", {}, dom("tr", {}, heads.map(h => dom("th", {scope:"col", text:h})))), dom("tbody", {}, rows))));
  card.addEventListener("click", e => {
    const b = e.target.closest("[data-focus-user]");
    if (!b || b.disabled) return;
    analytics.focusUser = Number(b.dataset.focusUser);
    drawProfiles();
    $("#boxTitle")?.scrollIntoView({block:"start", behavior:matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"});
  });
  return card;
}

/* ======================= 3. Demanda ======================= */
const periodDate = s => new Date(s + "T12:00:00-05:00");
const dayFmt = new Intl.DateTimeFormat("es-CO", {day:"numeric", month:"short", timeZone:"America/Bogota"});
const periodLabel = (s, period) => (period === "weekly" ? "Semana del " : "") + dayFmt.format(periodDate(s));
async function renderDemand(panel) {
  const horizon = analytics.period === "weekly" ? 4 : 7;
  const data = analytics.demand = await api("/admin/analytics/demand?period=" + analytics.period + "&horizon=" + horizon);
  if (stale(panel, "demanda")) return;
  const products = data.products || [];
  if (analytics.product !== "global" && !products.some(p => String(p.product_id) === analytics.product)) analytics.product = "global";
  const tpl = document.createElement("template");
  // listbox() escapa cada nombre con esc(); es el componente accesible del panel (sin <select> nativo)
  tpl.innerHTML = listbox({name:"demandProduct", label:"Producto", value:analytics.product,
    options:[{value:"global", label:"Todos los productos (global)"}, ...products.map(p => ({value:String(p.product_id), label:p.name}))]});
  const picker = tpl.content.firstElementChild;
  picker.classList.add("demandPicker");
  setupListbox(picker);
  $("input", picker).addEventListener("change", e => { analytics.product = e.target.value; drawDemand(); });
  panel.replaceChildren(
    dom("div", {className:"panelBar demandBar"},
      segmented("Período", [["daily", "Diaria"], ["weekly", "Semanal"]], analytics.period, period => { analytics.period = period; showAnalytics("demanda"); }),
      picker),
    dom("div", {id:"demandBody", className:"demandBody"}));
  drawDemand();
}
function drawDemand() {
  const box = $("#demandBody"), data = analytics.demand;
  if (!box || !data) return;
  const series = analytics.product === "global" ? data.global : (data.products || []).find(p => String(p.product_id) === analytics.product);
  const title = analytics.product === "global" ? "Demanda global" : series?.name || "Producto";
  if (!series || !(series.history || []).length) {
    box.replaceChildren(dom("div", {className:"card emptyState compact"}, dom("h2", {text:"Aún no hay ventas para estimar"}),
      dom("p", {className:"muted", text:"La serie usa pedidos confirmados, en preparación, enviados o entregados. Cuando existan ventas aparecerá aquí."})));
    return;
  }
  const chart = dom("section", {className:"card demandCard", "aria-labelledby":"demandTitle"},
    dom("div", {className:"cardHead"}, dom("div", {}, dom("h2", {id:"demandTitle", text:title}),
      dom("p", {className:"muted", text:"Unidades vendidas por " + (data.period === "weekly" ? "semana" : "día") + " · " + series.history.length + " períodos"}))),
    demandLegend());
  const plotBox = dom("div", {className:"plotBox"});
  chart.append(plotBox, demandTable(series, data.period));
  box.replaceChildren(chart, demandMetrics(series, data.period));
  responsiveChart(plotBox, w => drawDemandChart(plotBox, series, data.period, w));
}
function demandLegend() {
  const item = (cls, text) => {
    const s = svgEl("svg", {viewBox:"0 0 24 8", width:24, height:8, "aria-hidden":"true"});
    s.append(svgEl("line", {x1:0, x2:24, y1:4, y2:4, class:cls}));
    return dom("li", {}, s, text);
  };
  return dom("ul", {className:"chartLegend"}, item("lineObserved", "Demanda observada"), item("lineEstimated", "Estimada por regresión lineal"), item("lineForecast", "Proyección"));
}
function drawDemandChart(wrap, s, period, width) {
  wrap.replaceChildren();
  const hist = s.history, fc = s.forecast || [];
  const points = [...hist.map(h => ({period:h.period, observed:h.observed, estimated:h.estimated, split:h.split})),
    ...fc.map(f => ({period:f.period, predicted:f.predicted, split:"forecast"}))];
  const n = points.length;
  const vals = points.flatMap(p => [p.observed, p.estimated, p.predicted]).filter(v => v != null);
  const ticks = niceTicks(Math.min(0, ...vals), Math.max(1, ...vals), 4);
  const y0 = ticks[0], y1 = ticks[ticks.length - 1];
  const H = Math.round(width < 480 ? 240 : 300), padL = 40, padR = 12, top = 28, bottom = 34;
  const x = i => n === 1 ? (padL + width - padR) / 2 : padL + (width - padL - padR) * i / (n - 1);
  const y = v => top + (H - top - bottom) * (1 - (v - y0) / (y1 - y0 || 1));
  const svg = svgEl("svg", {viewBox:`0 0 ${width} ${H}`, width, height:H, class:"demandChart", tabindex:"0", role:"img",
    "aria-label":"Demanda observada frente a estimada. Usa las flechas para recorrer los períodos."});
  const trainEnd = s.train_periods ? s.train_periods - 1 : -1;
  const zones = [];
  if (s.test_periods) zones.push(["Evaluación", trainEnd + 0.5, hist.length - 0.5, "zoneTest"]);
  if (fc.length) zones.push(["Proyección", hist.length - 0.5, n - 0.5, "zoneForecast"]);
  if (s.train_periods) zones.unshift(["Entrenamiento", -0.5, trainEnd + 0.5, "zoneTrain"]);
  const zx = i => Math.max(padL, Math.min(width - padR, n === 1 ? x(0) : padL + (width - padL - padR) * i / (n - 1)));
  for (const [label, a, b, cls] of zones) {
    const xa = zx(a), xb = zx(b);
    svg.append(svgEl("rect", {x:xa, y:top - 4, width:Math.max(0, xb - xa), height:H - top - bottom + 4, class:"zone " + cls}));
    if (xb - xa > 56) svg.append(svgEl("text", {x:xa + 6, y:top - 10, class:"axisText zoneLabel"}, label));
  }
  for (const t of ticks) {
    svg.append(svgEl("line", {x1:padL, x2:width - padR, y1:y(t), y2:y(t), class:t === 0 ? "baseLine" : "gridLine"}),
      svgEl("text", {x:padL - 8, y:y(t) + 4, "text-anchor":"end", class:"axisText"}, fmtDec.format(t)));
  }
  const labelEvery = Math.max(1, Math.ceil(n / Math.max(2, Math.floor((width - padL - padR) / 84))));
  points.forEach((p, i) => {
    if (i % labelEvery === 0 || i === n - 1) {
      if (i !== n - 1 && n - 1 - i < labelEvery) return; // la ultima etiqueta siempre va; la anterior cede si chocan
      svg.append(svgEl("text", {x:x(i), y:H - 12, "text-anchor":i === 0 ? "start" : i === n - 1 ? "end" : "middle", class:"axisText"}, dayFmt.format(periodDate(p.period))));
    }
  });
  const path = (list, key) => list.filter(([, v]) => v != null).map(([i, v]) => x(i) + "," + y(v)).join(" ");
  const histIdx = hist.map((h, i) => [i, h]);
  svg.append(svgEl("polyline", {points:path(histIdx.map(([i, h]) => [i, h.estimated]), "e"), class:"lineEstimated"}));
  if (fc.length) {
    const last = hist[hist.length - 1];
    const lead = last.estimated != null ? [[hist.length - 1, last.estimated]] : [];
    svg.append(svgEl("polyline", {points:path([...lead, ...fc.map((f, j) => [hist.length + j, f.predicted])]), class:"lineForecast"}));
  }
  svg.append(svgEl("polyline", {points:path(histIdx.map(([i, h]) => [i, h.observed])), class:"lineObserved"}));
  if (n <= 40) histIdx.forEach(([i, h]) => svg.append(svgEl("circle", {cx:x(i), cy:y(h.observed), r:3, class:"dotObserved"})));
  const cross = svgEl("line", {y1:top - 4, y2:H - bottom, class:"crosshair", visibility:"hidden"});
  const mObs = svgEl("circle", {r:5, class:"markObserved", visibility:"hidden"});
  const mEst = svgEl("circle", {r:5, class:"markEstimated", visibility:"hidden"});
  svg.append(cross, mEst, mObs);
  const hit = svgEl("rect", {x:padL, y:top - 4, width:width - padL - padR, height:H - top - bottom + 4, class:"hitArea"});
  svg.append(hit);
  wrap.append(svg);
  const tip = chartTip(wrap);
  let active = -1;
  const show = i => {
    active = Math.max(0, Math.min(n - 1, i));
    const p = points[active], cx = x(active);
    cross.setAttribute("x1", cx); cross.setAttribute("x2", cx); cross.setAttribute("visibility", "visible");
    const est = p.split === "forecast" ? p.predicted : p.estimated;
    if (p.observed != null) { mObs.setAttribute("cx", cx); mObs.setAttribute("cy", y(p.observed)); mObs.setAttribute("visibility", "visible"); }
    else mObs.setAttribute("visibility", "hidden");
    if (est != null) { mEst.setAttribute("cx", cx); mEst.setAttribute("cy", y(est)); mEst.setAttribute("visibility", "visible"); }
    else mEst.setAttribute("visibility", "hidden");
    const zone = {train:"Entrenamiento", test:"Evaluación", forecast:"Proyección"}[p.split] || "";
    const lines = [];
    if (p.observed != null) lines.push(["Reales", fmtDec.format(p.observed) + " u.", "swObserved"]);
    if (est != null) lines.push([p.split === "forecast" ? "Proyectadas" : "Estimadas", fmtDec.format(est) + " u.", p.split === "forecast" ? "swForecast" : "swEstimated"]);
    tip.show(cx, Math.min(...[p.observed, est].filter(v => v != null).map(y)), periodLabel(p.period, period) + (zone ? " · " + zone : ""), lines);
  };
  const hide = () => { active = -1; tip.hide(); [cross, mObs, mEst].forEach(el => el.setAttribute("visibility", "hidden")); };
  const nearest = e => {
    const rect = svg.getBoundingClientRect();
    const px = (e.clientX - rect.left) * (width / rect.width);
    return n === 1 ? 0 : Math.round((px - padL) / ((width - padL - padR) / (n - 1)));
  };
  hit.addEventListener("pointermove", e => show(nearest(e)));
  hit.addEventListener("pointerleave", hide);
  svg.addEventListener("focus", () => show(active < 0 ? hist.length - 1 : active));
  svg.addEventListener("blur", hide);
  svg.addEventListener("keydown", e => {
    const step = {ArrowRight:1, ArrowLeft:-1}[e.key];
    if (step) { e.preventDefault(); show((active < 0 ? hist.length - 1 : active) + step); }
    else if (e.key === "Home") { e.preventDefault(); show(0); }
    else if (e.key === "End") { e.preventDefault(); show(n - 1); }
    else if (e.key === "Escape") hide();
  });
}
function demandTable(s, period) {
  const rows = [...s.history.map(h => [h.period, h.observed, h.estimated, {train:"Entrenamiento", test:"Evaluación"}[h.split] || h.split]),
    ...(s.forecast || []).map(f => [f.period, null, f.predicted, "Proyección"])];
  return dom("details", {className:"dataDetails"},
    dom("summary", {text:"Ver los datos de la gráfica"}),
    dom("div", {className:"tableWrap"}, dom("table", {},
      dom("thead", {}, dom("tr", {}, ["Período", "Unidades reales", "Unidades estimadas", "Tramo"].map(t => dom("th", {scope:"col", text:t})))),
      dom("tbody", {}, rows.map(([p, o, e, z]) => dom("tr", {},
        dom("td", {text:periodLabel(p, period)}), dom("td", {className:"num", text:o == null ? "Sin dato" : fmtDec.format(o)}),
        dom("td", {className:"num", text:e == null ? "Sin dato" : fmtDec.format(e)}), dom("td", {text:z})))))));
}
function demandMetrics(s, period) {
  const m = s.metrics, model = s.model;
  const unit = period === "weekly" ? "u. por semana" : "u. por día";
  const metric = (label, value, note) => dom("div", {className:"metric"}, dom("dt", {text:label}), dom("dd", {}, dom("strong", {className:"num", text:value}), note ? dom("span", {className:"muted", text:note}) : null));
  const card = dom("section", {className:"card metricsCard", "aria-labelledby":"metricsTitle"},
    dom("div", {className:"cardHead"}, dom("h2", {id:"metricsTitle", text:"Métricas del modelo"}),
      dom("span", {className:"muted", text:(s.train_periods || 0) + " de entrenamiento · " + (s.test_periods || 0) + " de evaluación"})));
  if (s.short_series) {
    card.append(dom("p", {className:"shortNote"}, iconOf("alert"),
      dom("span", {text:"Serie corta: con menos de cinco períodos las métricas son orientativas" + (m ? "." : " y todavía no hay tramo de evaluación.")})));
  }
  if (!model) {
    card.append(dom("p", {className:"muted", text:"Con uno o ningún período no se puede ajustar una recta."}));
    return card;
  }
  const fmtM = v => v == null ? "No aplica" : fmtDec.format(v);
  card.append(dom("dl", {className:"metricGrid"},
    metric("MAE", m ? fmtM(m.mae) : "Sin dato", "unidades"),
    metric("RMSE", m ? fmtM(m.rmse) : "Sin dato", "unidades"),
    metric("R²", m ? fmtM(m.r2) : "Sin dato", m && m.r2 == null ? "varianza de prueba cero" : m && m.r2 < 0 ? "peor que la media" : null),
    metric("Pendiente (m)", fmtM(model.slope), unit),
    metric("Intercepto (b)", fmtM(model.intercept), "unidades en el primer período")));
  card.append(dom("p", {className:"muted modelNote", text:"Estimada = m · x + b, con x = 0 en el primer período. La proyección usa una recta ajustada con todo el histórico" +
    (s.forecast_model ? " (m = " + fmtDec.format(s.forecast_model.slope) + ", b = " + fmtDec.format(s.forecast_model.intercept) + ")" : "") + " y no baja de cero."}));
  return card;
}

/* ---------- Modelos IA: clasificador de fraude y regresor de demanda Keras (contrato en backend/PHASE5_API.md) ----------
   GET /admin/ml/status, POST /admin/ml/train {}, POST /admin/ml/predict/fraud {order_id|invoice_id|payment_id},
   GET /admin/ml/predict/demand?horizon. Reutiliza dom(), svgEl(), segmented(), chartTip(), responsiveChart() y niceTicks(). */
const ML_SIGNAL = {
  // Bloques que el backend explica juntos (PHASE5_API.md): hora, estado del hash, método y canal
  hour:"Hora del día", hash_state:"Integridad del hash", payment_method:"Método de pago", channel:"Canal de venta",
  log_amount:"Monto de la operación", log_prior_frequency:"Frecuencia previa de la cuenta", discount_fraction:"Descuento aplicado",
  cancellation_rate:"Tasa de cancelaciones", hash_invalid:"Integridad del hash (divergencia)", hash_unknown:"Integridad del hash (sin auditoría)",
  hour_sin:"Hora del día", hour_cos:"Hora del día", efectivo:"Método: efectivo", tarjeta:"Método: tarjeta", transferencia:"Método: transferencia",
  pse:"Método: PSE", nequi:"Método: Nequi", presencial:"Canal: presencial", web:"Canal: web", app:"Canal: app", domicilio:"Canal: domicilio"
};
const ML_REF = [["order_id", "Pedido"], ["invoice_id", "Factura"], ["payment_id", "Pago"]];
const ML_ERROR = {
  model_not_trained:"Todavía no hay modelos entrenados.", training_busy:"Ya hay un entrenamiento en curso.", ml_unavailable:"Este despliegue no incluye TensorFlow: los modelos se entrenan y consultan en el backend con Docker.", training_stalled:"El entrenamiento anterior no terminó. Vuelve a iniciarlo.",
  insufficient_test:"No hay suficientes datos en el tramo de prueba.", insufficient_history:"No hay historial suficiente para entrenar.",
  invalid_label_file:"El archivo de etiquetas adjudicadas no es válido.", artifact_unavailable:"Los archivos del modelo no están disponibles."
};
const ml = {status:null, ref:"order_id", product:null, demand:null, recent:null};
const pctFmt = new Intl.NumberFormat("es-CO", {style:"percent", maximumFractionDigits:1});
const mlPct = v => v == null ? "Sin dato" : pctFmt.format(v);
const probText = p => p == null ? "Sin dato" : p > 0 && p < 0.001 ? "menos de 0,1 %" : p > 0.999 && p < 1 ? "más de 99,9 %" : pctFmt.format(p);
const mlErr = err => ML_ERROR[err.data?.error] || err.message;

async function renderModels(view) {
  if (state.me?.role !== "admin") return;
  const train = dom("button", {type:"button", className:"btn primary", id:"trainModels", text:"Entrenar / Actualizar modelos"});
  train.addEventListener("click", () => trainModels(train));
  view.replaceChildren(dom("div", {className:"mlView"},
    dom("div", {className:"viewHead"},
      dom("div", {}, dom("h1", {text:"Modelos IA"}),
        dom("p", {text:"Redes neuronales Keras para estimar fraude y demanda, evaluadas en un tramo de prueba cronológico que el entrenamiento nunca ve."})),
      dom("div", {}, train)),
    dom("p", {id:"mlLive", className:"sr", role:"status", "aria-live":"polite"}),
    dom("div", {id:"mlBody", className:"mlBody"})));
  await loadModels();
}
async function loadModels() {
  const body = $("#mlBody");
  if (!body) return;
  body.setAttribute("aria-busy", "true");
  try {
    ml.status = await api("/admin/ml/status");
    if (!body.isConnected) return;
    if (ml.status.training?.state === "running") resumeTraining();
    const fraud = ml.status.models?.fraud_classifier, demand = ml.status.models?.demand_regressor;
    if (!fraud?.run && !demand?.run) {
      body.replaceChildren(dom("div", {className:"card emptyState mlEmpty"},
        dom("h2", {text:"Todavía no hay modelos entrenados"}),
        dom("p", {className:"muted", text:"Entrena para crear el clasificador de fraude y el regresor de demanda. El proceso tarda unos segundos y queda registrado con su versión y semilla."})));
      return;
    }
    body.replaceChildren(...[
      dom("section", {className:"mlSection", "aria-labelledby":"mlStatusTitle"},
        dom("h2", {id:"mlStatusTitle", className:"sectionTitle", text:"Estado y procedencia de los datos"}),
        dom("div", {className:"mlModels"}, modelCard("Clasificador de fraude", fraud, fraudProvenance), modelCard("Regresor de demanda", demand, demandProvenance))),
      fraud?.run ? fraudSection(fraud.run) : null,
      demand?.run ? dom("section", {className:"mlSection", id:"mlDemand", "aria-labelledby":"mlDemandTitle"},
        dom("h2", {id:"mlDemandTitle", className:"sectionTitle", text:"Demanda: Keras frente a regresión lineal"}),
        dom("div", {id:"mlDemandBody", className:"mlDemandBody"})) : null].filter(Boolean));
    if (demand?.run && ml.status.available !== false) loadDemandComparison();
  } catch (err) {
    if (err.status === 401 || !body.isConnected) return;
    const retry = dom("button", {type:"button", className:"btn secondary", text:"Reintentar"});
    retry.addEventListener("click", loadModels);
    body.replaceChildren(dom("div", {className:"card emptyState mlEmpty"}, dom("h2", {text:"No pudimos consultar los modelos"}), dom("p", {className:"muted", text:mlErr(err)}), retry));
  } finally {
    body.removeAttribute("aria-busy");
    // Despliegue sin TensorFlow (Vercel): se muestran las corridas registradas, pero no se entrena ni se predice
    if (ml.status?.available === false && body.isConnected) {
      if (!$(".mlUnavailable", body)) body.prepend(dom("p", {className:"shortNote mlUnavailable"}, iconOf("alert"), dom("span", {text:ML_ERROR.ml_unavailable})));
      const train = $("#trainModels");
      if (train) { train.disabled = true; train.title = ML_ERROR.ml_unavailable; }
    }
  }
}
async function trainModels(button) {
  if (button.disabled) return;
  setBusy(button, true, "Entrenando…");
  const live = $("#mlLive");
  if (live) live.textContent = "Entrenando los modelos. Puede tardar unos minutos.";
  try {
    const res = await api("/admin/ml/train", {method:"POST", body:{}});
    // 202: el servidor entrena en segundo plano (TensorFlow supera el timeout de gunicorn). 201: modo síncrono.
    const version = res.training ? await waitForTraining() : res.runs?.[0]?.version;
    finishTraining(version);
    await loadModels();
  } catch (err) {
    if (err.status === 401) return;
    toast(mlErr(err) || "No pudimos entrenar los modelos.");
    if (live) live.textContent = "";
  } finally {
    const current = $("#trainModels");
    if (current) setBusy(current, false);
  }
}
const ML_POLL_MS = 3000;
const ML_POLL_LIMIT = 400; // unos 20 minutos; después se puede volver a consultar recargando la pestaña
/* Consulta GET /ml/status hasta que el trabajo termine. Devuelve la versión o lanza el error del trabajo. */
async function waitForTraining() {
  for (let i = 0; i < ML_POLL_LIMIT; i++) {
    await new Promise(resolve => setTimeout(resolve, ML_POLL_MS));
    if (!$("#trainModels")) throw Object.assign(new Error(""), {status:401}); // salió de la pestaña: dejar de consultar
    const job = (await api("/admin/ml/status")).training;
    if (!job || job.state === "running") continue;
    if (job.state === "succeeded") return job.version;
    throw Object.assign(new Error(job.message || "El entrenamiento falló."), {status:409, data:{error:job.error}});
  }
  throw new Error("El entrenamiento sigue en curso. Vuelve a abrir la pestaña en unos minutos.");
}
function finishTraining(version) {
  const message = "Modelos entrenados" + (version ? ": versión " + version.slice(0, 8) : "") + ".";
  toast(message);
  const live = $("#mlLive");
  if (live) live.textContent = message;
}
/* Si se abre la pestaña con un entrenamiento en curso (otro administrador o una recarga), retoma la espera */
async function resumeTraining() {
  const button = $("#trainModels");
  if (!button || button.disabled) return;
  setBusy(button, true, "Entrenando…");
  try {
    finishTraining(await waitForTraining());
    await loadModels();
  } catch (err) {
    if (err.status !== 401) toast(mlErr(err) || "No pudimos completar el entrenamiento.");
  } finally {
    const current = $("#trainModels");
    if (current) setBusy(current, false);
  }
}

/* ======================= 1. Estado y procedencia ======================= */
function modelCard(title, model, provenance) {
  const run = model?.run;
  const card = dom("section", {className:"card mlModel", "aria-label":"Estado del " + title.toLowerCase()});
  if (!run) {
    card.append(dom("h3", {text:title}), pillBadge("warn", "clock", "Sin entrenar"), dom("p", {className:"muted", text:"Este modelo aún no tiene una versión registrada."}));
    return card;
  }
  const loadState = model.loaded ? ["ok", "check", "Cargado desde disco .keras"]
    : model.on_disk ? ["ok", "check", "Guardado en disco .keras"] : ["bad", "alert", "Archivo .keras no disponible"];
  const ds = run.dataset_summary || {};
  card.append(...[
    dom("div", {className:"mlModelHead"}, dom("h3", {text:title}), pillBadge(...loadState)),
    !model.loaded && model.on_disk ? dom("p", {className:"muted mlNote", text:"Se verifica su SHA-256 y se carga en memoria con la primera predicción."}) : null,
    dom("dl", {className:"mlFacts"},
      dom("div", {}, dom("dt", {text:"Versión"}), dom("dd", {}, hashCell(run.version, "versión del modelo"))),
      dom("div", {}, dom("dt", {text:"Entrenado"}), dom("dd", {text:fmtDate(run.trained_at)})),
      dom("div", {}, dom("dt", {text:"Semilla"}), dom("dd", {className:"num", text:String(run.seed)})),
      dom("div", {}, dom("dt", {text:"Épocas"}), dom("dd", {className:"num", text:ds.epochs == null ? "Sin dato" : String(ds.epochs)})),
      dom("div", {}, dom("dt", {text:"Motor"}), dom("dd", {text:"TensorFlow " + (ds.tensorflow || "?") + " · Keras " + (ds.keras || "?")}))),
    provenance(ds)].filter(Boolean)); // append() escribiria "null" como texto
  return card;
}
const sourceList = sources => Object.entries(sources || {}).map(([k, v]) => fmtInt.format(v) + (k === "real" ? " reales" : k === "simulated" ? " simulados" : " " + k)).join(" · ") || "Sin datos";
function fraudProvenance(ds) {
  const simulated = ds.simulated_labels || ["train", "test"].some(s => ds[s]?.label_sources?.simulated);
  const split = (label, s) => dom("div", {className:"splitRow"},
    dom("span", {className:"splitName", text:label}),
    dom("strong", {className:"num", text:fmtInt.format(s?.size ?? 0)}),
    dom("span", {className:"muted", text:sourceList(s?.label_sources) + " · " + mlPct(s?.fraud_fraction) + " fraude"}));
  return dom("div", {className:"provenance"},
    dom("div", {className:"provHead"}, dom("h4", {text:"Procedencia de las etiquetas"}),
      simulated ? pillBadge("info", "dot", "Incluye casos simulados documentados") : pillBadge("ok", "check", "Solo etiquetas reales")),
    split("Entrenamiento", ds.train), split("Prueba", ds.test),
    dom("p", {className:"muted provNote", text:"Corte cronológico: " + (ds.cutoff ? fmtDate(ds.cutoff) : "sin dato") + ". Pagos reales: " + fmtInt.format(ds.real_payments ?? 0) +
      ", adjudicados: " + fmtInt.format(ds.adjudicated ?? 0) + ", etiquetas tardías excluidas: " + fmtInt.format(ds.late_labels_excluded ?? 0) + "."}));
}
function demandProvenance(ds) {
  const simulated = ds.source === "simulated";
  return dom("div", {className:"provenance"},
    dom("div", {className:"provHead"}, dom("h4", {text:"Procedencia de los datos"}),
      simulated ? pillBadge("info", "dot", "Incluye casos simulados documentados") : pillBadge("ok", "check", "Ventas reales")),
    dom("div", {className:"splitRow"}, dom("span", {className:"splitName", text:"Entrenamiento"}), dom("strong", {className:"num", text:fmtInt.format(ds.train_size ?? 0)}),
      dom("span", {className:"muted", text:"producto-días · " + fmtInt.format(ds.training_examples ?? 0) + " ejemplos"})),
    dom("div", {className:"splitRow"}, dom("span", {className:"splitName", text:"Prueba"}), dom("strong", {className:"num", text:fmtInt.format(ds.test_size ?? 0)}),
      dom("span", {className:"muted", text:"producto-días reservados"})),
    dom("p", {className:"muted provNote", text:"Corte: " + (ds.cutoff || "sin dato") + ". " + fmtInt.format(ds.products ?? 0) + " productos, " +
      fmtInt.format(ds.real_sale_days ?? 0) + " días de venta reales" + (simulated ? "; serie sintética identificada porque el calendario real cubre menos de 14 días." : ".")}));
}

/* ======================= 2. Clasificador de fraude ======================= */
function fraudSection(run) {
  const m = run.metrics || {}, cm = m.confusion_matrix || {};
  const real = m.by_label_source?.real;
  const kpi = (label, value, note, lead) => dom("div", {className:"card mlKpi" + (lead ? " lead" : "")},
    dom("span", {className:"kpiLabel", text:label}), dom("strong", {className:"num", text:mlPct(value)}), dom("span", {className:"muted", text:note}));
  return dom("section", {className:"mlSection", "aria-labelledby":"mlFraudTitle"},
    dom("h2", {id:"mlFraudTitle", className:"sectionTitle", text:"Clasificador de fraude"}),
    real === null ? dom("p", {className:"shortNote"}, iconOf("alert"), dom("span", {text:"No hubo casos reales etiquetados en prueba: estas métricas describen el simulador, no el fraude real de la tienda."})) : null,
    dom("div", {className:"mlFraudGrid"},
      dom("div", {className:"mlKpis"},
        kpi("F1-Score", m.f1, "equilibrio entre precisión y sensibilidad", true),
        kpi("Precisión", m.precision, "de lo marcado como fraude, cuánto lo era"),
        kpi("Sensibilidad (Recall)", m.recall, "del fraude real, cuánto se detectó")),
      confusionMatrix(cm, run.dataset_summary?.test?.size)),
    fraudEvaluator());
}
function confusionMatrix(cm, size) {
  const total = (cm.tp || 0) + (cm.fp || 0) + (cm.tn || 0) + (cm.fn || 0);
  const max = Math.max(1, cm.tp || 0, cm.fp || 0, cm.tn || 0, cm.fn || 0);
  const cell = (key, title, ok) => {
    const value = cm[key] || 0;
    const el = dom("div", {className:"cmCell " + (ok ? "hit" : "miss"), role:"cell"},
      dom("span", {className:"cmCode", text:key.toUpperCase()}),
      dom("strong", {className:"num", text:fmtInt.format(value)}),
      dom("span", {className:"cmLabel", text:title}),
      dom("span", {className:"cmShare muted", text:total ? pctFmt.format(value / total) : "0 %"}));
    // Intensidad proporcional al recuento, un solo tono (escala secuencial)
    el.style.setProperty("--cm-mix", Math.round(8 + 42 * value / max) + "%");
    return el;
  };
  return dom("section", {className:"card cmCard", "aria-labelledby":"cmTitle"},
    dom("div", {className:"cardHead"}, dom("h3", {id:"cmTitle", text:"Matriz de confusión"}),
      dom("span", {className:"muted", text:fmtInt.format(size ?? total) + " casos de prueba · umbral 0,5"})),
    dom("div", {className:"cmGrid", role:"table", "aria-label":"Matriz de confusión: filas reales, columnas predichas"},
      dom("div", {role:"row", className:"cmRow cmHeadRow"},
        dom("span", {role:"columnheader", className:"cmCorner", text:"Real \\ Predicho"}),
        dom("span", {role:"columnheader", className:"cmAxis", text:"Fraudulenta"}),
        dom("span", {role:"columnheader", className:"cmAxis", text:"Normal"})),
      dom("div", {role:"row", className:"cmRow"},
        dom("span", {role:"rowheader", className:"cmAxis", text:"Fraudulenta"}),
        cell("tp", "Verdaderos positivos", true), cell("fn", "Falsos negativos", false)),
      dom("div", {role:"row", className:"cmRow"},
        dom("span", {role:"rowheader", className:"cmAxis", text:"Normal"}),
        cell("fp", "Falsos positivos", false), cell("tn", "Verdaderos negativos", true))));
}
function fraudEvaluator() {
  const input = dom("input", {id:"mlRefId", name:"refId", type:"text", inputmode:"numeric", autocomplete:"off", "aria-describedby":"mlRefHint"});
  const form = dom("form", {className:"mlEval", id:"mlEvalForm", novalidate:true},
    segmented("Tipo de operación", ML_REF, ml.ref, key => { ml.ref = key; refreshRefLabel(); }),
    dom("div", {className:"mlEvalRow"},
      dom("label", {className:"field"}, dom("span", {id:"mlRefLabel", text:"ID del pedido"}), input),
      dom("button", {type:"submit", className:"btn secondary", id:"mlEvalBtn", text:"Evaluar operación"})),
    dom("p", {id:"mlRefHint", className:"muted mlHint", text:"Escribe el número interno o elige un pedido reciente."}),
    dom("div", {id:"mlRecent", className:"mlRecent"}));
  form.addEventListener("submit", e => { e.preventDefault(); evaluateFraud(form); });
  const card = dom("section", {className:"card mlEvalCard", "aria-labelledby":"mlEvalTitle"},
    dom("div", {className:"cardHead"}, dom("h3", {id:"mlEvalTitle", text:"Evaluar una operación"}),
      dom("span", {className:"muted", text:"La probabilidad es descriptiva: la tienda no rechaza pagos con ella."})),
    dom("div", {className:"mlEvalGrid"}, form, dom("div", {id:"mlResult", className:"mlResult", "aria-live":"polite"},
      dom("p", {className:"muted mlResultEmpty", text:"El resultado aparecerá aquí con la probabilidad y las señales que más influyeron."}))));
  loadRecentOrders();
  return card;
}
function refreshRefLabel() {
  const label = $("#mlRefLabel"), recent = $("#mlRecent");
  if (label) label.textContent = "ID " + {order_id:"del pedido", invoice_id:"de la factura", payment_id:"del pago"}[ml.ref];
  if (recent) recent.hidden = ml.ref !== "order_id";
}
async function loadRecentOrders() {
  try {
    if (!ml.recent) ml.recent = (await api("/admin/orders?page=1")).orders.slice(0, 5);
  } catch { ml.recent = []; }
  const box = $("#mlRecent");
  if (!box || !ml.recent.length) return;
  box.replaceChildren(dom("span", {className:"baLabel", text:"Pedidos recientes"}),
    dom("span", {className:"mlRecentChips"}, ml.recent.map(o => {
      const chip = dom("button", {type:"button", className:"chip", "aria-pressed":"false", text:o.order_number});
      chip.addEventListener("click", () => {
        $$(".chip", box).forEach(c => c.setAttribute("aria-pressed", String(c === chip)));
        const input = $("#mlRefId");
        input.value = String(o.id);
        input.removeAttribute("aria-invalid");
        $("#mlEvalForm .fieldError")?.remove();
        evaluateFraud($("#mlEvalForm"));
      });
      return chip;
    })));
  refreshRefLabel();
}
async function evaluateFraud(form) {
  const input = $("#mlRefId", form), button = $("#mlEvalBtn", form), result = $("#mlResult");
  clearFieldErrors(form);
  input.setAttribute("aria-describedby", "mlRefHint"); // clearFieldErrors quita la ayuda junto con el error
  const raw = input.value.trim();
  if (!/^\d+$/.test(raw) || Number(raw) < 1) {
    showFieldErrors(form, {refId:"Escribe un número de identificación válido (entero positivo)."});
    input.focus();
    return;
  }
  if (button.disabled) return;
  setBusy(button, true, "Evaluando…");
  result.setAttribute("aria-busy", "true");
  try {
    const res = await api("/admin/ml/predict/fraud", {method:"POST", body:{[ml.ref]:Number(raw)}});
    renderFraudResult(result, res, ML_REF.find(([k]) => k === ml.ref)[1] + " #" + raw);
    markFraudLoaded();
  } catch (err) {
    if (err.status === 401) return;
    if (err.status === 404) showFieldErrors(form, {refId:"No existe " + {order_id:"un pedido", invoice_id:"una factura", payment_id:"un pago"}[ml.ref] + " con ese ID."});
    else if (err.status === 400 && err.data?.fields) showFieldErrors(form, {refId:Object.values(err.data?.fields)[0]});
    else result.replaceChildren(dom("p", {className:"shortNote"}, iconOf("alert"), dom("span", {text:mlErr(err)})));
  } finally {
    result.removeAttribute("aria-busy");
    if (button.isConnected) setBusy(button, false);
  }
}
/* La primera prediccion verifica el SHA-256 y carga el .keras: la tarjeta de estado lo refleja sin recargar */
function markFraudLoaded() {
  const card = $('.mlModel[aria-label="Estado del clasificador de fraude"]');
  const badge = card && $(".mlModelHead .badge", card);
  if (!badge || badge.textContent === "Cargado desde disco .keras") return;
  badge.replaceWith(pillBadge("ok", "check", "Cargado desde disco .keras"));
  $(".mlNote", card)?.remove();
}
function renderFraudResult(box, res, label) {
  const fraud = res.predicted_label === "fraudulenta";
  const p = Math.max(0, Math.min(1, Number(res.fraud_probability) || 0));
  const bar = dom("div", {className:"scoreMeter", role:"meter", "aria-valuemin":"0", "aria-valuemax":"100", "aria-valuenow":String(Math.round(p * 1000) / 10), "aria-label":"Probabilidad de fraude"},
    dom("span", {className:"meterFill " + (fraud ? "bad" : "info")}));
  bar.firstChild.style.width = Math.max(p * 100, p > 0 ? 1 : 0) + "%";
  const signals = (res.signals || []).map(s => {
    const d = Number(s.delta_probability) || 0;
    const up = d > 0;
    const pp = Math.abs(d * 100);
    return dom("li", {className:"signal"},
      dom("span", {text:ML_SIGNAL[s.feature] || s.feature}),
      dom("span", {className:"signalDelta " + (up ? "up" : "down"), title:(up ? "Aumenta" : "Reduce") + " la probabilidad"},
        pp < 0.01 ? "Efecto mínimo (" + (up ? "sube" : "baja") + ")" : (up ? "+" : "-") + fmtDec.format(pp) + " pp"));
  });
  box.replaceChildren(...[
    dom("div", {className:"mlResultHead"}, dom("span", {className:"cellMain", text:label}),
      fraud ? pillBadge("bad", "alert", "Fraudulenta") : pillBadge("ok", "check", "Normal")),
    dom("div", {className:"mlProb"}, dom("strong", {className:"num", text:probText(p)}), dom("span", {className:"muted", text:"probabilidad de fraude"})),
    bar,
    signals.length ? dom("div", {}, dom("h4", {className:"signalsTitle", text:"Señales con más peso"}), dom("ol", {className:"signals"}, signals),
      dom("p", {className:"muted mlHint", text:"pp = puntos porcentuales que cambia la probabilidad si esa señal tomara su valor medio de entrenamiento."})) : null,
    dom("p", {className:"muted mlHint", text:"Modelo " + String(res.version || "").slice(0, 8) + " · predicción #" + res.id + " guardada."})].filter(Boolean));
}

/* ======================= 3. Demanda: Keras frente a regresion lineal ======================= */
async function loadDemandComparison() {
  const box = $("#mlDemandBody");
  if (!box) return;
  try {
    ml.demand = await api("/admin/ml/predict/demand?horizon=7");
  } catch (err) {
    if (err.status === 401 || !box.isConnected) return;
    box.replaceChildren(dom("div", {className:"card emptyState mlEmpty"}, dom("h3", {text:"No pudimos cargar la comparación"}), dom("p", {className:"muted", text:mlErr(err)})));
    return;
  }
  if (!box.isConnected) return;
  const products = ml.demand.products || [];
  if (!products.some(p => String(p.product_id) === String(ml.product))) ml.product = products[0] ? String(products[0].product_id) : null;
  let picker = null;
  if (products.length > 1) {
    const tpl = document.createElement("template");
    tpl.innerHTML = listbox({name:"mlProduct", label:"Producto", value:ml.product, options:products.map(p => ({value:String(p.product_id), label:p.name}))});
    picker = tpl.content.firstElementChild;
    picker.classList.add("demandPicker");
    setupListbox(picker);
    $("input", picker).addEventListener("change", e => { ml.product = e.target.value; drawComparison(); });
  }
  box.replaceChildren(
    dom("div", {className:"panelBar"},
      dom("p", {className:"muted", text:"Ambos modelos se evalúan en las mismas fechas reservadas después del corte (" + (ml.demand.cutoff || "sin dato") + ")."}),
      ml.demand.source === "simulated" ? pillBadge("info", "dot", "Serie simulada documentada") : null, picker),
    dom("div", {id:"mlCompare", className:"demandBody"}));
  drawComparison();
}
function drawComparison() {
  const box = $("#mlCompare"), d = ml.demand;
  if (!box || !d) return;
  const product = (d.products || []).find(p => String(p.product_id) === String(ml.product));
  if (!product || !(product.test || []).length) {
    box.replaceChildren(dom("div", {className:"card emptyState mlEmpty"}, dom("h3", {text:"Sin tramo de prueba para este producto"}),
      dom("p", {className:"muted", text:"Un producto necesita al menos tres períodos previos para entrar en la comparación."})));
    return;
  }
  const legendItem = (cls, text) => {
    const s = svgEl("svg", {viewBox:"0 0 24 8", width:24, height:8, "aria-hidden":"true"});
    s.append(svgEl("line", {x1:0, x2:24, y1:4, y2:4, class:cls}));
    return dom("li", {}, s, text);
  };
  const chart = dom("section", {className:"card demandCard", "aria-labelledby":"mlChartTitle"},
    dom("div", {className:"cardHead"}, dom("div", {}, dom("h3", {id:"mlChartTitle", text:product.name}),
      dom("p", {className:"muted", text:"Unidades por día · " + product.test.length + " días de prueba" + ((product.forecast || []).length ? " y " + product.forecast.length + " proyectados" : "")}))),
    dom("ul", {className:"chartLegend"}, legendItem("mlObserved", "Demanda observada"), legendItem("mlKeras", "Predicción Keras (red neuronal)"), legendItem("mlLinear", "Regresión lineal simple (Fase 4)")));
  const plot = dom("div", {className:"plotBox"});
  chart.append(plot, comparisonTable(product));
  box.replaceChildren(chart, errorTable(d.metrics || {}));
  responsiveChart(plot, w => drawCompareChart(plot, product, w));
}
function drawCompareChart(wrap, product, width) {
  wrap.replaceChildren();
  const test = product.test, fc = product.forecast || [];
  const pts = [...test.map(t => ({...t, zone:"test"})), ...fc.map(f => ({...f, zone:"forecast"}))];
  const n = pts.length;
  const vals = pts.flatMap(p => [p.observed, p.keras, p.linear_phase4]).filter(v => v != null);
  const ticks = niceTicks(Math.min(0, ...vals), Math.max(1, ...vals), 4);
  const y0 = ticks[0], y1 = ticks[ticks.length - 1];
  const H = width < 480 ? 240 : 300, padL = 40, padR = 12, top = 28, bottom = 34;
  const x = i => n === 1 ? (padL + width - padR) / 2 : padL + (width - padL - padR) * i / (n - 1);
  const y = v => top + (H - top - bottom) * (1 - (v - y0) / (y1 - y0 || 1));
  const svg = svgEl("svg", {viewBox:`0 0 ${width} ${H}`, width, height:H, class:"demandChart", tabindex:"0", role:"img",
    "aria-label":"Demanda observada frente a las predicciones de Keras y de la regresión lineal. Usa las flechas para recorrer los días."});
  const step = n > 1 ? (width - padL - padR) / (n - 1) : 0;
  if (fc.length) {
    const xa = x(test.length - 1) + step / 2;
    svg.append(svgEl("rect", {x:xa, y:top - 4, width:Math.max(0, width - padR - xa), height:H - top - bottom + 4, class:"zone zoneForecast"}),
      svgEl("text", {x:xa + 6, y:top - 10, class:"axisText zoneLabel"}, "Proyección"));
  }
  svg.append(svgEl("text", {x:padL, y:top - 10, class:"axisText zoneLabel"}, "Prueba reservada"));
  for (const t of ticks) svg.append(svgEl("line", {x1:padL, x2:width - padR, y1:y(t), y2:y(t), class:t === 0 ? "baseLine" : "gridLine"}),
    svgEl("text", {x:padL - 8, y:y(t) + 4, "text-anchor":"end", class:"axisText"}, fmtDec.format(t)));
  const every = Math.max(1, Math.ceil(n / Math.max(2, Math.floor((width - padL - padR) / 84))));
  pts.forEach((p, i) => {
    if ((i % every === 0 && (i === n - 1 || n - 1 - i >= every)) || i === n - 1)
      svg.append(svgEl("text", {x:x(i), y:H - 12, "text-anchor":i === 0 ? "start" : i === n - 1 ? "end" : "middle", class:"axisText"}, dayFmt.format(periodDate(p.period))));
  });
  const line = (key, cls) => svg.append(svgEl("polyline", {class:cls, points:pts.map((p, i) => p[key] == null ? null : x(i) + "," + y(p[key])).filter(Boolean).join(" ")}));
  line("linear_phase4", "mlLinear");
  line("keras", "mlKeras");
  line("observed", "mlObserved");
  const cross = svgEl("line", {y1:top - 4, y2:H - bottom, class:"crosshair", visibility:"hidden"});
  const marks = {observed:svgEl("circle", {r:5, class:"markObservedMl", visibility:"hidden"}), keras:svgEl("circle", {r:5, class:"markKeras", visibility:"hidden"}),
    linear_phase4:svgEl("circle", {r:5, class:"markLinear", visibility:"hidden"})};
  const hit = svgEl("rect", {x:padL, y:top - 4, width:width - padL - padR, height:H - top - bottom + 4, class:"hitArea"});
  svg.append(cross, ...Object.values(marks), hit);
  wrap.append(svg);
  const tip = chartTip(wrap);
  let active = -1;
  const show = i => {
    active = Math.max(0, Math.min(n - 1, i));
    const p = pts[active], cx = x(active);
    cross.setAttribute("x1", cx); cross.setAttribute("x2", cx); cross.setAttribute("visibility", "visible");
    for (const [k, m] of Object.entries(marks)) {
      if (p[k] == null) { m.setAttribute("visibility", "hidden"); continue; }
      m.setAttribute("cx", cx); m.setAttribute("cy", y(p[k])); m.setAttribute("visibility", "visible");
    }
    const lines = [];
    if (p.observed != null) lines.push(["Observada", fmtDec.format(p.observed) + " u.", "swObservedMl"]);
    lines.push(["Keras", fmtDec.format(p.keras) + " u.", "swObserved"], ["Regresión lineal", fmtDec.format(p.linear_phase4) + " u.", "swEstimated"]);
    tip.show(cx, Math.min(...[p.observed, p.keras, p.linear_phase4].filter(v => v != null).map(y)),
      periodLabel(p.period, "daily") + (p.zone === "forecast" ? " · Proyección" : ""), lines);
  };
  const hide = () => { active = -1; tip.hide(); cross.setAttribute("visibility", "hidden"); Object.values(marks).forEach(m => m.setAttribute("visibility", "hidden")); };
  hit.addEventListener("pointermove", e => {
    const r = svg.getBoundingClientRect();
    show(n === 1 ? 0 : Math.round(((e.clientX - r.left) * (width / r.width) - padL) / step));
  });
  hit.addEventListener("pointerleave", hide);
  svg.addEventListener("focus", () => show(active < 0 ? test.length - 1 : active));
  svg.addEventListener("blur", hide);
  svg.addEventListener("keydown", e => {
    const mv = {ArrowRight:1, ArrowLeft:-1}[e.key];
    if (mv) { e.preventDefault(); show((active < 0 ? test.length - 1 : active) + mv); }
    else if (e.key === "Home") { e.preventDefault(); show(0); }
    else if (e.key === "End") { e.preventDefault(); show(n - 1); }
    else if (e.key === "Escape") hide();
  });
}
function comparisonTable(product) {
  const rows = [...product.test.map(t => [t, "Prueba"]), ...(product.forecast || []).map(f => [f, "Proyección"])];
  const v = x => x == null ? "Sin dato" : fmtDec.format(x);
  return dom("details", {className:"dataDetails"}, dom("summary", {text:"Ver los datos de la gráfica"}),
    dom("div", {className:"tableWrap"}, dom("table", {},
      dom("thead", {}, dom("tr", {}, ["Día", "Observada", "Keras", "Regresión lineal", "Tramo"].map(t => dom("th", {scope:"col", text:t})))),
      dom("tbody", {}, rows.map(([p, zone]) => dom("tr", {},
        dom("td", {text:periodLabel(p.period, "daily")}), dom("td", {className:"num", text:v(p.observed)}),
        dom("td", {className:"num", text:v(p.keras)}), dom("td", {className:"num", text:v(p.linear_phase4)}), dom("td", {text:zone})))))));
}
function errorTable(metrics) {
  const k = metrics.keras || {}, l = metrics.linear_phase4 || {};
  const rows = [["MAE", "mae", "lower", "unidades"], ["RMSE", "rmse", "lower", "unidades"], ["R²", "r2", "higher", "1 es ajuste perfecto"]];
  const better = (a, b, dir) => a == null || b == null || a === b ? null : (dir === "lower" ? a < b : a > b) ? "keras" : "linear";
  const winsKeras = rows.filter(([, key, dir]) => better(k[key], l[key], dir) === "keras").length;
  const winsLinear = rows.filter(([, key, dir]) => better(k[key], l[key], dir) === "linear").length;
  const maeWinner = better(k.mae, l.mae, "lower");
  // El ganador se decide una vez por métrica (Keras contra lineal) y la insignia va solo en su celda
  const cell = (who, key, dir) => {
    const val = (who === "keras" ? k : l)[key];
    const won = better(k[key], l[key], dir) === who;
    return dom("td", {className:"num errCell" + (won ? " winner" : "")},
      dom("span", {text:val == null ? (key === "r2" ? "No aplica" : "Sin dato") : fmtDec.format(val)}),
      won ? pillBadge("ok", "check", key === "r2" ? "Mejor ajuste" : "Menor error") : null);
  };
  return dom("section", {className:"card metricsCard", "aria-labelledby":"mlErrTitle"},
    dom("div", {className:"cardHead"}, dom("h3", {id:"mlErrTitle", text:"Error en el tramo reservado"})),
    maeWinner ? dom("p", {className:"mlVerdict"},
      dom("strong", {text:maeWinner === "keras" ? "Keras" : "La regresión lineal"}),
      " obtiene menor error medio (MAE) y gana " + (maeWinner === "keras" ? winsKeras : winsLinear) + " de 3 métricas.") : null,
    dom("div", {className:"tableWrap"}, dom("table", {className:"errTable"},
      dom("thead", {}, dom("tr", {}, dom("th", {scope:"col", text:"Métrica"}), dom("th", {scope:"col", text:"Keras"}), dom("th", {scope:"col", text:"Regresión lineal"}))),
      dom("tbody", {}, rows.map(([label, key, dir, note]) => dom("tr", {},
        dom("td", {}, dom("span", {className:"cellMain", text:label}), dom("span", {className:"cellSub", text:note})),
        cell("keras", key, dir), cell("linear", key, dir)))))),
    dom("p", {className:"muted modelNote", text:"Métricas agregadas por producto y día. No se exige que Keras supere al modelo lineal: la tabla muestra el resultado tal cual."}));
}
