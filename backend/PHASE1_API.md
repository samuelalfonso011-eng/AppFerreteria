# FerrePro | Contratos de la Fase 1

Las rutas usan la sesión de Flask. En escrituras, envía la cookie de sesión cuando corresponda y el encabezado `X-CSRF-Token`. El token se obtiene en `GET /api/auth/csrf` y se renueva al iniciar sesión en `POST /api/auth/login`. Usa JSON salvo al adjuntar un comprobante. Los importes representan COP. Facturas y pagos devuelven los importes como cadenas con dos decimales.

## Usuarios | Solo admin

- `GET /api/admin/users?page=1` devuelve `200` con `{"users":[...],"page":1,"pages":1,"total":1}`. Cada página contiene hasta 25 cuentas.
- `POST /api/admin/users` devuelve `201` con `{"user":{...}}`. Requiere `name`, `email`, `password` y `role`. El estado `is_active` es opcional y su valor inicial es `true`.
- `PATCH /api/admin/users/{user_id}` acepta uno o ambos campos de `{"role":"employee","is_active":false}`. Devuelve `200` con `{"user":{...}}`. Al cambiar el rol o establecer el estado se revocan las sesiones. El administrador autenticado conserva su rol y estado activo.

Los roles son `admin`, `employee` y `customer`. La contraseña inicial se valida con las reglas del registro existente. El alta administrativa deja la cuenta lista para iniciar sesión si está activa. El correo duplicado devuelve `409 email_taken`.

```json
{
  "user": {
    "id": 8,
    "name": "Turno de caja",
    "email": "caja@example.com",
    "role": "employee",
    "is_active": true,
    "email_verification_pending": false,
    "created_at": "2026-11-25T15:00:00Z",
    "last_login_at": null
  }
}
```

## Pedidos | POST /api/orders

Conserva el checkout existente. `channel` admite `web` (valor inicial), `app`, `presencial` y `domicilio`. Los canales presencial y domicilio requieren admin o empleado. El backend toma el ID del cliente de su sesión cuando compra con su cuenta. Admin y empleado pueden enviar `customer_id` de un cliente activo. El servidor registra el ID del operador desde su sesión.

```json
{
  "channel": "presencial",
  "customer_id": 12,
  "name": "Laura Gómez",
  "email": "laura@example.com",
  "phone": "3001234567",
  "doc_type": "CC",
  "doc_number": "1020304050",
  "accept_terms": true,
  "accept_privacy": true,
  "idempotency_key": "7f7802d3-a66f-4778-a82e-c0ed151ff90a",
  "items": [
    {"product_id": 7, "quantity": 2},
    {"product_id": 9, "quantity": 1}
  ]
}
```

Para web, app y domicilio incluye `department`, `city`, `neighborhood` y `street_address`. En presencial esos campos son opcionales y el envío cuesta cero. `complement`, `notes` y `expected_total` son opcionales. `expected_total` compara el total del checkout antes de cualquier ajuste de facturación.

Devuelve `201` con `{"order":{...},"created":true}`. Un reintento con la misma clave y contexto de compra devuelve `200` con `created:false`. El pedido público conserva `order_number`, `status`, `status_label`, `items`, `subtotal`, `shipping_cost`, `total`, `city` y `created_at`, y añade `channel`. El operador recibe el detalle administrativo con `id`, `channel`, `customer_id` y `employee_id`. Usa `order.id` para facturar.

## Listado de pedidos | GET /api/admin/orders

Solo admin. El filtro opcional `channel` admite `presencial`, `web`, `app` y `domicilio`. Se combina con `status`, `q` y `page`. Si se omite, el listado incluye todos los canales. Un valor vacío o inválido devuelve `400` con `fields.channel`.

Ejemplo de respuesta `200` para `GET /api/admin/orders?channel=web`.

```json
{
  "orders": [
    {
      "id": 42,
      "order_number": "FP-261125-A1B2C3",
      "status": "CONFIRMED",
      "status_label": "Confirmado",
      "channel": "web",
      "customer_id": 12,
      "employee_id": null,
      "customer_name": "Laura Gómez",
      "city": "Medellín",
      "total": 100000,
      "item_count": 1,
      "created_at": "2026-11-25T15:00:00Z"
    }
  ],
  "page": 1,
  "pages": 1,
  "total": 1
}
```

## Facturas | POST /api/orders/{id}/invoice

Admin puede facturar cualquier pedido. Empleado puede facturar los pedidos que registró. Envía `{}` o `{"discount_amount":"1000.00"}`. El descuento es opcional y se aplica al subtotal de productos. El impuesto se calcula sobre el subtotal descontado con `INVOICE_TAX_RATE`, una fracción configurable en el servidor que comienza en cero. El envío se suma después. La emisión confirma el pedido si estaba pendiente.

Devuelve `201` al emitir y `200` con la misma factura y `created:false` en reintentos. El consecutivo es único y puede tener saltos por transacciones fallidas. La facturación no modifica el stock. Devuelve `409 order_cancelled` para un pedido cancelado y `400 invalid_discount` si el descuento supera el subtotal.

```json
{
  "created": true,
  "invoice": {
    "id": 24,
    "invoice_number": 24,
    "order_id": 42,
    "employee_id": 8,
    "status": "emitida",
    "subtotal": "100000.00",
    "shipping_cost": "0.00",
    "discount_amount": "1000.00",
    "tax_amount": "18810.00",
    "total_amount": "117810.00",
    "created_at": "2026-11-25T15:02:00Z",
    "items": [
      {"product_id":7,"name":"Taladro","sku":"FP-0007","quantity":1,"unit_price":"100000.00","subtotal":"100000.00"}
    ]
  }
}
```

## Factura y saldo | GET /api/orders/{id}/invoice

Admin puede consultar cualquier pedido. Empleado puede consultar los pedidos que registró. El ID de la URL es el del pedido. Si el pedido no existe o queda fuera del alcance del empleado, la API devuelve `404`.

Si el pedido existe y todavía no tiene factura, devuelve `200`.

```json
{"invoice": null, "payments": [], "balance": 0}
```

Si hay factura, devuelve `200` con el mismo objeto `invoice` de la emisión y el historial completo de pagos, ordenado por ID ascendente. `balance` es un número JSON en COP. El servidor resta del total únicamente los pagos con estado `aprobado` y devuelve cero si el resultado es negativo. Cada pago incluye su `receipt_url` privada o `null`.

```json
{
  "invoice": {
    "id": 24,
    "invoice_number": 24,
    "order_id": 42,
    "employee_id": 8,
    "status": "emitida",
    "subtotal": "100000.00",
    "shipping_cost": "0.00",
    "discount_amount": "1000.00",
    "tax_amount": "18810.00",
    "total_amount": "117810.00",
    "created_at": "2026-11-25T15:02:00Z",
    "items": [
      {"product_id":7,"name":"Taladro","sku":"FP-0007","quantity":1,"unit_price":"100000.00","subtotal":"100000.00"}
    ]
  },
  "payments": [
    {
      "id": 13,
      "invoice_id": 24,
      "order_id": 42,
      "payment_method": "efectivo",
      "amount": "25000.00",
      "status": "aprobado",
      "receipt_url": null,
      "paid_at": "2026-11-25T15:05:00Z",
      "created_at": "2026-11-25T15:05:00Z"
    }
  ],
  "balance": 92810
}
```

## Pagos | POST /api/invoices/{id}/payments

Admin y empleado tienen el mismo alcance que para facturar. Sin comprobante, envía `{"payment_method":"efectivo","amount":"25000.00"}`. Con comprobante usa `FormData` con los campos `payment_method`, `amount` y `receipt` (un archivo PDF, PNG o JPEG de hasta 5 MiB). El navegador genera el encabezado multipart. El ID de la ruta es `invoice.id`.

Métodos admitidos: `efectivo`, `tarjeta`, `transferencia`, `pse`, `nequi`. Efectivo y tarjeta se registran como aprobados por el operador, sin conexión a una pasarela. Los otros métodos quedan pendientes. Los pagos pendientes y aprobados consumen saldo disponible. La API devuelve `409 payment_exceeds_balance` si se excede ese saldo. Cada POST exitoso crea un pago.

```json
{
  "payment": {
    "id": 13,
    "invoice_id": 24,
    "order_id": 42,
    "payment_method": "transferencia",
    "amount": "25000.00",
    "status": "pendiente",
    "receipt_url": "/api/payments/13/receipt",
    "paid_at": null,
    "created_at": "2026-11-25T15:05:00Z"
  }
}
```

El éxito devuelve `201`. Sin adjunto, `receipt_url` es `null`. El archivo se descarga con `GET /api/payments/{id}/receipt` usando la sesión de Flask y el mismo alcance del pedido. Devuelve el archivo como adjunto y usa caché privada deshabilitada.

## Errores comunes

```json
{"error":"validation","message":"Revisa los campos marcados.","fields":{"receipt":"Adjunta un archivo PDF, PNG o JPEG válido."}}
```

`401` indica sesión ausente, `403` indica permiso, origen o CSRF inválido, `404` indica recurso ausente o fuera del alcance del empleado, `413` indica tamaño excedido y `415` indica un formato de petición no admitido.

Ejecuta la prueba desde la raíz con `python -m pytest backend/tests/test_phase1.py -q`.
