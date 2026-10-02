"""
DB-backed tests for the asset library and overlay composition.

The cross-app guard is the important one: an asset from one app must never
be composited into another app's video. ffmpeg is invoked for real in the
render tests, because the overlay bugs found during development (orphaned
filter chains, a 600-second output) were invisible to string assertions.
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
            video_url, cost_usd, cost_source, created_at, updated_at, user_id)
           VALUES (?, ?, ?, ?, 12, 'completed', ?, 0.25, 'usage.cost', ?, ?, ?)""",
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
        assert created["media_url"].endswith(created["id"])
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


class TestOverlayCompositionGuard:
    def test_requires_a_completed_generation(self, api, tmp_root):
        from models import OverlayCompositionRequest, StudioGenerationRequest
        profile = _profile(api, "Overlay Pending")
        project = _project(api, profile)
        from models import now_iso
        gen_id = str(uuid.uuid4())
        now = now_iso()
        _run(api._execute(
            """INSERT INTO generations
               (id, studio_project_id, brand_profile_id, duration, status,
                created_at, updated_at, user_id)
               VALUES (?, ?, ?, 12, 'generating', ?, ?, ?)""",
            (gen_id, project["id"], profile["id"], now, now, ANON)))
        with pytest.raises(HTTPException) as err:
            _run(api.create_overlay_composition(
                gen_id, OverlayCompositionRequest(), ANON))
        assert err.value.status_code == 409
        del StudioGenerationRequest

    def test_blocked_claim_prevents_composition(self, api, tmp_root):
        from models import OverlayCompositionRequest
        profile = _profile(api, "Overlay Claim")
        gen, project = _completed_generation(api, profile, _make_base_clip(tmp_root / "bc1.mp4"))
        _run(api._execute(
            "UPDATE studio_projects SET safety_report = ? WHERE id = ?",
            ('{"passed": false, "blocking": [{"claim": "cures anxiety"}]}', project["id"])))
        with pytest.raises(HTTPException) as err:
            _run(api.create_overlay_composition(
                gen["id"], OverlayCompositionRequest(), ANON))
        assert err.value.status_code == 409

    def test_cross_app_asset_is_reported_as_rejected(self, api, tmp_root):
        from models import OverlayCompositionRequest
        p1 = _profile(api, "Overlay Owner")
        p2 = _profile(api, "Overlay Foreign")
        gen, _ = _completed_generation(api, p1, _make_base_clip(tmp_root / "bc2.mp4"))
        foreign = _insert_asset(
            api, p2["id"], "screenshot", _make_image(tmp_root / "foreign.png"))
        result = _run(api.create_overlay_composition(
            gen["id"], OverlayCompositionRequest(asset_ids=[foreign["id"]]), ANON))
        reasons = [r["reason"] for r in result["rejected_assets"]]
        assert any("different App Profile" in r for r in reasons)
        # And it must not appear in the spec.
        row = _run(api._fetch_one(
            "SELECT spec FROM overlay_compositions WHERE id = ?", (result["id"],)))
        assert foreign["id"] not in (row["spec"] or "")

    def test_unknown_asset_is_reported_as_rejected(self, api, tmp_root):
        from models import OverlayCompositionRequest
        profile = _profile(api, "Overlay Unknown")
        gen, _ = _completed_generation(api, profile, _make_base_clip(tmp_root / "bc3.mp4"))
        result = _run(api.create_overlay_composition(
            gen["id"], OverlayCompositionRequest(asset_ids=[str(uuid.uuid4())]), ANON))
        assert any(r["reason"] == "not found" for r in result["rejected_assets"])

    def test_retired_project_attachment_is_refused(self, api, tmp_root):
        """
        Face-only product, hard-error choice: a project still holding a
        screenshot from before cannot compose until it is detached. The
        refusal names the rule instead of silently dropping the input.
        """
        from models import OverlayCompositionRequest
        profile = _profile(api, "Overlay Retired")
        gen, project = _completed_generation(api, profile, _make_base_clip(tmp_root / "bc4.mp4"))
        shot = _insert_asset(
            api, profile["id"], "screenshot", _make_image(tmp_root / "retired_shot.png"))
        _run(api._execute(
            "UPDATE studio_projects SET assets = ? WHERE id = ?",
            (json.dumps([{
                "asset_id": shot["id"], "kind": "screenshot",
                "label": "Old screenshot", "file_path": shot["file_path"],
            }]), project["id"])))
        with pytest.raises(HTTPException) as err:
            _run(api.create_overlay_composition(
                gen["id"], OverlayCompositionRequest(), ANON))
        assert err.value.status_code == 409
        assert "face-only" in str(err.value.detail)


class TestAudioAssets:
    """
    Audio uploads are gone — the voiceover/music pipeline has no input — but
    the attach-time audio validation still guards the API against callers
    passing audio options with the photograph.
    """

    def test_audio_options_are_rejected_for_the_photograph(self, api, tmp_root):
        from models import AttachAssetRequest
        profile = _profile(api, "Audio Image Guard")
        shot = _make_image(tmp_root / "audio-guard.png")
        asset = _insert_asset(api, profile["id"], "character_reference", shot)
        project = _project(api, profile)
        with pytest.raises(HTTPException) as err:
            _run(api.attach_asset_to_project(
                project_id=project["id"],
                payload=AttachAssetRequest(asset_id=asset["id"], audio_role="background"),
                user_id=ANON,
            ))
        assert err.value.status_code == 400
        assert "apply only to audio" in str(err.value.detail)

    def test_audio_role_and_gain_are_validated(self, api, tmp_root):
        from models import AttachAssetRequest
        profile = _profile(api, "Audio Validation")
        asset = _insert_asset(
            api, profile["id"], "character_reference", _make_image(tmp_root / "validate.png"))
        project = _project(api, profile)
        with pytest.raises(HTTPException) as err:
            _run(api.attach_asset_to_project(
                project_id=project["id"],
                payload=AttachAssetRequest(asset_id=asset["id"], audio_role="theme"),
                user_id=ANON,
            ))
        assert err.value.status_code == 400
        with pytest.raises(HTTPException) as err:
            _run(api.attach_asset_to_project(
                project_id=project["id"],
                payload=AttachAssetRequest(asset_id=asset["id"], audio_gain=99),
                user_id=ANON,
            ))
        assert err.value.status_code == 400

    def test_unconfirmed_rights_are_rejected_at_composition(self, api, tmp_root):
        from models import OverlayCompositionRequest
        profile = _profile(api, "Audio Rights")
        gen, project = _completed_generation(
            api, profile, _make_base_clip(tmp_root / "rights_base.mp4", seconds=6))
        face = _insert_asset(
            api, profile["id"], "character_reference",
            _make_image(tmp_root / "rights.png"))
        _run(api._execute(
            "UPDATE assets SET rights_confirmed = 0 WHERE id = ?", (face["id"],)))
        _run(api._execute(
            "UPDATE studio_projects SET assets = ? WHERE id = ?",
            (json.dumps([{
                "asset_id": face["id"], "kind": "character_reference",
                "label": "Founder face", "file_path": face["file_path"],
            }]), project["id"])))
        result = _run(api.create_overlay_composition(
            gen["id"], OverlayCompositionRequest(), ANON))
        assert any(r["reason"] == "rights unconfirmed" for r in result["rejected_assets"])

    def test_voiceover_mutes_generated_audio_in_its_window(self, api, tmp_root):
        import overlays
        voice = _make_tone(tmp_root / "voice.m4a", seconds=2)
        inputs, graph, warnings, output = overlays.build_audio_filter(
            {"audios": [{
                "path": str(voice), "start": 2, "end": 4,
                "role": "voiceover", "gain": 1.0,
            }]},
            duration=6,
            first_audio_index=1,
            base_has_audio=True,
        )
        assert warnings == []
        assert output == "outa"
        assert inputs == [str(voice)]
        assert "volume=0:enable='between(t,2.0,4.0)'" in graph
        assert "adelay=2000|2000" in graph


@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg not installed")
class TestOverlayRendering:
    """
    These render for real. The two worst bugs in this feature -- an orphaned
    filter chain, and a 600-second output from looped stills -- produced a
    successful exit code and a plausible-looking file, so only an actual
    render plus a duration check catches them.
    """

    def test_composition_produces_a_clip_of_the_right_length(self, api, tmp_root):
        from models import OverlayCompositionRequest
        profile = _profile(api, "Render Length")
        base = _make_base_clip(tmp_root / "len.mp4", seconds=12)
        gen, _ = _completed_generation(api, profile, base)
        shot = _insert_asset(
            api, profile["id"], "character_reference", _make_image(tmp_root / "len_shot.png"))
        _run(api._execute(
            "UPDATE studio_projects SET hook_line='Hi', script='A script.', cta='Try free' WHERE 1=1"
        ))
        result = _run(api.create_overlay_composition(
            gen["id"], OverlayCompositionRequest(asset_ids=[shot["id"]]), ANON))
        assert result["status"] == "completed", result.get("error")
        import overlays
        out = Path(_run(api._fetch_one(
            "SELECT output_path FROM overlay_compositions WHERE id = ?", (result["id"],))
        )["output_path"])
        assert out.is_file()
        # The looped-still bug produced a 600s file from a 12s base.
        assert abs(overlays.probe_duration(out) - 12.0) < 0.5

    def test_screen_recording_is_declared_as_an_input(self, api, tmp_root):
        """A video layer referenced but never given an -i fails the render."""
        import overlays
        base = _make_base_clip(tmp_root / "rec_base.mp4", seconds=12)
        rec = _make_clip(tmp_root / "rec_src.mp4", seconds=6)
        spec = {
            "captions": [{"start": 0, "end": 3, "text": "Watch"}],
            "images": [],
            "videos": [{"path": str(rec), "start": 3, "end": 9, "kind": "screen_recording"}],
        }
        _, inputs, _ = overlays.build_filter_graph(spec, 12, overlays.resolve_font())
        assert str(rec) in inputs

    def test_full_render_with_captions_and_no_end_card(self, api, tmp_root):
        """
        Was `test_full_render_with_caption_and_end_card`.

        The composition still renders a real caption over real footage, and it
        must STILL render with no end card even though the project row carries a
        populated `cta` column — the column survives in the schema for rows
        written before a call to action stopped being generated, so this is the
        end-to-end proof that a stale one cannot become a generated close burnt
        into a file the founder already recorded their own CTA for.

        A caller may still send `end_card_text` (the schema accepts it for
        compatibility); what matters is that it cannot put a close on the video,
        which is asserted last.
        """
        from models import OverlayCompositionRequest
        profile = _profile(api, "Render Full")
        base = _make_base_clip(tmp_root / "full_base.mp4", seconds=12)
        gen, project = _completed_generation(api, profile, base)
        _run(api._execute(
            """UPDATE studio_projects SET hook_line = 'Hi', script = 'A script.',
               cta = 'Try it free',
               overlays = ? WHERE id = ?""",
            ('[{"start":0,"end":3,"text":"Stop scrolling"}]', project["id"])))
        result = _run(api.create_overlay_composition(
            gen["id"], OverlayCompositionRequest(end_card_text="Try it free"), ANON))
        assert result["status"] == "completed", result.get("error")
        applied = result["applied"]
        assert applied["captions"] == 1
        assert applied["end_card"] is False

    def test_captions_can_be_suppressed(self, api, tmp_root):
        from models import OverlayCompositionRequest
        profile = _profile(api, "Render No Captions")
        base = _make_base_clip(tmp_root / "nocap_base.mp4", seconds=8)
        gen, project = _completed_generation(api, profile, base)
        _run(api._execute(
            """UPDATE studio_projects SET hook_line='Hi', script='S.',
               overlays = ? WHERE id = ?""",
            ('[{"start":0,"end":3,"text":"Nope"}]', project["id"])))
        result = _run(api.create_overlay_composition(
            gen["id"], OverlayCompositionRequest(include_captions=False), ANON))
        assert result["status"] == "completed", result.get("error")
        assert result["applied"]["captions"] == 0

    def test_missing_font_fails_softly_and_keeps_the_video(self, api, tmp_root, monkeypatch):
        """
        Losing an overlay must never lose the video. With no font the text
        layers are skipped, the render is reported failed, and the generation
        itself is untouched.
        """
        import overlays
        from models import OverlayCompositionRequest
        monkeypatch.setattr(overlays, "resolve_font", lambda: None)
        profile = _profile(api, "Render No Font")
        base = _make_base_clip(tmp_root / "nofont_base.mp4", seconds=8)
        gen, project = _completed_generation(api, profile, base)
        _run(api._execute(
            """UPDATE studio_projects SET hook_line='Hi', script='S.',
               overlays = ? WHERE id = ?""",
            ('[{"start":0,"end":3,"text":"Text"}]', project["id"])))
        result = _run(api.create_overlay_composition(
            gen["id"], OverlayCompositionRequest(), ANON))
        assert result["status"] == "failed"
        # The generation still exists and still has its own clip.
        still_there = _run(api.get_generation(gen["id"], ANON))
        assert still_there["status"] == "completed"
        assert Path(api.pipeline.VIDEOS_DIR / f"{gen['id']}.mp4").is_file()

    def test_composition_can_be_fetched(self, api, tmp_root):
        from models import OverlayCompositionRequest
        profile = _profile(api, "Render Fetch")
        base = _make_base_clip(tmp_root / "fetch_base.mp4", seconds=8)
        gen, _ = _completed_generation(api, profile, base)
        _run(api.create_overlay_composition(gen["id"], OverlayCompositionRequest(), ANON))
        fetched = _run(api.get_overlay_composition(gen["id"], ANON))
        assert fetched["composition"] is not None
        assert fetched["composition"]["status"] in ("completed", "failed")

    def test_no_composition_returns_none(self, api, tmp_root):
        profile = _profile(api, "Render None")
        gen, _ = _completed_generation(
            api, profile, _make_base_clip(tmp_root / "none.mp4", seconds=4))
        assert _run(api.get_overlay_composition(gen["id"], ANON))["composition"] is None
