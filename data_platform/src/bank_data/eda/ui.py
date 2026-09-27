"""Read-only EDA viewer and sanitized exploration laboratory. Launch with make eda-ui."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from bank_data.eda.core import PHASES, read_json
from bank_data.eda.explorer import (
    EXPECTED_ROWS,
    graph_dot,
    relationship_alerts,
    relationship_rows,
    sample_csv,
    sample_rows,
    workflow_assessments,
)

TEXT = {
    "title": ("Exploración del dataset bancario", "Banking dataset exploration"),
    "subtitle": ("Evidencia, calidad y decisiones por fase", "Evidence, quality and decisions by phase"),
    "language": ("Idioma / Language", "Idioma / Language"),
    "run": ("Ejecución", "Run"),
    "refresh": ("Actualizar resultados", "Refresh results"),
    "empty": ("Ejecuta make eda para generar el primer inventario.", "Run make eda to generate the first inventory."),
    "inventory": ("01 · Inventario", "01 · Inventory"),
    "profile": ("02 · Calidad", "02 · Quality"),
    "curate": ("03 · Depuración y relaciones", "03 · Curation and relationships"),
    "analyze": ("04 · Demanda y texto", "04 · Demand and text"),
    "report": ("05 · Decisiones e informe", "05 · Decisions and report"),
    "pending": (
        "Esta fase aún no ha terminado. Los resultados anteriores siguen disponibles.",
        "This phase has not completed. Previous results remain available.",
    ),
    "files": ("Archivos CSV", "CSV files"),
    "tables": ("Tablas presentes", "Tables present"),
    "size": ("Tamaño de entrada (GB)", "Input size (GB)"),
    "table": ("Tabla", "Table"),
    "all": ("Todas", "All"),
    "remote": (
        "Cobertura local; no se verificó el inventario remoto. Datos sintéticos.",
        "Local coverage; remote inventory was not verified. Synthetic data.",
    ),
    "columns": ("Completitud y tipos", "Completeness and types"),
    "checks": ("Reglas de coherencia", "Consistency rules"),
    "categories": ("Categorías observadas", "Observed categories"),
    "errors": ("Archivos rechazados", "Rejected files"),
    "conservation": ("Destino de cada registro", "Disposition of every record"),
    "joins": ("Cobertura y multiplicación de joins", "Join coverage and fanout"),
    "identity": ("Consistencia de cliente y agente", "Customer and agent consistency"),
    "raw": ("Original tipado", "Typed original"),
    "clean": ("Depurado", "Curated"),
    "layer": ("Capa", "Layer"),
    "country": ("País", "Country"),
    "channel": ("Canal", "Channel"),
    "segment": ("Segmento", "Segment"),
    "month": ("Mes", "Month"),
    "contacts": ("Contactos", "Contacts"),
    "resolved": ("Resolución registrada", "Recorded resolution"),
    "escalated": ("Escalamiento registrado", "Recorded escalation"),
    "denominator": ("Respuestas conocidas: {n}", "Known responses: {n}"),
    "reasons": ("Volumen por motivo", "Volume by reason"),
    "monthly": ("Evolución mensual", "Monthly trend"),
    "outcomes": ("Reclamos, encuestas y monedas", "Complaints, surveys and currencies"),
    "text": ("Diversidad textual y evaluación", "Text diversity and evaluation"),
    "text_note": (
        "Este diagnóstico de texto cubre toda la ejecución, independientemente de los filtros de demanda.",
        "This text diagnostic covers the entire run, independently of demand filters.",
    ),
    "historical": (
        "Las banderas históricas no miden resolución automatizada segura. Los promedios usan solo valores válidos.",
        "Historical flags do not measure safe automated resolution. Averages use valid values only.",
    ),
    "workflow": ("Comparación de workflows", "Workflow comparison"),
    "unknown": (
        "No hay evidencia suficiente para elegir un ganador por volumen. Revisar etiquetas y relaciones.",
        "Volume alone does not support a winner. Review labels and relationships.",
    ),
    "download": ("Descargar informe agregado", "Download aggregate report"),
    "missing_data": ("No hay resultados para esta selección.", "No results for this selection."),
    "status": ("Estado de las fases", "Phase status"),
    "details": ("Detalle agregado", "Aggregate detail"),
    "not_available": ("Sin dato", "Not available"),
    "phase_inventory": (
        "Qué hay en la descarga local: archivos, tamaño, tablas, variantes de esquema y particiones. "
        "No evalúa la calidad todavía.",
        "What is in the local download: files, size, tables, schema variants and partitions. "
        "It does not assess quality yet.",
    ),
    "phase_profile": (
        "Qué valores faltan o no cumplen el tipo o las reglas del diccionario. Aquí los datos se miden; "
        "no se eliminan.",
        "Which values are missing or fail the dictionary's types or rules. Data is measured here; it is not removed.",
    ),
    "phase_curate": (
        "Cómo termina cada fila: conservada, duplicada exacta, inválida o en conflicto; "
        "además mide relaciones entre tablas.",
        "Where each row ends up: retained, exact duplicate, invalid or conflicting; "
        "it also measures relationships between tables.",
    ),
    "phase_analyze": (
        "Demanda agregada, resultados históricos y límites del texto para evaluar casos de uso. "
        "Los filtros solo cambian la demanda.",
        "Aggregate demand, historical outcomes and text limits for evaluating use cases. Filters change demand only.",
    ),
    "phase_report": (
        "Comparación de flujos de trabajo y reporte compartible. No asigna un ganador automático porque "
        "faltan etiquetas y relaciones verificadas.",
        "Workflow comparison and shareable report. It does not select an automatic winner because "
        "verified labels and relationships are missing.",
    ),
    "text_summary": ("Resumen de textos", "Text summary"),
    "text_labels": ("Etiquetas vinculadas", "Linked labels"),
    "text_contradictions": ("Contradicciones entre textos y etiquetas", "Text and label contradictions"),
    "text_temporal_probe": ("Riesgo de fuga temporal", "Temporal leakage probe"),
    "text_review_sample": ("Muestra para revisión manual", "Manual-review sample"),
    "process": ("Proceso EDA", "EDA process"),
    "laboratory": ("Laboratorio", "Laboratory"),
    "explore": ("Explorar tablas", "Explore tables"),
    "relations": ("Mapa de relaciones", "Relationship map"),
    "decide": ("Decidir caso de uso", "Choose a use case"),
    "lab_pending": (
        "El laboratorio requiere que las fases de depuración y análisis estén completas.",
        "The laboratory requires completed curation and analysis phases.",
    ),
    "explore_help": (
        "Compara el contrato, la calidad y una muestra local sanitizada. Los campos personales y el texto libre "
        "se omiten; los identificadores aparecen como referencias hash.",
        "Compare the contract, quality and a sanitized local sample. Personal and free-text fields are omitted; "
        "identifiers appear as hashed references.",
    ),
    "rows": ("Filas", "Rows"),
    "fields": ("Columnas", "Columns"),
    "missing_required": ("Faltantes obligatorios", "Required missing"),
    "duplicates": ("Duplicados colapsados", "Collapsed duplicates"),
    "conflicts": ("Conflictos de clave", "Key conflicts"),
    "column_profile": ("Perfil de columnas", "Column profile"),
    "missingness": ("Valores faltantes", "Missing values"),
    "distribution": ("Distribución categórica", "Category distribution"),
    "disposition": ("Destino de filas", "Row disposition"),
    "volume_comparison": ("Volumen esperado frente al observado", "Expected versus observed volume"),
    "schema_drift": ("Desviaciones del diccionario", "Dictionary drift"),
    "sample": ("Muestra sanitizada", "Sanitized sample"),
    "sample_size": ("Tamaño de muestra", "Sample size"),
    "sample_unavailable": (
        "No se encontró el warehouse local; los agregados siguen disponibles, pero no la muestra.",
        "The local warehouse was not found; aggregates remain available, but the sample does not.",
    ),
    "download_sample": ("Descargar muestra sanitizada", "Download sanitized sample"),
    "relation_help": (
        "Verde: 100% y coherencia semántica; amarillo: 95-99.99%; rojo: menos de 95% o identidad "
        "inconsistente; gris: sin claves observables. Línea continua: clave obligatoria; "
        "discontinua: clave opcional.",
        "Green: 100% and semantic consistency; yellow: 95-99.99%; red: below 95% or inconsistent identity; "
        "gray: no observable keys. Solid line: required key; dashed: optional key.",
    ),
    "relation": ("Relación", "Relationship"),
    "alerts": ("Hallazgos críticos", "Critical findings"),
    "decision_help": (
        "Cada semáforo conserva su evidencia. No se suman puntajes porque las dimensiones no son intercambiables.",
        "Each traffic light retains its evidence. Scores are not added because the dimensions are not interchangeable.",
    ),
    "project_choice": (
        "El steering vigente prioriza la atención de disputas. Estos semáforos comparan la viabilidad de los datos; "
        "no cambian por sí solos la elección del proyecto.",
        "The current steering prioritizes dispute handling. These traffic lights compare data feasibility; "
        "they do not change the project choice on their own.",
    ),
    "demand_outcomes": ("Demanda y resultados históricos", "Demand and historical outcomes"),
    "decision_matrix": ("Semáforos por caso de uso", "Use-case traffic lights"),
    "operational_signals": ("Señales operativas", "Operational signals"),
    "column_name": ("Columna", "Column"),
    "current_choice": ("Selección vigente", "Current project choice"),
    "workflow_accounts_payments": ("Consultas de cuentas y pagos", "Account and payment inquiries"),
    "workflow_card_support": ("Soporte de tarjetas", "Card support"),
    "workflow_technical_support": ("Soporte técnico", "Technical support"),
    "workflow_product_information": ("Información de productos", "Product information"),
    "workflow_disputes": ("Atención de disputas", "Dispute handling"),
    "dimension_data_availability": ("Disponibilidad de datos", "Data availability"),
    "dimension_join_integrity": ("Integridad de relaciones", "Join integrity"),
    "dimension_demand_evidence": ("Evidencia de demanda", "Demand evidence"),
    "dimension_evaluation_readiness": ("Preparación para evaluación", "Evaluation readiness"),
    "dimension_policy_safety": ("Seguridad de política", "Policy safety"),
    "status_green": ("Verde", "Green"),
    "status_yellow": ("Amarillo", "Yellow"),
    "status_red": ("Rojo", "Red"),
    "status_gray": ("Gris", "Gray"),
    "alert_low_coverage": ("Cobertura de relación muy baja", "Very low relationship coverage"),
    "alert_no_origin_ids": (
        "Los reclamos no tienen IDs de interacción de origen",
        "Complaints have no origin interaction IDs",
    ),
    "alert_different_customer_owner": (
        "El producto reclamado pertenece a otro cliente",
        "The complained-about product belongs to a different customer",
    ),
    "warehouse_readonly": (
        "La muestra se consulta en modo de solo lectura y nunca incluye el archivo de revisión privada.",
        "The sample is queried in read-only mode and never includes the private review file.",
    ),
}


def t(key: str) -> str:
    return TEXT[key][0 if st.session_state.get("language", "Español") == "Español" else 1]


@st.cache_data(show_spinner=False)
def artifact(path: str, modified_ns: int) -> Any:
    del modified_ns  # Included in the cache key to invalidate completed phase updates.
    return read_json(Path(path))


def load(run: Path, name: str) -> Any:
    path = run / name
    return artifact(str(path), path.stat().st_mtime_ns)


@st.cache_data(show_spinner=False)
def sanitized_sample(path: str, modified_ns: int, table: str, layer: str, limit: int) -> list[dict[str, Any]]:
    del modified_ns
    return sample_rows(Path(path), table, layer, limit)


def display_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Make aggregate tables safe and readable for Streamlit's Arrow conversion."""
    columns = list(dict.fromkeys(column for row in rows for column in row))
    normalized = [
        {
            column: (
                t("not_available")
                if (value := row.get(column)) is None
                else json.dumps(value, ensure_ascii=False, sort_keys=True)
                if isinstance(value, (dict, list))
                else value
            )
            for column in columns
        }
        for row in rows
    ]
    types_by_column: dict[str, set[type[Any]]] = {}
    for row in normalized:
        for column, value in row.items():
            types_by_column.setdefault(column, set()).add(type(value))

    mixed_columns = {column for column, kinds in types_by_column.items() if len(kinds) > 1}
    if not mixed_columns:
        return normalized
    return [
        {column: str(value) if column in mixed_columns else value for column, value in row.items()}
        for row in normalized
    ]


def show(rows: list[dict[str, Any]]) -> None:
    if rows:
        st.dataframe(display_rows(rows), hide_index=True, width="stretch")
    else:
        st.info(t("missing_data"))


def chart(rows: list[dict[str, Any]], x: str, y: str, *, line: bool = False) -> None:
    if rows:
        chart_rows = [{x: row.get(x), y: row.get(y)} for row in rows]
        st.vega_lite_chart(
            chart_rows,
            {
                "mark": {"type": "line" if line else "bar", "color": "#346538"},
                "encoding": {
                    "x": {"field": x, "type": "ordinal", "sort": "ascending" if line else "-y"},
                    "y": {"field": y, "type": "quantitative"},
                    "tooltip": [{"field": x}, {"field": y, "type": "quantitative"}],
                },
            },
            width="stretch",
        )


def comparison_chart(rows: list[dict[str, Any]], x: str, y: str, series: str, *, line: bool = False) -> None:
    if rows:
        chart_rows = [{x: row.get(x), y: row.get(y), series: row.get(series)} for row in rows]
        encoding: dict[str, Any] = {
            "x": {"field": x, "type": "ordinal"},
            "y": {"field": y, "type": "quantitative"},
            "color": {"field": series, "type": "nominal"},
            "tooltip": [{"field": x}, {"field": series}, {"field": y, "type": "quantitative"}],
        }
        if not line:
            encoding["xOffset"] = {"field": series}
        st.vega_lite_chart(
            chart_rows,
            {
                "mark": {"type": "line" if line else "bar", "point": line},
                "encoding": encoding,
            },
            width="stretch",
        )


def select_table(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    choice = st.selectbox(t("table"), [t("all"), *sorted({row["table"] for row in rows})], key=key)
    return rows if choice == t("all") else [row for row in rows if row["table"] == choice]


def inventory_page(run: Path) -> None:
    rows = load(run, "inventory.json")
    cols = st.columns(3)
    cols[0].metric(t("files"), f"{sum(row['files'] for row in rows):,}")
    cols[1].metric(t("tables"), sum(row["files"] > 0 for row in rows))
    cols[2].metric(t("size"), f"{sum(row['bytes'] for row in rows) / 1e9:.2f}")
    st.caption(t("remote"))
    show(rows)
    chart(rows, "table", "bytes")


def profile_page(run: Path) -> None:
    data = load(run, "profile.json")
    rows = select_table(data["columns"], "profile_table")
    st.subheader(t("columns"))
    show(rows)
    st.subheader(t("checks"))
    selected = {row["table"] for row in rows}
    show([row for row in data["checks"] if row["table"] in selected])
    with st.expander(t("categories")):
        show([row for row in data["categories"] if row["table"] in selected])
    if data["file_errors"]:
        st.warning(t("errors"))
        show(data["file_errors"])


def curate_page(run: Path) -> None:
    data = load(run, "curate.json")
    st.subheader(t("conservation"))
    show(select_table(data["tables"], "curate_table"))
    st.subheader(t("joins"))
    show(data["relationships"])
    st.subheader(t("identity"))
    show(data["consistency"])


def analyze_page(run: Path) -> None:
    data = load(run, "analyze.json")
    layer = st.radio(
        t("layer"), ["typed", "clean"], format_func=lambda x: t("raw" if x == "typed" else "clean"), horizontal=True
    )
    rows = [row for row in data["demand"] if row["layer"] == layer]
    columns = st.columns(4)
    for widget, field in zip(columns, ("country", "channel", "segment", "month"), strict=True):
        options = sorted({str(row[field]) for row in rows})
        selected = widget.multiselect(t(field), options, key=f"filter_{field}")
        if selected:
            rows = [row for row in rows if str(row[field]) in selected]
    metrics = st.columns(3)
    metrics[0].metric(t("contacts"), f"{sum(row['contacts'] for row in rows):,}")
    for widget, num, den in [
        (metrics[1], "resolved", "resolution_known"),
        (metrics[2], "escalated", "escalation_known"),
    ]:
        denominator = sum(row[den] for row in rows)
        value = f"{100 * sum(row[num] for row in rows) / denominator:.1f}%" if denominator else "N/A"
        widget.metric(t(num), value)
        widget.caption(t("denominator").format(n=denominator))
    st.caption(t("historical"))
    for title, field in [("reasons", "reason"), ("monthly", "month")]:
        aggregate: dict[str, int] = {}
        for row in rows:
            key = str(row[field])
            aggregate[key] = aggregate.get(key, 0) + row["contacts"]
        st.subheader(t(title))
        chart(
            [{field: key, "contacts": value} for key, value in sorted(aggregate.items())],
            field,
            "contacts",
            line=field == "month",
        )
    with st.expander(t("details")):
        show(rows)
    st.subheader(t("text"))
    st.caption(t("text_note"))
    for key in ("summary", "labels", "contradictions", "temporal_probe", "review_sample"):
        if key in data["text"]:
            st.markdown(f"**{t(f'text_{key}')}**")
            show([data["text"][key]])
    if "languages" in data["text"]:
        show(data["text"]["languages"])
    with st.expander(t("outcomes")):
        for key, value in data["outcomes"].items():
            st.write(key)
            if isinstance(value, list):
                show(value)
            else:
                st.caption(value)


def report_page(run: Path) -> None:
    analysis = load(run, "analyze.json")
    st.subheader(t("workflow"))
    st.info(t("unknown"))
    show(analysis["workflows"])
    content = (run / "report.md").read_text(encoding="utf-8")
    st.download_button(t("download"), content, file_name=f"eda-{run.name}.md", mime="text/markdown")
    st.markdown(content)


def explore_page(run: Path) -> None:
    st.info(t("explore_help"))
    profile = load(run, "profile.json")
    curation = load(run, "curate.json")
    table = st.selectbox(t("table"), sorted({row["table"] for row in profile["tables"]}), key="explore_table")
    layer = st.radio(
        t("layer"),
        ["typed", "clean"],
        format_func=lambda value: t("raw" if value == "typed" else "clean"),
        horizontal=True,
    )
    table_profile = next(row for row in profile["tables"] if row["table"] == table)
    table_curation: dict[str, Any] = next((row for row in curation["tables"] if row["table"] == table), {})
    columns = [row for row in profile["columns"] if row["table"] == table]
    row_count = table_profile["rows"] if layer == "typed" else table_curation.get("clean_rows", 0)
    metrics = st.columns(5)
    metrics[0].metric(t("rows"), f"{row_count:,}")
    metrics[1].metric(t("fields"), len(columns))
    metrics[2].metric(t("missing_required"), f"{sum(row['missing'] for row in columns if row['required']):,}")
    metrics[3].metric(t("duplicates"), f"{table_curation.get('collapsed_duplicates', 0):,}")
    metrics[4].metric(t("conflicts"), f"{table_curation.get('conflicting_key', 0):,}")

    with st.expander(t("volume_comparison")):
        comparison_chart(
            [
                {"table": row["table"], "source": source, "rows": count}
                for row in profile["tables"]
                for source, count in (("expected", EXPECTED_ROWS.get(row["table"])), ("observed", row["rows"]))
                if count is not None
            ],
            "table",
            "rows",
            "source",
        )

    left, right = st.columns(2)
    with left:
        st.subheader(t("missingness"))
        chart(columns, "column", "missing")
    with right:
        st.subheader(t("disposition"))
        disposition = [
            {"outcome": key, "rows": table_curation.get(key, 0)}
            for key in ("clean_rows", "collapsed_duplicates", "invalid_required", "conflicting_key")
        ]
        chart(disposition, "outcome", "rows")
    st.subheader(t("column_profile"))
    show(columns)
    drift = [
        {"issue": "required_missing", "violations": sum(row["missing"] for row in columns if row["required"])},
        {"issue": "invalid_type", "violations": sum(row["invalid_type"] for row in columns)},
        *[
            {"issue": row["rule"], "violations": row["violations"]}
            for row in profile["checks"]
            if row["table"] == table
        ],
    ]
    st.subheader(t("schema_drift"))
    chart(drift, "issue", "violations")
    show(drift)
    categories = [row for row in profile["categories"] if row["table"] == table]
    if categories:
        st.subheader(t("distribution"))
        category = st.selectbox(t("column_name"), sorted({row["column"] for row in categories}), key="category_column")
        selected_categories = [row for row in categories if row["column"] == category]
        chart(selected_categories, "value", "rows")
        with st.expander(t("details")):
            show(selected_categories)

    st.subheader(t("sample"))
    st.caption(t("warehouse_readonly"))
    warehouse = run / "warehouse.duckdb"
    if not warehouse.exists():
        st.warning(t("sample_unavailable"))
        return
    limit = st.select_slider(t("sample_size"), options=[25, 50, 100], value=25)
    rows = sanitized_sample(str(run), warehouse.stat().st_mtime_ns, table, layer, limit)
    show(rows)
    if rows:
        st.download_button(
            t("download_sample"),
            sample_csv(rows),
            file_name=f"{table}-{layer}-sanitized.csv",
            mime="text/csv",
        )


def relations_page(run: Path) -> None:
    st.info(t("relation_help"))
    rows = relationship_rows(run)
    curation = load(run, "curate.json")
    table_counts = {row["table"]: row["clean_rows"] for row in curation["tables"]}
    st.graphviz_chart(graph_dot(rows, table_counts), width="stretch")
    labels = [f"{row['child']}.{row['column']} -> {row['parent']}" for row in rows]
    selected = st.selectbox(t("relation"), labels)
    show([rows[labels.index(selected)]])
    alerts = relationship_alerts(rows)
    if alerts:
        st.subheader(t("alerts"))
        show(
            [
                {
                    **alert,
                    "finding": t(f"alert_{alert['finding']}"),
                }
                for alert in alerts
            ]
        )


def decide_page(run: Path) -> None:
    st.info(t("decision_help"))
    st.info(t("project_choice"))
    analysis = load(run, "analyze.json")
    st.subheader(t("demand_outcomes"))
    demand = [row for row in analysis["demand_summary"] if row["layer"] == "clean"]
    chart(demand, "reason", "contacts")
    show(
        [
            {
                "reason": row["reason"],
                "contacts": row["contacts"],
                "resolution_rate": row["resolution_rate"],
                "escalation_rate": row["escalation_rate"],
                "followup_rate": row["followup_rate"],
            }
            for row in demand
        ]
    )
    monthly: dict[str, int] = {}
    for row in analysis["demand"]:
        if row["layer"] == "clean":
            monthly[row["month"]] = monthly.get(row["month"], 0) + row["contacts"]
    chart(
        [{"month": month, "contacts": contacts} for month, contacts in sorted(monthly.items())],
        "month",
        "contacts",
        line=True,
    )
    comparison_chart(
        [
            {"reason": row["reason"], "metric": metric, "rate": row[metric]}
            for row in demand
            for metric in ("resolution_rate", "escalation_rate", "followup_rate")
        ],
        "reason",
        "rate",
        "metric",
    )
    st.subheader(t("text"))
    text_data = analysis["text"]
    show([text_data[key] for key in ("summary", "labels", "temporal_probe") if key in text_data])
    if text_data.get("languages"):
        chart(text_data["languages"], "detected_language", "rows")
    st.subheader(t("operational_signals"))
    profile = load(run, "profile.json")
    signals = [
        row
        for row in profile["categories"]
        if (row["table"], row["column"])
        in {
            ("transactions", "transaction_status"),
            ("transactions", "transaction_type"),
            ("products", "product_type"),
            ("digital_events", "event_category"),
        }
    ]
    for table, column in sorted({(row["table"], row["column"]) for row in signals}):
        st.markdown(f"**{table}.{column}**")
        chart([row for row in signals if row["table"] == table and row["column"] == column], "value", "rows")
    st.subheader(t("decision_matrix"))
    workflow_labels = {
        "accounts_payments": "workflow_accounts_payments",
        "card_support": "workflow_card_support",
        "technical_support": "workflow_technical_support",
        "product_information": "workflow_product_information",
        "disputes": "workflow_disputes",
    }
    for workflow in workflow_assessments(run):
        is_choice = workflow["project_choice"]
        title = t(workflow_labels[workflow["workflow"]])
        if is_choice:
            title = f"{title} · {t('current_choice')}"
        with st.expander(title, expanded=is_choice):
            show(
                [
                    {
                        **dimension,
                        "dimension": t(f"dimension_{dimension['dimension']}"),
                        "status": t(f"status_{dimension['status']}"),
                    }
                    for dimension in workflow["dimensions"]
                ]
            )


def main() -> None:
    st.set_page_config(page_title="Banking EDA", layout="wide")
    st.sidebar.selectbox("Idioma / Language", ["Español", "English"], key="language")
    st.title(t("title"))
    st.caption(t("subtitle"))
    root = Path("data/eda")
    runs = sorted(
        [p for p in root.glob("*") if (p / "manifest.json").exists() and (p / "status.json").exists()],
        key=lambda p: (p / "manifest.json").stat().st_mtime_ns,
        reverse=True,
    )
    if not runs:
        st.info(t("empty"))
        return
    selected = st.sidebar.selectbox(t("run"), [p.name for p in runs])
    run = root / selected
    if st.sidebar.button(t("refresh")):
        artifact.clear()
        st.rerun()
    status = load(run, "status.json")
    st.sidebar.caption(t("status"))
    for name in PHASES:
        st.sidebar.write(f"{t(name)}: {status.get(name, {}).get('state', 'pending')}")
    functions = {
        "inventory": inventory_page,
        "profile": profile_page,
        "curate": curate_page,
        "analyze": analyze_page,
        "report": report_page,
    }

    def page(name: str) -> Any:
        def render() -> None:
            st.header(t(name))
            if status.get(name, {}).get("state") != "complete":
                st.info(t("pending"))
                return
            st.info(t(f"phase_{name}"))
            functions[name](run)

        return render

    def laboratory_page(name: str, function: Any) -> Any:
        def render() -> None:
            st.header(t(name))
            if any(status.get(phase, {}).get("state") != "complete" for phase in ("curate", "analyze")):
                st.info(t("lab_pending"))
                return
            function(run)

        return render

    st.navigation(
        {
            t("process"): [st.Page(page(name), title=t(name), url_path=name) for name in PHASES],
            t("laboratory"): [
                st.Page(laboratory_page("explore", explore_page), title=t("explore"), url_path="explore"),
                st.Page(laboratory_page("relations", relations_page), title=t("relations"), url_path="relations"),
                st.Page(laboratory_page("decide", decide_page), title=t("decide"), url_path="decide"),
            ],
        }
    ).run()


if __name__ == "__main__":
    main()
