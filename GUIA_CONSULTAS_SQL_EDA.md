# Guía de consultas SQL para el EDA

Puedes consultar los datos desde Python usando SQL sobre el archivo DuckDB que ya tienes.

```text
data/eda/372ff8010bafd0b4d802/warehouse.duckdb
```

## Cómo ejecutar las consultas

Desde la raíz del proyecto, abre Python:

```bash
.venv/bin/python
```

Pega esto una sola vez:

```python
import duckdb

con = duckdb.connect(
    "data/eda/372ff8010bafd0b4d802/warehouse.duckdb",
    read_only=True,
)

def consultar(sql):
    con.sql(sql).show()
```

Después puedes ejecutar cada consulta así:

```python
consultar("""
SELECT transaction_status, COUNT(*) AS cantidad
FROM typed.transactions
GROUP BY transaction_status
ORDER BY cantidad DESC;
""")
```

La conexión es de solo lectura: puedes explorar sin modificar la base ni los CSV.

Usa `typed` para investigar calidad, porque conserva también las filas que posteriormente se excluyeron. Usa `clean` para analizar las filas que pasaron la depuración.

## 1. Tablas y columnas disponibles

```sql
SELECT table_schema, table_name, table_type
FROM information_schema.tables
WHERE table_schema IN ('raw', 'typed', 'clean', 'audit')
ORDER BY table_schema, table_name;
```

Para inspeccionar una tabla:

```sql
DESCRIBE typed.transactions;
```

Vale la pena porque muestra qué datos puedes consultar y cuáles son sus tipos. Por ejemplo, `transaction_date` es una fecha con hora y `amount` es un decimal.

## 2. Muestra de datos

```sql
SELECT
    transaction_id,
    transaction_date,
    transaction_type,
    amount,
    currency,
    channel,
    transaction_status
FROM typed.transactions
LIMIT 20;
```

Vale la pena porque permite comprender los valores antes de agruparlos. `LIMIT` es una muestra rápida, no una muestra aleatoria ni representativa.

## 3. Nulos en campos importantes

```sql
SELECT
    COUNT(*) AS total,
    COUNT(*) FILTER (
        WHERE duration_seconds IS NULL
    ) AS sin_duracion,
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE duration_seconds IS NULL
        ) / NULLIF(COUNT(*), 0),
        2
    ) AS porcentaje_sin_duracion
FROM typed.call_transcripts;
```

Vale la pena porque permite diferenciar un problema menor de uno que afecta una parte importante de la tabla. El EDA encontró 24.029 transcripciones sin duración.

Para inspeccionar esos casos:

```sql
SELECT
    transcript_id,
    interaction_id,
    duration_seconds,
    _source_file,
    _source_row
FROM typed.call_transcripts
WHERE duration_seconds IS NULL
LIMIT 30;
```

`_source_file` y `_source_row` permiten rastrear un registro hasta el CSV original.

## 4. Nulos por canal

```sql
SELECT
    channel,
    COUNT(*) AS transacciones,
    COUNT(*) FILTER (
        WHERE branch_id IS NULL
    ) AS sin_sucursal,
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE branch_id IS NULL
        ) / NULLIF(COUNT(*), 0),
        2
    ) AS porcentaje_sin_sucursal
FROM typed.transactions
GROUP BY channel
ORDER BY transacciones DESC;
```

Vale la pena porque una sucursal ausente puede tener sentido en operaciones digitales. Sirve para decidir qué nulos son errores y cuáles son esperables.

Para textos, un valor con espacios tampoco debe contarse como presente:

```sql
SELECT COUNT(*) AS clientes_sin_email
FROM typed.customers
WHERE NULLIF(TRIM(email), '') IS NULL;
```

## 5. Efecto de la limpieza

```sql
SELECT 'typed' AS capa, COUNT(*) AS filas
FROM typed.call_transcripts

UNION ALL

SELECT 'clean' AS capa, COUNT(*) AS filas
FROM clean.call_transcripts;
```

```sql
SELECT disposition, COUNT(*) AS filas
FROM audit.call_transcripts_rows
GROUP BY disposition
ORDER BY filas DESC;
```

Vale la pena porque muestra qué eliminó la depuración y por qué. `invalid_required` señala campos obligatorios inválidos y `conflicting_key` señala claves con contenido contradictorio.

## 6. Identificadores repetidos

```sql
SELECT
    transaction_id,
    COUNT(*) AS repeticiones
FROM typed.transactions
GROUP BY transaction_id
HAVING COUNT(*) > 1
ORDER BY repeticiones DESC
LIMIT 50;
```

Vale la pena porque una clave repetida puede multiplicar filas al hacer un `JOIN` e inflar métricas. Si no devuelve filas, no encontró identificadores repetidos.

También puedes inspeccionar campos que deberían ser únicos:

```sql
SELECT product_number, COUNT(*) AS repeticiones
FROM typed.products
WHERE product_number IS NOT NULL
GROUP BY product_number
HAVING COUNT(*) > 1
ORDER BY repeticiones DESC;
```

## 7. Cobertura temporal y volumen mensual

```sql
SELECT
    DATE_TRUNC('month', transaction_date)::DATE AS mes,
    COUNT(*) AS transacciones,
    COUNT(DISTINCT customer_id) AS clientes_activos,
    MIN(transaction_date) AS primera_transaccion,
    MAX(transaction_date) AS ultima_transaccion
FROM clean.transactions
GROUP BY 1
ORDER BY 1;
```

Vale la pena porque identifica cobertura temporal, cambios de volumen y meses parcialmente cubiertos. Un mes con menos registros puede estar incompleto.

## 8. Montos y estados de transacciones

```sql
SELECT
    currency,
    transaction_status,
    COUNT(*) AS transacciones,
    MIN(amount) AS minimo,
    ROUND(AVG(amount), 2) AS promedio,
    MEDIAN(amount) AS mediana,
    QUANTILE_CONT(amount, 0.95) AS percentil_95,
    MAX(amount) AS maximo
FROM clean.transactions
GROUP BY currency, transaction_status
ORDER BY currency, transacciones DESC;
```

Vale la pena porque compara operaciones típicas con valores extremos. Si la media es mucho mayor que la mediana, hay montos grandes elevando el promedio.

Separar por moneda evita sumar COP, ARS y USD como si fueran equivalentes.

## 9. Integridad de la relación clientes-sucursales

```sql
SELECT
    COUNT(*) AS clientes,
    COUNT(*) FILTER (
        WHERE c.registration_branch_id IS NULL
    ) AS sin_id_sucursal,
    COUNT(*) FILTER (
        WHERE c.registration_branch_id IS NOT NULL
          AND b.branch_id IS NULL
    ) AS sucursal_inexistente,
    COUNT(*) FILTER (
        WHERE b.branch_id IS NOT NULL
    ) AS sucursal_encontrada
FROM typed.customers c
LEFT JOIN typed.branches b
    ON c.registration_branch_id = b.branch_id;
```

Vale la pena porque diferencia una clave ausente de una clave cuyo registro padre no existe. El EDA encontró problemas fuertes en esta relación.

## 10. Productos de reclamos y cliente correcto

```sql
SELECT
    COUNT(*) AS reclamos_con_producto,
    COUNT(*) FILTER (
        WHERE p.product_id IS NULL
    ) AS producto_inexistente,
    COUNT(*) FILTER (
        WHERE p.product_id IS NOT NULL
          AND c.customer_id IS DISTINCT FROM p.customer_id
    ) AS cliente_no_coincide
FROM typed.complaints c
LEFT JOIN typed.products p
    ON c.affected_product_id = p.product_id
WHERE c.affected_product_id IS NOT NULL;
```

Vale la pena porque un ID existente no garantiza que la relación sea correcta. Esta consulta detecta reclamos asociados a productos de otro cliente.

## 11. Motivos de contacto, resolución y duración

```sql
SELECT
    reason_category,
    COUNT(*) AS contactos,
    COUNT(was_resolved) AS contactos_con_resultado,
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE was_resolved = TRUE
        ) / NULLIF(COUNT(was_resolved), 0),
        2
    ) AS porcentaje_resuelto,
    ROUND(
        AVG(duration_seconds) FILTER (
            WHERE duration_seconds >= 0
        ) / 60.0,
        2
    ) AS duracion_promedio_minutos
FROM clean.call_center_interactions
GROUP BY reason_category
ORDER BY contactos DESC;
```

Vale la pena porque combina demanda, resolución y tiempo de atención para identificar temas que merecen más análisis. El porcentaje usa solo resultados conocidos.

Estos son resultados históricos del dataset sintético; no estiman directamente lo que resolvería un agente automático.

## 12. Diversidad de las transcripciones

```sql
SELECT
    COUNT(*) AS filas,
    COUNT(customer_text) AS textos_no_nulos,
    COUNT(DISTINCT customer_text) AS textos_distintos
FROM clean.call_transcripts;
```

Para revisar las plantillas más repetidas:

```sql
SELECT
    COUNT(*) AS repeticiones
FROM clean.call_transcripts
WHERE NULLIF(TRIM(customer_text), '') IS NOT NULL
GROUP BY customer_text
ORDER BY repeticiones DESC
LIMIT 10;
```

Vale la pena porque muchas transcripciones pueden contener muy pocos textos diferentes. El EDA documenta solo 42 textos distintos, algo importante si se quiere entrenar o evaluar un clasificador.

## 13. Integridad de llaves foráneas de `call_transcripts`

El diccionario de `data/contexto` marca como obligatorias estas tres relaciones:

| Llave en `call_transcripts` | Tabla padre y llave primaria |
|---|---|
| `interaction_id` | `call_center_interactions.interaction_id` |
| `customer_id` | `customers.customer_id` |
| `agent_id` | `service_agents.agent_id` |

Las cuatro consultas están en [call_transcripts_fk_integrity.sql](data_platform/analysis/call_transcripts_fk_integrity.sql). Revisan llaves ausentes y huérfanas, claves primarias ausentes o repetidas, y que el cliente y agente de la transcripción sean los de la interacción. La última consulta devuelve hasta 100 ejemplos de fallas con archivo y fila de origen.

Para ejecutarlas en el warehouse local desde la raíz del proyecto:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import duckdb

sql = Path('data_platform/analysis/call_transcripts_fk_integrity.sql').read_text()
con = duckdb.connect('data/eda/372ff8010bafd0b4d802/warehouse.duckdb', read_only=True)
for numero, consulta in enumerate(sql.split(';'), 1):
    if consulta.strip():
        resultado = con.execute(consulta)
        print(f'Consulta {numero}:', resultado.fetchall())
PY
```

Resultado en el snapshot local: `typed.call_transcripts` tiene 171.321 filas; cada una de las tres llaves está presente y encuentra su padre en las 171.321. No hay claves primarias ausentes o repetidas en las tres tablas padre, ni diferencias de cliente o agente con la interacción. La consulta de ejemplos no devuelve filas. Este conteo incluye las 24.029 transcripciones que `clean` excluye por `duration_seconds` ausente; esa falla es independiente de las llaves foráneas.

## Orden sugerido

Empieza por las consultas 1 a 5 para conocer la estructura y entender los nulos. Luego revisa las relaciones con 9 y 10. Finalmente, pasa al análisis de negocio con 7, 8 y 11.
