# Datos iniciales del MVP en PostgreSQL

Guía completa para preparar, cargar y verificar los datos del MVP, y hoja de ruta para cargar después la
entrega completa. Implementa la [decisión 0032](../adr/0032-bounded-local-gold-seed-for-mvp.md).

## 1. Qué se construye

La entrega del organizador (13 tablas en CSV) se valida y transforma con DuckDB/dbt en cinco tablas gold.
PostgreSQL recibe solo un subconjunto determinista de 200 clientes con todo lo que necesitan los cuatro
workflows (consulta de cuentas, tarjetas, disputas y crédito).

```text
CSV (data/ o bucket S3) → contratos/Pandera → bronze → dbt/DuckDB silver → gold *_serving.parquet
                                                                               │
                                                  bank-data seed (200 clientes, determinista)
                                                                               │
                                                                               ▼
                                             PostgreSQL esquema app (Alembic 0008 + RLS + estado)
```

| Capa | Dónde vive | Rol |
|---|---|---|
| Fuente | `data/*.csv` y particiones diarias, o el bucket S3 | Entrega original, fuera de git |
| Bronze, silver, gold | `data/warehouse-local/` (fuente `local`) o `data/warehouse/` (fuente `s3`) | Preparación y analítica |
| Aplicación | PostgreSQL del `docker compose` | Lecturas por cliente, sesiones, casos, auditoría |

Las otras ocho tablas de la entrega (interacciones de call center, transcripciones, campañas, eventos
digitales, encuestas, sucursales, agentes y tipos de cambio) se quedan en DuckDB. Ningún workflow del MVP
las lee desde PostgreSQL.

## 2. Requisitos

- `uv`, Docker con Compose, y `make setup` ejecutado una vez (instala dependencias y hooks).
- Disco: unos 10 GB libres para la fuente local. Medido en esta entrega: 5,1 GB de CSV, 5,1 GB de copia raw,
  1 GB de bronze, 2,3 GB de `warehouse.duckdb` y 231 MB de gold.
- Memoria: el `dbt build` completo es el paso más exigente. Ajustar DuckDB a la RAM disponible (sección 4).

## 3. Obtener la fuente

Hay dos caminos; cada uno usa su propio warehouse y no se mezclan.

### Opción A: CSV locales (la usada en este checkout)

Copiar la entrega completa a `data/`, conservando su estructura: tablas planas (`customers.csv`,
`products.csv`, ...) y carpetas por tabla con snapshots y particiones diarias (`transactions/`,
`complaints/`, ...). No copiar `data/eda`, `data/contexto` ni `data/warehouse-local` como fuente; el
descubrimiento local los ignora igualmente, porque filtra por las tablas y layouts contratados antes de
calcular hashes.

### Opción B: bucket S3 del organizador

El bucket es de solo lectura y sus datos de acceso vienen en el PDF del organizador. Escribirlos solo en
`.env`, nunca en documentos, issues, commits ni prompts:

| Variable | Contenido |
|---|---|
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Credenciales de solo lectura del PDF |
| `AWS_DEFAULT_REGION` | `us-east-2` |
| `DATA_BUCKET` | Nombre del bucket del PDF |
| `DATA_PREFIX` | `data/` |

Después, `make data-download` hace una descarga incremental guiada por el manifiesto hacia `data/warehouse/`.
En todos los comandos siguientes, usar `DATA_SOURCE=s3` en lugar de `DATA_SOURCE=local LOCAL_DIR=data`.

## 4. Configurar `.env`

```bash
cp .env.example .env
```

Llenar como mínimo:

- `POSTGRES_ADMIN_PASSWORD` y `POSTGRES_APP_PASSWORD`: roles propietario y aplicación.
- `SESSION_SECRET`: al menos 32 bytes aleatorios y **estable**. Determina los digests de identidad
  (documento y últimos cuatro dígitos del teléfono); si se rota, hay que volver a ejecutar el seed.
  Se puede generar con `openssl rand -base64 64`.

Dejar vacías las opciones que no se usen, como `NOMBRE=`, sin comentarios en la misma línea.

Recursos de DuckDB según la RAM de la máquina:

| RAM total | `BANK_DATA_DUCKDB_MEMORY_LIMIT` | `BANK_DATA_DUCKDB_THREADS` |
|---|---|---|
| 8 GB | `3GB` | `2` |
| 16 GB | `8GB` | `4` |
| 32 GB o más | `8GB` o más | `8` |

Los valores de `.env.example` (`8GB`, 8 hilos) necesitan al menos 16 GB. En una máquina de 7,7 GB, el
sistema mata `dbt build` al construir `stg_transactions`. No aparece ningún error, y `transactions_serving.parquet`
y `complaints_serving.parquet` no se escriben. Se pueden fijar en `.env` o solo para una corrida:

```bash
export BANK_DATA_DUCKDB_MEMORY_LIMIT=3GB BANK_DATA_DUCKDB_THREADS=2
```

Comprobar qué variables están definidas sin mostrar valores:

```bash
make env-check
```

## 5. Construir gold

```bash
make pipeline DATA_SOURCE=local LOCAL_DIR=data
make data-report DATA_SOURCE=local LOCAL_DIR=data
```

`make pipeline` ejecuta tres pasos:

1. `ingest`: lista 7.671 CSV, valida contratos de fila y escribe bronze o cuarentena. Es incremental: si se
   repite sin cambios, informa `unchanged=7671 loaded=0`. En la primera corrida aceptó 23.471.159 filas y
   envió 24.029 a cuarentena, con 0 objetos fallidos.
2. `build`: `dbt build` sobre 315 nodos (modelos y pruebas). Con 3 GB y 2 hilos tardó unos 9 minutos y usó
   menos de 5 GB de RAM. Resultado esperado: `PASS=313 WARN=2 ERROR=0`.
3. `test`: vuelve a ejecutar las pruebas dbt y la frescura de las fuentes; debe terminar con
   `tests and freshness passed`.

Las dos advertencias esperadas son pruebas `relationships` de nivel `warn`. 149.995 clientes y 831 agentes
tienen un `branch_id` que no existe en `branches.csv`. No bloquean el MVP, pero hacen que las sucursales
casi nunca se puedan enlazar.

Confirmar los cinco Parquet serving:

```bash
find data/warehouse-local/gold -maxdepth 1 -name '*_serving.parquet' -printf '%f\n' | sort
```

Deben aparecer `complaints`, `credit_profiles`, `customers`, `products` y `transactions`. Revisar
`data/warehouse-local/quality-report.md` para ver filas aceptadas, cuarentena y frescura.

## 6. Sembrar y verificar PostgreSQL

```bash
make up
make seed DATA_SOURCE=local LOCAL_DIR=data SEED_CUSTOMERS=200
make verify-seed DATA_SOURCE=local LOCAL_DIR=data SEED_CUSTOMERS=200
```

`make seed` aplica las migraciones Alembic pendientes y después hace upserts en una sola transacción. La
selección de clientes (`data_platform/src/bank_data/seed/selection.py`) es determinista:

1. Personas: cada una de las 16 personas de `data_platform/seed/personas.yaml` toma el primer cliente que
   cumple su criterio (`criteria.py`), p. ej. tarjeta bloqueada, puntaje límite o reclamante recurrente.
2. Cobertura: un mínimo de clientes por país (MX, CO, AR) y al menos uno por segmento.
3. Relleno: hasta `SEED_CUSTOMERS`, en orden de `md5(semilla || customer_id)`.

Solo son candidatos los clientes activos con un teléfono de al menos cuatro dígitos, porque la
identificación usa esos dígitos. A la base nunca llegan documentos ni teléfonos en claro, solo digests
con clave.

`make verify-seed` es de solo lectura. Rehace la misma selección y compara con PostgreSQL los IDs de cada
tabla, los digests de identidad, el personal y los registros sintéticos. Resultado verificado en esta
entrega:

| Tabla `app.*` | Filas |
|---|---|
| `customers` | 200 |
| `identity_directory` | 200 |
| `products` | 559 |
| `transactions` | 6.119 |
| `historical_complaints` | 84 |
| `credit_profiles` | 200 |
| `staff_members` | 2 |
| `dispute_cases` (sintético) | 1 |
| `credit_applications` (sintético) | 1 |

Debe informar `verified revision=0008 personas=16`. Los conteos relacionados salen de gold; cambian si
cambia la entrega o la lista de personas.

## 7. Validación técnica

```bash
uv run --frozen pytest data_platform/tests/unit/test_sources.py data_platform/tests/unit/test_seed_verify.py -q
uv run --frozen pytest data_platform/tests/integration/test_seed.py -q
uv run --frozen pytest services/api/tests/integration/test_row_level_security.py -q
```

Estas 43 pruebas pasan sobre este checkout. Las de integración requieren Docker. La validación funcional
sigue con los escenarios de los cuatro workflows en `services/api/tests/integration/workflows/`, usando el
backend PostgreSQL.

## 8. Operación y problemas frecuentes

| Situación | Qué hacer |
|---|---|
| El build termina sin error pero faltan Parquet | Falta memoria. Bajar límite e hilos (sección 4) y repetir `make pipeline`; la ingesta no reprocesa nada |
| Queda `warehouse.duckdb.tmp` o `.wal` | Resto de un build interrumpido; DuckDB lo recupera en la siguiente corrida. No borrar a mano |
| Cambiaron los CSV | Repetir `make pipeline`, revisar el reporte y después `seed` + `verify-seed` |
| Falla una prueba dbt o la frescura | No sembrar. Revisar el manifiesto, la cuarentena y el reporte |
| `verify-seed` falla | No usar esa base para la demo; volver a sembrar y verificar |
| Se rotó `SESSION_SECRET` | Volver a sembrar: los digests de identidad dependen del secreto |
| Una demo cambió el estado de una tarjeta | `make seed` restablece el estado de los productos al de gold. Hacerlo antes de la demo, no durante |

El seed no limpia las tablas operativas (sesiones, conversaciones, turnos, auditoría).

## 9. Hoja de ruta: cargar la entrega completa

El seed actual no sirve para cargar todo con solo subir `SEED_CUSTOMERS`. Lee todas las filas elegidas a
memoria como objetos de dominio, filtra con `IN (unnest($ids))` y escribe todo en una sola transacción con
`executemany`. Además, excluye a los clientes que no son activos o no tienen teléfono. Tamaño real de gold
en esta entrega:

| Tabla gold | Filas totales | En el MVP |
|---|---|---|
| `customers_serving` | 150.000 | 200 |
| `products_serving` | 400.000 | 559 |
| `transactions_serving` | 4.425.008 | 6.119 |
| `complaints_serving` | 67.095 | 84 |
| `credit_profiles_serving` | 150.000 | 200 |

De los 150.000 clientes, 127.700 están activos, 14.914 inactivos, 4.407 suspendidos y 2.979 cerrados. Unos
6.700 no tienen teléfono utilizable. Las transacciones van del 2023-06-17 al 2026-06-18. Si se extrapola el
tamaño actual (unos 600 bytes por transacción con índices), `app.transactions` rondaría los 2,6 GB. Es una
estimación que hay que medir.

Propuesta por fases. Cada una debe cerrarse con un ADR o PR propio.

### Fase 0: decisiones previas

- Política de clientes no elegibles. Propuesta: cargar los 150.000 en `app.customers` con su estado real y
  crear `identity_directory` solo para quienes tengan documento y teléfono válidos. Los workflows ya deben
  rechazar clientes no activos, y hay que probarlo.
- Preservar el estado operativo. Definir qué columnas son de la fuente y cuáles puede cambiar la aplicación
  (p. ej. `product_status` al bloquear una tarjeta). Propuesta: guardar un hash de la fila de origen y
  actualizar solo si la fila de la base sigue igual a la última versión sembrada.
- Alcance. Confirmar que las ocho tablas restantes siguen en DuckDB o identificar qué workflow las necesita.
- Recalcular los registros sintéticos de demo (disputa y solicitud) solo para las personas, no para toda la
  base.

### Fase 1: cargador por lotes con staging y COPY

- Comando nuevo, p. ej. `bank-data load-full`, separado del seed del MVP, que se sigue usando para las demos.
- Particionar por clientes en lotes (p. ej. 5.000 `customer_id` en orden estable) y leer cada tabla gold
  del lote desde DuckDB en Arrow o CSV, sin crear objetos de dominio por fila.
- Por lote: `COPY` a tablas de staging `UNLOGGED`, luego `INSERT ... SELECT ... ON CONFLICT DO UPDATE` hacia
  `app.*` aplicando la regla de la fase 0, todo en una transacción por lote.
- Respetar el orden de claves foráneas: clientes, identidad, productos, transacciones, reclamos y perfiles.
- Mantener las mismas conversiones de tipos que usan hoy los mappers (`product_to_row`, `transaction_to_row`, ...),
  con pruebas que comparen ambos caminos sobre la muestra.

### Fase 2: checkpoints, reanudación y conciliación

- Una tabla de control (p. ej. `app.load_batches`) con corrida, número de lote, rango de clientes, hash de
  las entradas gold, conteos por tabla, estado y tiempos. Una migración Alembic nueva la crea.
- Al reanudar, saltar los lotes con estado `done` y el mismo hash. Si el hash cambió, recargar ese lote.
- Conciliación por lote: conteos y un checksum (p. ej. `md5(string_agg(id, ',' ORDER BY id))`) en DuckDB y
  en PostgreSQL. Extender `verify-seed` con un modo completo que agregue estos resultados y compare una
  muestra de filas columna por columna.

### Fase 3: capacidad y rendimiento

- Revisar índices para las consultas reales: transacciones por `customer_id` y `transaction_at`, productos
  por cliente. Evaluar particionar `app.transactions` por mes.
- Para la carga inicial: crear índices secundarios después del `COPY`, ajustar `maintenance_work_mem` y
  `max_wal_size`, y ejecutar `ANALYZE` al final.
- Medir con la base completa las latencias p95 de los endpoints de los cuatro workflows con RLS activo, el
  tamaño en disco y la duración de la carga.
- Dimensionar el volumen de Docker o la instancia administrada con margen para WAL, índices y crecimiento.

### Fase 4: actualización incremental

- La ingesta y los modelos incrementales de dbt ya procesan solo los CSV nuevos o cambiados. El cargador
  debería cargar solo los lotes afectados, usando una marca de agua (fecha de partición o `_ingested_at`)
  para transacciones y reclamos.
- Programar la corrida como job (cron o el orquestador que se elija) con alertas si fallan la conciliación
  o las pruebas dbt.

### Fase 5: entorno compartido o producción

- PostgreSQL administrado con backups y recuperación a un punto en el tiempo, secretos en un gestor y no en
  `.env`, y el rol de carga separado del rol de la aplicación.
- Probar primero en un entorno de staging con los datos completos antes de tocar la base que usa la demo.

### Criterios de aceptación de la carga completa

- Los conteos de `app.*` coinciden con gold según la política de la fase 0 y todos los lotes están en `done`.
- Una corrida repetida sin cambios en la fuente no modifica filas.
- El estado operativo modificado por la aplicación sobrevive a una recarga.
- Las pruebas de RLS y los escenarios de los cuatro workflows pasan sobre la base completa.
- Una interrupción a mitad de la carga se reanuda sin duplicar datos ni empezar de cero.
