# FerrePro en Vercel

Importa este repositorio desde su raíz. La configuración publica la tienda en `/` y el panel en `/admin`. El build copia a `dist/` los ocho archivos públicos del frontend. Los permisos de administrador y trabajador se siguen validando en Flask.

Mientras Flask solo corra en el PC, las consultas `/api/*` del despliegue devuelven HTTP 503. Para habilitar el catálogo, el inicio de sesión y los pedidos, despliega el backend con el Dockerfile existente, su PostgreSQL y almacenamiento persistente para los modelos y reportes. Configura estas variables:

| Servicio | Variable | Valor |
| --- | --- | --- |
| Vercel | `FLASK_API_ORIGIN` | Origen HTTPS público del backend, sin ruta. |
| Flask | `PUBLIC_BASE_URL` | Origen HTTPS exacto de la tienda en Vercel. También se utiliza para los enlaces de correo. |
| Flask | `TRUSTED_HOSTS` | Nombre de host del backend, además de los demás hosts autorizados para Flask. |

Vuelve a desplegar el frontend después de cambiar el origen de la API. Comprueba que `GET /api/auth/csrf` devuelve JSON y que un empleado puede iniciar sesión y consultar pedidos. Las credenciales de PostgreSQL, correo y Gemini pertenecen al entorno de Flask.
