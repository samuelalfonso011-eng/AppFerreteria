# FerrePro en Vercel

El proyecto `appferreteria` publica la tienda en `https://ferrepro-co.vercel.app/` y el panel en `/admin`. El dominio anterior, `https://appferreteria.vercel.app/`, sigue activo y autorizado en `TRUSTED_HOSTS`; los enlaces de los correos usan el nuevo (`PUBLIC_BASE_URL`).

- **Frontend estático:** `scripts/build-vercel.mjs` copia a `dist/` los ocho archivos públicos.
- **API:** `vercel.json` reescribe `/api/:path*` hacia la función Python `api/index.py`, que carga la app Flask de `backend/` con las dependencias de `requirements.txt` (raíz). Flask recibe la ruta original y valida sesión, CSRF, origen y roles como en local.
- **Base de datos:** Supabase mediante el **Session pooler** (IPv4). La conexión directa `db.<ref>.supabase.co` solo tiene IPv6 y falla desde muchas redes.

## Variables de entorno

Se cargan una vez en el entorno Production. Desde la raíz, con `vercel login` hecho y el proyecto vinculado:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\vercel-env.ps1
```

El script lee `backend/.env` sin mostrar valores, genera una `SECRET_KEY` nueva y define `FLASK_ENV=production`, `TRUSTED_HOSTS`, `TRUSTED_PROXY_HOPS=1` y `PUBLIC_BASE_URL`. La conexión, la clave secreta, la contraseña SMTP y la clave de Gemini quedan como secretos. Después hay que volver a desplegar.

## Límites del entorno serverless

- **Modelos IA:** TensorFlow supera el límite de 250 MB de una función, así que `requirements.txt` no lo incluye. `GET /api/admin/ml/status` responde con `available: false` y muestra las corridas registradas; entrenar y predecir responden `503 ml_unavailable`. Para la pestaña Modelos IA completa usa el backend con Docker (`Dockerfile`), que sí instala TensorFlow y tiene disco persistente para `backend/ml_artifacts/`.
- **Disco de solo lectura:** el reporte de benchmarks queda solo en memoria de la instancia (`report_file: null`).
- **Límites por instancia:** el límite de intentos y la caché viven en la memoria de cada instancia; la caché se invalida con el token compartido de la base.
- **Duración:** `maxDuration` es 60 s (plan Hobby). El benchmark con los tamaños por defecto tarda unos 11 s.

## Comprobación

`GET /api/store` y `GET /api/catalog/products` deben responder 200 y `GET /api/admin/ml/status` 401 sin sesión. Un host que no esté en `TRUSTED_HOSTS` recibe 400.
