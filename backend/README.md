# FerrePro: backend (Fase 2)

API Flask + SQLAlchemy que sirve la tienda (`index.html`) y el Modo Admin (`/admin`) desde un solo origen.
Arquitectura migrada del proyecto anterior: fábrica `create_app`, modelos por dominio, servicios
transaccionales, kárdex de inventario, máquina de estados de pedidos y consentimientos versionados.

## Puesta en marcha (Windows, PowerShell)

Requiere Python 3.10 o superior.

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements-dev.txt
# Completa la instalación de supabase/README.md antes de arrancar.
flask --app run create-admin         # pide correo, nombre y contraseña (mínimo 12, letras y números)
python run.py                        # http://127.0.0.1:5000 y http://127.0.0.1:5000/admin
pytest -q                            # pruebas de API, caché, seguridad y flujo legal
```

La base de ejecución es PostgreSQL. Configura Supabase antes de iniciar Flask siguiendo [la guía de instalación](../supabase/README.md). SQLite en memoria queda reservado a las pruebas.

## Estructura

```
app/
  __init__.py      fábrica, cabeceras de seguridad (CSP, HSTS), errores JSON, archivos del frontend
  config.py        configuración por entorno leída de .env
  models/          user, catalog (Category, Product), inventory, order, consent, setting, cache_version
  services/        order_service, inventory_service, metrics_service
  api/             public (catálogo, tienda, legal), auth, orders (checkout y consulta)
  api/admin/       dashboard, catalog (productos y categorías), orders, inventory, settings
  legal/content.py textos legales versionados (POLICY_VERSION)
  utils/           cache, security, validation, http, timeutils
tests/             pytest
```

## Endpoints

| Método y ruta | Uso |
|---|---|
| GET `/api/catalog/products`, `/api/catalog/categories`, `/api/catalog/products/<slug>` | Catálogo, con caché y ETag |
| GET `/api/store`, `/api/legal`, `/api/legal/<slug>` | Datos de la tienda y textos legales, con caché y ETag |
| GET `/api/auth/csrf`, `/api/auth/me` · POST `/api/auth/login`, `/api/auth/logout` | Sesión |
| POST `/api/orders` | Checkout (exige `accept_terms` y `accept_privacy`) |
| POST `/api/orders/lookup` | Estado de un pedido con número y correo |
| `/api/admin/*` | Backoffice: solo cuentas con rol `admin` (401 sin sesión, 403 sin rol) |

## Seguridad

- Contraseñas con hash de Werkzeug; la sesión guarda una huella del hash, así que cambiar la contraseña cierra todas las sesiones.
- Cookie de sesión `HttpOnly`, `SameSite=Lax` y `Secure` en producción. Vida de 8 horas, con un máximo absoluto de 12.
- Toda escritura exige JSON, el mismo origen y el token CSRF en la cabecera `X-CSRF-Token`.
- Límite de intentos en el login (5 por correo e IP cada 15 minutos), el checkout y la consulta de pedidos.
- Validación y saneamiento de cada campo en el servidor; el frontend escapa todo el HTML que pinta.
- Los precios y el stock siempre los calcula el servidor. El stock se descuenta con un UPDATE condicional atómico, que nunca deja valores negativos, y los pedidos son idempotentes.
- Solo se sirven los 8 archivos del frontend; `backend/` y `.env` no son accesibles por HTTP.

## Caché e invalidación

1. Caché en memoria por proceso (TTL `CACHE_TTL`) para catálogo, categorías, detalle, tienda, textos legales y tablero.
2. Las claves llevan un token por ámbito guardado en la tabla `cache_versions`. Cualquier commit que toque
   productos, categorías, inventario o pedidos (incluida una compra) cambia el token **en la misma transacción**:
   ningún worker puede servir datos anteriores, aunque haya varios procesos.
3. Las respuestas públicas llevan `ETag` y `Cache-Control: no-cache`: el navegador revalida siempre y recibe
   un 304 sin cuerpo si nada cambió.

## Antes de operar con datos reales

- Completa razón social, NIT, domicilio y correo en Admin > Ajustes; los textos legales los usan.
- Haz revisar los textos de `app/legal/content.py` por un abogado. Si cambias su fondo, sube `POLICY_VERSION`.
- La factura electrónica DIAN se emite con tu proveedor autorizado usando los datos fiscales del pedido; esta API no la genera.
- En producción: `FLASK_ENV=production`, `SECRET_KEY` de 32 caracteres o más, `TRUSTED_HOSTS`, HTTPS y un servidor WSGI (por ejemplo waitress en Windows).

## Docker (local)

`compose.yaml` en la raíz levanta dos servicios:

- `db`: PostgreSQL 17 con los mismos `supabase/schema.sql`, `rls_policies.sql` y `seed.sql`. Los scripts se copian a la imagen (`docker/db.Dockerfile`) y corren solo la primera vez, con el volumen vacío.
- `backend`: Flask con gunicorn (2 procesos) en modo producción, usuario sin privilegios y sistema de archivos de solo lectura. Se conecta como `ferrepro_backend`, igual que en Supabase.

```powershell
Copy-Item .env.docker.example .env     # en la raíz; completa SECRET_KEY, POSTGRES_PASSWORD y BACKEND_DB_PASSWORD
docker compose up -d --build
docker compose exec backend flask create-admin
```

Tienda en http://localhost:8000 y admin en http://localhost:8000/admin.

| Tarea | Comando |
|---|---|
| Ver registros | `docker compose logs -f backend` |
| Pruebas dentro del contenedor | `docker compose --profile test run --rm --build tests` |
| Consola SQL | `docker compose exec db psql -U ferrepro_owner -d ferrepro` |
| Detener (conserva los datos) | `docker compose down` |
| Borrar la base local y empezar de cero | `docker compose down -v` |

Notas:

- Para usar Supabase desde el contenedor, define `DATABASE_URL` en el `.env` de la raíz. El servicio `db` sigue arrancando, pero no se usa.
- La cookie de sesión es `Secure` porque el contenedor corre en modo producción. Chrome, Edge y Firefox la aceptan en `http://localhost`; para otro dominio hace falta HTTPS.
- Para bases existentes, aplica las migraciones de `supabase/migrations/` con el rol administrador de PostgreSQL antes de reiniciar el backend.

## Autenticación

| Método y ruta | Uso |
|---|---|
| POST `/api/auth/register` | Crea una cuenta `customer` pendiente y envía el enlace de activación (48 horas). Exige `accept_terms` y `accept_privacy` y guarda ambos en `privacy_consents` (vista `legal_consents`) con propósito `registration`, versión e IP |
| POST `/api/auth/activation/resend` | Reenvía el enlace de una cuenta pendiente |
| POST `/api/auth/activate` | Activa la cuenta con el token del correo e inicia sesión |
| POST `/api/auth/password/forgot` | Envía un enlace para elegir contraseña nueva (30 minutos, un solo uso) |
| POST `/api/auth/password/reset` | Cambia la contraseña con el token, cierra las demás sesiones e inicia sesión |

- **Registro:** el servidor normaliza con `strip().lower()`. El índice único usa el correo normalizado. Un duplicado devuelve `409 email_taken`. El login devuelve el mismo error para contraseña incorrecta, cuenta desconocida o cuenta pendiente.
- **Enlaces firmados** con `SECRET_KEY` (itsdangerous), con una sal por propósito y un sello del hash de la contraseña y del estado de la cuenta: cada enlace vence y sirve una sola vez. Viajan en el fragmento de la URL (`/#activar/...`, `/#restablecer/...`), que el navegador no envía al servidor.
- **Contraseñas:** scrypt con sal (Werkzeug), de 12 a 128 caracteres, con letras y números, sin el correo dentro y sin claves comunes. La misma regla aplica a `create-admin`.
- **Límites:** registro (5 cada 10 minutos por IP), recuperación (5 por IP y 3 por correo cada 15 minutos) y uso de enlaces (10 cada 10 minutos por IP), además de los del login.
- El registro deja `email_verification_pending = true`. La activación o la recuperación con un enlace válido confirma el control del correo y habilita la cuenta. Una cuenta activa que se deshabilita queda fuera de esos flujos. El cierre de sesión revoca el identificador en `auth_sessions`.
### SMTP

Flask gestiona el envío. En producción, configura `PUBLIC_BASE_URL=https://tu-dominio.com` y `TRUSTED_HOSTS=tu-dominio.com`. Usa el `.env` raíz con Docker o `backend/.env` con Flask:

```dotenv
SMTP_HOST=smtp.tu-proveedor.com
SMTP_PORT=587
SMTP_USER=usuario-smtp
SMTP_PASSWORD=credencial-smtp
SMTP_FROM=no-reply@tu-dominio.com
SMTP_STARTTLS=true
SMTP_SSL=false
```

Para TLS implícito usa el puerto 465, `SMTP_SSL=true` y `SMTP_STARTTLS=false`. Para Mailpit en Docker inicia el perfil `mail` y usa `SMTP_HOST=mailpit`, `SMTP_PORT=1025`, `SMTP_STARTTLS=false`, `SMTP_SSL=false`, `SMTP_FROM=no-reply@ferrepro.local` y `PUBLIC_BASE_URL=http://localhost:8000` para desarrollo local. El buzón de Mailpit escucha en el puerto 8025. Para una URL pública usa HTTPS.

El registro y reenvío esperan la aceptación del servidor SMTP. Si falla el envío durante el registro, la API responde `503 mail_unavailable` y conserva la cuenta pendiente y sus consentimientos para reintentar desde el formulario. Los enlaces no se imprimen en registros de Flask.

### Pruebas

Desde la raíz, instala `backend/requirements-dev.txt` y ejecuta `python -m pytest backend/tests -q`. El flujo SMTP abre una conexión TCP local y recupera el enlace del mensaje recibido. Para ejecutar esa misma prueba con PostgreSQL, crea una base **desechable** con `schema.sql`, `rls_policies.sql` y `seed.sql`, asigna credenciales al rol `ferrepro_backend`, define `FERREPRO_TEST_POSTGRES_URL` con esa conexión y ejecuta `python -m pytest backend/tests/test_auth_smtp.py -q`. La prueba crea cuentas en esa base.

## Asistente de catálogo

`POST /api/chat` acepta `{"message":"…","history":[{"role":"user","content":"…"}]}`.
El historial es opcional y se conservan las últimas seis entradas. La respuesta contiene
`reply`, `mode` y `suggested_products`. Como en las otras escrituras, envía la cookie
y el token de `GET /api/auth/csrf` en `X-CSRF-Token`. El límite local es de diez solicitudes
por minuto por IP y por proceso.

Configura `GEMINI_API_KEY` y, si corresponde, `GEMINI_MODEL` en el entorno del proceso Flask.
En Docker esas dos variables deben llegar al contenedor backend. Para mantener el costo
en cero usa un proyecto de Google AI Studio sin facturación habilitada y un modelo con
cuota gratuita disponible. El modo IA envía a Google la pregunta y el historial reciente,
junto con un subconjunto del catálogo público y las políticas. Evita incluir datos personales
en los mensajes de prueba.

Con el servidor en ejecución, desde la raíz:

```powershell
python backend/tests/smoke_chat.py http://127.0.0.1:5000 --expect fallback
python backend/tests/smoke_chat.py http://127.0.0.1:5000 --expect ai
```

Ejecuta el primer comando con `GEMINI_API_KEY` vacía y el segundo tras reiniciar con una
llave válida y cuota disponible. `python -m pytest backend/tests/test_chat.py -q` comprueba
ambos modos, incluyendo una respuesta de Gemini simulada, HTTP 429 y fallos de conexión.
