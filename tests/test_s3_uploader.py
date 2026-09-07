import os

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

