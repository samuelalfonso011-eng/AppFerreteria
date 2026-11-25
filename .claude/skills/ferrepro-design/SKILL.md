---
name: ferrepro-design
description: Sistema de diseño estilo Apple de FerrePro (tienda de ferretería y Modo Admin). Úsala siempre que vayas a crear, editar o revisar cualquier interfaz de este proyecto (index.html, admin.html, styles.css, admin.css, theme.css, app.js o admin.js), aunque el pedido no diga "diseño": una pestaña nueva del admin, un modal, una tarjeta, un formulario, un botón, animaciones, modo oscuro, responsive o estados de carga. Define tokens claro/oscuro, movimiento, componentes y las reglas no negociables del repositorio.
---

# FerrePro: sistema de diseño

La tienda y el Modo Admin comparten una sola fuente de verdad: `theme.css`. Todo lo visual sale de sus variables; si un valor no existe, se crea como token allí y luego se usa. Así cambiar marca o tema es una sola edición y los dos temas nunca se separan.

## Antes de tocar UI

1. Lee `theme.css` completo (cambia con frecuencia) y el bloque del componente que vas a editar.
2. Agrega código en una sección nueva al final del archivo o con ediciones puntuales. No reescribas archivos completos: otros agentes trabajan en paralelo y una reescritura borra su trabajo sin aviso.
3. Si hay otro agente activo, no edites sus archivos (por ejemplo autenticación: `backend/app/api/auth.py`, `auth_service.py`, `security.py`, el bloque "Cuenta" de `app.js`).

## Reglas no negociables (de AGENTS.md)

- **Sin emoji ni guiones largos (em/en dash)** en UI, código, comentarios o textos. Usa iconos SVG con `currentColor` y dos puntos o comas.
- **Sin `<select>` nativo.** Usa el listbox accesible de `admin.js` (`listbox()` + `setupListbox()`): botón con `aria-haspopup="listbox"`, flechas, Home/End, Escape, búsqueda por letras.
- **Token por intención.** Eliminar o cancelar usa `--danger` en el botón y en su confirmación. Primario (`--accent`) es una sola acción afirmativa por vista; secundario es neutro (`--control`), nunca un color de relleno.
- **Movil primero.** Los estilos base son el teléfono; lo ancho se agrega con `min-width`. (`styles.css` de la Fase 1 es desktop-first: respétalo, pero el código nuevo va movil primero.)
- **Ocho estados** en todo control: normal, hover, focus-visible, active, disabled, cargando (`aria-busy`), error (`aria-invalid` + mensaje), seleccionado (`aria-selected`/`aria-pressed`/`checked`).
- **Nunca un borde de color en un solo lado** de tarjetas o avisos. Estado = icono + texto, nunca solo color.
- **Un solo foco por pantalla**: la tipografía display es al menos 2.5 veces el cuerpo.
- **Sin etiqueta "eyebrow" sobre un título** en código nuevo (regla de Impeccable): el título habla solo.

## Tema claro y oscuro

`[data-theme]` en `<html>`, puesto por `theme-init.js` (bloqueante en `<head>`, antes del CSS) para evitar el destello blanco. Preferencia en `localStorage` (`ferrepro.theme`), sigue al sistema si no hay elección.

| Rol | Claro | Oscuro | Token |
|---|---|---|---|
| Fondo de página | #fff | #000 | `--bg` (admin: `--canvas`) |
| Superficie / tarjeta | #f5f5f7 / #fff | #1d1d1f | `--surface`, `--elevated` |
| Control | #f5f5f7 | #2c2c2e | `--control`, `--control-hover` |
| Texto | #1d1d1f | #f5f5f7 | `--text` |
| Texto secundario | #6e6e73 | #a1a1a6 | `--text-2` |
| Enlace / foco | #0066cc / #0071e3 | #2997ff | `--link`, `--focus` |
| Botón primario | #0071e3 en ambos | | `--accent` (el blanco sobre #2997ff no llega a 4.5:1) |
| Barra de navegación | rgba(251,251,253,.8) | rgba(29,29,31,.8) | `--nav-bg` + `backdrop-filter: saturate(180%) blur(20px)` |

Estados: `--success-*`, `--warning-*`, `--danger-*`, `--info-*` (texto + fondo suave). Nunca escribas un hex en un componente.

## Movimiento

Curva única: `--ease` = `cubic-bezier(.25,.1,.25,1)`. Duraciones: `--dur-feedback` (120 ms), `--dur-enter` (320 ms), `--dur-exit` (200 ms, salir es más rápido que entrar), `--dur-reveal` (600 ms). Presión: `--press-scale` (.98).

- Anima solo `transform` y `opacity` salvo una razón concreta.
- Modales, buscador, menús y paneles: entrada y salida con `@starting-style` + `transition` de `display`/`overlay` con `allow-discrete`. Sin soporte, abren al instante (aceptable).
- **Hover: el elemento no se mueve** (se escaparía del puntero). Se eleva su sombra y se anima un hijo, por ejemplo la ilustración a `scale(1.03)`, dentro de `@media (hover:hover)`.
- Un solo momento propio por superficie (en la tienda: agregar al carrito, con el contador que late y la notificación). No pongas la misma entrada en cada sección.
- **`prefers-reduced-motion`**: quita desplazamientos, escalas, pulsos y brillos, pero conserva los fundidos de opacidad que confirman una acción. Reducir no es apagar todo.

Patrones listos para copiar: [references/patterns.md](references/patterns.md).

## Componentes

- **Tarjetas**: radio `--radius-card` (20px; las de producto y mosaico usan `--radius-tile`, 24px), elevación por borde O por sombra, nunca las dos. En oscuro el borde desaparece y separa la superficie.
- **Botones píldora**: `--radius-pill`, mínimo 44px de alto (objetivo táctil), `:active` con `scale(var(--press-scale))`.
- **Campos**: 44 a 48px de alto, `--radius-field`, foco `outline: 3px solid var(--focus)`, error con `aria-invalid` + `.fieldError` enlazado por `aria-describedby`.
- **Insignias de estado** (`.badge.ok|warn|bad|info`): icono SVG + texto.
- **Tablas del admin**: clase `stack` + `data-label` en cada `td`; en el teléfono cada fila es una tarjeta con etiquetas, desde 640px vuelve a ser tabla. Primera celda `cellLead`, acciones `cellActions`. Números con `font-variant-numeric: tabular-nums`.
- **Esqueletos**: `.skeleton` con la misma silueta que el contenido real (sin saltos al cargar), brillo que se apaga con movimiento reducido. Anuncia la carga con `aria-busy` y texto `.sr`.

## Rendimiento

- Lo que está bajo el primer pantallazo lleva `content-visibility: auto` + `contain-intrinsic-size`.
- Animaciones de entrada con `IntersectionObserver` y `rootMargin` amplio; el contenido es visible por defecto si el script falla.
- Listas largas: carga progresiva ("Cargar más" en bloques), no todo el DOM de golpe.
- Imágenes reales (no SVG en línea): `loading="lazy"` y `decoding="async"` fuera del hero, con `width`/`height` o `aspect-ratio`.

## Verificación antes de decir "listo"

Ejecuta y reporta lo que imprimen (no afirmes números sin medir):

```powershell
backend\venv\Scripts\python.exe scripts\check_no_emoji.py <archivo>
backend\venv\Scripts\python.exe scripts\lint_hardcodes.py <archivo>
$env:DS_REQUIRE_BROWSER="1"; node scripts\axe_audit.mjs <pagina>
```

Luego mira la página: claro y oscuro, 360px, 768px y 1280px, haz clic en cada control nuevo y revisa que la consola no tenga errores. Un gate verde no prueba buen gusto.
