# PLAN MAESTRO DE CORRECCIÓN Y PULIDO — FERRETERÍA EL CONSTRUCTOR (v1.2.0)

## 1. Rol e Instrucción General para el Agente de Antigravity
Actúa como Ingeniero de Software Full-Stack Senior (Python/Flask, SQLAlchemy, PostgreSQL/Supabase, Jinja2, CSS3 y JavaScript).
Tu objetivo es ejecutar la actualización **v1.2.0** sobre el código actual del proyecto para corregir **11 puntos específicos** de backend, base de datos, zona horaria, maquetación en Modo Oscuro, formularios centrados exclusivos para el **Valle de Aburrá**, internacionalización completa (ES/EN) y textos legales bajo la normativa de Colombia.

**Reglas estrictas de ejecución:**
- No rompas ninguna funcionalidad existente de la v1.0.0 ni el layout reparado del Panel Administrativo (`margin-left: 260px` en `.admin-main`).
- Trabaja fase por fase en el orden establecido a continuación.
- Verifica cada corrección con pruebas reales (`pytest` / cliente de pruebas de Flask) antes de avanzar a la siguiente fase.
- No dejes estilos inline con colores fijos (`#fff`, `#ffffff`, `white`) que rompan el Modo Oscuro.

---

## 2. FASE 1: Correcciones Críticas de Backend (Puntos 8, 9, 10 y 11)

### 2.1. Solución al `AttributeError` en `/admin/pedidos/<id>` y en Simulación de Compra (Puntos 9 y 10)
**Problema actual:**
Tanto al consultar el detalle de un pedido en `http://127.0.0.1:5000/admin/pedidos/1` como al confirmar una simulación de compra en el Checkout, Flask lanza un `AttributeError`.

**Causa técnica a inspeccionar y corregir:**
1. Revisar `app/models/order.py`, `app/models/payment.py`, `app/services/order_service.py`, `app/services/payment_service.py`, `app/routes/orders.py`, `app/routes/admin.py`, `app/templates/admin/order_detail.html` (o equivalente) y `app/templates/orders/`.
2. **Inconsistencia Enum vs. String:**
   - Si `order.status` o `payment.status` están definidos en SQLAlchemy como `db.String` y en el servicio o plantilla se llama a `order.status.value` o `payment.status.value` (o viceversa), se produce `AttributeError: 'str' object has no attribute 'value'`.
   - **Solución:** Estandarizar el acceso o agregar propiedades seguras en el modelo (`status_label`, `status_code`) y eliminar cualquier `.value` sobre strings en Python y Jinja2.
3. **Inconsistencia en nombres de relaciones SQLAlchemy:**
   - Verificar cómo están nombradas las relaciones en `Order`:
     - Pagos: si la relación es `payments` (lista `one-to-many`), pero la vista o el servicio llama a `order.payment` en singular, o viceversa. **Solución:** Definir o mantener `payments` y agregar en la clase `Order` una propiedad `@property def payment(self): return self.payments[-1] if self.payments else None` (y `@property def latest_payment(self)`), asegurando que tanto `order.payment` como `order.payments` funcionen sin lanzar `AttributeError`.
     - Ítems del pedido: verificar si la relación se llama `items` u `order_items`. Añadir un `@property` alias en `Order` para que ambos (`order.items` y `order.order_items`) devuelvan la lista de productos del pedido sin fallar.
     - Historial de estados: verificar si se llama `status_history` o `history` y asegurar que exista el atributo esperado por el template y el servicio.
4. **Inconsistencia en campos de dirección o usuario del pedido:**
   - Verificar que todas las columnas usadas al crear el pedido en `order_service.py` y leídas en `/admin/pedidos/<id>` (`recipient_name`, `recipient_phone`, `city`, `neighborhood`, `address_line`, `address_complement`, `delivery_notes`, `shipping_cost`, `subtotal`, `total`, `user`) existan exactamente con esos nombres en el modelo `Order` (y crear propiedades alias si una plantilla usa un nombre alternativo como `order.customer` en lugar de `order.user` o `order.shipping_address` en lugar de `order.address_line`).
5. **Verificación obligatoria:**
   - Ejecutar un test automatizado que cree un pedido completo mediante simulación de pago (aprobado, rechazado y pendiente) y luego haga `GET /admin/pedidos/1` y `GET /orders/1`, comprobando que ambas rutas devuelvan `200 OK` sin `AttributeError`.

### 2.2. Reparar Barra de Búsqueda al Iniciar Sesión como Cliente o Admin (Punto 8)
**Problema actual:**
Cuando el usuario inicia sesión (como cliente o como administrador), la barra de búsqueda global del encabezado deja de funcionar.

**Causa técnica y solución obligatoria:**
1. Inspeccionar `app/templates/base.html` (y cualquier parcial del navbar):
   - Al estar autenticado (`{% if current_user.is_authenticated %}`), se renderizan los enlaces `Modo Admin`, `Mis Pedidos`, `Administrador` y `Salir`.
   - Verificar si el botón `Salir` utiliza una etiqueta `<form method="POST" action="{{ url_for('auth.logout') }}">` que **no se cerró** con `</form>` o está mal anidada. En HTML5 no se permiten formularios anidados; si `<form>` queda abierto antes de la barra de búsqueda, el `<form>` del buscador queda inutilizado o envía al endpoint equivocado.
2. Asegurar que el formulario de búsqueda esté completamente aislado, bien cerrado y con ruta explícita al catálogo:
   ```html
   <form id="global-search-form" action="{{ url_for('products.catalog') }}" method="GET" role="search" class="navbar-search-form">
       <input type="search" name="q" id="global-search-input" value="{{ request.args.get('q', '') }}" placeholder="{{ t('search_placeholder') }}" aria-label="{{ t('search_placeholder') }}">
       <button type="submit" class="navbar-search-btn" aria-label="Buscar">
           <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
       </button>
   </form>
   ```
3. Revisar `app/static/js/` (`main.js`, `navigation.js` o similar):
   - Asegurar que ningún listener de formularios o interceptor SPA haga `e.preventDefault()` sobre `#global-search-form` sin redirigir a `/products?q=...` (o la ruta del catálogo con el parámetro de búsqueda que espere el backend: verificar si `routes/products.py` lee `request.args.get('q')` o `request.args.get('search')` y unificar ambos en el backend: `q = request.args.get('q') or request.args.get('search', '')`).

### 2.3. Configurar Zona Horaria Oficial de Colombia (America/Bogota, UTC-5) (Punto 11)
**Problema actual:**
Al registrar un usuario o crear un pedido en la noche (ej. 10:34 p. m. hora Colombia), el sistema muestra 3:34 a. m. del día siguiente porque está usando UTC (+00:00) sin convertir a America/Bogota (UTC-5).

**Solución obligatoria:**

1. Añadir `tzdata` en `requirements.txt` e instalarlo en el entorno virtual para garantizar soporte de `zoneinfo` en Windows.

2. Crear `app/utils/timezone.py`:

```python
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BOGOTA_TZ = ZoneInfo("America/Bogota")

def now_bogota():
    """Devuelve la fecha y hora actual en la zona horaria de Bogotá (UTC-5)."""
    return datetime.now(BOGOTA_TZ)

def to_bogota(dt):
    """Convierte un objeto datetime (naive UTC o aware) a America/Bogota."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BOGOTA_TZ)

def format_bogota(dt, fmt="%d/%m/%Y %I:%M %p"):
    """Formatea un datetime en hora de Bogotá, Colombia."""
    local_dt = to_bogota(dt)
    if local_dt is None:
        return ""
    formatted = local_dt.strftime(fmt)
    return formatted.replace("AM", "a. m.").replace("PM", "p. m.")
```

3. Registrar en `app/__init__.py` los filtros Jinja2 `bogota_time` y `bogota_date`:

```python
@app.template_filter("bogota_time")
def bogota_time_filter(dt, fmt="%d/%m/%Y %I:%M %p"):
    return format_bogota(dt, fmt)

@app.template_filter("bogota_date")
def bogota_date_filter(dt):
    return format_bogota(dt, "%d/%m/%Y")
```

4. Reemplazar en todas las plantillas (`admin/`, `orders/`, `auth/`, `profile/`) cualquier `.strftime(...)` directo por `{{ fecha | bogota_time }}`.

5. En los cálculos del Dashboard Administrativo (Ventas del día, Ventas de la semana, Ventas del mes), calcular el inicio del día usando la medianoche de America/Bogota y no la medianoche UTC.

---

## 3. FASE 2: Corrección de Modo Oscuro, Iconos Sociales y Notificación Toast (Puntos 1, 2 y 4)

### 3.1. Modo Oscuro Completo sin Recuadros Blancos (Punto 1)
**Problema actual:**
Al activar el Modo Oscuro, el fondo principal pasa a negro, pero varios contenedores mantienen `background: #ffffff` o `#f8f9fa` mientras que el texto interior cambia a blanco/gris claro, haciendo que los nombres de categorías, títulos de productos, precios y la barra de beneficios queden invisibles sobre fondo blanco.

**Solución obligatoria en CSS (`app/static/css/`):**

1. Definir variables CSS globales en `:root` y `[data-theme="dark"]` (y asegurar también compatibilidad si el script aplica `body.dark-mode` o `html[data-theme="dark"]`):

```css
:root {
    --bg-body: #F4F5F7;
    --bg-surface: #FFFFFF;
    --bg-surface-alt: #F8F9FA;
    --bg-input: #FFFFFF;
    --text-primary: #111111;
    --text-secondary: #4B5563;
    --text-muted: #6B7280;
    --border-color: #E5E7EB;
    --card-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
    --brand-yellow: #FFD100;
    --brand-yellow-hover: #E6BC00;
    --brand-black: #111111;
}

html[data-theme="dark"],
body.dark-mode,
[data-theme="dark"] body {
    --bg-body: #0D0D0D;
    --bg-surface: #18181B;
    --bg-surface-alt: #222226;
    --bg-input: #27272A;
    --text-primary: #F4F4F5;
    --text-secondary: #D4D4D8;
    --text-muted: #A1A1AA;
    --border-color: #2E2E34;
    --card-shadow: 0 6px 18px rgba(0, 0, 0, 0.45);
}
```

2. Auditar todo el CSS y las plantillas HTML para eliminar colores blancos fijos (`#fff`, `#ffffff`, `white`, `#f8f9fa`, `#f9fafb`) y reemplazarlos por variables en:
   - Barra superior y contenedor del buscador.
   - Franja de beneficios bajo el Hero (Entregas a Domicilio, Envío Gratis, Compra 100% Segura, Garantía de Calidad).
   - Tarjetas de Categorías de la Ferretería (`.category-card` y sus textos).
   - Tarjetas de Productos Destacados y catálogo general (`.product-card`, `.product-title`, `.product-category`, `.product-price`, etiqueta SKU).
   - Banner pre-footer (Regístrate hoy y gestiona tus pedidos de ferretería sin filas).
   - Tarjetas de Login, Registro, Recuperar Contraseña, Contacto, Perfil, Libreta de Direcciones, Carrito, Checkout y Páginas Legales.
   - Todos los `input`, `select`, `textarea`, tablas y modales.

### 3.2. Centrado de Botones de Redes Sociales y Reubicación del Botón de WhatsApp (Punto 2)
**Problema actual:**
- El botón flotante verde de WhatsApp aparece a la izquierda, superpuesto encima del botón amarillo "Explorar Catálogo" del Hero.
- En el pie de página (Footer), los 4 botones circulares de redes sociales tienen los iconos SVG desplazados hacia una esquina en lugar de estar centrados dentro del círculo.

**Solución obligatoria en CSS y HTML:**

**Botón Flotante de WhatsApp:**
- Ubicarlo exclusivamente en la esquina inferior derecha (`bottom: 24px; right: 24px; left: auto !important; top: auto !important;`).
- Ubicar el botón "Volver arriba" (Back to top) justo encima (`bottom: 90px; right: 26px;`) para que nunca colisionen.
- Centrar el icono SVG de WhatsApp con `display: flex; align-items: center; justify-content: center; padding: 0;`.

**Botones de Redes Sociales en el Footer:**

```css
.footer-socials, .social-links {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 12px;
    margin-top: 16px;
    padding: 0;
    list-style: none;
}
.footer-socials a, .social-links a, .social-btn {
    width: 42px;
    height: 42px;
    min-width: 42px;
    min-height: 42px;
    border-radius: 50%;
    background-color: #1F1F23;
    border: 1px solid #333338;
    color: #FFD100;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 0 !important;
    margin: 0 !important;
    line-height: 1 !important;
    text-decoration: none;
    transition: transform 0.2s ease, background-color 0.2s ease, color 0.2s ease;
}
.footer-socials a svg, .social-links a svg, .social-btn svg {
    width: 18px;
    height: 18px;
    display: block;
    margin: auto;
    fill: currentColor;
}
.footer-socials a:hover, .social-links a:hover, .social-btn:hover {
    background-color: #FFD100;
    color: #111111;
    border-color: #FFD100;
    transform: translateY(-3px);
}
```

### 3.3. Mensaje Emergente (Toast) al Agregar al Carrito sin Superposición (Punto 4)
**Problema actual:**
Al agregar un producto al carrito, el mensaje emergente de confirmación se superpone con elementos de navegación o contenido interactivo de la web.

**Solución obligatoria:**
- Crear un contenedor `#toast-container` fijo debajo de la altura del navbar superior (`top: 92px; right: 24px; z-index: 9999; pointer-events: none;`).
- Cada `.toast-item` debe tener:
  - `pointer-events: auto;`
  - `max-width: 360px;`
  - Fondo `--bg-surface`, texto `--text-primary`, borde izquierdo de `4px solid #FFD100` y sombra pronunciada.
  - Botón de cierre `×` inmediato y auto-cierre a los 2800ms con animación suave de salida, evitando apilar más de 2 notificaciones simultáneas (si se agrega otro producto rápido, actualizar el contador o reemplazar el toast anterior).

---

## 4. FASE 3: Rediseño Profesional de Formularios de Contacto y Direcciones del Valle de Aburrá (Puntos 5 y 6)

### 4.1. Rediseño y Centrado del Formulario de Contacto /contacto (Punto 5)
**Problema actual:**
El formulario "Envíanos un mensaje" en `/contacto` se ve desalineado, con campos que no están centrados ni proporcionados profesionalmente.

**Solución obligatoria:**

- Envolver la vista `/contacto` en un contenedor centrado (`max-width: 1080px; margin: 48px auto; padding: 0 20px;`).
- Diseñar una cuadrícula equilibrada de 2 columnas en escritorio (`display: grid; grid-template-columns: 1fr 1.4fr; gap: 32px; align-items: start;`) que pase a 1 columna centrada en móvil:
  - **Panel Izquierdo (Información Comercial):** Tarjeta con fondo oscuro `#141417`, texto blanco, acentos amarillos `#FFD100`, mostrando Dirección en Medellín, Teléfono/WhatsApp, Correo de soporte, Horario de despacho (Lunes a Sábado) y Cobertura en los 10 municipios del Valle de Aburrá.
  - **Panel Derecho (Tarjeta del Formulario "Envíanos un mensaje"):**
    - Contenedor con `background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: 14px; padding: 36px; box-shadow: var(--card-shadow); width: 100%; box-sizing: border-box;`.
    - Encabezado centrado o claramente jerarquizado con título y subtítulo.
    - Grid interna del formulario (`display: grid; grid-template-columns: 1fr 1fr; gap: 18px;`):
      - Fila 1: Nombre completo * (col 1) | Correo electrónico * (col 2).
      - Fila 2: Teléfono / Celular (col 1) | Asunto * (`<select>`: Cotización para obra, Consulta de stock, Estado de pedido, Garantías y devoluciones, Otro) (col 2).
      - Fila 3 (`grid-column: 1 / -1`): Mensaje detallado * (`<textarea rows="5">`).
      - Fila 4 (`grid-column: 1 / -1`): Casilla de aceptación de la Política de Tratamiento de Datos Personales alineada con `display: flex; align-items: center; gap: 10px;`.
      - Fila 5 (`grid-column: 1 / -1`): Botón de envío centrado de ancho completo (`width: 100%; height: 48px; font-weight: 700; background: #FFD100; color: #111111; border-radius: 8px;`).

### 4.2. Rediseño de Formularios de Dirección (Libreta de Direcciones y Checkout) exclusivos para el Valle de Aburrá (Punto 6)
**Problema actual:**
Tanto en la Libreta de Direcciones del perfil como en el Checkout, el formulario de dirección se ve poco profesional, desalineado e incluye el campo "Departamento o región", el cual sobra porque la ferretería opera únicamente en el Valle de Aburrá.

**Solución obligatoria:**

- Eliminar el campo "Departamento o región" de todos los formularios HTML (tanto en perfil/libreta de direcciones como en checkout).
- En el backend (`routes/orders.py`, `routes/public.py` o `services/order_service.py`), si el modelo `Address` u `Order` tiene la columna `department` o `region`, asignarle internamente el valor fijo `"Antioquia"` sin pedírselo al usuario.
- Convertir el campo "Ciudad o Municipio" en un `<select>` obligatorio con los 10 municipios del Valle de Aburrá:
  - Medellín
  - Bello
  - Itagüí
  - Envigado
  - Sabaneta
  - Copacabana
  - La Estrella
  - Girardota
  - Caldas
  - Barbosa

  (Validar también en el backend que el municipio recibido pertenezca a esta lista oficial del Valle de Aburrá).

- Maquetación centrada y profesional de la tarjeta de Dirección (`max-width: 680px; margin: 0 auto; background: var(--bg-surface); padding: 32px; border-radius: 14px; border: 1px solid var(--border-color);`):
  - Usar CSS Grid de 2 columnas (`grid-template-columns: repeat(2, 1fr); gap: 16px;`) en escritorio y 1 columna en móvil:
    - Fila 1: Nombre de quien recibe * | Teléfono celular de contacto * (placeholder: Ej: 300 000 0000).
    - Fila 2: Municipio (Valle de Aburrá) * (`<select>`) | Barrio o Sector * (placeholder: Ej: El Poblado, Belén, Machado...).
    - Fila 3 (`grid-column: 1 / -1`): Dirección exacta de entrega * (placeholder: Ej: Calle 50 # 45-20).
    - Fila 4: Interior / Apto / Bodega / Obra (placeholder: Ej: Bodega 3, Obra Torre Central) | Etiqueta (Opcional) (placeholder: Ej: Casa, Obra Norte, Taller).
    - Fila 5 (`grid-column: 1 / -1`): Indicaciones de entrega para el conductor (placeholder: Ej: Entregar en portería o preguntar por el encargado de obra).
    - Fila 6 (`grid-column: 1 / -1`): Botón principal centrado de ancho completo (`width: 100%`) con diseño industrial Amarillo/Negro.

---

## 5. FASE 4: Internacionalización Completa ES / EN (Punto 3)

### 5.1. Traducción del 100% de la Interfaz (Punto 3)
**Problema actual:**
Al cambiar el selector de idioma a EN, solo se traducen algunos elementos del menú y el resto de la página queda en español.

**Solución obligatoria:**

- Centralizar todas las cadenas de texto en `app/translations.py` con soporte completo para `es` y `en`.
- Exponer la función `t(key)` y la variable `current_lang` en todas las plantillas mediante `@app.context_processor`.
- Reemplazar los textos fijos en español en `base.html`, `home.html`, `products/`, `cart/`, `orders/`, `auth/`, `contact.html` y `footer` usando `{{ t('...') }}`:
  - **Navbar:** Modo Admin / Admin Mode, Mis Pedidos / My Orders, Salir / Logout, Ingresar / Login, Registrarse / Register, Carrito / Cart, Buscar herramientas, materiales o SKU... / Search tools, materials or SKU....
  - **Hero Home:** Badge FERRETERÍA INDUSTRIAL & DE OBRA / INDUSTRIAL & CONSTRUCTION HARDWARE, título Materiales y herramientas para construir con confianza. / Materials and tools to build with confidence., subtítulo, botones Explorar Catálogo / Explore Catalog y Tarifas de Entrega / Delivery Rates.
  - **Franja de Beneficios:** Entregas a Domicilio / Home & Site Delivery, Envío Gratis / Free Shipping, Compra 100% Segura / 100% Secure Purchase, Garantía de Calidad / Quality Guarantee y sus subtítulos.
  - **Sección Categorías:** EXPLORA POR SEGMENTO / EXPLORE BY SEGMENT, Categorías de la Ferretería / Hardware Categories, Ver todas / View all, contador productos / products, y traducción dinámica de nombres de categorías estándar (Herramientas Manuales -> Hand Tools, Herramientas Eléctricas -> Power Tools, Construcción -> Construction, Electricidad -> Electrical, Pintura y Acabados -> Paint & Finishes, Plomería y Tuberías -> Plumbing & Pipes, Seguridad Industrial -> Industrial Safety).
  - **Banners CTA y Productos Destacados:** RECOMENDADOS / RECOMMENDED, Productos Destacados / Featured Products, Ir al catálogo / Go to catalog, Precio unitario / Unit price, + Agregar / + Add, Agotado / Out of stock.
  - **Catálogo, Detalle, Carrito, Checkout, Contacto, Login, Registro y Footer:** Traducir todos los títulos, filtros, etiquetas de formularios, botones y enlaces del pie de página.

---

## 6. FASE 5: Marco Legal Colombiano Especializado para Ferretería (Punto 7)

### 6.1. Renovación de Páginas Legales según Normativa Colombiana y Estándares del Sector (Homecenter / Ferreterías en Colombia)

Reescribir y maquetar profesionalmente (con contenedor centrado `max-width: 880px`, tabla de contenido, tarjetas informativas y compatibilidad total con Modo Oscuro) las tres vistas legales:

**Política de Privacidad y Tratamiento de Datos Personales (`/politica-de-privacidad`):**
- Marco Legal: Artículo 15 de la Constitución Política de Colombia, Ley Estatutaria 1581 de 2012, Decreto Reglamentario 1377 de 2013 y Decreto Único Reglamentario 1074 de 2015.
- Responsable del Tratamiento: Ferretería El Constructor, Medellín, Antioquia, Colombia (contacto@ferreteriaelconstructor.com).
- Finalidades: Procesamiento y despacho de pedidos de materiales de construcción y herramientas en el Valle de Aburrá, validación de identidad, facturación, notificaciones de estado de entrega en obra o domicilio, atención de PQRS y seguridad de la plataforma.
- Derechos del Titular (Habeas Data): Conocer, actualizar, rectificar y suprimir sus datos personales; solicitar prueba de la autorización; revocar la autorización y acudir ante la Superintendencia de Industria y Comercio (SIC).
- Términos de Respuesta Legal: Consultas en un máximo de diez (10) días hábiles (Art. 14 Ley 1581 de 2012) y Reclamos en un máximo de quince (15) días hábiles (Art. 15 Ley 1581 de 2012).

**Términos y Condiciones Comerciales (`/terminos-y-condiciones`):**
- Marco Legal: Ley 1480 de 2011 (Estatuto del Consumidor) y Ley 527 de 1999 (Comercio Electrónico en Colombia).
- Cobertura Exclusiva de Despacho: Entregas habilitadas exclusivamente en los 10 municipios del Valle de Aburrá, Antioquia (Medellín, Bello, Itagüí, Envigado, Sabaneta, Copacabana, La Estrella, Girardota, Caldas y Barbosa). Entregas en primer piso, portería o entrada de obra con acceso vehicular seguro.
- Precios y Disponibilidad: Precios expresados en Pesos Colombianos (COP $). Confirmación sujeta a verificación transaccional de inventario en servidor.
- Derecho de Retracto (Art. 47 Ley 1480 de 2011): Plazo legal de cinco (5) días hábiles contados desde la entrega para devolver el producto sin uso, con empaques, sellos y accesorios originales. Excepciones aplicables a ferretería (Numeral 3 y 4 Art. 47): No aplica derecho de retracto sobre bienes confeccionados o cortados a medida solicitada por el cliente (cables eléctricos cortados por metro, cadenas, mangueras o perfiles dimensionados), pinturas preparadas bajo fórmula o color personalizado, ni materiales en bulto (cemento, estuco, mortero, adhesivos o químicos) cuyos sellos de fábrica hayan sido abiertos o expuestos a humedad.
- Garantía Legal (Art. 7 al 16 Ley 1480 de 2011): Cobertura por defectos de idoneidad, calidad y seguridad en herramientas eléctricas y manuales según tiempos del fabricante; excluye daños por sobrecarga en obra, voltaje inadecuado o desgaste natural de consumibles (brocas, discos abrasivos, lijas, cuchillas).
- Reversión del Pago (Art. 51 Ley 1480 y Decreto 587 de 2016) y Aviso de Pasarela en Modo de Prueba: Explicación de las causales legales de reversión dentro de los 5 días hábiles y declaración expresa de que el sistema opera actualmente con un módulo de pagos simulado (Sandbox) que no realiza débitos bancarios reales.

**Política de Cookies (`/politica-de-cookies`):**
- Adecuada a los lineamientos de la Superintendencia de Industria y Comercio (SIC) sobre el uso de cookies propias de sesión (`session`), seguridad (`csrf_token`), preferencias de interfaz (`theme`, `lang`) y consentimiento (`cookie_consent`), incluyendo tabla detallada de duración y finalidad.

---

## 7. Criterios de Aceptación y Pruebas Automatizadas (pytest)

Antes de finalizar la tarea, ejecutar la suite de pruebas y verificar que:

- `GET /admin/pedidos/1` y el flujo completo de confirmación de compra en `/orders/checkout` responden sin ningún `AttributeError` (200 OK).
- La barra de búsqueda funciona tanto para visitantes como para usuarios autenticados (clientes y administradores).
- Todas las fechas de registro de usuarios, creación de pedidos y movimientos de inventario se muestran en hora local de Bogotá (UTC-5).
- En Modo Oscuro, no queda ningún recuadro blanco con texto ilegible en Home, Catálogo, Formularios ni Perfil.
- Los iconos de redes sociales del footer están centrados al milímetro y el botón flotante de WhatsApp está en la esquina inferior derecha sin tapar ningún botón del Hero.
- Los formularios de `/contacto`, Libreta de Direcciones y Checkout están centrados, alineados, sin el campo "Departamento" y con el selector de los 10 municipios del Valle de Aburrá.
- El cambio de idioma ES | EN traduce toda la interfaz visible.