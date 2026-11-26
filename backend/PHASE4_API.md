# FerrePro | Calidad de datos y analítica

Todas las rutas usan sesión Flask y requieren rol `admin`. Sin sesión devuelven 401 y para cliente o empleado devuelven 403. El POST requiere JSON y el encabezado habitual `X-CSRF-Token`. Las respuestas contienen información privada y usan `Cache-Control: no-store`. Los ejemplos corresponden a peticiones contra una base de prueba.

## POST /api/admin/data-quality/audit

Envía `{}`. Devuelve 200 con el informe final. Una ejecución recorre los seis módulos y confirma las correcciones y sus incidencias en la misma transacción. Un nuevo POST crea una ejecución independiente. Los valores anteriores y propuestos son texto o null. `details.field` indica la columna o el atributo evaluado. Para candidatos duplicados, `details.related_entity_ids` identifica los demás registros del mismo módulo.

El informe cuenta incidencias por campo. Para el puntaje cuenta entidades distintas con incidencias pendientes después de las correcciones: 100 × (registros escaneados menos entidades pendientes) / registros escaneados. Un conjunto vacío obtiene 100. Cada módulo informa sus propios contadores.

La auditoría normaliza texto NFC, espacios y casing de correo y SKU. En nombres de categoría solo corrige el casing cuando el nombre está escrito todo en mayúsculas o todo en minúsculas; un nombre con mayúsculas y minúsculas mezcladas (por ejemplo `Bombillas LED` o `Tubería PVC`) se respeta para no destruir siglas ni marcas. Compara productos por nombre o SKU sin separadores, usuarios por correo y clientes por teléfono compartido en pedidos vinculados a cuentas distintas. Los invitados quedan fuera de la comparación de identidades. Los candidatos, categorías huérfanas, precios inválidos y campos obligatorios ausentes requieren revisión. Dos categorías con el mismo nombre se informan como `duplicate_candidate`; `inconsistent_category` queda reservado para productos que apuntan a una categoría inexistente. Los importes de facturas y pagos y sus documentos de integridad se conservan. Un total de factura cero puede corresponder a un descuento completo.

```json
{
  "auto_fixed_count": 1,
  "executed_at": "2026-11-26T03:55:06.697707Z",
  "executed_by": 1,
  "id": 1,
  "issues": [
    {
      "details": {
        "field": "name"
      },
      "entity_id": 1,
      "id": 1,
      "issue_type": "malformed_string",
      "module": "categories",
      "normalized_value": "Manuales",
      "original_value": "  MANUALES  ",
      "run_id": 1,
      "severity": "low",
      "status": "auto_fixed"
    }
  ],
  "issues_found": 1,
  "pending_review_count": 0,
  "quality_score": 100.0,
  "summary_by_module": {
    "categories": {
      "auto_fixed": 1,
      "pending_review": 0,
      "scanned": 1
    },
    "invoices": {
      "auto_fixed": 0,
      "pending_review": 0,
      "scanned": 0
    },
    "orders": {
      "auto_fixed": 0,
      "pending_review": 0,
      "scanned": 0
    },
    "payments": {
      "auto_fixed": 0,
      "pending_review": 0,
      "scanned": 0
    },
    "products": {
      "auto_fixed": 0,
      "pending_review": 0,
      "scanned": 1
    },
    "users": {
      "auto_fixed": 0,
      "pending_review": 0,
      "scanned": 3
    }
  },
  "total_records_scanned": 5
}
```

## GET /api/admin/data-quality/latest

Sin parámetros. Devuelve 200 con el mismo objeto del POST anterior, incluidas sus incidencias, o el literal JSON `null` antes de la primera auditoría. Los contadores (`pending_review_count`, `summary_by_module`, `quality_score`) describen la ejecución tal como ocurrió; el `status` de cada incidencia es el vigente.

## POST /api/admin/data-quality/issues/{id}/resolve

Envía `{}`. Marca como `resolved` una incidencia `pending_review` después de corregirla a mano. Devuelve 200 con `{"issue": {...}, "changed": true}`; repetir devuelve `"changed": false`. Una incidencia `auto_fixed` responde `409 issue_not_pending` y un ID inexistente `404`. Requiere `supabase/migrations/20261126090000_quality_resolve.sql`, que concede `UPDATE` solo sobre `status`.

## GET y POST /api/admin/analytics/users

`GET` es una lectura pura: calcula perfiles y alertas sin escribir en la base. Cada alerta trae el `id` y la fecha de su fila guardada, o `null` si todavía no se ha persistido. `POST` (cuerpo `{}`) recalcula, sincroniza `anomaly_alerts` y devuelve el mismo cuerpo con los IDs definitivos.

Sin parámetros. Devuelve 200 con perfiles de cuentas con rol actual customer o employee, incluidas las que no tienen actividad. `operations[].id` referencia pedidos para clientes y facturas para empleados. Montos en COP, porcentajes de descuentos de 0 a 100 y tasas de anulación de 0 a 1. La frecuencia del cliente (`orders_per_day`) divide su número de pedidos por los días calendario del intervalo común de pedidos vinculados; la del empleado (`invoices_per_day`) divide sus facturas por el intervalo común de facturas. En empate de canal se usa el primer nombre en orden alfabético.

Los boxplots usan interpolación lineal con posición (n - 1) × p y cercas de Tukey a 1,5 IQR. Los bigotes son los valores observados extremos dentro de las cercas. Sin observaciones se devuelve null. Las alertas usan la cerca superior. Un monto o descuento individual se compara **solo con las operaciones anteriores** de la misma cuenta y requiere al menos cuatro previas: una cerca calculada con todo el historial juzgaría una compra con datos posteriores a ella. `threshold_info` es la cerca vigente en el caso de mayor puntaje (su `n` cuenta las operaciones previas) y `source_record_ids` lista todas las operaciones que superaron su propia cerca. `amount_boxplot` sigue resumiendo todo el historial como dato descriptivo. La frecuencia diaria y la proporción de cancelaciones se comparan entre cuentas activas del mismo rol (al menos cuatro cuentas). También se compara el porcentaje medio de descuento entre empleados. Si dos reglas de descuento se disparan, se devuelve la de mayor puntaje.

Las alertas persistidas son el conjunto vigente, con una fila por usuario, rol y tipo. Cada `POST` actualiza sus evidencias, conserva su ID mientras la alerta exista y retira las que dejan de aplicar. El puntaje es 100 × exceso / (exceso + escala), donde exceso es la distancia positiva a la cerca superior y escala es IQR. Cuando IQR es cero se usa el máximo entre 1 y el valor absoluto de la cerca. El puntaje describe magnitud relativa, no probabilidad de fraude.

```json
{
  "alerts": [],
  "customer_window_days": 1,
  "global_boxplots": {
    "customer": {
      "iqr": 0.0,
      "lower": 100.0,
      "median": 100.0,
      "n": 1,
      "outliers": [],
      "q1": 100.0,
      "q3": 100.0,
      "upper": 100.0,
      "whisker_max": 100.0,
      "whisker_min": 100.0
    },
    "employee": {
      "iqr": 0.0,
      "lower": 90.0,
      "median": 90.0,
      "n": 1,
      "outliers": [],
      "q1": 90.0,
      "q3": 90.0,
      "upper": 90.0,
      "whisker_max": 90.0,
      "whisker_min": 90.0
    }
  },
  "profiles": [
    {
      "amount_boxplot": {
        "iqr": 0.0,
        "lower": 100.0,
        "median": 100.0,
        "n": 1,
        "outliers": [],
        "q1": 100.0,
        "q3": 100.0,
        "upper": 100.0,
        "whisker_max": 100.0,
        "whisker_min": 100.0
      },
      "cancellation_rate": 0.0,
      "name": "Ana Pérez",
      "operations": [
        {
          "amount": 100.0,
          "id": 1,
          "status": "CONFIRMED"
        }
      ],
      "operations_count": 1,
      "orders_per_day": 1.0,
      "predominant_channel": "web",
      "user_id": 2,
      "user_role": "customer"
    },
    {
      "amount_boxplot": {
        "iqr": 0.0,
        "lower": 90.0,
        "median": 90.0,
        "n": 1,
        "outliers": [],
        "q1": 90.0,
        "q3": 90.0,
        "upper": 90.0,
        "whisker_max": 90.0,
        "whisker_min": 90.0
      },
      "cancellation_rate": 0.0,
      "discounts": [
        {
          "amount": 10.0,
          "invoice_id": 1,
          "percent": 10.0
        }
      ],
      "invoices_issued": 1,
      "name": "Caja",
      "operations": [
        {
          "amount": 90.0,
          "id": 1,
          "status": "emitida"
        }
      ],
      "operations_count": 1,
      "user_id": 3,
      "user_role": "employee"
    }
  ]
}
```

Ejemplo de un elemento de `alerts` tras incorporar más pedidos. Los IDs identifican los documentos que sustentan la alerta.

```json
{
  "alert_type": "high_amount_outlier",
  "anomaly_score": 80.0,
  "created_at": "2026-11-26T03:55:06.763160Z",
  "explanation": "Monto superior al historial previo de la cuenta (COP). Valor 1500.00, límite 700.00 según las 5 operaciones anteriores.",
  "id": 1,
  "source_record_ids": {
    "order_ids": [
      5
    ]
  },
  "threshold_info": {
    "iqr": 200.0,
    "lower": -100.0,
    "median": 300.0,
    "n": 5,
    "outliers": [
      1500.0
    ],
    "q1": 200.0,
    "q3": 400.0,
    "upper": 700.0,
    "whisker_max": 400.0,
    "whisker_min": 100.0
  },
  "user_id": 2,
  "user_role": "customer"
}
```

## GET /api/admin/analytics/demand

| Parámetro opcional | Valores | Predeterminado |
|---|---|---|
| `period` | `daily` o `weekly` | `daily` |
| `horizon` | Entero de 1 a 30 períodos | 3 |
| `product_id` | ID positivo de producto | Todos los productos |

Un parámetro fuera de rango devuelve 400 con `fields`. Un producto inexistente devuelve 404. El filtro limita `products`; la serie `global` siempre agrega todas las unidades vendidas. Se usan líneas de pedidos confirmados, en preparación, enviados o entregados, excluyendo pedidos con factura anulada. Días de Bogotá y semanas desde el lunes. Cada producto comienza en su primera venta; los huecos se completan con cero hasta el último período con ventas globales. Sin ventas hay series vacías.

`history` está en orden cronológico. Para al menos tres períodos se ajusta una recta sobre los primeros max(2, floor(0,8 × n)) y se evalúa exclusivamente en el tramo posterior. `model` contiene la pendiente y el intercepto para x = 0 en el primer período. `estimated` usa exclusivamente este modelo, incluso en el tramo de prueba. MAE y RMSE están en unidades vendidas. R² puede ser negativo; es null cuando la varianza de prueba es cero. El modelo de pronóstico `forecast_model` usa todo el histórico después de evaluar; sus predicciones futuras se limitan a cero por abajo. Con menos de cinco períodos se marca `short_series`. Con dos se puede pronosticar, pero faltan métricas de prueba. Con uno o ninguno se omiten los modelos y pronósticos.

Respuesta 200 de `?period=daily&horizon=1&product_id=1`.

```json
{
  "global": {
    "forecast": [
      {
        "period": "2026-01-06",
        "predicted": 14.0
      }
    ],
    "forecast_model": {
      "intercept": -1.0,
      "slope": 3.0
    },
    "history": [
      {
        "estimated": 1.0,
        "observed": 1,
        "period": "2026-01-01",
        "split": "train"
      },
      {
        "estimated": 2.0,
        "observed": 2,
        "period": "2026-01-02",
        "split": "train"
      },
      {
        "estimated": 3.0,
        "observed": 3,
        "period": "2026-01-03",
        "split": "train"
      },
      {
        "estimated": 4.0,
        "observed": 4,
        "period": "2026-01-04",
        "split": "train"
      },
      {
        "estimated": 5.0,
        "observed": 15,
        "period": "2026-01-05",
        "split": "test"
      }
    ],
    "metrics": {
      "mae": 10.0,
      "r2": null,
      "rmse": 10.0
    },
    "model": {
      "intercept": 1.0,
      "slope": 1.0
    },
    "short_series": false,
    "test_periods": 1,
    "train_periods": 4
  },
  "horizon": 1,
  "period": "daily",
  "products": [
    {
      "forecast": [
        {
          "period": "2026-01-06",
          "predicted": 14.0
        }
      ],
      "forecast_model": {
        "intercept": -1.0,
        "slope": 3.0
      },
      "history": [
        {
          "estimated": 1.0,
          "observed": 1,
          "period": "2026-01-01",
          "split": "train"
        },
        {
          "estimated": 2.0,
          "observed": 2,
          "period": "2026-01-02",
          "split": "train"
        },
        {
          "estimated": 3.0,
          "observed": 3,
          "period": "2026-01-03",
          "split": "train"
        },
        {
          "estimated": 4.0,
          "observed": 4,
          "period": "2026-01-04",
          "split": "train"
        },
        {
          "estimated": 5.0,
          "observed": 15,
          "period": "2026-01-05",
          "split": "test"
        }
      ],
      "metrics": {
        "mae": 10.0,
        "r2": null,
        "rmse": 10.0
      },
      "model": {
        "intercept": 1.0,
        "slope": 1.0
      },
      "name": "Martillo",
      "product_id": 1,
      "short_series": false,
      "test_periods": 1,
      "train_periods": 4
    }
  ]
}
```

## Instalación

Aplica `supabase/migrations/20261126034955_quality_analytics.sql` antes de arrancar el backend actualizado en una base existente. El esquema inicial y las políticas también contienen las nuevas tablas para instalaciones nuevas. Ejecuta `python -m pytest backend/tests/test_phase4.py -q` desde la raíz para reproducir las pruebas específicas.
