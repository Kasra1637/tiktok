"""
The native Product Demo + CTA export.

The editor lives inside HookForge, so there is no handoff: no config endpoint,
no outbound link, no origin. What remains is the save path — a finished export
posted from the same origin, filed as a child generation beside the original.
Everything asserted here is about that contract: the original is untouched, the
export is really on disk, History shows it with its lineage, and only the
owner of the parent can file one.
"""
import asyncio
import importlib
import io
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

ANON = "anonymous"
OTHER = "someone-else"

MP4_BYTES = bytes(range(256)) * 8


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-demo-cta-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""
    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Keep exported clips out of live storage: VIDEOS_DIR is a module-level
    # constant pointing at the real storage/videos, and this test writes files
    # into it on every export.
    server.pipeline.VIDEOS_DIR = Path(tmpdir) / "videos"
    server.pipeline.GENERATED_DIR = Path(tmpdir) / "generated"
    server.pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    server.pipeline.GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    asyncio.run(server.init_db())
    try:
        yield server
    finally:
        sys.modules.pop("server", None)


def _run(coro):
    return asyncio.run(coro)


def _profile(api, name="Export", approved=False):
    from models import BrandProfileCreateRequest

    profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
        brand_name=name,
        brand_description="One list instead of eleven.",
        core_features=["One shared list"],
        primary_use_cases=["Evening reflection"],
        outcome_statements=[{
            "outcome": "One list instead of eleven",
            "who_feels_it": "people juggling lists",
            "from_feature": "One shared list",
            "how_it_helps": "Everything lands in one place so nothing needs reconciling",
        }],
    ), user_id=ANON))
    if approved:
        from models import ApproveAppProfileRequest
        _run(api.approve_app_profile(
            profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
    return profile


def _ready_project(api, name="Export"):
    """An approved profile and a project on it.

    Approved because that is the real starting state: the studio refuses to plan
    a video from an unreviewed profile, so this is what any founder's render
    actually sits on top of.
    """
    from models import CreateStudioProjectRequest

    profile = _profile(api, name, approved=True)
    project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
        brand_profile_id=profile["id"]), user_id=ANON))
    return profile, project


def _completed_generation(api, user_id=ANON):
    """A finished generation with a real local media path on its row."""
    profile, project = _ready_project(api)
    gen_id = str(uuid.uuid4())
    api.pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    (api.pipeline.VIDEOS_DIR / f"{gen_id}.mp4").write_bytes(MP4_BYTES)
    _run(api._execute(
        """INSERT INTO generations
           (id, studio_project_id, brand_profile_id, status, segment_role,
            segment_index, requested_duration, duration, strategy_version, attempt,
            retryable, approved, requested_at, created_at, updated_at, user_id,
            video_url)
VALUES (?, ?, ?, 'completed', 'primary', 0, 10, 10, 1, 1, 0, 1,
                   ?, ?, ?, ?, ?)""",
        (gen_id, project["id"], profile["id"], "2026-01-01", "2026-01-01",
         "2026-01-01", ANON,
         f"/api/media/videos/{gen_id}.mp4")))
    return profile, project, gen_id


def _upload(name="hookforge-demo-cta.mp4", data=MP4_BYTES):
    from starlette.datastructures import UploadFile
    return UploadFile(filename=name, file=io.BytesIO(data))


class TestStandaloneExport:
    """
    The no-generation path: someone brings their own footage to the editor
    without rendering a Hook + Story first. Same save, same validation, same
    signed playback, no parent.
    """

    def test_a_standalone_export_is_saved_with_no_parent(self, api):
        result = _run(api.save_demo_cta_export(file=_upload(), user_id=ANON))
        assert result["status"] == "completed"

        stored = _run(api._fetch_one(
            "SELECT studio_project_id, brand_profile_id, template_id, "
            "status, video_url FROM generations WHERE id = ?",
            (result["id"],)))
        # Nothing to inherit, so nothing is invented. A row pointing at a project
        # it does not belong to would be worse than a null. parent_generation_id
        # used to be asserted here and went with the variations feature; the
        # inherited project linkage is what now stands in for "no parent", since
        # a standalone export has to invent all of it and cannot.
        assert stored["studio_project_id"] in (None, "")
        assert stored["brand_profile_id"] in (None, "")
        assert stored["template_id"] in (None, "")
        assert stored["status"] == "completed"
        assert stored["video_url"].startswith("/api/media/videos/")

    def test_a_standalone_export_is_on_disk_and_in_history(self, api):
        result = _run(api.save_demo_cta_export(file=_upload(), user_id=ANON))
        assert (api.pipeline.VIDEOS_DIR / f"{result['id']}.mp4").read_bytes() == MP4_BYTES
        listed = _run(api.generation_history(user_id=ANON))["generations"]
        assert any(g["id"] == result["id"] for g in listed)

    def test_a_standalone_export_still_validates_the_file(self, api):
        with pytest.raises(HTTPException) as err:
            _run(api.save_demo_cta_export(
                file=_upload(name="notes.txt", data=b"not a video"), user_id=ANON))
        assert err.value.status_code == 400
        with pytest.raises(HTTPException) as err:
            _run(api.save_demo_cta_export(file=_upload(data=b""), user_id=ANON))
        assert err.value.status_code == 400

    def test_a_standalone_export_is_still_signed_for_playback(self, api):
        import media_signing

        result = _run(api.save_demo_cta_export(file=_upload(), user_id=ANON))
        url = next(
            g["video_url"] for g in _run(api.generation_history(user_id=ANON))["generations"]
            if g["id"] == result["id"]
        )
        query = dict(p.split("=", 1) for p in url.split("?", 1)[1].split("&"))
        assert media_signing.verify(url.split("/")[-1].split("?", 1)[0], query["exp"], query["sig"])

    def test_an_unknown_parent_still_404s_rather_than_saving_orphaned(self, api):
        """
        Naming a parent that does not exist is a mistake, not a request for a
        standalone row: silently dropping the parent would hide it.
        """
        with pytest.raises(HTTPException) as err:
            _run(api.save_demo_cta_export(
                generation_id=str(uuid.uuid4()), file=_upload(), user_id=ANON))
        assert err.value.status_code == 404


class TestExportSaved:
    def test_an_export_is_filed_beside_its_original(self, api):
        """
        Filed as its own row that inherits the render's project, so the finished
        piece appears next to the hook rather than replacing it. Both keep
        working as downloads.

        The parent pointer this used to assert on (parent_generation_id) went
        with the variations feature, so lineage is now carried by the inherited
        studio_project_id and the export's own segment role. What must not come
        back is the ORIGINAL being disturbed, which is pinned separately.
        """
        profile, project, gen_id = _completed_generation(api)
        result = _run(api.save_demo_cta_export(
            generation_id=gen_id, file=_upload(), user_id=ANON))
        assert result["status"] == "completed"

        stored = _run(api._fetch_one(
            "SELECT studio_project_id, brand_profile_id, video_url, status "
            "FROM generations WHERE id = ?", (result["id"],)))
        assert stored["studio_project_id"] == project["id"]
        assert stored["brand_profile_id"] == profile["id"]
        assert stored["status"] == "completed"
        # Filed beside it, not in place of it.
        original = _run(api._fetch_one(
            "SELECT video_url, status FROM generations WHERE id = ?", (gen_id,)))
        assert original["status"] == "completed"
        assert original["video_url"] != stored["video_url"]

    def test_the_export_really_is_on_disk_and_playable(self, api):
        """
        Asserted on the bytes, because a row pointing at nothing is the failure
        that looks fine until someone clicks it.
        """
        _, _, gen_id = _completed_generation(api)
        result = _run(api.save_demo_cta_export(
            generation_id=gen_id, file=_upload(), user_id=ANON))
        assert (api.pipeline.VIDEOS_DIR / f"{result['id']}.mp4").read_bytes() == MP4_BYTES

    def test_a_webm_export_is_accepted(self, api):
        """The recorder falls back to WebM where MP4 is unsupported."""
        _, _, gen_id = _completed_generation(api)
        result = _run(api.save_demo_cta_export(
            generation_id=gen_id,
            file=_upload(name="hookforge-demo-cta.webm", data=MP4_BYTES),
            user_id=ANON))
        assert result["status"] == "completed"

    def test_an_export_is_marked_as_one_so_recovery_never_reaches_for_a_provider(self, api):
        """
        The native-export marker, asserted on the WRITER.

        Two guards read this value: provider_download_candidates returns nothing
        for a marked row, and recovery_report verdicts it unrecoverable with
        "re-export it in the editor". Both are only meaningful if some writer
        actually stores it.

        It did not. When the variations feature was retired, the marker moved
        from variation_kind to segment_role and the reader followed -- but the
        export writer kept inheriting the parent's segment_role, so no row was
        ever 'demo_cta' and both guards were dead while their own tests kept
        passing against a hand-built row. That gap is the reason this asserts
        the stored value rather than the consumer's behaviour.
        """
        _, _, gen_id = _completed_generation(api)
        result = _run(api.save_demo_cta_export(
            generation_id=gen_id, file=_upload(), user_id=ANON))
        stored = _run(api._fetch_one(
            "SELECT segment_role FROM generations WHERE id = ?", (result["id"],)))
        assert stored["segment_role"] == "demo_cta"

    def test_a_standalone_export_is_marked_too(self, api):
        """
        Unconditionally, including with no parent to inherit from: a standalone
        export has no provider rendition either, and is the clearest case of it.
        """
        result = _run(api.save_demo_cta_export(file=_upload(), user_id=ANON))
        stored = _run(api._fetch_one(
            "SELECT segment_role FROM generations WHERE id = ?", (result["id"],)))
        assert stored["segment_role"] == "demo_cta"
        # And the guard it feeds agrees.
        assert api.provider_download_candidates(
            {"segment_role": stored["segment_role"],
             "video_url": "https://cdn.example/stored.mp4"}) == []

    def test_the_original_is_untouched_and_still_listed(self, api):
        """
        The additive guarantee, stated as a test: saving an export must not
        disturb the render it came from.
        """
        _, _, gen_id = _completed_generation(api)
        _run(api.save_demo_cta_export(
            generation_id=gen_id, file=_upload(), user_id=ANON))
        original = _run(api.get_generation(gen_id, user_id=ANON))
        assert original["status"] == "completed"
        listed = _run(api.generation_history(user_id=ANON))["generations"]
        assert gen_id in {g["id"] for g in listed}

    def test_the_export_appears_in_history_alongside_its_original(self, api):
        """
        The additive guarantee, restated on the listing: both rows are in
        history at once.

        The lineage assertions this used to make (parent_generation_id,
        variation_kind) went with the variations feature. What replaces them is
        that the export inherits the original's project — so the two sit under
        the same studio project rather than the export appearing unattached.
        """
        _, project, gen_id = _completed_generation(api)
        result = _run(api.save_demo_cta_export(
            generation_id=gen_id, file=_upload(), user_id=ANON))
        listed = _run(api.generation_history(user_id=ANON))["generations"]
        ids = {g["id"] for g in listed}
        assert {gen_id, result["id"]} <= ids
        entry = next(g for g in listed if g["id"] == result["id"])
        assert entry["studio_project_id"] == project["id"]

    def test_another_user_cannot_file_against_someone_elses_render(self, api):
        _, _, gen_id = _completed_generation(api)
        with pytest.raises(HTTPException) as err:
            _run(api.save_demo_cta_export(
                generation_id=gen_id, file=_upload(), user_id=OTHER))
        assert err.value.status_code == 404

    def test_an_unknown_parent_is_a_404(self, api):
        with pytest.raises(HTTPException) as err:
            _run(api.save_demo_cta_export(
                generation_id=str(uuid.uuid4()), file=_upload(), user_id=ANON))
        assert err.value.status_code == 404

    def test_a_non_video_upload_is_refused(self, api):
        _, _, gen_id = _completed_generation(api)
        with pytest.raises(HTTPException) as err:
            _run(api.save_demo_cta_export(
                generation_id=gen_id,
                file=_upload(name="notes.txt", data=b"not a video"),
                user_id=ANON))
        assert err.value.status_code == 400

    def test_an_empty_upload_is_refused_rather_than_stored(self, api):
        """
        A zero-byte row would look exactly like a real export in History and fail
        only on playback.
        """
        _, _, gen_id = _completed_generation(api)
        with pytest.raises(HTTPException) as err:
            _run(api.save_demo_cta_export(
                generation_id=gen_id,
                file=_upload(data=b""),
                user_id=ANON))
        assert err.value.status_code == 400

    def test_the_export_url_is_signed_so_history_can_play_it(self, api):
        """
        History's player reads this URL, and the media route is signed. An
        unsigned one would be a broken player on the page a founder uses most.
        """
        import media_signing

        _, _, gen_id = _completed_generation(api)
        result = _run(api.save_demo_cta_export(
            generation_id=gen_id, file=_upload(), user_id=ANON))
        history_url = next(
            g["video_url"] for g in _run(api.generation_history(user_id=ANON))["generations"]
            if g["id"] == result["id"]
        )
        query = dict(p.split("=", 1) for p in history_url.split("?", 1)[1].split("&"))
        assert media_signing.verify(
            history_url.split("/")[-1].split("?", 1)[0], query["exp"], query["sig"]
        )

    def test_the_step_spends_nothing_and_needs_no_approval(self, api):
        """
        The three gates guard a paid model call. This path stores a file the
        founder already exported, so it must not require readiness, a claim
        verdict, or an approved profile — otherwise the editor would be refusing
        work that costs nothing.
        """
        profile = _profile(api, "No Gates Needed")
        assert profile.get("status") != "approved"
        gen_id = str(uuid.uuid4())
        _run(api._execute(
            """INSERT INTO generations
               (id, studio_project_id, brand_profile_id, status, segment_role,
                segment_index, strategy_version, attempt, retryable, approved,
                requested_at, created_at, updated_at, user_id, video_url)
               VALUES (?, ?, ?, 'completed', 'primary', 0, 1, 1, 0, 0,
                       ?, ?, ?, ?, ?)""",
            (gen_id, "any-project", profile["id"], "2026-01-01", "2026-01-01",
             "2026-01-01", ANON,
             f"/api/media/videos/{gen_id}.mp4")))
        result = _run(api.save_demo_cta_export(
            generation_id=gen_id, file=_upload(), user_id=ANON))
        assert result["status"] == "completed"


class TestExistingFlowUntouched:
    def test_nothing_in_the_studio_flow_depends_on_the_editor(self, api):
        """
        A render, its download and its History row are all unaffected by whether
        anyone ever opens the Demo + CTA editor.
        """
        _, _, gen_id = _completed_generation(api)
        original = _run(api.generation_history(user_id=ANON))["generations"]
        assert any(g["id"] == gen_id for g in original)
        download = _run(api.get_generation(gen_id, user_id=ANON))["video_url"]
        assert download.startswith("/api/media/videos/")
        assert "?" in download
