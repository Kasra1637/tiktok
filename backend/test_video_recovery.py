"""Recovery must preserve actual saved video bytes, not substitute a parent render."""
import asyncio
import importlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock

import httpx
import pytest
from botocore.exceptions import ClientError
from starlette.datastructures import UploadFile
from starlette.requests import Request

sys.path.insert(0, str(Path(__file__).resolve().parent))
import storage_service
import media_signing


@pytest.fixture(scope="module")
def clips():
    directory = Path(tempfile.mkdtemp(prefix="real-recovery-video-"))
    result = {}
    for kind, codec in (("mp4", "libx264"), ("webm", "libvpx-vp9")):
        path = directory / f"clip.{kind}"
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
            "testsrc2=size=160x240:rate=15", "-t", "3", "-c:v", codec,
            "-pix_fmt", "yuv420p", str(path),
        ], check=True, capture_output=True, timeout=40)
        result[kind] = path.read_bytes()
    yield result
    shutil.rmtree(directory)


@pytest.fixture(scope="module")
def api():
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["CLERK_JWKS_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    sys.modules.pop("server", None)
    server = importlib.import_module("server")
    directory = Path(tempfile.mkdtemp(prefix="recovery-api-"))
    original = (server.pipeline.STORAGE_DIR, server.pipeline.VIDEOS_DIR)
    server.DB_PATH = directory / "test.db"
    server.pipeline.STORAGE_DIR = directory
    server.pipeline.VIDEOS_DIR = directory / "videos"
    server.pipeline.VIDEOS_DIR.mkdir()
    asyncio.run(server.init_db())
    yield server
    server.pipeline.STORAGE_DIR, server.pipeline.VIDEOS_DIR = original
    sys.modules.pop("server", None)
    shutil.rmtree(directory)


def run(coro):
    return asyncio.run(coro)


def seed(api, **values):
    generation_id = str(uuid.uuid4())
    run(api._execute(
        "INSERT INTO generations (id, status, user_id, video_url, r2_url, variation_kind, "
        "openrouter_job_id, duration, created_at, updated_at) "
        "VALUES (?, 'completed', ?, ?, ?, ?, ?, 3, '2026-01-01', '2026-01-01')",
        (generation_id, values.get("user_id", "owner"),
         values.get("video_url", f"/api/media/videos/{generation_id}.mp4"),
         values.get("r2_url", ""), values.get("variation_kind", "demo_cta"),
         values.get("openrouter_job_id")),
    ))
    return generation_id


def request():
    return Request({"type": "http", "method": "GET", "headers": [(b"range", b"bytes=0-99")],
                    "path": "/api/media/videos/test.mp4", "query_string": b""})


def serve(api, generation_id, signed=None):
    query = parse_qs(urlsplit(signed or media_signing.build_signed_path(f"{generation_id}.mp4")).query)
    return run(api.serve_video(f"{generation_id}.mp4", request(),
                              exp=query["exp"][0], sig=query["sig"][0]))


class TestRecoverySources:
    def test_missing_export_never_downloads_relative_path_or_parent(self, api, monkeypatch):
        generation_id = seed(api, openrouter_job_id="parent-job-not-this-export")
        monkeypatch.setattr(storage_service, "is_configured", lambda: False)
        download = Mock(side_effect=AssertionError("no HTTP download is allowed"))
        monkeypatch.setattr(api, "_download_generation_video", download)
        with pytest.raises(api.HTTPException) as error:
            run(api.retry_generation_storage(generation_id, "owner"))
        assert error.value.status_code == 409
        assert "Re-upload" in error.value.detail
        download.assert_not_called()

    @pytest.mark.parametrize("source", ["/api/media/videos/lost.mp4", "file:///secret", "https://", "ftp://host/clip"])
    def test_invalid_download_source_cannot_overwrite_local_bytes(self, api, source):
        path = api.pipeline.VIDEOS_DIR / "existing.mp4"
        path.write_bytes(b"surviving bytes")
        result, detail = run(api._download_generation_video(source, "existing"))
        assert result is None
        assert "HTTP(S)" in detail
        assert path.read_bytes() == b"surviving bytes"

    def test_provider_job_fallback_ignores_local_path(self, api):
        durable, provider = api._recovery_sources({
            "video_url": "/api/media/videos/missing.mp4", "openrouter_job_id": "job-77",
        })
        assert not durable
        assert provider.endswith("/videos/job-77/content?index=0")

    @pytest.mark.parametrize("kind", ["mp4", "webm"])
    def test_r2_restores_exact_export_without_trim_rescale_or_reupload(self, api, monkeypatch, clips, kind):
        generation_id = seed(api, r2_url="https://account.r2.cloudflarestorage.com/bucket/owner/export.mp4")
        monkeypatch.setattr(storage_service, "is_configured", lambda: True)
        client = Mock()
        def download(bucket, key, filename):
            assert key == f"owner/{generation_id}.mp4"
            Path(filename).write_bytes(clips[kind])
        client.download_file.side_effect = download
        monkeypatch.setattr(storage_service, "_get_client", lambda: client)
        monkeypatch.setattr(api, "_download_generation_video", Mock(side_effect=AssertionError("no provider download")))
        monkeypatch.setattr(api.overlays, "rescale_to_canvas", Mock(side_effect=AssertionError("preserve export")))
        monkeypatch.setattr(storage_service, "upload_video", Mock(side_effect=AssertionError("no reupload")))
        run(api._execute("UPDATE generations SET trim_to_seconds = 1 WHERE id = ?", (generation_id,)))
        result = run(api.retry_generation_storage(generation_id, "owner"))
        assert run(api.get_generation(generation_id, "owner"))["duration"] == 3
        path = api.pipeline.VIDEOS_DIR / f"{generation_id}.mp4"
        assert path.read_bytes() == clips[kind]
        assert result["storage_error"] is None
        assert "sig=" in result["playback_url"]
        assert serve(api, generation_id).headers["content-type"] == f"video/{kind}"

    def test_cloud_access_failure_does_not_claim_export_is_lost(self, api, monkeypatch):
        generation_id = seed(api, r2_url="https://account.r2.cloudflarestorage.com/bucket/owner/export.mp4")
        monkeypatch.setattr(storage_service, "is_configured", lambda: True)
        denied = ClientError({"Error": {"Code": "AccessDenied"}}, "GetObject")
        monkeypatch.setattr(storage_service, "restore_video", Mock(side_effect=denied))
        with pytest.raises(api.HTTPException) as error:
            run(api.retry_generation_storage(generation_id, "owner"))
        assert error.value.status_code == 502
        assert "does not prove the video is lost" in error.value.detail
        assert "cannot be recovered" not in error.value.detail

    def test_network_failure_preserves_previous_file(self, api, monkeypatch):
        path = api.pipeline.VIDEOS_DIR / "preserve.mp4"
        path.write_bytes(b"old bytes")
        class Client:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            def stream(self, *args): raise httpx.ConnectError("connection failed")
        monkeypatch.setattr(api.httpx, "AsyncClient", lambda **kwargs: Client())
        monkeypatch.setattr(api, "_DOWNLOAD_ATTEMPTS", 1)
        result, detail = run(api._download_generation_video("https://provider.invalid/clip", "preserve"))
        assert result is None
        assert path.read_bytes() == b"old bytes"
        assert not list(path.parent.glob(".preserve.mp4.*.download"))


class TestCloudPlayback:
    def test_private_cloud_copy_streams_same_origin_not_redirect(self, api, monkeypatch, clips):
        """The 307 to a presigned cloud URL stood here, but reading its body
        needs CORS on the bucket, which R2 does not grant by default — the
        Demo + CTA editor's fetch().blob() then failed as "Failed to fetch"
        for a clip that was never missing. Bytes now transit this route."""
        generation_id = seed(api, user_id="specific-owner", r2_url="https://private.invalid/clip")
        seen = []
        monkeypatch.setattr(storage_service, "is_configured", lambda: True)
        monkeypatch.setattr(storage_service, "cloud_video_head",
                            lambda owner, key: (len(clips["mp4"]), "video/mp4"))
        def ranged(owner, key, start, end):
            seen.append((owner, key, start, end))
            return io.BytesIO(clips["mp4"][start:end + 1])
        monkeypatch.setattr(storage_service, "open_cloud_range", ranged)
        response = serve(api, generation_id)
        assert response.status_code == 206
        assert "location" not in response.headers
        assert seen == [("specific-owner", generation_id, 0, 99)]
        assert response.headers["content-range"] == f"bytes 0-99/{len(clips['mp4'])}"
        assert response.headers["content-type"] == "video/mp4"
        async def body():
            return b"".join([part async for part in response.body_iterator])
        assert run(body()) == clips["mp4"][:100]

    def test_empty_local_file_uses_surviving_cloud_copy(self, api, monkeypatch, clips):
        generation_id = seed(api)
        (api.pipeline.VIDEOS_DIR / f"{generation_id}.mp4").write_bytes(b"")
        monkeypatch.setattr(storage_service, "is_configured", lambda: True)
        monkeypatch.setattr(storage_service, "cloud_video_head",
                            lambda owner, key: (len(clips["mp4"]), "video/mp4"))
        monkeypatch.setattr(storage_service, "open_cloud_range",
                            lambda owner, key, start, end: io.BytesIO(clips["mp4"][start:end + 1]))
        response = serve(api, generation_id)
        assert response.status_code == 206
        assert "location" not in response.headers

    def test_invalid_signature_does_not_lookup_storage(self, api, monkeypatch):
        lookup = Mock(side_effect=AssertionError("must authenticate first"))
        monkeypatch.setattr(api, "_fetch_one", lookup)
        with pytest.raises(api.HTTPException) as error:
            run(api.serve_video("clip.mp4", request(), exp="9999999999", sig="forged"))
        assert error.value.status_code == 404
        lookup.assert_not_called()

    def test_expired_signature_does_not_lookup_storage(self, api, monkeypatch):
        lookup = Mock(side_effect=AssertionError("must authenticate first"))
        monkeypatch.setattr(api, "_fetch_one", lookup)
        with pytest.raises(api.HTTPException):
            run(api.serve_video("clip.mp4", request(), exp="1", sig=media_signing.make_signature("clip.mp4", 1)))
        lookup.assert_not_called()

    def test_cloud_service_failure_is_not_missing_file(self, api, monkeypatch):
        generation_id = seed(api)
        monkeypatch.setattr(storage_service, "is_configured", lambda: True)
        monkeypatch.setattr(storage_service, "cloud_video_head", Mock(side_effect=RuntimeError("private details")))
        with pytest.raises(api.HTTPException) as error:
            serve(api, generation_id)
        assert error.value.status_code == 503
        assert "private details" not in error.value.detail

    def test_missing_cloud_copy_falls_back_to_external_before_404(self, api, monkeypatch):
        generation_id = seed(api, r2_url="https://cdn.invalid/owner/clip.mp4")
        monkeypatch.setattr(storage_service, "is_configured", lambda: True)
        monkeypatch.setattr(storage_service, "cloud_video_head",
                            Mock(side_effect=storage_service.CloudObjectMissing("gone")))
        response = serve(api, generation_id)
        assert response.status_code == 307
        assert response.headers["location"].startswith("https://cdn.invalid/")

    def test_other_owner_cannot_obtain_playback_link_or_retry(self, api):
        generation_id = seed(api)
        for coroutine in (api.get_generation(generation_id, "other"), api.retry_generation_storage(generation_id, "other")):
            with pytest.raises(api.HTTPException) as error:
                run(coroutine)
            assert error.value.status_code == 404

    @pytest.mark.parametrize("kind", ["mp4", "webm"])
    def test_real_export_save_and_history_preserve_container(self, api, monkeypatch, clips, kind):
        monkeypatch.setattr(storage_service, "is_configured", lambda: False)
        result = run(api.save_demo_cta_export(
            file=UploadFile(filename=f"export.{kind}", file=io.BytesIO(clips[kind])), user_id="owner"))
        row = next(row for row in run(api.generation_history(user_id="owner"))["generations"] if row["id"] == result["id"])
        assert row["playback_url"].startswith(f"/api/media/videos/{result['id']}.mp4?")
        response = serve(api, result["id"], row["playback_url"])
        assert response.status_code == 206
        assert response.headers["content-type"] == f"video/{kind}"
        async def body():
            return b"".join([part async for part in response.body_iterator])
        assert run(body()) == clips[kind][:100]


class TestStorageHelpers:
    @pytest.mark.parametrize("kind", ["mp4", "webm"])
    def test_presign_checks_exact_object_and_overrides_legacy_mime(self, monkeypatch, clips, kind):
        client = Mock()
        body = io.BytesIO(clips[kind][:16])
        client.get_object.return_value = {"Body": body}
        client.generate_presigned_url.return_value = "https://cloud.invalid/signed"
        monkeypatch.setattr(storage_service, "_get_client", lambda: client)
        assert storage_service.signed_read_url("owner", "id", 99999) == "https://cloud.invalid/signed"
        assert body.closed
        assert client.get_object.call_args.kwargs["Key"] == "owner/id.mp4"
        params = client.generate_presigned_url.call_args.kwargs
        assert params["Params"]["ResponseContentType"] == f"video/{kind}"
        assert params["ExpiresIn"] == 3600

    def test_missing_object_differs_from_service_error(self, monkeypatch):
        client = Mock()
        monkeypatch.setattr(storage_service, "_get_client", lambda: client)
        client.get_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        assert storage_service.signed_read_url("owner", "id") is None
        client.get_object.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "GetObject")
        with pytest.raises(ClientError): storage_service.signed_read_url("owner", "id")

    def test_cloud_head_reports_size_and_type(self, monkeypatch):
        client = Mock()
        client.head_object.return_value = {"ContentLength": 1000, "ContentType": "video/mp4"}
        monkeypatch.setattr(storage_service, "_get_client", lambda: client)
        assert storage_service.cloud_video_head("owner", "id") == (1000, "video/mp4")
        assert client.head_object.call_args.kwargs["Key"] == "owner/id.mp4"

    def test_cloud_head_missing_and_unconfigured(self, monkeypatch):
        client = Mock()
        monkeypatch.setattr(storage_service, "_get_client", lambda: client)
        client.head_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey"}}, "HeadObject")
        with pytest.raises(storage_service.CloudObjectMissing):
            storage_service.cloud_video_head("owner", "id")
        monkeypatch.setattr(storage_service, "_get_client", lambda: None)
        assert storage_service.cloud_video_head("owner", "id") is None
        assert storage_service.open_cloud_range("owner", "id", 0, 99) is None

    def test_cloud_range_sends_the_exact_span(self, monkeypatch, clips):
        client = Mock()
        client.get_object.return_value = {"Body": io.BytesIO(clips["mp4"][:100])}
        monkeypatch.setattr(storage_service, "_get_client", lambda: client)
        body = storage_service.open_cloud_range("owner", "id", 0, 99)
        assert client.get_object.call_args.kwargs["Range"] == "bytes=0-99"
        assert body.read() == clips["mp4"][:100]
        client.get_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        with pytest.raises(storage_service.CloudObjectMissing):
            storage_service.open_cloud_range("owner", "id", 0, 99)

    def test_presign_uses_real_boto3_signing_and_configured_bucket(self, monkeypatch, clips):
        import boto3
        from botocore.config import Config
        from botocore.stub import Stubber
        client = boto3.client("s3", endpoint_url="https://account.r2.cloudflarestorage.com",
                              aws_access_key_id="test-access", aws_secret_access_key="test-secret",
                              region_name="auto", config=Config(signature_version="s3v4"))
        monkeypatch.setattr(storage_service, "_get_client", lambda: client)
        monkeypatch.setattr(storage_service, "R2_BUCKET_NAME", "configured-bucket")
        with Stubber(client) as stubber:
            stubber.add_response("get_object", {"Body": io.BytesIO(clips["webm"][:16])},
                                 {"Bucket": "configured-bucket", "Key": "owner/id.mp4", "Range": "bytes=0-15"})
            url = storage_service.signed_read_url("owner", "id", 120)
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        assert parsed.hostname == "account.r2.cloudflarestorage.com"
        assert parsed.path == "/configured-bucket/owner/id.mp4"
        assert query["X-Amz-Expires"] == ["120"]
        assert query["response-content-type"] == ["video/webm"]
        assert "X-Amz-Signature" in query

    def test_invalid_cloud_download_cannot_destroy_existing_copy(self, monkeypatch, tmp_path):
        target = tmp_path / "clip.mp4"
        target.write_bytes(b"old bytes")
        client = Mock()
        client.download_file.side_effect = lambda bucket, key, filename: Path(filename).write_bytes(b"invalid")
        monkeypatch.setattr(storage_service, "_get_client", lambda: client)
        recovered, detail = storage_service.restore_video("owner", "id", target)
        assert recovered is None
        assert "complete" in detail
        assert target.read_bytes() == b"old bytes"
        assert list(tmp_path.iterdir()) == [target]

    def test_cloud_restore_missing_and_denied_remain_distinct(self, monkeypatch, tmp_path):
        client = Mock()
        monkeypatch.setattr(storage_service, "_get_client", lambda: client)
        client.download_file.side_effect = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        recovered, detail = storage_service.restore_video("owner", "id", tmp_path / "clip.mp4")
        assert recovered is None and detail == "Cloud copy not found."
        client.download_file.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "GetObject")
        with pytest.raises(ClientError):
            storage_service.restore_video("owner", "id", tmp_path / "clip.mp4")
        assert not list(tmp_path.iterdir())

    def test_webm_upload_mime_matches_bytes(self, monkeypatch, tmp_path, clips):
        path = tmp_path / "legacy.mp4"
        path.write_bytes(clips["webm"])
        client = Mock()
        monkeypatch.setattr(storage_service, "is_configured", lambda: True)
        monkeypatch.setattr(storage_service, "_get_client", lambda: client)
        assert storage_service.upload_video("owner", "id", path)
        assert client.upload_file.call_args.kwargs["ExtraArgs"]["ContentType"] == "video/webm"
