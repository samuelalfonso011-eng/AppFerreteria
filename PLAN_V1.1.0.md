# PLAN DE ACTUALIZACIÓN — SISTEMA WEB FERRETERÍA (v1.1.0)

## 1. Objetivo de la versión 1.1.0
Evolucionar la versión 1.0.0 funcional hacia la versión **1.1.0**, corrigiendo un bug crítico de maquetación en el Panel Administrativo y añadiendo una nueva identidad visual (Amarillo y Negro industrial), mejoras avanzadas de UI/UX, navegación fluida (carga parcial/SPA-like), internacionalización (ES/EN), modo oscuro, páginas legales con banner de cookies, recuperación de contraseña, formulario de contacto y optimización de recursos e imágenes temporales.

---

## 2. Fase 1: Corrección Crítica del Layout en Panel Admin (`admin/base.html` o `admin.css`)
### Diagnóstico del Bug Actual
En la vista actual del Dashboard Administrativo:
1. El `sidebar` izquierdo (`Panel Ferretería`) se superpone sobre el contenedor principal (`.admin-main` / `.admin-content`), tapando el inicio del encabezado ("Panel Operativo"), la primera tarjeta de indicadores a la izquierda de "TOTAL VENTAS HISTÓRICAS" y el botón "Revisar Alertas de Stock".
2. Existe un espacio en blanco excesivo en la parte superior del contenedor derecho que empuja el contenido hacia abajo.

### Solución Técnica Obligatoria
1. **Reestructurar el contenedor raíz del Admin (`.admin-layout` o `.admin-wrapper`):**
   - Aplicar `display: flex; min-height: 100vh; width: 100%; margin: 0; padding: 0;`.
2. **Configurar el Sidebar (`.admin-sidebar`):**
   - Definir un ancho fijo en escritorio: `width: 260px; flex-shrink: 0; position: fixed; top: 0; left: 0; height: 100vh; z-index: 1000; overflow-y: auto;`.
3. **Configurar el Contenedor Principal (`.admin-main` / `.admin-content`):**
   - Compensar el ancho del sidebar fijo: `margin-left: 260px; width: calc(100% - 260px); min-height: 100vh; display: flex; flex-direction: column; padding-top: 0 !important;`.
   - Eliminar cualquier `margin-top` o `height: 100vh` mal aplicado antes del `topbar` que esté generando el bloque blanco superior.
4. **Responsividad del Admin (`@media (max-width: 992px)`):**
   - En pantallas móviles/tablets, el sidebar debe pasar a `transform: translateX(-100%); transition: transform 0.3s ease;` con un botón hamburguesa en el `topbar` para abrirlo/cerrarlo (`.sidebar-open`), y `.admin-main` debe pasar a `margin-left: 0; width: 100%;`.
5. **Grid de Tarjetas KPI:**
   - Usar `display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1.25rem;` para que ninguna tarjeta quede cortada ni desbordada.

---

## 3. Fase 2: Identidad Visual Amarillo y Negro + Modo Oscuro
### Paleta de Colores (Estilo Ferretería Industrial)
Definir variables CSS globales en `:root` (`app/static/css/main.css` o `style.css`):
- `--brand-yellow: #FFD100;` (Amarillo industrial principal)
- `--brand-yellow-hover: #E6BC00;`
- `--brand-black: #111111;` (Negro profundo para barras, encabezados y contraste)
- `--brand-charcoal: #1E1E1E;` (Gris carbón para tarjetas oscuras y sidebar)
- `--text-on-yellow: #111111;` (Texto negro sobre botones amarillos para máximo contraste WCAG AAA)

### Modo Claro vs. Modo Oscuro (`[data-theme="dark"]`)
1. Implementar soporte mediante atributo `data-theme="dark"` en la etiqueta `<html>`.
2. Incluir un botón interruptor (Sol/Luna) en el `navbar` público y en el `topbar` del admin.
3. Guardar la preferencia en `localStorage.getItem('theme')` y aplicarla mediante un script inline en el `<head>` antes del renderizado para evitar parpadeos (FOUC).
4. En **Modo Oscuro**, los fondos principales pasan a `#121212`, tarjetas a `#1E1E1E`, bordes a `#2E2E2E`, textos a `#F5F5F5` y los acentos continúan en `--brand-yellow` (`#FFD100`).

---

## 4. Fase 3: Carpeta `img`, Favicon Custom e Imágenes Temporales
1. Crear y asegurar la carpeta `app/static/img/` y `app/static/img/temp/`.
2. Generar archivos SVG/PNG limpios y profesionales en estética amarillo/negro dentro de `app/static/img/`:
   - `favicon.svg` y `favicon.ico` (Icono de llave inglesa/tuerca en amarillo `#FFD100` sobre fondo negro `#111111`) y enlazarlo en `base.html` y `admin/base.html`.
   - `logo.svg`: Logotipo oficial de la ferretería en amarillo y negro.
   - `hero-banner.svg`: Ilustración/banner industrial para el inicio.
   - `placeholder-product.svg`: Imagen temporal predeterminada para productos sin foto o cuando falle la carga (`onerror="this.src='/static/img/placeholder-product.svg'"`).
   - Imágenes temporales por categoría en `app/static/img/temp/` (`herramientas.svg`, `electricidad.svg`, `plomeria.svg`, `construccion.svg`, `seguridad.svg`) y vincularlas a los productos de demostración si no tienen imagen subida.

---

## 5. Fase 4: Recuperación de Contraseña en Autenticación (`auth.py`)
1. **Rutas y Vistas:**
   - `GET/POST /auth/forgot-password`: Formulario donde el usuario ingresa su correo electrónico.
   - `GET/POST /auth/reset-password/<token>`: Formulario para definir nueva contraseña y confirmación.
2. **Lógica de Seguridad:**
   - Utilizar `itsdangerous.URLSafeTimedSerializer` (incluido con Flask) con `SECRET_KEY` para generar un token firmado con expiración de 30 minutos.
   - Si el servidor SMTP no está configurado en `.env`, en modo desarrollo registrar el enlace seguro de recuperación en la consola y mostrar un banner informativo controlado de entorno de pruebas (o enviar correo real si `MAIL_SERVER` está configurado).
   - Validar fortaleza de la nueva contraseña, actualizar el hash con `werkzeug.security.generate_password_hash` e invalidar sesiones previas.
3. **Enlace en Login:**
   - Añadir el enlace `"¿Olvidaste tu contraseña?"` debajo del campo de contraseña en `templates/auth/login.html`.

---

## 6. Fase 5: Páginas Legales y Banner de Aceptación de Cookies
1. **Nuevas rutas públicas en `routes/public.py`:**
   - `/politica-de-privacidad` (`templates/legal/privacy.html`): Tratamiento de datos personales, derechos del titular, finalidad de datos de entrega y contacto.
   - `/terminos-y-condiciones` (`templates/legal/terms.html`): Condiciones de uso, precios, disponibilidad de inventario, envíos, devoluciones y aclaración del entorno de pagos de prueba.
   - `/politica-de-cookies` (`templates/legal/cookies.html`): Detalle de cookies técnicas (sesión, CSRF, carrito, idioma, tema visual) y preferencias.
2. **Enlaces en el Footer y Registro:**
   - Vincular las tres páginas en el pie de página global y añadir casilla de verificación obligatoria de aceptación de términos y privacidad en el formulario de registro (`register.html`).
3. **Banner de Consentimiento de Cookies:**
   - Componente flotante inferior en `base.html` con botones: **"Aceptar todas"**, **"Solo esenciales"** y enlace a **"Política de Cookies"**.
   - Persistir la decisión en `localStorage` (`cookie_consent`) y en una cookie HTTP para no volver a mostrarlo una vez aceptado.

---

## 7. Fase 6: Formulario de Contacto y CTAs Repetidos
1. **Formulario de Contacto (`/contacto` y sección en Home):**
   - Campos: Nombre completo, Correo electrónico, Teléfono (opcional), Asunto (Consulta de producto, Cotización mayorista, Estado de pedido, Soporte), Mensaje y aceptación de política de privacidad.
   - Guardar los mensajes en una tabla `contact_messages` (con migración en SQLAlchemy) o registrarlos en el panel admin para que el administrador pueda consultarlos.
   - Protección CSRF y validación tanto en cliente como en servidor.
2. **CTAs Repetidos (Llamados a la Acción Estratégicos):**
   - Colocar CTAs claros en amarillo (`#FFD100`) y negro en:
     1. Hero principal de la página de inicio ("Explorar Catálogo" / "Ofertas de la Semana").
     2. Sección intermedia después de Categorías Destacadas ("¿Buscas herramientas para tu obra? Cotiza o compra en línea con envío a domicilio").
     3. Pre-footer antes de cerrar la página ("Regístrate hoy y gestiona tus pedidos de ferretería sin filas").
3. **Botones de Redes Sociales:**
   - Añadir iconos vectoriales (SVG) de WhatsApp, Instagram, Facebook y TikTok en el Footer y un botón de contacto rápido por WhatsApp/Soporte, con enlaces configurables desde `store_settings`.

---

## 8. Fase 7: UI/UX, Animaciones, Navegación Parcial (SPA-like) y Rendimiento
1. **Transición entre páginas (Cargar solo lo que ve el usuario):**
   - Implementar un interceptor ligero en JavaScript (`app/static/js/navigation.js`) usando `fetch()` y `History API` (`pushState` / `popstate`) para enlaces internos públicos:
     - Al hacer clic en un enlace interno, obtener el HTML, extraer únicamente el contenedor `#main-content` y actualizar el DOM con una transición suave de opacidad (`150ms`), manteniendo intactos el `navbar` y el `footer`.
     - Añadir barra de progreso superior amarilla durante la carga.
   - Aplicar `loading="lazy"` y `decoding="async"` a todas las imágenes del catálogo y usar `IntersectionObserver` para cargar recursos pesados únicamente cuando entran en el viewport.
2. **Animaciones suaves al hacer scroll (Scroll Reveal):**
   - Usar `IntersectionObserver` para aplicar clases `.reveal-visible` (transición suave de `opacity: 0; transform: translateY(20px)` a `opacity: 1; transform: translateY(0)`) en tarjetas de productos, categorías y secciones. Respetar `prefers-reduced-motion`.
3. **Microinteracciones y Estados Hover:**
   - Tarjetas de producto: elevación sutil (`transform: translateY(-4px)`), borde amarillo al pasar el cursor y zoom suave en la imagen.
   - Botones: efecto ripple o escala suave en `:active`, cambio de contraste en `:hover` y spinner integrado al agregar al carrito.
4. **Mobile Responsiveness y Menú Móvil:**
   - Menú tipo *Drawer* lateral o desplegable animado en dispositivos móviles (`< 768px`) con cierre al tocar fuera o presionar `Escape`.
   - Tablas del panel admin con contenedor `.table-responsive` (`overflow-x: auto`).
5. **Botón de Volver Arriba (Back to Top):**
   - Botón flotante en la esquina inferior derecha (amarillo con flecha negra) que aparece suavemente al superar `300px` de scroll vertical y ejecuta `window.scrollTo({ top: 0, behavior: 'smooth' })`.
6. **Validación de Formularios y Mejora de Mensajes de Error:**
   - Validación en tiempo real en inputs (bordes verdes/rojos, mensajes debajo de cada campo con iconos claros).
   - Sistema de notificaciones tipo **Toast** flotantes (Éxito, Advertencia, Error) con cierre automático y barra de tiempo, reemplazando alertas bruscas.
7. **Cambio de Idioma (ES / EN):**
   - Selector `ES | EN` en la barra superior.
   - Diccionario de traducción para textos de interfaz (navegación, botones, carrito, estados, títulos y formularios) gestionado por sesión/cookie (`/set-language/<lang>`) y soporte en plantillas/JS.
8. **Optimización de Velocidad:**
   - Compresión Gzip/Brotli o cabeceras de caché para estáticos en Flask (`SEND_FILE_MAX_AGE_DEFAULT`).
   - Carga diferida (`defer`) de scripts JavaScript.
   - Optimización de consultas SQLAlchemy (evitar N+1 usando `joinedload` en productos/categorías y pedidos).

---

## 9. Criterios de Verificación y Pruebas (`pytest`)
Antes de dar por terminada la versión 1.1.0, verificar y ejecutar pruebas para confirmar que:
1. En `/admin`, el sidebar **no oculta** ninguna tarjeta ni texto del Dashboard en ninguna resolución (`1920px`, `1366px`, `768px`, `375px`).
2. El flujo de recuperación de contraseña genera tokens válidos, rechaza tokens expirados/manipulados y actualiza la contraseña correctamente.
3. Las páginas `/politica-de-privacidad`, `/terminos-y-condiciones`, `/politica-de-cookies` y `/contacto` responden con código `200 OK`.
4. Todas las imágenes en `app/static/img/` y `favicon.svg` cargan sin errores `404`.
5. El cambio de tema (Claro/Oscuro) y de idioma (ES/EN) persiste al navegar entre páginas.
6. Todas las pruebas existentes de la v1.0.0 siguen pasando al 100%.