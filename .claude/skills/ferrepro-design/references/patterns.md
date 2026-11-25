# Patrones de código de FerrePro

Copia y adapta. Todos los valores salen de `theme.css`.

## Modal o panel con entrada y salida reales

```css
dialog{opacity:0;transform:translateY(var(--shift-lg)) scale(.98);
  transition:opacity var(--dur-exit) var(--ease),transform var(--dur-exit) var(--ease),
             overlay var(--dur-exit) allow-discrete,display var(--dur-exit) allow-discrete}
dialog[open]{opacity:1;transform:none;transition-duration:var(--dur-enter)}
@starting-style{dialog[open]{opacity:0;transform:translateY(var(--shift-lg)) scale(.98)}}
```

Para un elemento con el atributo `hidden` (buscador, menú), igual pero con `[hidden]{display:none;opacity:0;...}` y `@starting-style{.x:not([hidden]){...}}`.

## Hover de tarjeta sin mover la tarjeta

```css
.card{transition:box-shadow var(--dur) var(--ease)}
.card svg{transition:transform var(--dur-enter) var(--ease)}
@media(hover:hover){.card:hover{box-shadow:var(--shadow-hover)}.card:hover svg{transform:scale(1.03)}}
```

## Feedback de acción (contador que late)

```css
#badge.bump{animation:badgeBump var(--dur-reveal) var(--ease)}
@keyframes badgeBump{0%{transform:scale(1)}30%{transform:scale(1.35)}100%{transform:scale(1)}}
```

```js
badge.classList.remove("bump"); void badge.offsetWidth; badge.classList.add("bump");
```

## Movimiento reducido

```css
@media(prefers-reduced-motion:reduce){
  dialog,dialog[open]{transform:none}
  @starting-style{dialog[open]{transform:none}}
  #badge.bump{animation:none}
  .skeleton::after{animation:none;opacity:0}
}
```

## Tabla que se apila en el teléfono

```js
'<table class="stack"><thead>...</thead><tbody>' +
rows.map(r => '<tr><td class="cellLead">...</td><td data-label="Estado">...</td>' +
  '<td class="cellActions"><div class="rowActions">...</div></td></tr>').join("")
```

El CSS ya existe en `admin.css` (`table.stack`).

## Esqueleto con la silueta del contenido

```html
<div id="cards" aria-busy="true"><p class="sr">Cargando catálogo…</p>
  <div class="skeleton skeletonCard" aria-hidden="true"></div> ... </div>
```

Al llegar los datos, reemplaza el contenido y quita `aria-busy`.

## Escapar todo lo que se pinta con innerHTML

```js
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
```

Nombres de producto, clientes y textos del admin pasan siempre por `esc()`.
