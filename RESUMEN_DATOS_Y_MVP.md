# Datos disponibles y propuesta de MVP

Resumen para el equipo, basado en el [diccionario completo](<data/contexto/LATAM_Bank_Complete_Data_Dictionary (2).pdf>), el [resumen del dataset](<data/contexto/LATAM_Bank_Dataset_Summary (1).pdf>), el [reporte de calidad](docs/data/quality-report.md) y la arquitectura existente. Estado del entorno local revisado el 27 de septiembre de 2026.

## Qué datos hay

El dataset del organizador es sintético y relaciona clientes de México, Colombia y Argentina con productos, transacciones y actividad de atención. Cubre del 17 de junio de 2023 al 17 de junio de 2026. El diccionario anuncia aproximadamente 19 millones de filas en 13 tablas; la entrega perfilada en el repositorio contiene **23.495.188 filas**. La diferencia se debe principalmente a que `digital_events` supera la cantidad estimada. Los textos del organizador están en español; los casos en portugués deben prepararse y etiquetarse aparte.

| Grupo | Tabla | Filas observadas | Información principal | Uso para el MVP |
|---|---|---:|---|---|
| Banca | `customers` | 150.000 | Identidad, país, segmento y perfil | Vincular la sesión con un cliente |
| Banca | `products` | 400.000 | Cuentas, tarjetas, créditos, saldo, moneda y estado | Consultar saldos y productos propios |
| Banca | `transactions` | 4.425.008 | Movimientos, pagos, transferencias, importe y estado | Consultar pagos y resumir actividad |
| Atención | `call_center_interactions` | 686.296 | Motivo, canal, duración, resolución y escalamiento | Medir demanda; no es necesario para la primera consulta |
| Atención | `call_transcripts` | 171.321 en origen; 147.292 válidas | Texto de llamadas | Análisis exploratorio, con límites para entrenar intenciones |
| Atención | `satisfaction_surveys` | 212.759 | CSAT, NPS y comentarios | Evaluar resultados históricos |
| Atención | `complaints` | 67.095 | Reclamos, prioridad y estado | Contexto de disputas en una etapa posterior |
| Digital | `digital_events` | 15.620.994 | Navegación y errores de canales digitales | Analítica; fuera del camino inicial |
| Marketing | `marketing_campaigns` | 200 | Campañas y objetivos | Fuera del camino inicial |
| Marketing | `campaign_sends` | 1.746.801 | Envíos y respuestas a campañas | Fuera del camino inicial |
| Referencia | `branches` | 350 | Sucursales | Contexto; no es requisito inicial |
| Referencia | `service_agents` | 1.200 | Agentes de servicio | Contexto de atención y escalamiento |
| Referencia | `daily_exchange_rates` | 13.164 | Tasas diarias de cambio | Conversiones cuando hagan falta |

Las cifras observadas proceden del [reporte de calidad](docs/data/quality-report.md); son distintas de las estimaciones del PDF. Las claves principales y las columnas completas están en la [transcripción del diccionario](docs/organizer/DATA_DICTIONARY.md).

### Relaciones principales

```text
customers (customer_id)
  ├──< products (product_id, customer_id)
  │      └──< transactions (transaction_id, product_id, customer_id)
  ├──< complaints (complaint_id, customer_id)
  ├──< call_center_interactions (interaction_id, customer_id)
  │      ├──< call_transcripts (interaction_id)
  │      └──< satisfaction_surveys (interaction_id)
  ├──< digital_events (customer_id; puede ser nulo)
  └──< campaign_sends (campaign_id) >── marketing_campaigns

branches y service_agents aportan contexto de sucursales y atención.
daily_exchange_rates se une por fecha y par de monedas para conversiones.
```

El diagrama expresa las relaciones previstas, no garantiza que cada referencia sea válida. Casi todas las referencias de `customers.registration_branch_id` son huérfanas. `complaints` no trae un `transaction_id` y sus referencias no nulas a productos apuntan a productos de otros clientes en esta entrega. Los textos de `call_transcripts` son muy repetitivos y sus etiquetas de intención no sirven directamente como verdad de entrenamiento. Véase la [ficha de datos](docs/data/data-card.md).

## Qué usar primero

Para una demostración completa de **consulta de cuenta**, las tres tablas indispensables son `customers`, `products` y `transactions`. Permiten mostrar el saldo de una cuenta, el estado de un pago o transferencia y un resumen de movimientos por periodo. La respuesta debe identificar el producto sin revelar su número completo, limitarse al cliente de la sesión y mostrar la fecha de vigencia del dato. El [flujo de consulta de cuenta](docs/workflows/account-inquiry.md) ya define estas reglas.

`complaints` y el perfil de crédito derivado pueden alimentar después los flujos de disputas y crédito. `call_center_interactions`, encuestas y eventos digitales sirven mejor para justificar prioridades y evaluar la solución que para contestar la primera pregunta de un cliente. Una transacción no indica de forma fiable la dirección de transferencias y ajustes, así que un resumen no debe inventar saldos de apertura o cierre.

## Cómo llegan los datos a la aplicación

```text
CSV del organizador o muestra incluida en git
                  │
                  ▼
       contratos y validación Pandera
                  │
                  ▼
       bronze → dbt/DuckDB silver → gold Parquet
                                           │
                                   seed de clientes demo
                                           ▼
                            PostgreSQL: esquema app
                     datos bancarios acotados + sesiones
                     conversaciones + casos + auditoría
                                           ▲
                                    FastAPI ← React
```

[ADR 0007](docs/adr/0007-dbt-duckdb-and-pandera-for-the-data-platform.md) reserva DuckDB y dbt para preparación y análisis. PostgreSQL sirve un subconjunto acotado a la aplicación y guarda su estado operativo. El seed existente toma las vistas gold `customers_serving`, `products_serving`, `transactions_serving`, `complaints_serving` y `credit_profiles_serving`; no copia las 13 tablas crudas al esquema `app`. La muestra reproducible en git está en [`data_platform/sample/`](data_platform/sample/README.md).

### Qué hacen las migraciones PostgreSQL

Al iniciar por primera vez el contenedor, [`deploy/postgres/init/10-roles.sh`](deploy/postgres/init/10-roles.sh) crea el esquema `app` y dos roles: `bank_owner`, que ejecuta migraciones y seed, y `bank_app`, que usa la API con privilegios limitados. Esto solo ocurre cuando el volumen de PostgreSQL está vacío. Después, Alembic aplica las revisiones pendientes; su versión se registra dentro del esquema `app`. `make db-upgrade` ejecuta ese proceso, y `make seed` también lo ejecuta antes de cargar filas. Las migraciones crean estructura y reglas: **no descargan CSV ni cargan por sí solas los clientes del organizador**.

| Revisión | Qué crea o cambia | Relación con el MVP |
|---|---|---|
| [`0001`](services/api/src/bank_agent/adapters/persistence/postgres/migrations/versions/0001_context_and_directory.py) | Clientes reducidos a los campos necesarios, personal demo y directorio de identidad con claves de búsqueda derivadas | Identificar al cliente sin usar el CSV crudo como sesión |
| [`0002`](services/api/src/bank_agent/adapters/persistence/postgres/migrations/versions/0002_accounts_and_cards.py) | Productos, transacciones, historial de reclamos y perfiles de crédito, con índices y claves de pertenencia | Consultas de saldo, pagos y movimientos; contexto para otros workflows |
| [`0003`](services/api/src/bank_agent/adapters/persistence/postgres/migrations/versions/0003_disputes_and_credit.py) | Casos de disputa, solicitudes de crédito y claves de idempotencia para bloqueo de tarjeta | Persistir acciones verificables y evitar duplicados en reintentos |
| [`0004`](services/api/src/bank_agent/adapters/persistence/postgres/migrations/versions/0004_identity_and_sessions.py) | Sesiones, desafíos de código de un solo uso y eventos de confianza | Asociar cada solicitud HTTP futura con una identidad verificada |
| [`0005`](services/api/src/bank_agent/adapters/persistence/postgres/migrations/versions/0005_conversations_and_audit.py) | Conversaciones, turnos, registros de ejecución, handoffs y eventos de auditoría | Conservar contexto y evidencia de cada respuesta o escalamiento |
| [`0006`](services/api/src/bank_agent/adapters/persistence/postgres/migrations/versions/0006_row_level_security.py) | Seguridad por fila obligatoria en todas las tablas `app`, basada en el rol y cliente de la transacción | Limitar las filas visibles a las del cliente autenticado |
| [`0007`](services/api/src/bank_agent/adapters/persistence/postgres/migrations/versions/0007_grants_and_evaluation.py) | Permisos mínimos, protección de tablas de solo anexado y esquema `eval` separado | Restringir escrituras y conservar registros evaluables |
| [`0008`](services/api/src/bank_agent/adapters/persistence/postgres/migrations/versions/0008_audit_replay_check.py) | Consulta acotada del resumen criptográfico de un evento de auditoría | Reconocer un reintento idéntico sin revelar el evento completo |

La API abre cada unidad de trabajo PostgreSQL con `app.role` y `app.customer_id` dentro de la transacción. Las políticas de la revisión `0006` usan ese contexto; sin él, no autorizan filas. Además, el código de repositorios aplica sus propios filtros por cliente. Véanse la [conexión PostgreSQL](services/api/src/bank_agent/adapters/persistence/postgres/database.py) y [ADR 0009](docs/adr/0009-row-level-security-as-defense-in-depth.md).

### Relación exacta entre DuckDB y PostgreSQL

```text
DuckDB/dbt (preparación, sin sesión de usuario)
  customers_serving ────────────────> app.customers + app.identity_directory
  products_serving ─────────────────> app.products
  transactions_serving ─────────────> app.transactions
  complaints_serving ───────────────> app.historical_complaints
  credit_profiles_serving ──────────> app.credit_profiles
                              seed: solo clientes/personas seleccionados

PostgreSQL (servicio, con contexto de usuario)
  app.sessions + app.conversations + app.turns
  app.dispute_cases + app.credit_applications + app.handoffs
  app.execution_records + app.audit_events
```

El [constructor del seed](data_platform/src/bank_data/seed/bundle.py) lee gold por los `customer_id` seleccionados, convierte las filas a objetos del dominio y los carga con el [cargador PostgreSQL](services/api/src/bank_agent/adapters/persistence/postgres/seed.py). Los números de documento y teléfonos se transforman en claves de búsqueda derivadas; no se almacenan como valores crudos en `app.identity_directory`. El seed incluye dos registros sintéticos de demostración, un caso de disputa y una solicitud de crédito, porque esos casos no vienen en el dataset. Al atender solicitudes, la API usa los repositorios PostgreSQL cuando está configurada la conexión; DuckDB no es el almacén de sesiones o conversaciones.

### Estado de PostgreSQL en este checkout

- [`docker-compose.yml`](docker-compose.yml) define PostgreSQL 16 y un volumen persistente. Existen ocho migraciones Alembic que crean, entre otras, `app.customers`, `app.products`, `app.transactions`, `app.sessions`, `app.conversations`, `app.turns`, `app.handoffs` y `app.execution_records`, con controles de acceso por fila.
- [`make seed`](Makefile) migra y carga personas y registros demo de forma idempotente desde gold. El seed para las personas publicadas fue diseñado sobre la entrega completa; la muestra pequeña podría no satisfacer todos sus criterios.
- En la revisión local no había `.env`, contenedor PostgreSQL ni volumen Docker con el nombre del proyecto. Hay CSV locales bajo `data/`, pero no un warehouse gold construido. Por ello, **la estructura y el cargador están implementados; no hay una base local activa y poblada que se haya podido verificar**.
- La API tiene adaptadores PostgreSQL y lógica de los cuatro workflows, pero sus rutas HTTP actuales son solo las de salud. Falta conectar autenticación y conversación a la interfaz para una demo de cliente.

## Decisión de datos para el MVP

**Estado:** [ADR 0032](docs/adr/0032-bounded-local-gold-seed-for-mvp.md) aceptado. La fuente de la demo son los CSV completos ya presentes en `data/`; PostgreSQL recibe un subconjunto reproducible de 200 clientes, incluidas las 16 personas. La [guía de carga](docs/data/local-postgres-mvp.md) contiene los comandos y las verificaciones.

**Contexto.** Hay 13 tablas y millones de filas, una sola foto histórica y cuatro workflows ya definidos en el núcleo. La demo necesita un resultado verificable de extremo a extremo con datos del cliente autenticado.

**Opciones.** (1) Cargar las 13 tablas crudas en PostgreSQL; (2) consultar gold Parquet directamente en cada solicitud; (3) transformar en DuckDB y sembrar en PostgreSQL solo los registros de servicio y las personas demo.

**Decisión.** Elegir la opción 3, que sigue la arquitectura ya implementada. La migración de datos prepara `account_inquiry`, `card_support`, `dispute` y `credit` en PostgreSQL; la exposición HTTP y React queda fuera de esta carga. [ADR 0025](docs/adr/0025-tuesday-account-inquiry-mvp-and-observability.md) sigue rigiendo su propio hito de interfaz.

**Consecuencias.** La demo es reproducible y las consultas operativas quedan acotadas al cliente de la sesión. Debe declararse siempre la fecha de corte `2026-06-17`; el seed de las personas completas requiere gold de la entrega completa. Repetir el seed antes de una demo puede restablecer el estado de productos desde la fuente. La carga de 150.000 clientes requiere un proceso por lotes distinto; no basta con aumentar `SEED_CUSTOMERS`.

## Primer paso concreto

Ejecutar desde la raíz, con `data/` presente:

```bash
make pipeline DATA_SOURCE=local LOCAL_DIR=data
make data-report DATA_SOURCE=local LOCAL_DIR=data
```

Esto valida la ruta `CSV local → bronze → silver → gold` sin credenciales S3. Después, configurar `.env` según [`.env.example`](.env.example), iniciar PostgreSQL con `make up`, cargar `make seed DATA_SOURCE=local LOCAL_DIR=data SEED_CUSTOMERS=200` y reconciliar con `make verify-seed DATA_SOURCE=local LOCAL_DIR=data SEED_CUSTOMERS=200`. El siguiente trabajo de producto, separado de esta migración, es exponer los workflows por HTTP y conectarlos a React.
