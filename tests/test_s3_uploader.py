import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import s3_uploader


def test_get_s3_client_returns_none_without_credentials(monkeypatch):
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

    assert s3_uploader.get_s3_client() is None


def test_generate_presigned_url_returns_value_from_client(monkeypatch):
    class _Client:
        def generate_presigned_url(self, operation, Params, ExpiresIn):
            assert operation == "get_object"
            assert Params["Bucket"] == "bucket"
            assert Params["Key"] == "path/video.mp4"
            assert ExpiresIn == 123
            return "https://example.test/signed"

    monkeypatch.setattr(s3_uploader, "get_s3_client", lambda: _Client())

    signed = s3_uploader.generate_presigned_url("bucket", "path/video.mp4", expiration=123)

    assert signed == "https://example.test/signed"


def test_upload_job_artifacts_uploads_only_mp4_and_json(monkeypatch):
    calls = []
    monkeypatch.setenv("AWS_S3_BUCKET", "bucket")
    monkeypatch.setattr(os.path, "exists", lambda _: True)
    monkeypatch.setattr(os, "listdir", lambda _: ["a.mp4", "meta.json", "temp_skip.mp4", "note.txt"])
    monkeypatch.setattr(s3_uploader, "upload_file_to_s3", lambda path, bucket, key: calls.append((path, bucket, key)))

    s3_uploader.upload_job_artifacts("/tmp/output", "job-1")

    assert calls == [
        ("/tmp/output/a.mp4", "bucket", "job-1/a.mp4"),
        ("/tmp/output/meta.json", "bucket", "job-1/meta.json"),
    ]


def test_upload_file_to_s3_returns_false_without_credentials(monkeypatch):
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

    assert s3_uploader.upload_file_to_s3("/tmp/a.mp4", "bucket", "key") is False


def test_upload_file_to_s3_returns_true_on_success(monkeypatch):
    monkeypatch.setattr(
        s3_uploader,
        "get_s3_client",
        lambda: SimpleNamespace(upload_file=lambda *a, **k: None),
    )

    assert s3_uploader.upload_file_to_s3("/tmp/a.mp4", "bucket", "key") is True


def test_upload_file_to_s3_returns_false_for_invalid_inputs(monkeypatch):
    monkeypatch.setattr(s3_uploader, "get_s3_client", lambda: object())
    assert s3_uploader.upload_file_to_s3("", "bucket", "key") is False
    assert s3_uploader.upload_file_to_s3("/tmp/a.mp4", "", "key") is False
    assert s3_uploader.upload_file_to_s3("/tmp/a.mp4", "bucket", "") is False


def test_upload_file_to_s3_returns_false_on_exceptions(monkeypatch):
    class _ClientErr:
        def upload_file(self, *_args, **_kwargs):
            raise s3_uploader.ClientError({"Error": {"Code": "500", "Message": "boom"}}, "upload_file")

    class _AnyErr:
        def upload_file(self, *_args, **_kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(s3_uploader, "get_s3_client", lambda: _ClientErr())
    assert s3_uploader.upload_file_to_s3("/tmp/a.mp4", "bucket", "key") is False

    monkeypatch.setattr(s3_uploader, "get_s3_client", lambda: _AnyErr())
    assert s3_uploader.upload_file_to_s3("/tmp/a.mp4", "bucket", "key") is False


def test_generate_presigned_url_returns_none_when_clienterror(monkeypatch):
    class _Client:
        def generate_presigned_url(self, *_args, **_kwargs):
            raise s3_uploader.ClientError({"Error": {"Code": "403", "Message": "nope"}}, "generate_presigned_url")

    logger = MagicMock()
    monkeypatch.setattr(s3_uploader, "logger", logger)
    monkeypatch.setattr(s3_uploader, "get_s3_client", lambda: _Client())

    assert s3_uploader.generate_presigned_url("bucket", "path/video.mp4") is None
    logger.error.assert_called_once()


def test_delete_s3_object_validates_inputs_and_handles_success(monkeypatch):
    monkeypatch.setattr(s3_uploader, "get_s3_client", lambda: None)
    assert s3_uploader.delete_s3_object("bucket", "key") is False
    assert s3_uploader.delete_s3_object("", "key") is False
    assert s3_uploader.delete_s3_object("bucket", "") is False

    class _Client:
        def delete_object(self, **kwargs):
            return None

    monkeypatch.setattr(s3_uploader, "get_s3_client", lambda: _Client())
    assert s3_uploader.delete_s3_object("bucket", "key") is True


def test_delete_s3_object_returns_false_on_exception(monkeypatch):
    class _Client:
        def delete_object(self, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(s3_uploader, "get_s3_client", lambda: _Client())
    assert s3_uploader.delete_s3_object("bucket", "key") is False


def test_get_s3_object_size_handles_missing_or_error(monkeypatch):
    monkeypatch.setattr(s3_uploader, "get_s3_client", lambda: None)
    assert s3_uploader.get_s3_object_size("bucket", "key") == 0

    class _Failing:
        def head_object(self, **kwargs):
            raise RuntimeError("nope")

    monkeypatch.setattr(s3_uploader, "get_s3_client", lambda: _Failing())
    assert s3_uploader.get_s3_object_size("bucket", "key") == 0

    class _Good:
        def head_object(self, **kwargs):
            return {"ContentLength": 1234}

    monkeypatch.setattr(s3_uploader, "get_s3_client", lambda: _Good())
    assert s3_uploader.get_s3_object_size("bucket", "key") == 1234


