---
version: 1
slug: "app-templates-base-html"
primary_target: "app/templates/base.html"
related_targets: ["app/templates/admin/base_admin.html"]
---

# Surface brief: tienda pública + panel admin (rediseño visual)

Modo: Operate para el admin y para carrito/checkout/cuenta; la home y el catálogo venden, pero con prioridad a escanear y actuar. Audiencia: contratista en móvil (prioritario), comprador de hogar, personal de la ferretería. Restricciones: CSP estricta (sin scripts ni on* inline), SPA con `#main-content`, estilos inline existentes (~1.250) que apuntan a variables CSS.

## Direction contract

THESIS: una ferretería se reconoce por su rotulación y su señalética de seguridad, no por un tema de tienda genérico; la interfaz es una pared de rotulado en pizarra con el ámbar como color de acción. Rechaza el e-commerce claro-con-acento-azul y el negro-neón.

OWN-WORLD: pizarra `#1E293B` (barras, pie, panel lateral) y `#0F172A` (texto, modo oscuro) sobre fondo `#F8FAFC`; ámbar `#F59E0B` solo para la acción principal y el estado activo; naranja de seguridad `#EA580C` reservado para alertas, bajo stock y acciones críticas, nunca decorativo; tipografía de rotulado industrial condensada (Barlow Condensed) para títulos, precios y cifras, Inter para lectura; esquinas de 8 a 12 px; bordes de 1 px; sombras con desplazamiento y desenfoque.

STORY: el visitante ve precio, stock y unidad sin buscarlos, agrega con un toque grande y sabe qué pasó (toast); el administrador ve de un vistazo qué requiere acción.

FIRST VIEWPORT: barra superior pizarra con marca a la izquierda, buscador claro de ancho completo y carrito ámbar con contador a la derecha; debajo, el contenido de la página; en móvil el buscador baja a una segunda fila y todos los controles miden al menos 44 px.

FORM: dirección fijada por el usuario (paleta y prioridad dadas en su encargo y confirmadas en la entrevista); no se corrió el sorteo de conceptos. seed: none (unavailable)

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
