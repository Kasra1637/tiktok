"""
DB-backed tests for the asset library.

The cross-app guard is the important one: an asset from one app must never
leak into another app's video.
"""
import asyncio
import importlib
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

ANON = "anonymous"
OTHER_USER = "other-user"

HAS_FFMPEG = bool(shutil_which := __import__("shutil").which("ffmpeg"))


def _ffmpeg_available() -> bool:
    return shutil_which is not None


def _run(coro):
    return asyncio.run(coro)


def _make_image(path: Path, color="0x6A3FC0", size="600x1200") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", f"color=c={color}:s={size}:d=1",
        "-frames:v", "1", str(path),
    ], check=True, capture_output=True)
    return path


def _make_clip(path: Path, seconds=6, color="0x111111") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", f"color=c={color}:s=540x960:rate=30:duration={seconds}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path),
    ], check=True, capture_output=True)
    return path


def _make_base_clip(path: Path, seconds=12) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", f"testsrc=size=720x1280:rate=30:duration={seconds}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path),
    ], check=True, capture_output=True)
    return path


def _make_base_clip_with_audio(path: Path, seconds=6, frequency=220) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", f"testsrc=size=720x1280:rate=30:duration={seconds}",
        "-f", "lavfi", "-i", f"sine=frequency={frequency}:duration={seconds}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", str(path),
    ], check=True, capture_output=True)
    return path


def _make_tone(path: Path, seconds=3, frequency=440) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", f"sine=frequency={frequency}:duration={seconds}",
        "-c:a", "aac", str(path),
    ], check=True, capture_output=True)
    return path


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-p6-")
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
    server.pipeline.VIDEOS_DIR = Path(tmpdir) / "videos"
    server.pipeline.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    server.pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    asyncio.run(server.init_db())
    yield server
    sys.modules.pop("server", None)


@pytest.fixture(scope="module")
def tmp_root():
    return Path(tempfile.mkdtemp(prefix="tiktok-p6-files-"))


def _profile(api, name="Asset App"):
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


def _insert_asset(api, profile_id, kind, file_path, name="a.png", user_id=ANON):
    asset_id = str(uuid.uuid4())
    from models import now_iso
    now = now_iso()
    _run(api._execute(
        """INSERT INTO assets
           (id, brand_profile_id, kind, name, file_path, rights_confirmed, status,
            created_at, updated_at, user_id)
           VALUES (?, ?, ?, ?, ?, 1, 'active', ?, ?, ?)""",
        (asset_id, profile_id, kind, name, str(file_path), now, now, user_id)))
    return _run(api._fetch_one("SELECT * FROM assets WHERE id = ?", (asset_id,)))


def _project(api, profile):
    from models import CreateStudioProjectRequest
    template = _run(api.list_templates(user_id=ANON))["templates"][0]
    p = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
        brand_profile_id=profile["id"], template_id=template["id"]), user_id=ANON))
    return _run(api.get_studio_project(p["id"], ANON))


def _completed_generation(api, profile, base_clip: Path):
    """A generation row marked completed with a real clip on disk."""
    from models import now_iso
    gen_id = str(uuid.uuid4())
    project = _project(api, profile)
    target = api.pipeline.VIDEOS_DIR / f"{gen_id}.mp4"
    target.write_bytes(base_clip.read_bytes())
    now = now_iso()
    _run(api._execute(
        """INSERT INTO generations
           (id, studio_project_id, brand_profile_id, template_id, duration, status,
            video_url, created_at, updated_at, user_id)
           VALUES (?, ?, ?, ?, 12, 'completed', ?, ?, ?, ?)""",
        (gen_id, project["id"], profile["id"], project["template_id"],
         f"/api/media/videos/{gen_id}.mp4", now, now, ANON)))
    return _run(api.get_generation(gen_id, ANON)), project


def _upload(api, profile_id, kind, filename, src: Path, user_id=ANON, **kwargs):
    """Call upload_asset with plain values (Form defaults are Form objects)."""
    from fastapi import UploadFile
    with open(src, "rb") as fh:
        return _run(api.upload_asset(
            profile_id=profile_id,
            kind=kind,
            file=UploadFile(filename=filename, file=fh),
            label=kwargs.get("label", ""),
            notes=kwargs.get("notes", ""),
            rights_confirmed=kwargs.get("rights_confirmed", False),
            user_id=user_id,
        ))


class TestAssetLibrary:
    def test_upload_rejects_video_extension_declared_as_a_photo(self, api, tmp_root):
        """A .mp4 declared as the character reference would feed the wrong input."""
        profile = _profile(api, "Ext Check")
        src = _make_clip(tmp_root / "clip.mp4", seconds=1)
        with pytest.raises(HTTPException) as err:
            _upload(api, profile["id"], "character_reference", "clip.mp4", src)
        assert err.value.status_code == 400
        assert ".png" in str(err.value.detail)

    def test_upload_rejects_a_retired_kind(self, api, tmp_root):
        """
        Face-only product: screenshots, recordings, logos, photos, and audio
        are refused at the door — the pipeline that consumed them is gone.
        """
        profile = _profile(api, "Retired Kind")
        src = _make_image(tmp_root / "shot.png")
        for kind in ("screenshot", "screen_recording", "logo", "audio", "nonsense"):
            with pytest.raises(HTTPException) as err:
                _upload(api, profile["id"], kind, "shot.png", src)
            assert err.value.status_code == 400
            assert "Only the character reference" in str(err.value.detail)

    def test_upload_rejects_empty_file(self, api, tmp_root):
        profile = _profile(api, "Empty Asset")
        empty = tmp_root / "empty.png"
        empty.write_bytes(b"")
        with pytest.raises(HTTPException) as err:
            _upload(api, profile["id"], "character_reference", "empty.png", empty)
        assert err.value.status_code == 400

    def test_upload_stores_file_and_row(self, api, tmp_root):
        profile = _profile(api, "Upload OK")
        src = _make_image(tmp_root / "shot.png")
        created = _upload(api, profile["id"], "character_reference", "shot.png", src,
                          label="Founder face")
        assert created["kind"] == "character_reference"
        assert Path(created["file_path"]).is_file()
        assert created["media_url"].startswith(f"/api/media/assets/{created['id']}")
        assert created["label"] == "Founder face"
        # Stored under this profile's own folder.
        assert profile["id"] in created["file_path"]

    def test_upload_warns_when_no_face_detected(self, api, tmp_root):
        """
        Pre-flight check: a solid-color upload has no face, and the
        provider's privacy filter fires on exactly such photos. The upload
        still succeeds (the detector can be wrong) but says so.
        """
        profile = _profile(api, "Faceless Upload")
        src = _make_image(tmp_root / "faceless.png")
        created = _upload(api, profile["id"], "character_reference", "faceless.png", src)
        assert created["face_count"] == 0
        assert "No face detected" in created.get("face_warning", "")

    def test_upload_accepts_a_clear_face_quietly(self, api, tmp_root):
        import shutil
        profile = _profile(api, "Clear Face")
        src = tmp_root / "portrait.jpg"
        shutil.copy(BACKEND_DIR / "storage" / "samples" / "test_portrait.jpg", src)
        created = _upload(api, profile["id"], "character_reference", "portrait.jpg", src)
        assert created["face_count"] == 1
        assert "face_warning" not in created

    def test_listing_is_scoped_to_profile(self, api, tmp_root):
        p1 = _profile(api, "App One")
        p2 = _profile(api, "App Two")
        shot = _make_image(tmp_root / "shared.png")
        a1 = _insert_asset(api, p1["id"], "screenshot", shot)
        _insert_asset(api, p2["id"], "screenshot", shot)
        listed1 = _run(api.list_assets(profile_id=p1["id"], user_id=ANON))
        listed2 = _run(api.list_assets(profile_id=p2["id"], user_id=ANON))
        assert [a["id"] for a in listed1["assets"]] == [a1["id"]]
        assert a1["id"] not in [a["id"] for a in listed2["assets"]]

    def test_listing_filters_by_kind(self, api, tmp_root):
        profile = _profile(api, "Filter Kind")
        shot = _make_image(tmp_root / "f.png")
        face = _insert_asset(api, profile["id"], "character_reference", shot)
        _insert_asset(api, profile["id"], "screenshot", shot, name="legacy.png")
        listed = _run(api.list_assets(
            profile_id=profile["id"], kind="character_reference", user_id=ANON))
        assert [a["id"] for a in listed["assets"]] == [face["id"]]

    def test_another_users_profile_is_404(self, api):
        profile = _profile(api, "Private Assets")
        with pytest.raises(HTTPException) as err:
            _run(api.list_assets(profile_id=profile["id"], user_id=OTHER_USER))
        assert err.value.status_code == 404


class TestAssetUsageHistory:
    """
    The spec asks for asset usage history. An attachment is a snapshot stored
    on the project, not a foreign key, so detaching leaves the history intact —
    which is the behaviour worth pinning.
    """

    def _attach(self, api, profile, asset):
        from models import AttachAssetRequest
        project = _project(api, profile)
        _run(api.attach_asset_to_project(
            project_id=project["id"],
            payload=AttachAssetRequest(asset_id=asset["id"], start=0, end=5),
            user_id=ANON,
        ))
        return _run(api.get_studio_project(project["id"], ANON))

    def test_unused_asset_reports_zero(self, api, tmp_root):
        profile = _profile(api, "Unused Asset")
        shot = _make_image(tmp_root / "unused.png")
        asset = _insert_asset(api, profile["id"], "screenshot", shot)
        listed = _run(api.list_assets(profile_id=profile["id"], user_id=ANON))
        found = next(a for a in listed["assets"] if a["id"] == asset["id"])
        assert found["usage_count"] == 0
        assert found["used_in"] == []

    def test_attaching_records_the_project(self, api, tmp_root):
        profile = _profile(api, "Used Asset")
        shot = _make_image(tmp_root / "used.png")
        asset = _insert_asset(api, profile["id"], "character_reference", shot)
        self._attach(api, profile, asset)
        usage = _run(api.get_asset_usage(asset["id"], ANON))
        assert usage["usage_count"] == 1
        assert usage["used_in"][0]["status"] == "draft"

    def test_the_listing_carries_usage_too(self, api, tmp_root):
        """One index serves the whole page, so no per-asset lookup is needed."""
        profile = _profile(api, "List Usage")
        shot = _make_image(tmp_root / "listed.png")
        asset = _insert_asset(api, profile["id"], "character_reference", shot)
        self._attach(api, profile, asset)
        listed = _run(api.list_assets(profile_id=profile["id"], user_id=ANON))
        found = next(a for a in listed["assets"] if a["id"] == asset["id"])
        assert found["usage_count"] == 1

    def test_detaching_clears_current_usage(self, api, tmp_root):
        """
        Detach is a forward-looking edit: the founder is saying "stop using
        this here", so it must remove the project from the asset's usage. The
        record that must survive is deletion, not detachment.
        """
        profile = _profile(api, "Detach Clears")
        shot = _make_image(tmp_root / "detach.png")
        asset = _insert_asset(api, profile["id"], "character_reference", shot)
        project = self._attach(api, profile, asset)
        _run(api.detach_asset_from_project(
            project_id=project["id"], asset_id=asset["id"], user_id=ANON))
        assert _run(api.get_asset_usage(asset["id"], ANON))["usage_count"] == 0

    def test_the_project_keeps_its_record_after_the_asset_is_deleted(self, api, tmp_root):
        """
        Deleting the asset row does not rewrite the project, so a video that
        already shipped still shows what it was built from. This is the record
        that makes usage a history rather than a live join.
        """
        profile = _profile(api, "Delete Keeps Record")
        shot = _make_image(tmp_root / "keep.png")
        asset = _insert_asset(api, profile["id"], "character_reference", shot)
        project = self._attach(api, profile, asset)
        _run(api.delete_asset(asset["id"], ANON))
        after = _run(api.get_studio_project(project["id"], ANON))
        assert [a["asset_id"] for a in after["assets"]] == [asset["id"]]

    def test_usage_never_crosses_profiles(self, api, tmp_root):
        """
        The index is built per App Profile, so one app's project cannot show up
        in another app's asset history.
        """
        p1 = _profile(api, "Usage App One")
        p2 = _profile(api, "Usage App Two")
        shot = _make_image(tmp_root / "scoped.png")
        asset_one = _insert_asset(api, p1["id"], "character_reference", shot)
        self._attach(api, p2, _insert_asset(api, p2["id"], "character_reference", shot))
        assert _run(api.get_asset_usage(asset_one["id"], ANON))["usage_count"] == 0

    def test_another_users_asset_is_404(self, api, tmp_root):
        profile = _profile(api, "Private Usage")
        shot = _make_image(tmp_root / "private.png")
        asset = _insert_asset(api, profile["id"], "screenshot", shot)
        with pytest.raises(HTTPException) as err:
            _run(api.get_asset_usage(asset["id"], OTHER_USER))
        assert err.value.status_code == 404

    def test_deleting_a_used_asset_reports_the_orphaned_projects(self, api, tmp_root):
        """
        Deleting the file does not rewrite history, so the response has to say
        what is now broken rather than deleting quietly.
        """
        profile = _profile(api, "Delete Used")
        shot = _make_image(tmp_root / "del.png")
        asset = _insert_asset(api, profile["id"], "character_reference", shot)
        self._attach(api, profile, asset)
        result = _run(api.delete_asset(asset["id"], ANON))
        assert result["usage_count"] == 1
        assert "1 project" in result["note"]

    def test_deleting_an_unused_asset_warns_about_nothing(self, api, tmp_root):
        profile = _profile(api, "Delete Free")
        shot = _make_image(tmp_root / "free.png")
        asset = _insert_asset(api, profile["id"], "screenshot", shot)
        result = _run(api.delete_asset(asset["id"], ANON))
        assert result["usage_count"] == 0
        assert result["note"] is None

    def test_malformed_attachment_json_is_skipped(self, api, tmp_root):
        """
        A project whose assets column holds junk must not break the listing for
        every other asset in the profile.
        """
        from models import now_iso
        profile = _profile(api, "Bad JSON")
        shot = _make_image(tmp_root / "bad.png")
        asset = _insert_asset(api, profile["id"], "screenshot", shot)
        now = now_iso()
        project_id = str(uuid.uuid4())
        _run(api._execute(
            """INSERT INTO studio_projects
               (id, brand_profile_id, template_id, status, assets, script_version,
                duration_seconds, created_at, updated_at, user_id)
               VALUES (?, ?, ?, 'draft', ?, 0, 15, ?, ?, ?)""",
            (project_id, profile["id"], "tpl-bad", "not json", now, now, ANON)))
        listed = _run(api.list_assets(profile_id=profile["id"], user_id=ANON))
        found = next(a for a in listed["assets"] if a["id"] == asset["id"])
        assert found["usage_count"] == 0

    def test_an_attachment_entry_without_an_id_is_ignored(self, api, tmp_root):
        """A snapshot written before ids were recorded should not crash the index."""
        from models import UpdateStudioProjectRequest
        profile = _profile(api, "No Asset Id")
        shot = _make_image(tmp_root / "noid.png")
        asset = _insert_asset(api, profile["id"], "screenshot", shot)
        project = _project(api, profile)
        _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(assets=[{"kind": "screenshot", "file_path": "x"}]),
            user_id=ANON,
        ))
        assert _run(api.get_asset_usage(asset["id"], ANON))["usage_count"] == 0

    def test_archive_hides_from_default_listing(self, api, tmp_root):
        from models import UpdateAssetRequest
        profile = _profile(api, "Archive Asset")
        shot = _make_image(tmp_root / "ar.png")
        asset = _insert_asset(api, profile["id"], "screenshot", shot)
        _run(api.update_asset(
            asset_id=asset["id"],
            payload=UpdateAssetRequest(status="archived"), user_id=ANON))
        active = _run(api.list_assets(profile_id=profile["id"], user_id=ANON))
        assert asset["id"] not in [a["id"] for a in active["assets"]]
        with_archived = _run(api.list_assets(
            profile_id=profile["id"], include_archived=True, user_id=ANON))
        assert asset["id"] in [a["id"] for a in with_archived["assets"]]

    def test_delete_removes_row_and_file(self, api, tmp_root):
        """
        The file must live under the assets dir to be unlinked: delete_asset
        refuses to remove anything outside it, so a crafted file_path cannot
        delete arbitrary files.
        """
        profile = _profile(api, "Delete Asset")
        inside = api.pipeline.ASSETS_DIR / f"del-{uuid.uuid4().hex[:8]}.png"
        _make_image(inside)
        asset = _insert_asset(api, profile["id"], "screenshot", inside)
        assert inside.is_file()
        _run(api.delete_asset(asset["id"], ANON))
        assert not inside.is_file()
        remaining = _run(api.list_assets(
            profile_id=profile["id"], include_archived=True, user_id=ANON))
        assert asset["id"] not in [a["id"] for a in remaining["assets"]]

    def test_delete_keeps_files_outside_the_assets_dir(self, api, tmp_root):
        """Containment guard: a row pointing elsewhere must not delete it."""
        profile = _profile(api, "Delete Outside")
        outside = _make_image(tmp_root / "outside.png")
        asset = _insert_asset(api, profile["id"], "screenshot", outside)
        _run(api.delete_asset(asset["id"], ANON))
        assert outside.is_file()

    def test_another_user_cannot_touch_asset(self, api, tmp_root):
        profile = _profile(api, "Asset Isolation")
        shot = _make_image(tmp_root / "iso.png")
        asset = _insert_asset(api, profile["id"], "screenshot", shot)
        with pytest.raises(HTTPException) as err:
            _run(api.delete_asset(asset["id"], OTHER_USER))
        assert err.value.status_code == 404


class TestCrossAppGuard:
    def test_attaching_another_apps_asset_is_refused(self, api, tmp_root):
        """
        The core guard. One app's photograph must never anchor another
        app's video.
        """
        from models import AttachAssetRequest
        p1 = _profile(api, "Guard One")
        p2 = _profile(api, "Guard Two")
        shot = _make_image(tmp_root / "guard.png")
        foreign = _insert_asset(api, p2["id"], "screenshot", shot)
        project = _project(api, p1)
        with pytest.raises(HTTPException) as err:
            _run(api.attach_asset_to_project(
                project_id=project["id"],
                payload=AttachAssetRequest(asset_id=foreign["id"]),
                user_id=ANON))
        assert err.value.status_code == 400
        assert "different app" in str(err.value.detail)

    def test_own_asset_attaches(self, api, tmp_root):
        from models import AttachAssetRequest
        profile = _profile(api, "Attach Own")
        shot = _make_image(tmp_root / "own.png")
        own = _insert_asset(api, profile["id"], "character_reference", shot, name="Own")
        project = _project(api, profile)
        result = _run(api.attach_asset_to_project(
            project_id=project["id"],
            payload=AttachAssetRequest(asset_id=own["id"], start=2, end=8),
            user_id=ANON))
        assert len(result["assets"]) == 1
        assert result["assets"][0]["start"] == 2

    def test_attach_refuses_missing_file(self, api, tmp_root):
        from models import AttachAssetRequest
        profile = _profile(api, "Attach Missing")
        ghost = _insert_asset(api, profile["id"], "screenshot", tmp_root / "gone.png")
        project = _project(api, profile)
        with pytest.raises(HTTPException) as err:
            _run(api.attach_asset_to_project(
                project_id=project["id"],
                payload=AttachAssetRequest(asset_id=ghost["id"]), user_id=ANON))
        assert err.value.status_code == 409

    def test_detach_removes_from_project(self, api, tmp_root):
        from models import AttachAssetRequest
        profile = _profile(api, "Detach")
        shot = _make_image(tmp_root / "det.png")
        own = _insert_asset(api, profile["id"], "character_reference", shot)
        project = _project(api, profile)
        _run(api.attach_asset_to_project(
            project_id=project["id"],
            payload=AttachAssetRequest(asset_id=own["id"]), user_id=ANON))
        result = _run(api.detach_asset_from_project(project["id"], own["id"], ANON))
        assert result["assets"] == []

    def test_attaching_a_retired_kind_is_refused(self, api, tmp_root):
        """
        Face-only product: a screenshot sitting in the library from before
        can never join a project again. The refusal names the rule.
        """
        from models import AttachAssetRequest
        profile = _profile(api, "Retired Attach")
        shot = _make_image(tmp_root / "retired.png")
        old = _insert_asset(api, profile["id"], "screenshot", shot)
        project = _project(api, profile)
        with pytest.raises(HTTPException) as err:
            _run(api.attach_asset_to_project(
                project_id=project["id"],
                payload=AttachAssetRequest(asset_id=old["id"]),
                user_id=ANON))
        assert err.value.status_code == 400
        assert "Only the character reference" in str(err.value.detail)
