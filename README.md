# 🛠️ Sistema Web Integral para Ferretería

Sistema web full-stack de comercio electrónico y administración operativa para ferreterías, desarrollado con **Python (Flask)**, **PostgreSQL (Supabase)**, **Jinja2**, **HTML5/CSS3/JavaScript moderno** y arquitectura modular por capas.

---

## 📌 Modos de la Aplicación

1. **Modo Usuario (Tienda Virtual Pública):**
   - Catálogo interactivo con filtros por categoría, búsqueda por nombre/SKU, rango de precios y disponibilidad.
   - Fichas de detalle con características técnicas, SKU y stock en tiempo real.
   - Carrito persistente en PostgreSQL para usuarios registrados y temporal en sesión para visitantes.
   - Recálculo estricto de subtotales, totales y tarifas de entrega en el servidor.
   - Checkout con snapshots inmutables de dirección de entrega e items comprados.
   - Módulo de pagos en **Modo de Prueba** (simulación de pagos aprobados, rechazados y pendientes sin cobros reales ni captura de tarjetas bancarias).
   - Perfil de cliente con libreta de direcciones y seguimiento de pedidos con cancelación y reposición de inventario.

2. **Modo Administrador (Panel Privado Protegido):**
   - **Dashboard Operativo:** Indicadores comerciales reales (ventas confirmadas del día, semana, mes, pedidos por estado, stock bajo, clientes registrados y ranking de productos más vendidos).
   - **CRUD de Productos:** Alta, edición, activación/desactivación y eliminación segura con comprobación de integridad referencial.
   - **Gestión de Categorías:** Normalización automática de nombres y slugs.
   - **Kárdex de Inventario:** Auditoría inmutable de movimientos (`PURCHASE_ENTRY`, `SALE_EXIT`, `ADJUSTMENT_IN`, `ADJUSTMENT_OUT`, `ORDER_CANCEL_RESTORE`), alertas de stock mínimo y formulario de ajuste manual con concurrencia segura (`with_for_update`).
   - **Gestión de Pedidos:** Búsqueda, detalle, trazabilidad y transiciones controladas de la máquina de estados.
   - **Gestión de Clientes:** Métricas de compra y control de cuentas activas/desactivadas.
   - **Auditoría de Pagos:** Registro de transacciones simuladas.
   - **Configuración de Tienda:** Edición de tarifas de envío, umbral de envío gratis, horarios y contacto.

---

## 🚀 Requisitos e Instalación en Windows

### 1. Prerrequisitos
- Python 3.10+ instalado y agregado al `PATH`.
- Git instalado.
- Cuenta o proyecto en **Supabase** (o base de datos local SQLite para desarrollo inicial).

### 2. Configurar Entorno Virtual en PowerShell
Abre tu terminal en la carpeta del proyecto:

```powershell
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual en Windows
.\venv\Scripts\activate

# Instalar dependencias (versiones fijadas). Producción: requirements.txt
pip install -r requirements-dev.txt
```

### 3. Configurar Variables de Entorno (`.env`)
Copia la plantilla `.env.example` como `.env`:

```powershell
Copy-Item .env.example .env
```

Edita el archivo `.env` con tus credenciales. Genera la clave con
`python -c "import secrets; print(secrets.token_hex(32))"`. El archivo `.env` está en `.gitignore`: **nunca lo subas al repositorio**.
```ini
FLASK_ENV=development
SECRET_KEY=<pega_aqui_la_clave_generada>
DATABASE_URL=postgresql://postgres:tu_password@db.tu_proyecto.supabase.co:5432/postgres
FLASK_RUN_PORT=5000
FLASK_RUN_HOST=127.0.0.1
```

> **Nota sobre Supabase:**  
> Si tu proyecto de Supabase utiliza el Connection Pooler (PgBouncer o Supavisor), utiliza el puerto `6543`:
> `DATABASE_URL=postgresql://postgres.tu_id:tu_pass@aws-0-sa-east-1.pooler.supabase.com:6543/postgres?sslmode=require`

### 4. Inicializar Base de Datos y Datos Demo

```powershell
# Inicializar roles y configuración comercial
flask init-roles

# Sembrar catálogo inicial de ferretería con productos y stock auditado
flask seed-demo-data

# Crear de forma segura tu usuario Administrador
flask create-admin
```
*(El comando `flask create-admin` solicitará de manera interactiva el correo, nombre y contraseña con encriptación segura).*

### 5. Ejecutar Pruebas Automatizadas (Pytest)

```powershell
.\venv\Scripts\pytest -v
```

### 6. Iniciar Servidor Local

```powershell
python run.py
```
Abre tu navegador en: **`http://localhost:5000`**

---

## 🔒 Seguridad Implementada
- **Hash Seguro de Contraseñas:** Algoritmos `scrypt` / `pbkdf2:sha256` mediante Werkzeug.
- **Protección CSRF:** Tokens validados en todos los formularios mediante Flask-WTF.
- **Autorización Estricta:** Decorador `@admin_required` que valida el rol en el servidor.
- **Idempotencia de Checkout:** Tokens únicos por transacción que evitan cobros o pedidos duplicados por doble clic.
- **Concurrencia Segura:** Descuento de stock protegido con `with_for_update()` en transacciones PostgreSQL.
- **Saneamiento de Archivos:** Validación de extensiones (`.jpg`, `.png`, `.webp`) y firmas binarias (*magic bytes*) con Pillow.

---

## ☁️ Preparación para Despliegue Futuro en Vercel & Supabase
- **Almacenamiento de Fotos:** El servicio `ImageService` está desacoplado para alternar del disco local (`app/static/uploads/products/`) a **Supabase Storage** mediante buckets S3 compatibles.
- **Base de Datos Cloud:** PostgreSQL en Supabase gestiona la persistencia fuera del sistema de archivos efímero de Vercel.
- **Punto de Entrada WSGI:** La aplicación utiliza el patrón estándar `create_app()` adaptable a funciones serverless en Vercel.
