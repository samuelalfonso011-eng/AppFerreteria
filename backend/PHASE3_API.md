# FerrePro | Integridad financiera

Solo el rol de aplicación `admin` accede a estas rutas mediante su sesión Flask. Las escrituras reciben un objeto JSON y el encabezado habitual `X-CSRF-Token`. Sesión ausente devuelve HTTP 401. Sesión de empleado o cliente devuelve 403. Los ejemplos proceden de una base de pruebas.

## GET /api/admin/integrity/status

Devuelve HTTP 200 con el número de eslabones, el resultado de la última auditoría y hasta cinco eventos en orden descendente. `status` resume la última comprobación. Es `unverified` antes de la primera auditoría o si creció la cadena después de una auditoría válida. Un resultado comprometido permanece visible hasta la siguiente verificación. Al inicio, `last_verification` es null y `recent_events` puede estar vacío. Para comprobar cambios directos recientes hay que ejecutar la verificación.

```json
{
  "last_verification": {
    "checked_at": "2026-11-26T00:28:55.307596Z",
    "checked_by": "admin:1",
    "details": {
      "head_hash": "76e3f93630906da9b4c7dcd4c5757474b18e91f52838b77ec2aadcbc896d3e06"
    },
    "failure_reason": null,
    "first_broken_entity_id": null,
    "first_broken_entity_type": null,
    "first_broken_seq_no": null,
    "id": 1,
    "status": "valid",
    "total_records_checked": 1
  },
  "recent_events": [
    {
      "created_at": "2026-11-26T00:28:55.281958Z",
      "current_hash": "76e3f93630906da9b4c7dcd4c5757474b18e91f52838b77ec2aadcbc896d3e06",
      "entity_id": 1,
      "entity_type": "invoice",
      "event_type": "issued",
      "hash_short": "76e3f9363090",
      "prev_hash": "GENESIS",
      "seq_no": 1
    }
  ],
  "status": "valid",
  "total_records": 1
}
```

## POST /api/admin/integrity/verify

Envía `{}`. Tanto el resultado válido como el comprometido devuelven HTTP 200 y se guardan como filas independientes. Usa `status` para decidir qué mostrar. `total_records_checked` incluye el eslabón donde se detuvo el recorrido. `checked_by` identifica la cuenta con `admin:<id>` o el ejecutor `system`.

### Cadena válida

```json
{
  "checked_at": "2026-11-26T00:28:55.307596Z",
  "checked_by": "admin:1",
  "details": {
    "head_hash": "76e3f93630906da9b4c7dcd4c5757474b18e91f52838b77ec2aadcbc896d3e06"
  },
  "failure_reason": null,
  "first_broken_entity_id": null,
  "first_broken_entity_type": null,
  "first_broken_seq_no": null,
  "id": 1,
  "status": "valid",
  "total_records_checked": 1
}
```

### Primera divergencia

En este ejemplo cambió el impuesto de la factura y, por consiguiente, su total. Para `payload_mismatch`, `details.expected` y `details.actual` son cadenas JSON canónicas. El frontend puede usar `JSON.parse` para comparar campos. Para hashes y secuencias, estos valores son cadenas o números simples.

```json
{
  "checked_at": "2026-11-26T00:28:55.348739Z",
  "checked_by": "admin:1",
  "details": {
    "actual": "{\"created_at\":\"2026-11-26T00:28:55.273959Z\",\"discount_amount\":\"0.00\",\"employee_id\":1,\"invoice_number\":1,\"items_sha256\":\"255d096cdfcf0c108edcad618edbaa4ab431c09965b57b956e0810ea656c2e6c\",\"order_id\":1,\"shipping_cost\":\"0.00\",\"status\":\"emitida\",\"subtotal\":\"489900.00\",\"tax_amount\":\"1.00\",\"total_amount\":\"489901.00\"}",
    "expected": "{\"created_at\":\"2026-11-26T00:28:55.273959Z\",\"discount_amount\":\"0.00\",\"employee_id\":1,\"invoice_number\":1,\"items_sha256\":\"255d096cdfcf0c108edcad618edbaa4ab431c09965b57b956e0810ea656c2e6c\",\"order_id\":1,\"shipping_cost\":\"0.00\",\"status\":\"emitida\",\"subtotal\":\"489900.00\",\"tax_amount\":\"0.00\",\"total_amount\":\"489900.00\"}"
  },
  "failure_reason": "payload_mismatch",
  "first_broken_entity_id": 1,
  "first_broken_entity_type": "invoice",
  "first_broken_seq_no": 1,
  "id": 2,
  "status": "compromised",
  "total_records_checked": 1
}
```

| Motivo | Interpretación |
|---|---|
| `prev_hash_broken` | El enlace apunta a un hash anterior incorrecto. |
| `hash_mismatch` | El SHA-256 recalculado difiere del almacenado. |
| `payload_mismatch` | El último evento de la entidad difiere de sus datos actuales. |
| `missing_entity` | El documento referenciado desapareció. |
| `missing_event` | Existe un documento sin evento. Su secuencia desconocida se devuelve como null. |
| `sequence_gap` | Falta una posición o la cadena se acortó desde una auditoría válida. La referencia de entidad puede ser null. |
| `checkpoint_mismatch` | El hash de una posición auditada anteriormente cambió. |

## GET /api/admin/integrity/chain?page=1&per_page=25

Devuelve HTTP 200. La primera página contiene los eventos más recientes. El límite configurable es de 1 a 100 filas. `hash_short` contiene los 12 primeros caracteres de `current_hash`. Para copiar o comparar usa el hash completo. Una página sin resultados devuelve `entries: []`.

```json
{
  "entries": [
    {
      "created_at": "2026-11-26T00:28:55.281958Z",
      "current_hash": "76e3f93630906da9b4c7dcd4c5757474b18e91f52838b77ec2aadcbc896d3e06",
      "entity_id": 1,
      "entity_type": "invoice",
      "event_type": "issued",
      "hash_short": "76e3f9363090",
      "prev_hash": "GENESIS",
      "seq_no": 1
    }
  ],
  "page": 1,
  "pages": 1,
  "per_page": 1,
  "total": 1
}
```

## Anulación de una factura

`POST /api/admin/invoices/{id}/void` con `{}` devuelve HTTP 200 con `{"invoice": ...}`, usando el objeto de la Fase 1 con estado `anulada`. La anulación agrega un evento `voided`. Reintentar conserva el mismo historial. Una factura inexistente devuelve 404. Los pagos pendientes o aprobados impiden anularla (`409 active_payments`). Una discrepancia previa con su último evento bloquea la operación (`409 integrity_conflict`). Las correcciones financieras futuras deben crear su evento `adjustment` dentro de la transacción del documento.

## Formato y alcance de la cadena

Una sola secuencia empieza en 1. La entrada de SHA-256 es UTF-8 y tiene el formato `seq_no|entity_type|entity_id|event_type|canonical_payload|prev_hash`. El primer enlace usa `GENESIS`. Cada payload es un objeto JSON compacto, con claves ordenadas, texto Unicode, dinero como cadena de dos decimales y fechas UTC con seis decimales y sufijo Z. Se comprueba cada enlace histórico y se compara el estado actual del documento con su último evento.

Las facturas protegen el número, pedido, empleado, importes, envío, estado, fecha y el resumen de sus ítems en orden de ID. El resumen se calcula concatenando cada JSON de línea con un salto de línea final. Los pagos protegen factura, pedido, monto, método, estado, fechas, ruta, tipo y SHA-256 de los bytes del comprobante. La API de integridad devuelve hashes y referencias. La descarga de archivos conserva el contrato de permisos de la Fase 1.

## Instalación y auditorías de sistema

Con las escrituras de facturación detenidas, aplica `supabase/migrations/20261126002349_financial_integrity.sql` después de la migración de facturación y despliega el backend actualizado antes de reanudarlas. La instalación inicial sella los documentos existentes en su estado de migración, en orden de fecha, tipo e ID. La auditoría acredita cambios a partir de ese punto. Reaplicar la migración conserva el historial. El acceso directo de navegador queda revocado. El rol SQL privado de Flask puede leer y anexar, y la API exige rol admin para las consultas de auditoría.

Para verificar desde un programador de tareas, ejecuta `flask --app run verify-integrity` desde `backend/`. Guarda una auditoría como `system`, imprime el mismo JSON y termina con código 1 al detectar una divergencia. La frecuencia la define el operador.

La cadena y los puntos de comprobación residen en la misma base. Un propietario con control de ambas tablas podría reescribir también las evidencias. Para acreditar el historial frente a ese actor se necesita conservar el hash de cabeza en un sistema de confianza independiente.
