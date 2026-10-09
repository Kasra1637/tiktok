"""
Assets must outlive the container they were uploaded into.

A Cloud Run deploy hands every instance a fresh disk, so a photograph kept
only locally vanishes between one morning and the next: the preview route
404s (the founder sees an empty thumbnail box), attach refuses with "the
asset file is missing on disk", and generation will not spend a credit on a
face it cannot read. The upload therefore also lands in R2, and every
consumer — serving, attaching, and the identity pass — restores through
`server._ensure_asset_file` instead of refusing on a file the cloud holds.

The R2 client is faked throughout: these tests are about the round-trip
contract (push on upload, pull on read, refuse only when the cloud is
genuinely empty), not about Cloudflare.
"""
import asyncio
import importlib
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException
from starlette.requests import Request

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

import media_signing
import storage_service

ANON = "anonymous"

# A real photograph, because the generation path decodes the restored bytes
# (face crop, bounds, data URI) and synthetic magic bytes would fail there.
PORTRAIT_BYTES = (BACKEND_DIR / "storage" / "samples" / "test_portrait.jpg").read_bytes()
# Past download_asset's size floor but not an image of any format it accepts.
JUNK_BYTES = b"definitely not an image " * 16


def _run(coro):
    return asyncio.run(coro)


def _client_capturing_upload(calls):
    class Client:
        def upload_file(self, filename, bucket, key, ExtraArgs=None):
            calls.append({"filename": filename, "bucket": bucket, "key": key,
                          "extra": ExtraArgs or {}})

        def download_file(self, bucket, key, filename):
            raise AssertionError("not used")

        def delete_object(self, Bucket=None, Key=None):
            raise AssertionError("not used")

    return Client()


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-assetdur-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""

    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Keep test uploads inside the temp tree, not the real storage dir.
    server.pipeline.ASSETS_DIR = Path(tmpdir) / "assets"
    server.pipeline.ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    asyncio.run(server.init_db())
    yield server
    sys.modules.pop("server", None)


@pytest.fixture()
def tmp_root():
    return Path(tempfile.mkdtemp(prefix="tiktok-assetdur-files-"))


def _profile(api, name="Durable Assets"):
    from models import BrandProfileCreateRequest, ApproveAppProfileRequest
    p = _run(api.create_brand(payload=BrandProfileCreateRequest(
        brand_name=name,
        brand_description="A focus timer for people who stall on starting.",
        core_features=["Task timer", "Reminders"],
        usage_moments=["Starting a task they have been avoiding"],
        outcome_statements=[{
            "outcome": "Starting without stalling on setup",
            "who_feels_it": "people who stall on starting",
            "from_feature": "Task timer",
            "how_it_helps": "The timer starts in one tap so there is nothing to set up",
        }],
    ), user_id=ANON))
    _run(api.approve_app_profile(
        profile_id=p["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
    return _run(api.get_app_profile(p["id"], ANON))


def _upload(api, profile_id, filename, src: Path, label=""):
    """Call upload_asset with plain values (Form defaults are Form objects)."""
    from fastapi import UploadFile
    with open(src, "rb") as fh:
        return _run(api.upload_asset(
            profile_id=profile_id,
            kind="character_reference",
            file=UploadFile(filename=filename, file=fh),
            label=label,
            notes="",
            rights_confirmed=True,
            user_id=ANON,
        ))


def _photo(api, tmp_root, name="portrait.jpg"):
    src = tmp_root / name
    src.write_bytes(PORTRAIT_BYTES)
    return src


def _signed_query(asset_id):
    return dict(
        pair.split("=", 1)
        for pair in media_signing.build_signed_asset_path(asset_id).split("?", 1)[1].split("&")
    )


def _serve(api, asset_id):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": f"/api/media/assets/{asset_id}",
        "raw_path": f"/api/media/assets/{asset_id}".encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"testserver")],
        "client": ("test", 1),
        "server": ("testserver", 80),
    }
    return _run(api.serve_asset(asset_id, Request(scope), **_signed_query(asset_id)))


def _fake_restore_bytes(api, monkeypatch, data, calls=None):
    """Configure a storage layer that reports itself configured and hands back
    `data` for whatever object is asked for."""
    monkeypatch.setattr(api.storage_service, "is_configured", lambda: True)

    def download(user_id, asset_id, target):
        if calls is not None:
            calls.append((user_id, asset_id, Path(target)))
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return True

    monkeypatch.setattr(api.storage_service, "download_asset", download)
    return download


def _fake_restore_fails(api, monkeypatch, calls=None):
    monkeypatch.setattr(api.storage_service, "is_configured", lambda: True)

    def download(user_id, asset_id, target):
        if calls is not None:
            calls.append((user_id, asset_id, Path(target)))
        return False

    monkeypatch.setattr(api.storage_service, "download_asset", download)
    return download


class TestUploadKeepsADurableCopy:
    def test_the_upload_also_lands_in_r2(self, api, tmp_root, monkeypatch):
        profile = _profile(api, "Push On Upload")
        calls = []
        monkeypatch.setattr(
            api.storage_service, "upload_asset",
            lambda user_id, asset_id, path: calls.append((user_id, asset_id, Path(path))) or True,
        )
        created = _upload(api, profile["id"], "portrait.jpg", _photo(api, tmp_root))
        assert len(calls) == 1
        user_id, asset_id, path = calls[0]
        assert (user_id, asset_id) == (ANON, created["id"])
        # The bytes pushed are the bytes on disk, not a re-encode.
        assert path == Path(created["file_path"])
        assert path.read_bytes() == PORTRAIT_BYTES

    def test_a_storage_outage_does_not_fail_the_upload(self, api, tmp_root, monkeypatch):
        """The local copy already serves this instance; durability is additive."""
        profile = _profile(api, "Upload Without Storage")

        def boom(user_id, asset_id, path):
            raise RuntimeError("R2 unreachable")

        monkeypatch.setattr(api.storage_service, "upload_asset", boom)
        created = _upload(api, profile["id"], "portrait.jpg", _photo(api, tmp_root))
        assert Path(created["file_path"]).is_file()

    def test_the_object_key_is_namespaced_under_the_owner(self):
        assert storage_service._asset_key("user-1", "asset-1") == "user-1/assets/asset-1"


class TestServingRestoresFromTheCloud:
    def test_a_lost_local_copy_comes_back_and_serves(self, api, tmp_root, monkeypatch):
        profile = _profile(api, "Restore On Serve")
        created = _upload(api, profile["id"], "portrait.jpg", _photo(api, tmp_root))
        Path(created["file_path"]).unlink()
        calls = []
        _fake_restore_bytes(api, monkeypatch, PORTRAIT_BYTES, calls)

        response = _serve(api, created["id"])

        assert Path(response.path).is_file()
        assert Path(response.path).read_bytes() == PORTRAIT_BYTES
        assert calls == [(ANON, created["id"], Path(response.path))]
        row = _run(api._fetch_one("SELECT content_type FROM assets WHERE id = ?", (created["id"],)))
        assert response.media_type == (row.get("content_type") or "image/jpeg")

    def test_the_restore_rewrites_a_row_pointing_at_an_old_container(
        self, api, tmp_root, monkeypatch
    ):
        """The stored path names a disk that no longer exists; after the
        restore the row must name the file that does, or attach and
        generation — which read file_path directly — would still miss."""
        from models import now_iso
        profile = _profile(api, "Repointed Row")
        asset_id = str(uuid.uuid4())
        stale = tmp_root / "old-container" / f"{asset_id}.jpg"
        now = now_iso()
        _run(api._execute(
            """INSERT INTO assets
               (id, brand_profile_id, kind, name, file_path, rights_confirmed, status,
                created_at, updated_at, user_id)
               VALUES (?, ?, 'character_reference', 'portrait.jpg', ?, 1, 'active', ?, ?, ?)""",
            (asset_id, profile["id"], str(stale), now, now, ANON)))
        _fake_restore_bytes(api, monkeypatch, PORTRAIT_BYTES)

        restored = _run(api._ensure_asset_file(
            _run(api._fetch_one("SELECT * FROM assets WHERE id = ?", (asset_id,)))))

        assert restored is not None and restored.is_file()
        assert restored != stale
        row = _run(api._fetch_one("SELECT file_path FROM assets WHERE id = ?", (asset_id,)))
        assert row["file_path"] == str(restored)

    def test_serving_is_404_when_the_cloud_copy_is_gone(self, api, tmp_root, monkeypatch):
        profile = _profile(api, "Nothing To Restore")
        created = _upload(api, profile["id"], "portrait.jpg", _photo(api, tmp_root))
        Path(created["file_path"]).unlink()
        _fake_restore_fails(api, monkeypatch)
        with pytest.raises(HTTPException) as err:
            _serve(api, created["id"])
        assert err.value.status_code == 404

    def test_serving_is_404_without_touching_storage_when_it_is_unconfigured(
        self, api, tmp_root, monkeypatch
    ):
        profile = _profile(api, "No Storage Configured")
        created = _upload(api, profile["id"], "portrait.jpg", _photo(api, tmp_root))
        Path(created["file_path"]).unlink()
        monkeypatch.setattr(api.storage_service, "is_configured", lambda: False)
        calls = []
        monkeypatch.setattr(
            api.storage_service, "download_asset",
            lambda *args: calls.append(args) or True,
        )
        with pytest.raises(HTTPException) as err:
            _serve(api, created["id"])
        assert err.value.status_code == 404
        assert calls == []

    def test_an_intact_local_copy_never_touches_the_cloud(self, api, tmp_root, monkeypatch):
        profile = _profile(api, "Local Stays Local")
        created = _upload(api, profile["id"], "portrait.jpg", _photo(api, tmp_root))
        monkeypatch.setattr(api.storage_service, "is_configured", lambda: True)
        calls = []
        monkeypatch.setattr(
            api.storage_service, "download_asset",
            lambda *args: calls.append(args) or True,
        )
        response = _serve(api, created["id"])
        assert Path(response.path) == Path(created["file_path"])
        assert calls == []


class TestAttachingRestoresBeforeRefusing:
    def _attach(self, api, profile, asset_id):
        from models import AttachAssetRequest, CreateStudioProjectRequest
        template = _run(api.list_templates(user_id=ANON))["templates"][0]
        project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"], template_id=template["id"]), user_id=ANON))
        return _run(api.attach_asset_to_project(
            project_id=project["id"],
            payload=AttachAssetRequest(asset_id=asset_id),
            user_id=ANON,
        ))

    def test_attach_succeeds_after_a_restore(self, api, tmp_root, monkeypatch):
        profile = _profile(api, "Attach After Restore")
        created = _upload(api, profile["id"], "portrait.jpg", _photo(api, tmp_root))
        Path(created["file_path"]).unlink()
        _fake_restore_bytes(api, monkeypatch, PORTRAIT_BYTES)

        attached = self._attach(api, profile, created["id"])

        assert attached["assets"][-1]["asset_id"] == created["id"]
        assert Path(attached["assets"][-1]["file_path"]).is_file()

    def test_attach_still_refuses_when_there_is_nothing_to_restore(
        self, api, tmp_root, monkeypatch
    ):
        profile = _profile(api, "Attach With No File")
        created = _upload(api, profile["id"], "portrait.jpg", _photo(api, tmp_root))
        Path(created["file_path"]).unlink()
        _fake_restore_fails(api, monkeypatch)
        with pytest.raises(HTTPException) as err:
            self._attach(api, profile, created["id"])
        assert err.value.status_code == 409
        assert "missing on disk" in str(err.value.detail)


class TestGenerationRestoresTheReference:
    def _reference(self, api, asset_id, model_key="minimax-h3"):
        return _run(api._studio_identity_references(
            assets=[{"asset_id": asset_id, "kind": "character_reference",
                     "label": "Founder"}],
            model_key=model_key,
            user_id=ANON,
        ))

    def test_the_identity_pass_recovers_a_lost_photo(self, api, tmp_root, monkeypatch):
        profile = _profile(api, "Identity Restore")
        created = _upload(api, profile["id"], "portrait.jpg", _photo(api, tmp_root))
        Path(created["file_path"]).unlink()
        _fake_restore_bytes(api, monkeypatch, PORTRAIT_BYTES)

        reference = self._reference(api, created["id"])

        assert reference is not None and Path(reference).is_file()

    def test_the_identity_pass_still_refuses_with_nothing_to_restore(
        self, api, tmp_root, monkeypatch
    ):
        profile = _profile(api, "Identity Without File")
        created = _upload(api, profile["id"], "portrait.jpg", _photo(api, tmp_root))
        Path(created["file_path"]).unlink()
        _fake_restore_fails(api, monkeypatch)
        with pytest.raises(HTTPException) as err:
            self._reference(api, created["id"])
        assert err.value.status_code == 409
        assert "missing its file" in str(err.value.detail)


class TestDeletingRemovesTheDurableCopy:
    def test_delete_removes_the_r2_object(self, api, tmp_root, monkeypatch):
        profile = _profile(api, "Delete Durable")
        created = _upload(api, profile["id"], "portrait.jpg", _photo(api, tmp_root))
        calls = []
        monkeypatch.setattr(
            api.storage_service, "delete_asset",
            lambda user_id, asset_id: calls.append((user_id, asset_id)) or True,
        )
        response = _run(api.delete_asset(created["id"], ANON))
        assert response["deleted"] == created["id"]
        assert calls == [(ANON, created["id"])]


class TestTheStorageLayerContract:
    """The R2 layer's own behaviour: validation, and never raising for a
    service that is merely having a bad day."""

    def test_a_download_that_would_land_non_image_bytes_is_refused(self, monkeypatch, tmp_root):
        class Client:
            def download_file(self, bucket, key, filename):
                Path(filename).write_bytes(JUNK_BYTES)

        monkeypatch.setattr(storage_service, "_get_client", lambda: Client())
        target = tmp_root / "restored.jpg"
        assert storage_service.download_asset("u", "a", target) is False
        assert not target.exists()
        # No half-written temp left behind either.
        assert list(tmp_root.iterdir()) == []

    def test_a_download_of_a_real_image_installs_it(self, monkeypatch, tmp_root):
        class Client:
            def download_file(self, bucket, key, filename):
                Path(filename).write_bytes(PORTRAIT_BYTES)

        monkeypatch.setattr(storage_service, "_get_client", lambda: Client())
        target = tmp_root / "restored.jpg"
        assert storage_service.download_asset("u", "a", target) is True
        assert target.read_bytes() == PORTRAIT_BYTES
        assert list(tmp_root.iterdir()) == [target]

    def test_a_missing_object_is_false_not_a_crash(self, monkeypatch, tmp_root):
        class Client:
            def download_file(self, bucket, key, filename):
                raise ClientError(
                    {"Error": {"Code": "NoSuchKey", "Message": "gone"}}, "GetObject")

        monkeypatch.setattr(storage_service, "_get_client", lambda: Client())
        assert storage_service.download_asset("u", "a", tmp_root / "x.jpg") is False

    def test_an_upload_failure_returns_false_instead_of_raising(
        self, monkeypatch, tmp_root
    ):
        class Client:
            def upload_file(self, filename, bucket, key, ExtraArgs=None):
                raise ClientError(
                    {"Error": {"Code": "500", "Message": "boom"}}, "PutObject")

        monkeypatch.setattr(storage_service, "_get_client", lambda: Client())
        monkeypatch.setattr(storage_service, "is_configured", lambda: True)
        src = tmp_root / "portrait.jpg"
        src.write_bytes(PORTRAIT_BYTES)
        assert storage_service.upload_asset("u", "a", src) is False

    def test_upload_reports_the_image_content_type(self, monkeypatch, tmp_root):
        calls = []
        monkeypatch.setattr(
            storage_service, "_get_client", lambda: _client_capturing_upload(calls))
        monkeypatch.setattr(storage_service, "is_configured", lambda: True)
        src = tmp_root / "portrait.jpg"
        src.write_bytes(PORTRAIT_BYTES)
        assert storage_service.upload_asset("u", "a", src) is True
        assert calls[0]["extra"]["ContentType"] == "image/jpeg"
        assert calls[0]["key"] == "u/assets/a"
