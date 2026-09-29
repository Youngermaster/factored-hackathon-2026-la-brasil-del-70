import io
import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest
from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from botocore.stub import Stubber

from bank_data.errors import ConfigurationError, SourceAccessError
from bank_data.ingest.local import LocalSource, file_md5
from bank_data.ingest.s3 import S3Source, error_code, is_transient
from bank_data.ingest.source import SourceObject
from bank_data.logs import configure_logging
from bank_data.settings import S3Settings
from bank_data.workspace import Workspace

FAKE_KEY_ID = "AKIAFAKEFIXTURE00001"
FAKE_SECRET = "fake-secret-value-for-tests-only-0000000000"  # noqa: S105 (a fixture value, not a credential)
FAKE_BUCKET = "fixture-bucket-not-real"


def _settings() -> S3Settings:
    return S3Settings(
        aws_access_key_id=FAKE_KEY_ID,  # type: ignore[arg-type]
        aws_secret_access_key=FAKE_SECRET,  # type: ignore[arg-type]
        aws_default_region="us-east-2",
        data_bucket=FAKE_BUCKET,
        data_prefix="data/",
    )


def _source(**kwargs: object) -> tuple[S3Source, Stubber]:
    source = S3Source.from_settings(_settings())
    client = source._client
    stubber = Stubber(client)
    stubber.activate()
    fast = S3Source(client, FAKE_BUCKET, "data/", sleep=lambda _: None, **kwargs)  # type: ignore[arg-type]
    return fast, stubber


def test_local_source_lists_files_with_md5_etags_and_skips_docs_and_preview(tmp_path: Path) -> None:
    (tmp_path / "customers.csv").write_text("a\n1\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("docs", encoding="utf-8")
    (tmp_path / "preview").mkdir()
    (tmp_path / "preview" / "customers.csv").write_text("a\n1\n", encoding="utf-8")
    partition = tmp_path / "transactions" / "year=2024" / "month=01" / "day=01"
    partition.mkdir(parents=True)
    (partition / "transactions_20240101.csv").write_text("b\n2\n", encoding="utf-8")

    source = LocalSource(tmp_path)
    listed = list(source.list_objects())

    assert [obj.key for obj in listed] == [
        "customers.csv",
        "transactions/year=2024/month=01/day=01/transactions_20240101.csv",
    ]
    assert listed[0].etag == file_md5(tmp_path / "customers.csv")
    assert source.prefix == ""
    destination = tmp_path / "out" / "copy.csv"
    source.download(listed[0], destination)
    assert destination.read_text(encoding="utf-8") == "a\n1\n"


def test_local_source_requires_an_existing_directory(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        LocalSource(tmp_path / "missing")
    source = LocalSource(tmp_path)
    gone = SourceObject("gone.csv", "e", 1, datetime(2026, 1, 1, tzinfo=UTC))
    with pytest.raises(SourceAccessError, match=r"gone\.csv"):
        source.download(gone, tmp_path / "x.csv")


def test_local_workspace_ignores_non_data_before_hashing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "customers.csv").write_text("customer_id\nCUS-A\n", encoding="utf-8")
    valid = tmp_path / "transactions" / "year=2024" / "month=01" / "day=01"
    valid.mkdir(parents=True)
    (valid / "transactions_20240101.csv").write_text("transaction_id\nTXN-A\n", encoding="utf-8")
    invalid = tmp_path / "transactions" / "year=2024" / "month=13" / "day=01"
    invalid.mkdir(parents=True)
    (invalid / "transactions_20241301.csv").write_text("bad", encoding="utf-8")
    for directory in ("contexto", "eda", "warehouse-local", "warehouse-sample"):
        target = tmp_path / directory
        target.mkdir()
        (target / "customers.csv").write_text("not input", encoding="utf-8")
    (tmp_path / "notes.pdf").write_text("not input", encoding="utf-8")

    hashed: list[str] = []

    def record_hash(path: Path) -> str:
        hashed.append(path.relative_to(tmp_path).as_posix())
        return "fixture-etag"

    monkeypatch.setattr("bank_data.ingest.local.file_md5", record_hash)
    source = Workspace.resolve("local", local_dir=tmp_path, warehouse_dir=tmp_path / "warehouse-local").data_source()
    listed = list(source.list_objects())

    expected = ["customers.csv", "transactions/year=2024/month=01/day=01/transactions_20240101.csv"]
    assert [item.key for item in listed] == expected
    assert hashed == expected


def test_s3_source_lists_objects_under_the_prefix() -> None:
    source, stubber = _source()
    stubber.add_response(
        "list_objects_v2",
        {
            "Contents": [
                {
                    "Key": "data/transactions/year=2024/month=01/day=01/t.csv",
                    "ETag": '"abc"',
                    "Size": 5,
                    "LastModified": datetime(2026, 8, 31, tzinfo=UTC),
                },
                {
                    "Key": "data/branches.csv",
                    "ETag": '"def"',
                    "Size": 7,
                    "LastModified": datetime(2026, 8, 31, tzinfo=UTC),
                },
                {"Key": "data/folder/", "ETag": '"x"', "Size": 0, "LastModified": datetime(2026, 8, 31, tzinfo=UTC)},
            ],
            "IsTruncated": False,
        },
        {"Bucket": FAKE_BUCKET, "Prefix": "data/"},
    )

    listed = list(source.list_objects())

    assert [(obj.key, obj.etag, obj.size) for obj in listed] == [
        ("data/branches.csv", "def", 7),
        ("data/transactions/year=2024/month=01/day=01/t.csv", "abc", 5),
    ]
    assert source.label == "s3"
    assert source.prefix == "data/"


def _body(payload: bytes) -> StreamingBody:
    return StreamingBody(io.BytesIO(payload), len(payload))


def test_s3_download_retries_transient_errors_then_writes_atomically(tmp_path: Path) -> None:
    source, stubber = _source(attempts=3)
    obj = SourceObject("data/branches.csv", "abc", 5, datetime(2026, 8, 31, tzinfo=UTC))
    stubber.add_client_error("get_object", service_error_code="SlowDown", http_status_code=503)
    stubber.add_response("get_object", {"Body": _body(b"hello")}, {"Bucket": FAKE_BUCKET, "Key": obj.key})

    destination = tmp_path / "raw" / "branches.csv"
    source.download(obj, destination)

    assert destination.read_bytes() == b"hello"
    assert not destination.with_name("branches.csv.partial").exists()


def test_s3_download_gives_up_on_a_permanent_error_without_leaking_secrets(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    configure_logging([FAKE_KEY_ID, FAKE_SECRET, FAKE_BUCKET])
    source, stubber = _source(attempts=3)
    obj = SourceObject("data/branches.csv", "abc", 5, datetime(2026, 8, 31, tzinfo=UTC))
    stubber.add_client_error(
        "get_object",
        service_error_code="AccessDenied",
        service_message=f"denied for {FAKE_KEY_ID} on {FAKE_BUCKET} with {FAKE_SECRET}",
        http_status_code=403,
    )

    with pytest.raises(SourceAccessError) as raised:
        source.download(obj, tmp_path / "x.csv")

    message = str(raised.value)
    assert "AccessDenied" in message
    assert "data/branches.csv" in message
    for secret in (FAKE_KEY_ID, FAKE_SECRET, FAKE_BUCKET):
        assert secret not in message
        assert secret not in repr(raised.value)
    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__ is True
    assert not (tmp_path / "x.csv").exists()


def test_s3_download_rejects_a_truncated_body(tmp_path: Path) -> None:
    source, stubber = _source(attempts=1)
    obj = SourceObject("data/branches.csv", "abc", 10, datetime(2026, 8, 31, tzinfo=UTC))
    stubber.add_response("get_object", {"Body": _body(b"short")}, {"Bucket": FAKE_BUCKET, "Key": obj.key})

    with pytest.raises(SourceAccessError, match="OSError"):
        source.download(obj, tmp_path / "x.csv")
    assert not (tmp_path / "x.csv").exists()


def test_settings_never_show_credentials() -> None:
    settings = _settings()
    shown = repr(settings) + str(settings)
    for secret in (FAKE_KEY_ID, FAKE_SECRET, FAKE_BUCKET):
        assert secret not in shown
    assert settings.configured is True
    assert set(settings.secret_values()) == {FAKE_KEY_ID, FAKE_SECRET, FAKE_BUCKET}
    assert S3Settings(data_bucket="  ", _env_file=None).configured is False


def test_missing_bucket_is_a_configuration_error() -> None:
    with pytest.raises(ConfigurationError, match="DATA_BUCKET"):
        S3Source.from_settings(S3Settings(data_bucket=None, _env_file=None))
    with pytest.raises(ConfigurationError):
        S3Source(object(), "b", "p", attempts=0)


def test_classifies_transient_errors() -> None:
    throttled = ClientError({"Error": {"Code": "Throttling", "Message": "m"}}, "GetObject")
    denied = ClientError({"Error": {"Code": "AccessDenied", "Message": "m"}}, "GetObject")
    assert is_transient(throttled) is True
    assert is_transient(denied) is False
    assert is_transient(ConnectionResetError()) is True
    assert error_code(denied) == "AccessDenied"
    assert error_code(ValueError()) == "ValueError"
    assert error_code(ClientError({"Error": {}}, "GetObject")) == "ClientError"


def test_log_filter_masks_secrets_in_messages_and_fields(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging([FAKE_SECRET, FAKE_BUCKET])
    logger = logging.getLogger("bank_data.test")
    logger.warning("value %s in %s", FAKE_SECRET, "text", extra={"detail": f"bucket {FAKE_BUCKET}"})
    try:
        raise RuntimeError(FAKE_SECRET)
    except RuntimeError:
        logger.exception("failure")

    output = capsys.readouterr().err
    assert FAKE_SECRET not in output
    assert FAKE_BUCKET not in output
    assert "[redacted]" in output
    assert '"detail": "bucket [redacted]"' in output
