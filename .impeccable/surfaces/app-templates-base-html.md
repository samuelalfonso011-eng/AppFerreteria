---
version: 1
slug: "app-templates-base-html"
primary_target: "app/templates/base.html"
related_targets: ["app/templates/admin/base_admin.html"]
---

# Surface brief: tienda pública (rediseño completo; el admin hereda después)

Modo: Operate con intención de venta. Home, catálogo, producto, carrito y checkout. Audiencia: contratista en móvil, a pleno sol y con guantes (prioritario); comprador de hogar. Restricciones: CSP estricta (sin scripts ni on* inline), SPA sobre `#main-content`, estilos inline existentes que apuntan a variables CSS, i18n, modo claro/oscuro.

## Direction contract

THESIS: el estado de cada producto y cada acción se lee como una señal de obra (NTC 1461): una banda de encabezado con una palabra en mayúsculas, legible a distancia y al sol. Rechaza la tienda blanca de tarjetas redondeadas con banner promocional y la "pared pizarra con rotulado" de la v1.3.

OWN-WORLD: fondo `#F8FAFC`, pizarra `#1E293B` para la barra y el pie, tinta `#0F172A`. Las bandas de estado usan colores semánticos y no decoran: verde señal `#166534` = DISPONIBLE/INFORMACIÓN, ámbar `#F59E0B` = POCAS/PRECAUCIÓN, naranja `#EA580C` = AGOTADO/ALERTA. El ámbar es además el único color de la acción principal y del recorrido activo (carrito, checkout). Overpass (letra de señal vial) para bandas, títulos, precios y cifras; Atkinson Hyperlegible para lectura. Esquinas de 8–10 px, filete de 1 px, sin sombras difusas decorativas.

STORY: el visitante ve banda de estado, referencia, precio a tamaño de señal y unidad sin buscarlos; agrega con un botón de 44 px y una notificación con banda confirma qué pasó y el subtotal.

FIRST VIEWPORT: barra pizarra con marca a la izquierda y carrito ámbar con contador a la derecha; buscador de 48 px a lo ancho; riel de categorías con snap; título de sección grande; cuadrícula de tarjetas de 2 columnas en móvil (4–5 en escritorio), cada una con banda de estado arriba, imagen a escala fija, REF, nombre, precio grande, unidad y botón. Movimiento distintivo: la banda de señal, compartida por tarjetas, notificaciones, alertas y estados vacíos.
Aportes: densidad sin relleno (vista de lista); ámbar solo para el recorrido activo; escala fija de imagen y precios sobre una línea base común; jerarquía por escala; un solo código (REF) visible en todo el recorrido; un eje a la vez en el riel móvil.

FORM: Señal de obra, candidata 6 de 7 de la lista propia, asignada por el sorteo y elegida por el usuario. seed:7d65e1bfbb7f852a

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
