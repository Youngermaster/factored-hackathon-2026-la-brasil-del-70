-- Ejecutar en data/eda/372ff8010bafd0b4d802/warehouse.duckdb.
-- La capa typed conserva las filas que clean descarta por otras reglas de calidad.
-- Las tres referencias son obligatorias según data/contexto/LATAM_Bank_Complete_Data_Dictionary (2).pdf.

-- 1. Cobertura de las tres llaves: ausente incluye NULL, vacío o solo espacios.
-- Los EXISTS evitan multiplicar transcripciones si alguna clave del padre está repetida.
WITH validacion AS (
    SELECT
        t.transcript_id,
        NULLIF(TRIM(t.interaction_id), '') AS interaction_id,
        NULLIF(TRIM(t.customer_id), '') AS customer_id,
        NULLIF(TRIM(t.agent_id), '') AS agent_id,
        EXISTS (
            SELECT 1 FROM typed.call_center_interactions i
            WHERE i.interaction_id = t.interaction_id
        ) AS tiene_interaccion,
        EXISTS (
            SELECT 1 FROM typed.customers c
            WHERE c.customer_id = t.customer_id
        ) AS tiene_cliente,
        EXISTS (
            SELECT 1 FROM typed.service_agents a
            WHERE a.agent_id = t.agent_id
        ) AS tiene_agente
    FROM typed.call_transcripts t
),
claves AS (
    SELECT 'interaction_id' AS llave, interaction_id AS valor, tiene_interaccion AS tiene_padre FROM validacion
    UNION ALL
    SELECT 'customer_id', customer_id, tiene_cliente FROM validacion
    UNION ALL
    SELECT 'agent_id', agent_id, tiene_agente FROM validacion
)
SELECT
    llave,
    COUNT(*) AS total_transcripciones,
    COUNT(*) FILTER (WHERE valor IS NULL) AS llave_ausente,
    COUNT(*) FILTER (WHERE valor IS NOT NULL AND NOT tiene_padre) AS padre_inexistente,
    COUNT(*) FILTER (WHERE valor IS NOT NULL AND tiene_padre) AS padre_encontrado
FROM claves
GROUP BY llave
ORDER BY llave;

-- 2. Las claves primarias de los padres deben estar presentes y ser únicas.
WITH padres AS (
    SELECT 'call_center_interactions' AS tabla, NULLIF(TRIM(interaction_id), '') AS llave
    FROM typed.call_center_interactions
    UNION ALL
    SELECT 'customers', NULLIF(TRIM(customer_id), '') FROM typed.customers
    UNION ALL
    SELECT 'service_agents', NULLIF(TRIM(agent_id), '') FROM typed.service_agents
),
repetidas AS (
    SELECT tabla, llave, COUNT(*) AS apariciones
    FROM padres WHERE llave IS NOT NULL
    GROUP BY tabla, llave HAVING COUNT(*) > 1
),
resumen_repetidas AS (
    SELECT tabla, COUNT(*) AS claves_repetidas, SUM(apariciones - 1) AS filas_excedentes
    FROM repetidas GROUP BY tabla
)
SELECT p.tabla,
       COUNT(*) FILTER (WHERE p.llave IS NULL) AS llave_padre_ausente,
       COALESCE(MAX(r.claves_repetidas), 0) AS claves_repetidas,
       COALESCE(MAX(r.filas_excedentes), 0) AS filas_excedentes
FROM padres p LEFT JOIN resumen_repetidas r ON p.tabla = r.tabla
GROUP BY p.tabla ORDER BY p.tabla;

-- 3. Consistencia: una transcripción debe apuntar al cliente y agente de su interacción.
-- Solo se comparan transcripciones cuyo interaction_id encuentra un padre.
SELECT
    COUNT(*) AS interacciones_encontradas,
    COUNT(*) FILTER (WHERE t.customer_id IS DISTINCT FROM i.customer_id) AS cliente_distinto,
    COUNT(*) FILTER (WHERE t.agent_id IS DISTINCT FROM i.agent_id) AS agente_distinto
FROM typed.call_transcripts t
JOIN typed.call_center_interactions i ON t.interaction_id = i.interaction_id;

-- 4. Ejemplos trazables de fallas. No muestra el texto ni datos personales.
SELECT
    t.transcript_id,
    t.interaction_id,
    t.customer_id,
    t.agent_id,
    t._source_file,
    t._source_row,
    CASE
        WHEN NULLIF(TRIM(t.interaction_id), '') IS NULL THEN 'interaction_id ausente'
        WHEN NOT EXISTS (SELECT 1 FROM typed.call_center_interactions i WHERE i.interaction_id = t.interaction_id)
            THEN 'interaccion inexistente'
        WHEN NULLIF(TRIM(t.customer_id), '') IS NULL THEN 'customer_id ausente'
        WHEN NOT EXISTS (SELECT 1 FROM typed.customers c WHERE c.customer_id = t.customer_id)
            THEN 'cliente inexistente'
        WHEN NULLIF(TRIM(t.agent_id), '') IS NULL THEN 'agent_id ausente'
        WHEN NOT EXISTS (SELECT 1 FROM typed.service_agents a WHERE a.agent_id = t.agent_id)
            THEN 'agente inexistente'
        WHEN t.customer_id IS DISTINCT FROM i.customer_id THEN 'cliente distinto de la interaccion'
        WHEN t.agent_id IS DISTINCT FROM i.agent_id THEN 'agente distinto de la interaccion'
    END AS falla
FROM typed.call_transcripts t
LEFT JOIN typed.call_center_interactions i ON t.interaction_id = i.interaction_id
WHERE falla IS NOT NULL
ORDER BY t._source_file, t._source_row
LIMIT 100;
