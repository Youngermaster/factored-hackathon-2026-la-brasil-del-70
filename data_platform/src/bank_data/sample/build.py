"""``bank-data sample``: extract, pseudonymize, and write the committed sample with its README."""

from collections import defaultdict
from pathlib import Path

import duckdb

from bank_data.contracts.tables import TABLES_BY_NAME
from bank_data.errors import ConfigurationError
from bank_data.sample.extract import (
    SampleExtractor,
    SampleResult,
    SampleSettings,
    layout_files,
    preview_files,
    pseudonymize,
    write_sample,
)
from bank_data.sample.readme import DatasetVersion, partition_digest, render_readme
from bank_data.workspace import Workspace


def dataset_version(workspace: Workspace) -> DatasetVersion:
    """The delivery the sample comes from, read from the manifest of the s3 warehouse."""
    if not workspace.manifest_path.exists():
        raise ConfigurationError("no manifest in the s3 warehouse; run `make data-download` and `make pipeline` first")
    connection = duckdb.connect(str(workspace.manifest_path), read_only=True)
    try:
        rows = connection.execute(
            "select object_key, etag, table_name from objects where status in ('loaded', 'quarantined') "
            "and table_name is not null order by object_key"
        ).fetchall()
    finally:
        connection.close()
    snapshots: list[tuple[str, str]] = []
    daily: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for key, etag, table in rows:
        if TABLES_BY_NAME[str(table)].layout == "snapshot":
            snapshots.append((str(key), str(etag)))
        else:
            daily[str(table)].append((str(key), str(etag)))
    return DatasetVersion(
        label=workspace.config.dataset.version,
        snapshot_date=workspace.config.dataset.snapshot_date.isoformat(),
        snapshot_etags=tuple(snapshots),
        partition_digests=tuple((table, len(pairs), partition_digest(pairs)) for table, pairs in sorted(daily.items())),
    )


def build_sample(workspace: Workspace, output_dir: Path, settings: SampleSettings | None = None) -> SampleResult:
    settings = settings or SampleSettings()
    version = dataset_version(workspace)
    extractor = SampleExtractor(workspace.bronze_dir, workspace.config.dataset.snapshot_date, settings)
    result = extractor.extract()
    tables = pseudonymize(result.tables)
    files = layout_files(tables) | preview_files(tables, settings.preview_rows)
    write_sample(output_dir, files)
    readme = render_readme(tables, settings.preview_rows, version, settings, len(result.customers), result.coverage)
    (output_dir / "README.md").write_text(readme, encoding="utf-8", newline="")
    return SampleResult(result.customers, tables, result.coverage, result.source_rows)
