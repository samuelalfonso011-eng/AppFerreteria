# FerrePro | Modelos de fraude y demanda

Los cuatro endpoints usan sesión de administrador y `Cache-Control: no-store`. Las escrituras reciben JSON y `X-CSRF-Token`. Para la vista inicial, consulta status. Después de entrenar, usa la versión devuelta para identificar las métricas en pantalla y refresca status. Las predicciones leen artefactos sin entrenar. Estos ejemplos proceden de la demostración aislada, con etiquetas y ventas **simuladas**.

## POST /api/admin/ml/train

Cuerpo `{}` o `{"seed":42}`. La semilla acepta enteros de 0 a 2147483647. TensorFlow tarda más que el timeout de 30 s de gunicorn, así que la petición **inicia el entrenamiento en segundo plano** y devuelve `202` con el estado del trabajo. El panel consulta `GET /api/admin/ml/status` (campo `training`) hasta que `state` pase a `succeeded` o `failed`. Solo corre un entrenamiento a la vez: un segundo POST mientras hay uno en curso devuelve `409 training_busy`, también desde otro worker, porque el estado se guarda en `ML_ARTIFACT_DIR/training.json`, en el volumen compartido.

```json
{
  "training": {
    "state": "running",
    "seed": 42,
    "started_at": "2026-11-26T08:10:02.114233Z",
    "finished_at": null,
    "version": null,
    "error": null,
    "message": null
  }
}
```

Con `ML_TRAIN_ASYNC=0` (modo de las pruebas) y en el CLI el entrenamiento es síncrono y devuelve `201` con las dos corridas. Las corridas comparten `version`. Cada modelo tiene su propio ID. `dataset_summary` y `metrics` difieren por modelo; `by_label_source.real: null` indica que no hubo casos reales etiquetados en prueba. La matriz usa el umbral 0,5. Las métricas de demanda están agregadas por producto y día del tramo reservado. Este es el resultado de la demostración `--demo --seed 42`, el mismo objeto que después aparece en `run` de `GET /status`:

```json
{
  "runs": [
    {
      "id": 1,
      "model_name": "fraud_classifier",
      "version": "d5b51a1dc1294f7b95d9930edb7f7740",
      "trained_at": "2026-11-26T05:57:30.313043Z",
      "artifact_path": "d5b51a1dc1294f7b95d9930edb7f7740/fraud_classifier.keras",
      "seed": 42,
      "dataset_summary": {
        "cutoff": "2025-01-01T00:00:00Z",
        "real_payments": 0,
        "adjudicated": 0,
        "late_labels_excluded": 0,
        "simulated_labels": true,
        "train": {
          "size": 256,
          "fraud_fraction": 0.1875,
          "normal": 208,
          "fraudulenta": 48,
          "label_sources": {
            "simulated": 256
          },
          "first": "2024-12-21T08:00:00Z",
          "last": "2024-12-31T23:00:00Z"
        },
        "test": {
          "size": 64,
          "fraud_fraction": 0.234375,
          "normal": 49,
          "fraudulenta": 15,
          "label_sources": {
            "simulated": 64
          },
          "first": "2025-01-01T00:00:00Z",
          "last": "2025-01-03T15:00:00Z"
        },
        "oversampled_train_rows": 160,
        "epochs": 16,
        "tensorflow": "2.21.0",
        "keras": "3.15.1",
        "artifact_sha256": "6389da170a8970153847198eac23d60ae60ee4a1aaa75eb683c8f184b70676de",
        "metadata_sha256": "699c186fd2c9a95ac209cd3552502afa55fea8a1cbc5ff6257c2664442d85c1d"
      },
      "metrics": {
        "precision": 0.7058823529411765,
        "recall": 0.8,
        "f1": 0.75,
        "confusion_matrix": {
          "tp": 12,
          "fp": 5,
          "tn": 44,
          "fn": 3
        },
        "by_label_source": {
          "real": null,
          "simulated": {
            "precision": 0.7058823529411765,
            "recall": 0.8,
            "f1": 0.75,
            "confusion_matrix": {
              "tp": 12,
              "fp": 5,
              "tn": 44,
              "fn": 3
            }
          }
        }
      }
    },
    {
      "id": 2,
      "model_name": "demand_regressor",
      "version": "d5b51a1dc1294f7b95d9930edb7f7740",
      "trained_at": "2026-11-26T05:57:33.727740Z",
      "artifact_path": "d5b51a1dc1294f7b95d9930edb7f7740/demand_regressor.keras",
      "seed": 42,
      "dataset_summary": {
        "source": "simulated",
        "real_sale_days": 0,
        "excluded_products": 0,
        "cutoff": "2025-03-14",
        "train_size": 142,
        "training_examples": 612,
        "test_size": 36,
        "products": 2,
        "epochs": 16,
        "tensorflow": "2.21.0",
        "keras": "3.15.1",
        "artifact_sha256": "33b1ee24f6463ff441ac4ebdce6fd7964378f63f2205eba67500ea97823ce0b3",
        "metadata_sha256": "ae98ca35509cc677e171945727fe3b61f413f7ba6cdc03a862d73889a37f9595"
      },
      "metrics": {
        "keras": {
          "mae": 1.4894946946038141,
          "rmse": 1.7827734681749046,
          "r2": 0.6415721819072766
        },
        "linear_phase4": {
          "mae": 2.3995354887655034,
          "rmse": 2.737960526882864,
          "r2": 0.15459706844655197
        }
      }
    }
  ]
}
```

## GET /api/admin/ml/status

Devuelve 200. Antes del primer entrenamiento, la respuesta es:

```json
{
  "models": {
    "demand_regressor": {
      "loaded": false,
      "on_disk": false,
      "run": null
    },
    "fraud_classifier": {
      "loaded": false,
      "on_disk": false,
      "run": null
    }
  }
}
```

Tras entrenar, cada `run` contiene exactamente el objeto correspondiente de `runs` mostrado arriba. `on_disk` indica si están presentes el archivo .keras y el JSON asociado. `loaded` indica si esa versión se encuentra en memoria en el proceso Flask que respondió. En la primera inferencia se verifican ambos SHA-256 y se carga el modelo. Un reinicio conserva versiones y archivos si la base y el volumen son persistentes.

`training` describe el último entrenamiento iniciado desde la API, o es `null` si nunca hubo uno. `state` vale `running`, `succeeded` (con `version`) o `failed` (con `error` y `message`, por ejemplo `insufficient_test`). Si un trabajo queda en `running` más de `ML_TRAIN_STALE_SECONDS` (3600 por defecto), por ejemplo porque el proceso se reinició, se informa como `failed` con `error: "training_stalled"` y se puede volver a entrenar.

```json
{
  "models": { "...": "igual que arriba" },
  "training": {
    "state": "succeeded",
    "seed": 42,
    "started_at": "2026-11-26T08:10:02.114233Z",
    "finished_at": "2026-11-26T08:10:51.902114Z",
    "version": "d5b51a1dc1294f7b95d9930edb7f7740",
    "error": null,
    "message": null
  }
}
```

## POST /api/admin/ml/predict/fraud

Elige una sola forma de entrada: `{"order_id":42}`, `{"invoice_id":24}`, `{"payment_id":13}` o el objeto `transaction` del ejemplo. Los IDs existen en la base del backend. La referencia de pedido usa los datos del pedido en su creación, la de factura sus datos de emisión y la de pago incluye método y factura asociada. El snapshot de BD se construye en el servidor. Los IDs de cuenta y documento sirven para trazabilidad, quedan excluidos del vector numérico.

Para una transacción libre son obligatorios `occurred_at` (ISO con zona), `amount` (COP, 0 a 10¹²) y `channel` (presencial, web, app o domicilio). Son opcionales `payment_method` (efectivo, tarjeta, transferencia, pse, nequi o null), `prior_frequency` (entero entre 0 y 10000000), `discount_pct` (0 a 100), `cancellation_rate` (0 a 1) y `hash_valid` (0, 1 o null). Frecuencia, descuento y tasa comienzan en cero. Método e integridad desconocidos se representan por null. La auditoría declarada en una transacción libre es un dato suministrado por el administrador.

```json
{
  "transaction": {
    "occurred_at": "2025-01-01T15:00:00Z",
    "amount": 50000,
    "channel": "web",
    "payment_method": "tarjeta",
    "prior_frequency": 3,
    "hash_valid": 1
  }
}
```

Devuelve 201 y guarda una predicción por POST exitoso. `delta_probability` es el cambio local de la salida respecto a sustituir esa característica por su media de entrenamiento. Las tres señales con mayor valor absoluto son descriptivas. El campo de probabilidad es la salida sigmoide del modelo. La app no la utiliza para rechazar pagos.

```json
{
  "fraud_probability": 1.7539792951382083e-09,
  "id": 1,
  "model_run_id": 1,
  "predicted_label": "normal",
  "signals": [
    {
      "delta_probability": -2.1378941539307306e-07,
      "feature": "discount_fraction"
    },
    {
      "delta_probability": -7.819362479732916e-08,
      "feature": "cancellation_rate"
    },
    {
      "delta_probability": -4.234215722487278e-08,
      "feature": "log_amount"
    }
  ],
  "version": "d5b51a1dc1294f7b95d9930edb7f7740"
}
```

## GET /api/admin/ml/predict/demand

Acepta `product_id` opcional y `horizon` de 1 a 30 días (7 por defecto). Sin filtro devuelve los productos representados en la corrida. Los IDs negativos identifican series simuladas. `test` contiene el histórico reservado con observación y predicciones. `forecast` contiene los períodos posteriores al último día del dataset guardado con `observed: null`. Ambas curvas se expresan en unidades. La recta conserva pendiente e intercepto del entrenamiento. Para los días futuros, Keras puede usar los rezagos observados hasta el final del dataset; sus pesos y normalización se mantienen fijos.

Ejemplo 200 para `?product_id=-1&horizon=2`.

```json
{
  "cutoff": "2025-03-14",
  "metrics": {
    "keras": {
      "mae": 1.4894946946038141,
      "r2": 0.6415721819072766,
      "rmse": 1.7827734681749046
    },
    "linear_phase4": {
      "mae": 2.3995354887655034,
      "r2": 0.15459706844655197,
      "rmse": 2.737960526882864
    }
  },
  "model_run_id": 2,
  "products": [
    {
      "forecast": [
        {
          "keras": 20.23063850402832,
          "linear_phase4": 23.002695778935408,
          "observed": null,
          "period": "2025-04-01"
        },
        {
          "keras": 24.769283294677734,
          "linear_phase4": 23.125324243788455,
          "observed": null,
          "period": "2025-04-02"
        }
      ],
      "name": "Producto simulado 1",
      "product_id": -1,
      "test": [
        {
          "keras": 23.67229461669922,
          "linear_phase4": 20.795383411580595,
          "observed": 24,
          "period": "2025-03-14"
        },
        {
          "keras": 21.333221435546875,
          "linear_phase4": 20.91801187643364,
          "observed": 21,
          "period": "2025-03-15"
        },
        {
          "keras": 20.62007713317871,
          "linear_phase4": 21.040640341286682,
          "observed": 19,
          "period": "2025-03-16"
        },
        {
          "keras": 18.715877532958984,
          "linear_phase4": 21.16326880613973,
          "observed": 17,
          "period": "2025-03-17"
        },
        {
          "keras": 19.38286590576172,
          "linear_phase4": 21.285897270992777,
          "observed": 20,
          "period": "2025-03-18"
        },
        {
          "keras": 22.631040573120117,
          "linear_phase4": 21.40852573584582,
          "observed": 21,
          "period": "2025-03-19"
        },
        {
          "keras": 25.686817169189453,
          "linear_phase4": 21.531154200698865,
          "observed": 24,
          "period": "2025-03-20"
        },
        {
          "keras": 24.185832977294922,
          "linear_phase4": 21.65378266555191,
          "observed": 25,
          "period": "2025-03-21"
        },
        {
          "keras": 22.20762825012207,
          "linear_phase4": 21.776411130404956,
          "observed": 22,
          "period": "2025-03-22"
        },
        {
          "keras": 21.709321975708008,
          "linear_phase4": 21.899039595258003,
          "observed": 20,
          "period": "2025-03-23"
        },
        {
          "keras": 20.784143447875977,
          "linear_phase4": 22.021668060111047,
          "observed": 17,
          "period": "2025-03-24"
        },
        {
          "keras": 21.245849609375,
          "linear_phase4": 22.14429652496409,
          "observed": 18,
          "period": "2025-03-25"
        },
        {
          "keras": 23.83988380432129,
          "linear_phase4": 22.266924989817134,
          "observed": 21,
          "period": "2025-03-26"
        },
        {
          "keras": 26.706911087036133,
          "linear_phase4": 22.38955345467018,
          "observed": 25,
          "period": "2025-03-27"
        },
        {
          "keras": 24.699874877929688,
          "linear_phase4": 22.51218191952323,
          "observed": 27,
          "period": "2025-03-28"
        },
        {
          "keras": 22.723440170288086,
          "linear_phase4": 22.634810384376273,
          "observed": 24,
          "period": "2025-03-29"
        },
        {
          "keras": 22.283451080322266,
          "linear_phase4": 22.757438849229317,
          "observed": 22,
          "period": "2025-03-30"
        },
        {
          "keras": 22.075246810913086,
          "linear_phase4": 22.88006731408236,
          "observed": 20,
          "period": "2025-03-31"
        }
      ]
    }
  ],
  "source": "simulated",
  "version": "d5b51a1dc1294f7b95d9930edb7f7740"
}
```

## Errores

| HTTP | Código o causa |
|---|---|
| 400 | Validación de campos o JSON. |
| 401 / 403 | Sesión, rol u origen/CSRF según el guardia del panel. |
| 404 | Referencia de operación inexistente o producto ausente del modelo. |
| 202 | Entrenamiento iniciado en segundo plano (consultar `GET /status`). |
| 409 | `model_not_trained`, `training_busy`, `insufficient_test` o `insufficient_history`. Los dos últimos llegan en `training.error` cuando el entrenamiento corre en segundo plano. |
| 422 | `invalid_label_file` por archivo de adjudicaciones inválido. |
| 503 | `artifact_unavailable` por archivos ausentes, dañados o directorio no escribible. |

## Procedencia y separación temporal

**Fraude.** Se toma la fecha de creación del pago como instante de decisión. El corte se sitúa al 80 % de las fechas distintas. Una fecha empatada siempre pertenece al mismo lado. Frecuencia y anulaciones usan pedidos previos de la cuenta cliente, o del empleado cuando falta cliente, y el historial de cancelación anterior a la operación. Para invitados sin identidad quedan en cero. El estado de integridad deriva de la auditoría de Fase 3 disponible antes del instante sobre un eslabón de la factura ya creado. Una auditoría válida que cubre ese eslabón da 1; una divergencia atribuida a esa factura da 0. Sin evidencia aplicable queda null y el modelo incluye un indicador de desconocimiento.

Las etiquetas reales requieren revisión externa. `ML_LABEL_FILE` apunta a un CSV UTF-8 gestionado por el operador, con columnas `payment_id,label,adjudicated_at`; ejemplo de formato: `13,fraudulenta,2026-11-25T18:00:00Z`. Una fila por pago, etiqueta `normal` o `fraudulenta`, adjudicación desde la operación hasta el instante actual. Para pagos anteriores al corte, las etiquetas disponibles a partir del corte se excluyen. Una alerta de Fase 4, una factura anulada o un comprobante ausente por sí solos nunca constituyen una etiqueta de fraude.

Si train contiene menos de ocho casos adjudicados de alguna clase, se incorpora un corpus determinístico con etiquetas `simulated`. El simulador elige una clase latente y genera distribuciones superpuestas de montos, frecuencia, descuentos y otras características: **ambas clases comparten el mismo soporte** (descuento de 0 a 65 % con Beta, cancelaciones de 0 a 1 con Beta, frecuencia exponencial con tope 200, divergencia de hash posible en las dos clases, 25 % en fraude y 4 % en normales). Ningún valor delata la etiqueta por sí solo. La versión anterior usaba rangos anidados (por ejemplo, descuento normal hasta 30 % y fraudulento hasta 65 %) y producía `hash_valid = 0` solo en fraude: esos valores identificaban la clase con certeza e inflaban la precisión. `backend/tests/test_audit_fixes.py` comprueba que no vuelva a ocurrir. Incluye un tramo de evaluación sintético separado cronológicamente. Los recuentos y las métricas distinguen los dos orígenes. Sin adjudicaciones, las métricas solo describen el simulador. La normalización se adapta a train original y se serializa dentro del .keras; después se sobremuestrea únicamente la clase minoritaria de train. El tramo de prueba conserva su distribución.

**Demanda.** La variable objetivo son unidades brutas de ítems facturados por producto y día de emisión en Bogotá. Se omite el día actual incompleto. Esta definición evita reclasificar retrospectivamente ventas según una anulación posterior. Desde la primera venta de cada producto se rellenan huecos con cero hasta el último día observado del conjunto. Si el calendario disponible cubre menos de catorce días se usa una serie sintética identificada. Un único corte temporal separa todos los productos. Un producto necesita al menos tres períodos previos para entrar en la comparación.

Keras usa último valor conocido, media móvil de hasta siete días, índice de período, día de semana cíclico y horizonte. Se crean ejemplos directos de varios horizontes solo dentro de train. Se ajustan en train tanto la normalización de entradas como la escala de salida. Para **todo** el tramo de test, el origen de rezagos queda congelado en el corte; ningún valor observado de test entra en su propia evaluación ni en la de los días posteriores. La regresión usa la función de mínimos cuadrados de Fase 4 sobre el historial anterior de cada producto. Los dos modelos se evalúan exactamente en las mismas fechas. R² es null si el objetivo de prueba tiene varianza cero. No se exige que Keras supere al modelo lineal.

## Operación y reproducción

1. En una base existente aplica las migraciones de facturación, integridad y `supabase/migrations/20261126044431_ml_models.sql` antes de habilitar estas rutas. Las claves públicas de Supabase carecen de acceso a las tablas ML.
2. Instala `backend/requirements.txt`. Desde la raíz ejecuta `python backend/scripts/train_ml_models.py --seed 42`. Usa la misma conexión Flask y publica los dos archivos y sus metadatos antes de confirmar las dos filas de versión. Una ejecución concurrente devuelve conflicto.
3. `ML_ARTIFACT_DIR` apunta por defecto a `backend/ml_artifacts/`. En contenedor monta un volumen persistente escribible por Flask, compartido entre workers. Dimensiona la memoria para TensorFlow. El entrenamiento desde la API corre en un hilo del worker, así que no depende del timeout de gunicorn; el CLI sigue siendo síncrono. Las rutas de inferencia requieren el registro de la corrida y el par de archivos de esa versión.
4. Para reproducir el ejemplo aislado, ejecuta `python backend/scripts/train_ml_models.py --demo --seed 42`. Usa SQLite en memoria y conserva los .keras, metadatos y `runs.json` bajo `backend/ml_artifacts/demo/<version>/`. Las versiones operativas se guardan fuera de Git. TensorFlow y Keras, la semilla y las épocas quedan registrados; entre arquitecturas y runtimes puede haber diferencias de redondeo.
5. Ejecuta `python -m pytest backend/tests/test_phase5.py backend/tests/test_audit_fixes.py -q` para comprobar separación cronológica, adjudicaciones, normalización, recarga, inferencia, permisos, entrenamiento en segundo plano y que el simulador no filtre la etiqueta.
