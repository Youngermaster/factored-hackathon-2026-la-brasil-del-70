# Continuar el procesamiento local para el MVP

Guía de reanudación de la opción 3: CSV locales → DuckDB/dbt → PostgreSQL. Los datos originales y los
artefactos generados están bajo `data/` y permanecen fuera de Git. La decisión arquitectónica está en
[ADR 0032](docs/adr/0032-bounded-local-gold-seed-for-mvp.md); el resumen de tablas y del MVP está en
[RESUMEN_DATOS_Y_MVP.md](RESUMEN_DATOS_Y_MVP.md). La guía completa de setup, operación y hoja de ruta
para la carga total está en [docs/data/local-postgres-mvp.md](docs/data/local-postgres-mvp.md).

## Punto donde quedó la ejecución

Estado comprobado en este checkout:

| Componente | Estado |
|---|---|
| Fuente local | `data/`, 7.671 CSV reconocidos por la fuente local acotada |
| Ingesta | Completa: 7.671 objetos, 23.471.159 filas aceptadas, 24.029 en cuarentena, 0 fallos |
| Manifiesto | `data/warehouse-local/manifest.duckdb`, último run `succeeded`, código 0 |
| DuckDB/dbt gold | Completo: 315 nodos, 313 PASS, 2 WARN, 0 ERROR; `bank-data test` y `data-report` correctos; los cinco `*_serving.parquet` existen |
| PostgreSQL | Sembrado y reconciliado: revisión `0008`, 16 personas, 200 clientes, 559 productos, 6.119 transacciones, 84 reclamos, 200 perfiles de crédito, 200 identidades, 2 staff, 1 disputa y 1 solicitud de crédito sintéticas |
| Configuración local | `.env` existe y se corrigieron sus líneas opcionales vacías; sus secretos no deben copiarse a este documento ni a Git |

La cuarentena de 24.029 filas corresponde a registros rechazados por contratos de fila; no hubo objetos
completos fallidos ni cambios de esquema que bloquearan el pipeline.

Las dos advertencias de dbt son pruebas `relationships` de nivel `warn`. 149.995 clientes y 831 agentes
tienen un `branch_id` que no existe en `branches.csv`. No bloquean el MVP, pero conviene revisarlas antes de
usar sucursales en la aplicación.

El build se había interrumpido por memoria. Con `BANK_DATA_DUCKDB_MEMORY_LIMIT=8GB` y 8 hilos en una
máquina de 7,7 GB, el sistema mataba `dbt build` al llegar a `stg_transactions`. Terminó con
`export BANK_DATA_DUCKDB_MEMORY_LIMIT=3GB BANK_DATA_DUCKDB_THREADS=2`; usar esos valores en esta máquina
(ver [la guía](docs/data/local-postgres-mvp.md)).

## Reanudar desde este punto

Ejecutar desde la raíz del repositorio. El pipeline es incremental: la ingesta volverá a comprobar los
CSV contra el manifiesto y no debería volver a procesar objetos sin cambios. Después construye y prueba gold.

```bash
make pipeline DATA_SOURCE=local LOCAL_DIR=data
make data-report DATA_SOURCE=local LOCAL_DIR=data
```

Confirmar que existan los cinco Parquet serving antes de cargar PostgreSQL:

```bash
find data/warehouse-local/gold -maxdepth 1 -name '*_serving.parquet' -printf '%f\n' | sort
```

El resultado debe incluir `customers_serving.parquet`, `products_serving.parquet`,
`transactions_serving.parquet`, `complaints_serving.parquet` y `credit_profiles_serving.parquet`.

Luego sembrar y reconciliar los datos de aplicación:

```bash
make up
make seed DATA_SOURCE=local LOCAL_DIR=data SEED_CUSTOMERS=200
make verify-seed DATA_SOURCE=local LOCAL_DIR=data SEED_CUSTOMERS=200
```

`make seed` aplica las migraciones pendientes y carga las 16 personas, dos miembros de staff, 200 clientes
seleccionados determinísticamente, sus productos, transacciones, reclamos y perfiles de crédito, más los
registros sintéticos de demo. `make verify-seed` es de solo lectura y compara la selección gold con
PostgreSQL, incluyendo los digests de identidad y la revisión del esquema. Debe indicar revisión `0008`,
200 clientes y 16 personas. El seed puede restablecer estados de productos al valor del CSV; ejecutarlo
antes de iniciar una demostración que cambie esos estados.

## Reproducir desde cero en otro checkout

1. Colocar la entrega completa en `data/`, conservando su estructura de snapshots y particiones diarias.
   No copiar `data/eda` ni `data/warehouse-local` como fuente.
2. Copiar `.env.example` a `.env`; llenar `POSTGRES_ADMIN_PASSWORD`, `POSTGRES_APP_PASSWORD` y un
   `SESSION_SECRET` estable de al menos 32 bytes. Dejar vacías las opciones no usadas como `NOMBRE=` sin
   comentarios en la misma línea. No compartir ni versionar `.env`.
3. Ejecutar en orden:

   ```bash
   make pipeline DATA_SOURCE=local LOCAL_DIR=data
   make data-report DATA_SOURCE=local LOCAL_DIR=data
   make up
   make seed DATA_SOURCE=local LOCAL_DIR=data SEED_CUSTOMERS=200
   make verify-seed DATA_SOURCE=local LOCAL_DIR=data SEED_CUSTOMERS=200
   ```

Cada fuente usa su warehouse separado. Para `local`, el listado filtra las rutas por las tablas y layouts
contratados antes de calcular hashes, así que PDFs, EDA y warehouses bajo `data/` no se ingieren.

## Evolución a los 150.000 clientes

No basta con cambiar `SEED_CUSTOMERS`: el seed actual reúne sus filas en memoria y escribe en una transacción.
La carga completa necesita lotes o `COPY` con staging, checkpoints y reanudación, conciliación por lote,
pruebas de capacidad y una política para preservar el estado operativo. También debe definir cómo manejar
clientes inactivos o sin teléfono, que no cumplen hoy los criterios de selección e identificación.
