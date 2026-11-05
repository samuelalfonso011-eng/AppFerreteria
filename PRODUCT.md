# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Maestro de obra / contratista** (prioridad visual confirmada por el dueño): compra rápido y en volumen, a menudo desde el celular, en la obra, con luz solar fuerte y a veces con las manos sucias o con guantes.
- **Comprador de hogar** (casual): compra puntual de materiales y herramientas, necesita orientación y confianza.
- **Administrador / personal de la ferretería** (operan el panel): atienden pedidos, ajustan inventario y precios, revisan alertas de bajo stock. Usan el panel tanto en escritorio como en celular.

## Product Purpose

Tienda virtual y panel administrativo de una ferretería en el Valle de Aburrá (Antioquia, Colombia). Permite comprar con precios, descuentos y stock validados en el servidor, y operar inventario (kárdex), pedidos, clientes y pagos. El pago es una simulación (modo de prueba, sin cobro real).

## Capabilities and Constraints

- Backend Flask + Jinja2 renderizado en servidor; JS vanilla sin framework; PostgreSQL (Supabase) o SQLite local.
- Entrega solo en 10 municipios del Valle de Aburrá. Moneda COP (sin decimales). Interfaz en español con inglés opcional (i18n propio).
- Hay modo claro y oscuro; la preferencia se guarda en `localStorage`.
- **Restricción técnica obligatoria:** Content-Security-Policy estricta para scripts. No se permiten `<script>` inline sin nonce ni atributos `on*`; los comportamientos van en `static/js/` (hay `csp-handlers.js` con `data-confirm`, `data-autosubmit`, `data-print`, `data-img-fallback`). Los atributos `style=` sí están permitidos (`style-src 'unsafe-inline'`).
- La navegación tipo SPA (`navigation.js`) reemplaza `#main-content`; el JS nuevo debe sobrevivir a ese intercambio (delegación de eventos).
- Fuentes permitidas por CSP: propias y Google Fonts. Scripts externos: solo `cdn.jsdelivr.net` (Chart.js).

## Brand Commitments

- Nombre configurable desde el panel (`store_name`; por defecto «Ferretería El Constructor»).
- **Paleta binding fijada por el dueño:** pizarra `#1E293B`, ámbar `#F59E0B` o naranja de seguridad `#EA580C` como acentos industriales, fondo claro `#F8FAFC`. Reemplaza la identidad amarillo/negro anterior (v1.1.0), que deja de ser referencia.
- Mobile-first; alto contraste; micro-interacciones, estados de carga (skeletons/spinners), toasts y estados vacíos bien diseñados.

## Evidence on Hand

- No hay fotografías reales de productos ni logotipo gráfico: hay ilustraciones vectoriales temporales por categoría en `app/static/img/temp/` y un favicon SVG. No inventar fotos, reseñas, clientes ni cifras.

## Product Principles

- La información que decide la compra (precio, disponibilidad, unidad) siempre es visible y escaneable de un vistazo.
- Los controles son grandes y tolerantes: se usan de pie, con una mano, con sol.
- El panel prioriza la velocidad de operación y las alertas accionables sobre la decoración.
- Ninguna mejora visual debe romper la CSP, la navegación SPA ni la validación en servidor.

## Accessibility & Inclusion

- Contraste mínimo WCAG AA (4.5:1 texto normal, 3:1 texto grande); foco de teclado siempre visible; objetivos táctiles de al menos 44 px; respeto de `prefers-reduced-motion`.
- Facts marcados como inferidos del repositorio y de la solicitud (no confirmados en entrevista): prioridad del perfil contratista (sí confirmado), horarios y datos de contacto reales de la tienda (por definir, vienen de `StoreSetting`).
