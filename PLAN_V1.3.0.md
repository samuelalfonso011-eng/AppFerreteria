# PLAN MAESTRO DE ARQUITECTURA, RENDIMIENTO Y SEGURIDAD — FERRETERÍA EL CONSTRUCTOR (v1.3.0)

## 1. Rol y Objetivo de la Versión 1.3.0
Actúa como Arquitecto de Software Senior, Especialista en Ciberseguridad, Ingeniero de Rendimiento (Performance) y Desarrollador Full-Stack Python/Flask.
Tu objetivo es evolucionar el sistema hacia la versión **1.3.0**, implementando optimización algorítmica $O(N)$, sistema de caché con invalidación automática ante cambios en base de datos, deduplicación de llamadas API, idempotencia contra dobles pagos, control estricto de procesos/workers con timeouts, alertas de gasto, facturación electrónica (estándar DIAN Colombia), política de reembolsos, gráficos interactivos en el Dashboard, compresión de imágenes, SEO/metadatos, protección anti-spam y endurecimiento HTTPS/secretos.

**Reglas de ejecución:**
- Mantén intactas todas las correcciones de las versiones `v1.0.0`, `v1.1.0` y `v1.2.0` (layout del Admin, Modo Oscuro, zona horaria `America/Bogota`, municipios del Valle de Aburrá e internacionalización `ES/EN`).
- Implementa fase por fase y valida con pruebas automatizadas (`pytest`) al finalizar cada bloque.

---

## 2. FASE 1: Rendimiento, Complejidad Algorítmica $O(N)$, Caché e Invalidación Automática

### 2.1. Eliminación de Ciclos Anidados y Optimización a Complejidad $O(N)$
1. **Auditoría de código Python (`app/services/`, `app/routes/`) y JavaScript (`app/static/js/`):**
   - Buscar y eliminar cualquier ciclo anidado (`for ... in ...: for ... in ...`) que cruce colecciones en memoria con complejidad cuadrática $O(N^2)$.
   - **En Python:** Transformar listas de búsqueda en diccionarios o conjuntos (`dict` / `set`) indexados por `id` o `sku` para lograr búsquedas en tiempo constante $O(1)$ y recorridos totales en tiempo lineal $O(N)$.
   - **En SQLAlchemy:** Prohibir consultas dentro de bucles (`N+1 queries`). Utilizar `joinedload`, `selectinload` o consultas agrupadas con `func.sum`, `func.count` y `GROUP BY` directamente en PostgreSQL.
   - **En JavaScript:** Usar `Map` o `Set` para cruzar ítems del carrito, filtros de catálogo y estados del DOM en una sola pasada $O(N)$.

### 2.2. Sistema de Caché e Invalidación Automática en Base de Datos
1. **Implementación de Caché (`app/utils/cache.py` o `Flask-Caching`):**
   - Implementar un gestor de caché en memoria con TTL configurable (`SimpleCache` con soporte para Redis futuro) para almacenar resultados de:
     - Listado de categorías activas (`cache_key="categories:active"`).
     - Catálogo público y productos destacados (`cache_key="products:featured"`, `"catalog:page:..."`).
     - Configuraciones de la tienda (`cache_key="store:settings"`).
     - Indicadores y series de datos del Dashboard Administrativo (`cache_key="admin:dashboard:metrics"`).
2. **Invalidación Automática en cada cambio de Base de Datos:**
   - Registrar **SQLAlchemy Event Listeners** (`after_insert`, `after_update`, `after_delete` y `after_commit`) en `app/extensions.py` o `app/utils/cache.py` sobre los modelos `Product`, `Category`, `Order`, `OrderItem`, `Payment`, `InventoryMovement` y `StoreSettings`.
   - Siempre que ocurra un `INSERT`, `UPDATE` o `DELETE` en cualquiera de esas tablas, invalidar inmediatamente las llaves de caché afectadas (`cache.clear()` o limpieza selectiva por prefijo) para garantizar que el usuario y el administrador jamás vean datos obsoletos.

### 2.3. Optimización de Llamadas API y Eliminación de Duplicados
1. **Deduplicación en Frontend (`app/static/js/`):**
   - Implementar un wrapper central `apiFetch(url, options)` con:
     - **Mapa de peticiones en vuelo (`inFlightRequests = new Map()`):** Si se dispara una petición `GET` idéntica mientras otra igual sigue pendiente, reutilizar la misma promesa en lugar de abrir una segunda conexión HTTP.
     - **AbortController y Debounce (`300ms`):** En el buscador y filtros dinámicos, cancelar cualquier petición previa inconclusa si el usuario sigue escribiendo o cambiando filtros.
2. **Consolidación en Backend:**
   - Evitar múltiples llamadas separadas al cargar una vista; consolidar respuestas JSON de carrito, contadores y validación de stock en una sola respuesta estructurada.

### 2.4. Control de Procesos, Jobs, Cron Jobs y Workers (Cero Procesos Indefinidos)
1. **Timeouts estrictos en Base de Datos y Servidor (`app/config.py`):**
   - Configurar en `SQLALCHEMY_ENGINE_OPTIONS`:
     - `pool_pre_ping: True`
     - `pool_recycle: 300`
     - `pool_timeout: 15`
     - `connect_args: {"options": "-c statement_timeout=10000"}` (corta automáticamente cualquier consulta en PostgreSQL que supere 10 segundos).
2. **Gestor Seguro de Tareas y Limpieza (`app/utils/worker_guard.py`):**
   - Cualquier tarea programada, hilo secundario (envío de correos, limpieza de carritos abandonados, compresión de imágenes o mantenimiento) debe ejecutarse con un **timeout máximo obligatorio (`MAX_TASK_TIMEOUT = 15s`)**, bloque `try / finally` que libere `db.session.remove()` y cierre descriptores de archivo.
   - Prohibir bucles `while True:` sin condición de salida ni tareas en segundo plano que queden corriendo indefinidamente.

---

## 3. FASE 2: Idempotencia en Pagos, Factura Electrónica y Alertas de Gasto

### 3.1. Prevención Estricta de Doble Pago en una Compra
1. **Llave de Idempotencia (`idempotency_key`):**
   - Al cargar la vista de Checkout (`GET /orders/checkout`), generar un token único `checkout_idempotency_key` (`uuid4().hex`) guardado en la sesión y en un campo oculto del formulario.
   - En el modelo `Order` y `Payment`, validar la existencia de `idempotency_key` (con restricción `UNIQUE`).
2. **Bloqueo Transaccional y Control de Estado:**
   - Al recibir `POST /orders/checkout` o procesar un pago en `payment_service.py`:
     - Consumir e invalidar inmediatamente la llave de idempotencia en sesión de forma atómica.
     - Bloquear la fila del pedido/inventario con `with_for_update()` en SQLAlchemy.
     - Si el pedido ya tiene un pago en estado `APROBADO_PRUEBA` o una transacción en curso, rechazar cualquier segundo intento y redirigir directamente a la vista de confirmación del pedido existente sin volver a cobrar ni descontar stock dos veces.
   - **En Frontend:** Deshabilitar el botón de confirmar compra en el primer clic (`button.disabled = true`), evitando dobles envíos por doble clic.

### 3.2. Módulo de Facturación Electrónica (Estándar DIAN Colombia en Modo Simulación)
1. **Datos Fiscales del Adquirente en Checkout:**
   - Añadir en el paso de compra los datos para Facturación Electrónica:
     - Tipo de documento (`CC - Cédula de Ciudadanía`, `NIT`, `CE - Cédula de Extranjería`, `Pasaporte`).
     - Número de documento / NIT (con dígito de verificación opcional).
     - Razón Social o Nombre Completo y Correo de recepción de factura electrónica.
2. **Generación de Factura Electrónica (`app/services/invoice_service.py`):**
   - Al confirmarse un pedido con pago aprobado, generar automáticamente el registro de **Factura Electrónica de Venta**:
     - Prefijo y consecutivo autorizado simulado: `FE-0001`, `FE-0002`, etc.
     - Cálculo desglosado: Subtotal base gravable, **IVA (19%)**, costo de transporte y Total en **COP (\$)**.
     - Generación de **CUFE (Código Único de Factura Electrónica)** simulado mediante hash `SHA-384` (combinando número de factura, fecha/hora `America/Bogota`, NIT emisor de la ferretería, documento del cliente y total).
     - Código QR en SVG generado dinámicamente con los metadatos de validación.
3. **Vista e Impresión de Factura (`/orders/<id>/invoice` y en Panel Admin):**
   - Plantilla profesional de Representación Gráfica de Factura Electrónica (`templates/orders/invoice.html`) lista para visualizar e imprimir/guardar como PDF (`window.print()`), accesible tanto por el cliente en `"Mis Pedidos"` como por el administrador en `/admin/pedidos/<id>`.

### 3.3. Sistema de Alertas de Gasto y Monitoreo de Recursos
1. **Alertas de Presupuesto Operativo y Consumo en Panel Admin:**
   - En `store_settings` y en el Dashboard Administrativo, incorporar un panel de **Control y Alertas de Gasto Operativo**:
     - Monitoreo en tiempo real de uso de recursos (espacio ocupado en `uploads/`, conteo de registros en base de datos, tasa de peticiones/órdenes diarias y límite de presupuesto operativo mensual configurable en COP/USD).
     - Alerta visual automática (Amarillo al superar el **80%** del umbral configurado y Rojo al superar el **100%**).
2. **Alerta de Gasto / Tope de Compra para Clientes y Pedidos:**
   - Alertar en el panel administrativo cuando un pedido individual supere un umbral de alto valor configurable (ej. `> $2.000.000 COP`) para revisión prioritaria, y mostrar al cliente en el carrito un indicador de progreso de gasto y beneficio de envío gratuito.

---

## 4. FASE 3: Dashboard con Gráficos Reales, UX Modo Cliente y Compresión de Imágenes

### 4.1. Gráficos Interactivos en el Dashboard Administrativo
1. **Integración de Gráficos en `/admin` (`templates/admin/dashboard.html`):**
   - Crear un endpoint interno `GET /admin/api/metrics` (protegido por `@admin_required` y respaldado por caché) que devuelva series reales desde PostgreSQL.
   - Renderizar **3 gráficos interactivos** (con Chart.js o Canvas/SVG responsivo compatible con Modo Claro y Modo Oscuro en paleta Amarillo `#FFD100`, Verde, Gris y Carbón):
     1. **Evolución de Ventas Confirmadas (Líneas/Barras):** Ventas de los últimos 7 o 30 días según el filtro de fechas.
     2. **Top 5 Productos Más Vendidos (Barras Horizontales):** Por unidades vendidas e ingresos generados.
     3. **Distribución de Pedidos por Estado (Gráfico de Dona):** Pendientes, En preparación, Enviados, Entregados y Cancelados.

### 4.2. Eliminar Avisos de Registro en Modo Cliente Autenticado
1. **Condicionales en Plantillas (`home.html`, `base.html`, `products/`):**
   - Envolver el banner pre-footer (`"Regístrate hoy y gestiona tus pedidos de ferretería sin filas"`) y cualquier botón o aviso de `"Crear Cuenta de Cliente"` dentro de `{% if not current_user.is_authenticated %}`.
   - Cuando el cliente ya haya iniciado sesión, ocultar por completo los avisos de registro o mostrar en su lugar un acceso directo limpio a `"Ver Mis Pedidos"` / `"Continuar Comprando"`.

### 4.3. Compresión Automática de Imágenes
1. **Pipeline de Optimización con `Pillow` (`app/utils/image_optimizer.py`):**
   - Añadir `Pillow` en `requirements.txt`.
   - Al subir cualquier imagen de producto desde el Panel Administrativo:
     - Validar firma binaria real de la imagen.
     - Redimensionar proporcionalmente si supera `1200x1200 px` usando filtro `Image.Resampling.LANCZOS`.
     - Eliminar metadatos EXIF innecesarios.
     - Comprimir y guardar en formato optimizado (**WebP** o **JPEG progresivo** con `quality=80`, `optimize=True`), reduciendo el peso entre un 60% y 80%.
   - Añadir atributos `width`, `height`, `loading="lazy"` y `decoding="async"` en todas las etiquetas `<img>`.

---

## 5. FASE 4: Política de Reembolsos, SEO/Metadatos y Seguridad Avanzada (HTTPS, Secretos y Anti-Spam)

### 5.1. Página de Política de Reembolsos y Devoluciones (`/politica-de-reembolsos`)
1. **Ruta y Plantilla (`templates/legal/refunds.html`):**
   - Crear la ruta pública `/politica-de-reembolsos` vinculada en el Footer (`Legal & Privacidad`), en el Checkout y traducida en `ES | EN`.
   - Contenido adaptado a **Ferretería El Constructor (Valle de Aburrá)** bajo la **Ley 1480 de 2011 (Estatuto del Consumidor de Colombia)** y el **Decreto 587 de 2016**:
     - **Derecho de Retracto (Art. 47):** 5 días hábiles desde la entrega; devolución del 100% del dinero en un plazo máximo legal de 30 días calendario (o antes).
     - **Reversión del Pago (Art. 51 y Decreto 587 de 2016):** 5 días hábiles ante fraude, operación no solicitada, producto no recibido, producto defectuoso o no correspondiente a lo solicitado.
     - **Condiciones de Estado del Producto Ferretero:** Empaque original sellado, sin uso en obra, accesorios completos y factura electrónica.
     - **Productos Excluidos de Reembolso por Retracto:** Materiales cortados a medida (cables eléctricos por metro, tuberías o cadenas cortadas), pinturas preparadas por colorimetría a pedido y bultos de cemento, mortero, estuco o químicos abiertos o húmedos.
     - **Paso a paso para solicitar un reembolso** desde el perfil del cliente o formulario de soporte.

### 5.2. Metadescripciones, Metadatos SEO y Datos Estructurados
1. **Bloques SEO Dinámicos en `base.html` y todas las vistas:**
   - Implementar bloques Jinja2 `{% block meta_title %}`, `{% block meta_description %}`, `{% block meta_keywords %}` y `{% block canonical_url %}`.
   - Incluir etiquetas **Open Graph** (`og:title`, `og:description`, `og:type`, `og:url`, `og:image`, `og:locale="es_CO"`) y **Twitter Cards** (`twitter:card="summary_large_image"`).
   - En el detalle de producto (`products/detail.html`), generar la metadescripción dinámica con el nombre del producto, SKU, categoría y disponibilidad en Medellín y el Valle de Aburrá, además de un bloque **JSON-LD (`schema.org/Product` y `schema.org/HardwareStore`)**.

### 5.3. Protección Anti-Spam en Todos los Formularios Públicos
1. **Defensa Multicapa (`app/utils/anti_spam.py`):**
   - **Campo Honeypot Invisible:** Agregar un input oculto por CSS (`name="website_url"`, `tabindex="-1"`, `autocomplete="off"`) en los formularios de Contacto, Registro, Login y Recuperación de contraseña. Si un bot lo llena, rechazar silenciosamente la petición.
   - **Validación de Tiempo Mínimo de Envío (`form_loaded_at`):** Firmar el timestamp de carga del formulario; si se envía en menos de `2 segundos` (comportamiento de bot automatizado), bloquear el envío.
   - **Rate Limiting por IP:** Limitar intentos por dirección IP (ej. máximo 5 envíos de contacto por hora, 5 intentos de login por minuto, 3 solicitudes de recuperación por cada 15 minutos), devolviendo `HTTP 429 Too Many Requests` con mensaje amigable.
   - **Sanitización de Contenido:** Bloquear inyecciones de múltiples hipervínculos (`http://`, `https://`, `[url]`) o patrones de spam masivo en el cuerpo de los mensajes de contacto.

### 5.4. Forzar HTTPS y Cabeceras de Seguridad
1. **Middleware HTTPS y Seguridad (`app/__init__.py`):**
   - Configurar `ProxyFix` de `werkzeug.middleware.proxy_fix` para detectar correctamente `X-Forwarded-Proto`.
   - En un hook `@app.before_request`, si `FORCE_HTTPS=True` en variables de entorno o si `not app.debug` y el host no es `127.0.0.1` / `localhost`, redirigir automáticamente cualquier petición `http://` a `https://` con código `301 Moved Permanently`.
   - Añadir en `@app.after_request` las cabeceras de seguridad:
     - `Strict-Transport-Security: max-age=31536000; includeSubDomains`
     - `X-Content-Type-Options: nosniff`
     - `X-Frame-Options: SAMEORIGIN`
     - `Referrer-Policy: strict-origin-when-cross-origin`

### 5.5. Auditoría de Secretos en Frontend y Endurecimiento de `.gitignore`
1. **Escaneo de Seguridad en Frontend:**
   - Auditar todas las plantillas `.html` y archivos `.js` / `.css` para garantizar que **ninguna** clave de API, `SECRET_KEY`, `DATABASE_URL` ni credencial de Supabase se inyecte en el cliente.
2. **Actualización de `.gitignore`:**
   - Asegurar que `.gitignore` bloquee estrictamente:
     ```gitignore
     .env
     .env.*
     !.env.example
     *.pem
     *.key
     *.crt
     *.sqlite
     *.db
     __pycache__/
     venv/
     .venv/
     instance/
     .pytest_cache/
     app/static/uploads/products/*
     !app/static/uploads/products/.gitkeep
     ```

---

## 6. Criterios de Verificación y Pruebas (`pytest`) para v1.3.0
Ejecutar y validar pruebas automatizadas para confirmar que:
1. La ruta `/politica-de-reembolsos` responde `200 OK` y está enlazada en el Footer en `ES` y `EN`.
2. Al confirmar un pedido se genera su **Factura Electrónica (`FE-XXXX`)** con CUFE y vista imprimible en `/orders/<id>/invoice`.
3. Los banners de `"Regístrate hoy"` no aparecen cuando un cliente ha iniciado sesión.
4. El Dashboard (`/admin`) renderiza los gráficos con datos reales y `/admin/api/metrics` responde JSON válido.
5. Enviar dos peticiones simultáneas o repetidas con el mismo `idempotency_key` en el checkout **no** genera doble cobro ni duplica el pedido.
6. Cualquier cambio en productos, categorías o pedidos invalida automáticamente el caché.
7. Los formularios rechazan envíos con el campo *honeypot* lleno o que superen el límite de peticiones (Anti-Spam).
8. Al subir una imagen de producto, `Pillow` la comprime y optimiza correctamente.
9. La redirección HTTPS y las cabeceras de seguridad funcionan cuando `FORCE_HTTPS` está activo.