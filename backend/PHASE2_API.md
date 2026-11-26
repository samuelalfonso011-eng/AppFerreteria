# Fase 2: Algoritmos y Análisis Experimental (contrato de API)

Contrato para la pantalla **Benchmarks** del Modo Admin. Todo vive bajo `/api/admin`, así que hereda el
guardia del blueprint admin: sin sesión responde `401`, con una cuenta que no es `admin` responde `403`.
Las respuestas llevan `Cache-Control: no-store`. El `POST` necesita el encabezado CSRF igual que el resto
del admin (`X-CSRF-Token`).

| Método | Ruta | Uso |
|---|---|---|
| `POST` | `/api/admin/benchmarks/run` | Ejecuta el experimento y devuelve el reporte completo |
| `GET` | `/api/admin/benchmarks/latest` | Devuelve el último reporte guardado (memoria o archivo) |

## Algoritmos medidos

Implementados a mano en `app/services/algorithms_service.py` (sin `sorted()`, `.sort()`, `heapq` ni
`ORDER BY`; una prueba revisa el árbol de sintaxis para garantizarlo).

| Clave (`algorithm`) | Etiqueta (`label`) | Complejidad | Grupo en `series` |
|---|---|---|---|
| `linear_search` | Búsqueda lineal por ID | O(n) | `o_n` |
| `sum_sales` | Suma de ventas | O(n) | `o_n` |
| `count_by_customer` | Pedidos por cliente (hash map) | O(n) | `o_n` |
| `insertion_sort` | Insertion Sort por fecha | O(n^2) | `o_n2` |
| `naive_ranking` | Ranking ingenuo de productos | O(n^2) | `o_n2` |
| `merge_sort` | Merge Sort por fecha | O(n log n) | `o_nlogn` |
| `rank_top` | Ranking con hash map + Merge Sort | O(n log n) | `o_nlogn` |

Comparaciones Antes vs Después (`comparison[].operation`):

- `Ordenar pedidos por fecha`: `insertion_sort` frente a `merge_sort`.
- `Ranking de productos más vendidos`: `naive_ranking` frente a `rank_top`.

Ambos ordenamientos son estables y usan la clave `(created_at, id)`, así que el resultado es idéntico
incluso con fechas repetidas. El ranking ordena por unidades descendente y desempata por `product_id`.

## POST /api/admin/benchmarks/run

### Cuerpo (todos los campos son opcionales)

```json
{
  "source": "synthetic",
  "sizes": [100, 500, 1000, 2500, 5000],
  "repetitions": 3,
  "seed": 42,
  "search_id": 2
}
```

| Campo | Tipo | Por defecto | Reglas |
|---|---|---|---|
| `source` | `"synthetic"` o `"real"` | `"synthetic"` | `real` mide sobre los pedidos de la base (un solo N = número de pedidos, máximo 5000) |
| `sizes` | lista de enteros | `[100, 500, 1000, 2500, 5000]` | 1 a 6 valores, cada uno entre 10 y 5000; se quitan duplicados y se ordenan. Se ignora con `source: "real"` |
| `repetitions` | entero | `3` | 3 a 5 |
| `seed` | entero | `42` | 0 a 2147483647. Con la misma semilla los datos sintéticos son idénticos en cualquier máquina |
| `search_id` | entero | último pedido | ID de pedido que busca la búsqueda lineal en los resultados reales |

**Tope de seguridad.** En modo sintético, `suma(n^2) x repeticiones` no puede superar la carga de los
tamaños por defecto con 5 repeticiones (unos 18 s en este equipo, por debajo del timeout de 30 s de
gunicorn). Si se excede responde `400` en el campo `sizes`. Solo corre un benchmark a la vez por proceso.

**Datos reales siempre presentes.** Aunque `source` sea `synthetic`, el endpoint lee la base (medido aparte
en `timing.db_fetch_ms`) y llena `results` con los indicadores de negocio. Si la base no responde, en modo
sintético `results` llega en `null`; en modo real responde `503`.

### 200: reporte completo

Ejemplo con `{"sizes": [100, 500], "repetitions": 3}`. Las listas `comparison` y `measurements`
están recortadas: llegan con 2 filas por N y 7 filas por N respectivamente.

```json
{
  "meta": {
    "python": "3.13.17",
    "implementation": "CPython",
    "os": "Windows-10-10.0.19045-SP0",
    "machine": "AMD64",
    "processor": "Intel64 Family 6 Model 142 Stepping 12, GenuineIntel",
    "cpu_count": 4,
    "run_at": "2026-11-26T00:11:48Z",
    "source": "synthetic",
    "seed": 42,
    "sizes": [100, 500],
    "repetitions": 3,
    "timer": { "name": "time.perf_counter", "resolution_s": 1e-07 },
    "argv": null,
    "report_file": "backend/reports/benchmark_latest.json"
  },
  "timing": {
    "db_fetch_ms": 3450.7639,
    "compute_ms": 132.2
  },
  "series": {
    "labels": [100, 500],
    "o_n": {
      "linear_search": [0.0086, 0.0381],
      "sum_sales": [0.0343, 0.1529],
      "count_by_customer": [0.0195, 0.0878]
    },
    "o_n2": {
      "insertion_sort": [0.7459, 18.7364],
      "naive_ranking": [0.139, 1.9081]
    },
    "o_nlogn": {
      "merge_sort": [0.4269, 2.7286],
      "rank_top": [0.0986, 0.5574]
    }
  },
  "comparison": [
    {
      "n": 100,
      "operation": "Ordenar pedidos por fecha",
      "before": {
        "algorithm": "insertion_sort",
        "complexity": "O(n^2)",
        "min_ms": 0.7412,
        "avg_ms": 0.7466,
        "median_ms": 0.7459
      },
      "after": {
        "algorithm": "merge_sort",
        "complexity": "O(n log n)",
        "min_ms": 0.4225,
        "avg_ms": 0.4293,
        "median_ms": 0.4269
      },
      "speedup": 1.75,
      "improvement_pct": 42.8
    },
    {
      "n": 100,
      "operation": "Ranking de productos más vendidos",
      "before": {
        "algorithm": "naive_ranking",
        "complexity": "O(n^2)",
        "min_ms": 0.1358,
        "avg_ms": 0.1428,
        "median_ms": 0.139
      },
      "after": {
        "algorithm": "rank_top",
        "complexity": "O(n log n)",
        "min_ms": 0.0952,
        "avg_ms": 0.1009,
        "median_ms": 0.0986
      },
      "speedup": 1.41,
      "improvement_pct": 29.1
    }
  ],
  "measurements": [
    {
      "n": 100,
      "algorithm": "linear_search",
      "label": "Búsqueda lineal por ID",
      "complexity": "O(n)",
      "min_ms": 0.0074,
      "avg_ms": 0.01,
      "median_ms": 0.0086,
      "runs_ms": [0.014, 0.0086, 0.0074]
    }
  ],
  "equivalence": {
    "sort_by_date": true,
    "top_products": true,
    "checked_sizes": [100, 500]
  },
  "results": {
    "orders_count": 2,
    "items_count": 2,
    "total_sales": "648400.00",
    "sales_statuses": ["CONFIRMED", "PREPARING", "SHIPPED", "DELIVERED"],
    "top_products": [
      { "product_id": 1, "name": "Taladro Percutor Pro X1", "units": 1, "revenue": "489900.00" }
    ],
    "customers_count": 2,
    "orders_by_customer": [
      { "customer": "cliente@example.com", "orders": 1 }
    ],
    "search": {
      "target_id": 2,
      "found": true,
      "comparisons": 2,
      "order_number": "FP-261125-A9CF21",
      "total": "489900.00"
    },
    "first_order_at": "2026-11-25T06:08:06.348999Z",
    "last_order_at": "2026-11-25T06:14:13.219029Z"
  }
}
```

### Significado de los campos

- **Tiempos**: milisegundos medidos con `time.perf_counter`. Cada algoritmo corre `repetitions` veces
  sobre una copia de los mismos datos; se reportan `min_ms`, `avg_ms`, `median_ms` y cada corrida en
  `runs_ms`. Las series del gráfico usan la **mediana**.
- **`timing.db_fetch_ms`**: lectura de pedidos e ítems desde la base, separada del cómputo. `null` si no se
  leyó la base. **`timing.compute_ms`**: tiempo total de todas las mediciones.
- **`series`**: listo para un gráfico de líneas. `labels` es el eje X (N); cada lista tiene un valor por N
  en el mismo orden.
- **`comparison`**: tabla Antes vs Después. `speedup = mediana_antes / mediana_después` (2 decimales);
  `improvement_pct = (1 - después / antes) x 100` (1 decimal).
- **`equivalence`**: el servicio comprueba en cada N que Insertion Sort y Merge Sort devuelven el mismo
  orden y que ambos rankings coinciden. Si no coinciden la ejecución falla (no se guarda un reporte
  inválido), así que en una respuesta `200` estos valores son siempre `true`.
- **`results`**: indicadores de negocio sobre los datos reales. Dinero como texto con 2 decimales (se
  calcula con `Decimal`). `total_sales` y `top_products` solo cuentan pedidos en `sales_statuses`; los
  pedidos pendientes o cancelados no suman. `orders_by_customer` trae los 10 clientes con más pedidos.
  `search` es la búsqueda lineal: `comparisons` es cuántos registros revisó. Fechas en ISO 8601 UTC.
- **`meta.notes`** (opcional): avisos, por ejemplo cuando el modo real recorta a 5000 pedidos.
- **`meta.report_file`**: dónde se guardó el reporte, o `null` si el sistema de archivos no permitió
  escribir (el último reporte sigue disponible en memoria).

`results.orders_by_customer` contiene correos de clientes: la pantalla debe mostrarlos solo dentro del
Modo Admin y siempre con `textContent`.

### Errores

`400` validación (mismo formato que el resto de la API):

```json
{
  "error": "validation",
  "fields": {
    "sizes": "Cada tamaño debe ser un entero entre 10 y 5000.",
    "repetitions": "...",
    "source": "..."
  }
}
```

Tope de carga excedido:

```json
{
  "error": "validation",
  "fields": {
    "sizes": "La combinación de tamaños y repeticiones excede el tope seguro. Reduce los tamaños o las repeticiones."
  }
}
```

`401` sin sesión y `403` sin rol `admin`: formato estándar del guardia admin.

`409` ya hay una ejecución en curso:

```json
{ "error": "benchmark_running", "message": "Ya hay un benchmark en ejecución." }
```

`503` con `source: "real"` y la base caída:

```json
{ "error": "database_unavailable", "message": "No se pudo leer la base de datos." }
```

## GET /api/admin/benchmarks/latest

`200` devuelve exactamente el mismo objeto que el último `POST /run` exitoso. Primero busca en memoria y,
si el proceso se reinició o la petición cae en otro worker, lee `backend/reports/benchmark_latest.json`.

`404` si nunca se ha ejecutado:

```json
{ "error": "no_benchmark", "message": "Todavía no se ha ejecutado ningún benchmark." }
```

## Sugerencias para la pantalla Benchmarks

1. Al abrir, `GET /latest`; con `404`, estado vacío con el botón "Ejecutar benchmark".
2. El botón hace `POST /run` (puede tardar unos 10 s con los tamaños por defecto): deshabilitarlo y
   mostrar progreso indeterminado; con `409`, mostrar que ya hay una ejecución en curso.
3. Gráfico de líneas con `series` (eje X `labels`, una línea por algoritmo, escala logarítmica en Y
   recomendada porque O(n^2) crece mucho más rápido).
4. Tabla Antes vs Después con `comparison` agrupada por `n`.
5. Bloque de resultados reales con `results`, y el pie con `meta` (Python, sistema, CPU, semilla,
   repeticiones, fecha) para que el experimento sea reproducible.

## Reproducir desde la terminal

Desde `backend/`:

```powershell
venv\Scripts\python scripts\run_benchmarks.py --repetitions 5
```

Opciones: `--source synthetic|real`, `--sizes 100 500 1000 2500 5000` (hasta 20000 en la terminal),
`--repetitions 3..10`, `--seed 42`, `--search-id ID`, `--output ruta.json`, `--no-db` (solo sintético,
sin leer la base). Imprime la tabla Antes vs Después y guarda `backend/reports/benchmark_latest.json`.
Ese archivo no se versiona porque incluye correos de clientes reales.

### Resultado de referencia (este equipo, semilla 42, 5 repeticiones, mediana en ms)

Intel Core de 4 hilos, Windows 10, CPython 3.13.17.

| N | Insertion | Merge | Mejora | Ranking O(n^2) | Ranking O(n log n) | Mejora |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 0.744 | 0.423 | 1.76x | 0.136 | 0.094 | 1.44x |
| 500 | 18.806 | 2.715 | 6.93x | 1.921 | 0.546 | 3.52x |
| 1000 | 78.349 | 6.377 | 12.29x | 6.633 | 1.183 | 5.61x |
| 2500 | 705.172 | 18.115 | 38.93x | 29.142 | 2.766 | 10.53x |
| 5000 | 2431.227 | 41.491 | 58.6x | 50.661 | 4.333 | 11.69x |

Lectura: al duplicar N, Insertion Sort tarda unas 4 veces más (cuadrático) y Merge Sort algo más del
doble (n log n). Las operaciones O(n) crecen en línea recta: a N = 5000 la búsqueda lineal tarda 0.44 ms,
la suma de ventas 1.61 ms y el conteo por cliente 0.89 ms. La equivalencia se verificó en los 5 tamaños.

## Pruebas

```powershell
venv\Scripts\python -m pytest -q tests/test_algorithms.py tests/test_benchmarks_api.py
```

Cubren listas vacías y de un elemento, empates de fecha, que no se modifique la entrada, equivalencia
Insertion vs Merge sobre entradas aleatorias, rankings contra un cálculo de referencia, determinismo de
la semilla, la prohibición de ordenamientos nativos, la protección `401`/`403`, la validación y el tope,
el `409` por ejecución concurrente, el `404` inicial, la lectura del reporte desde archivo y la CLI.
