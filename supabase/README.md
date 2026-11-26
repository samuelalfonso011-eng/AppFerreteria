# FerrePro en Supabase

1. En SQL Editor, ejecuta `schema.sql`, `migrations/20261125233808_phase1_billing.sql`, `rls_policies.sql` y `seed.sql` en ese orden en el proyecto destinado a FerrePro. El seed agrega los productos que falten y conserva el inventario existente.
2. Asigna una contraseña aleatoria al rol PostgreSQL `ferrepro_backend` desde una sesión administrativa segura (en psql, `\password ferrepro_backend`). Es la identidad del proceso Flask.
3. Desde Connect copia la URI del **Session pooler**. Conserva el host, puerto y sufijo del usuario que proporciona Supabase. Sustituye el prefijo postgres por ferrepro_backend y usa la contraseña de ese rol codificada para URL. Conserva `sslmode=require` o configura `verify-full` con el certificado del proyecto.
4. En `backend/.env` configura `DATABASE_URL` con esa URI. Si el archivo aún no existe, copia primero `.env.example`. Genera `SECRET_KEY` con `python -c "import secrets; print(secrets.token_hex(32))"`. En producción configura `FLASK_ENV=production`, `TRUSTED_HOSTS` y HTTPS.
5. Desde `backend`, instala `python -m pip install -r requirements.txt`. Ejecuta `python -m flask --app run create-admin` para crear el administrador de prueba y elegir su contraseña de forma oculta. Flask guarda un hash en `users`. Inicia el servidor con `python run.py` y abre `http://127.0.0.1:5000/admin`.
6. Para comprobar la instalación, crea un producto de prueba, cambia su precio y consulta el catálogo en otra sesión. Haz una compra con datos ficticios, confírmala en Admin y revisa el stock, el historial y las dos filas en `legal_consents`. El checkout reserva stock al crear el pedido.

## Contrato y permisos

Flask sigue gestionando la autenticación mediante la tabla users y cookies firmadas. Los permisos del cliente web se comprueban en los controladores y los permisos SQL de Flask se asignan al rol privado ferrepro_backend. Las claves REST de Supabase no son necesarias. Las escrituras del catálogo y del inventario pasan por la API de Flask para actualizar el kárdex y el token compartido de caché en la misma transacción.

Los roles anon y authenticated solo pueden leer categorías activas y sus productos activos. El checkout público usa POST /api/orders. El servidor comprueba CSRF, aceptación de ambos documentos, precios, cantidades y disponibilidad antes de persistir el pedido completo. Los clientes públicos carecen de permisos directos para insertar líneas o consentimientos.

La vista legal_consents respeta RLS y expone privacy_consents.document como consent_type. Orders conserva total y la dirección desglosada del ORM, con total_amount y shipping_address derivados para consultas. La IP del consentimiento procede de la conexión recibida por Flask. Configura TRUSTED_PROXY_HOPS únicamente según los proxies de confianza de tu despliegue.

Los scripts están destinados a una base nueva de FerrePro o a una instalación previa de estos mismos scripts. Los datos de una base anterior requieren una transferencia independiente.


## Actualización de autenticación en una base existente

Aplica `migrations/20261125000000_auth_integrity.sql` en SQL Editor o mediante una conexión administrativa antes de desplegar el backend. La actualización revoca las sesiones del formato anterior. Las cuentas deben volver a iniciar sesión.

Si la migración detecta dos cuentas para el mismo correo normalizado, revierte la transacción. Identifica los registros y preserva los pedidos y consentimientos vinculados antes de resolver los duplicados.

```sql
select lower(trim(email)) as normalized_email, array_agg(id order by id) as user_ids
from public.users
group by lower(trim(email))
having count(*) > 1;
```

Flask usa SMTP directamente. Los proveedores, plantillas y SMTP del panel de Supabase Auth no intervienen en este flujo. Consulta la configuración SMTP en `backend/README.md`.

## Actualización de facturación en una base existente

Aplica `migrations/20261125233808_phase1_billing.sql` después de la migración de autenticación y antes de desplegar el backend. La migración incluye sus propias políticas y es repetible. Los pedidos anteriores quedan con canal `web` y referencias de usuario nulas. Para Docker con un volumen existente, aplica la migración con el propietario de la base. Los scripts de arranque se ejecutan al inicializar un volumen vacío.

Los comprobantes se guardan como bytes privados en `payments` y se descargan mediante Flask. La sesión y el rol se comprueban en Flask porque la aplicación no usa Supabase Auth. Consulta [los contratos de la Fase 1](../backend/PHASE1_API.md).
