"""A copy of `.env.example` gives the data platform an offline configuration: the committed sample, no S3."""

import shutil
from pathlib import Path

from bank_data.settings import PipelineSettings, S3Settings

EXAMPLE = Path(__file__).resolve().parents[3] / ".env.example"


def test_the_example_selects_the_committed_sample_and_needs_no_bucket(tmp_path: Path) -> None:
    copied = tmp_path / ".env"
    shutil.copyfile(EXAMPLE, copied)

    pipeline = PipelineSettings(_env_file=copied)
    s3 = S3Settings(_env_file=copied)

    assert pipeline.bank_data_source == "sample"
    assert pipeline.bank_data_warehouse_dir is None
    assert pipeline.warehouse_dir("sample").name == "warehouse-sample"
    assert s3.configured is False
    assert s3.aws_access_key_id is None
    assert s3.data_prefix == "data/"
