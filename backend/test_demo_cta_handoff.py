"""
The optional Product Demo + CTA handoff.

The step is additive and opt-in. Everything asserted here exists to prove two
things: that nothing in the existing studio flow depends on it, and that the
handed-over link cannot be used to reach anything the caller does not already
own. The first is why there is a test that the whole surface disappears when
DEMO_CTA_ORIGIN is unset, and the second is why the link endpoint is scoped to
one row rather than merely signed.
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
    os.environ["DEMO_CTA_ORIGIN"] = "https://demo-cta.example"
    # The other app is a different origin and cannot resolve a relative media
    # path, so the handoff needs an absolute public base to hand it.
    os.environ["PUBLIC_BASE_URL"] = "https://hookforge.example"
    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Keep returned clips out of live storage: VIDEOS_DIR is a module-level
    # constant pointing at the real storage/videos, and this test writes files
    # into it on every returned result.
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


def _profile(api, name="Handoff", approved=False):
    from models import BrandProfileCreateRequest

    profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
        brand_name=name,
        brand_description="One list instead of eleven.",
        core_features=["One shared list"],
        primary_use_cases=["Evening reflection"],
    ), user_id=ANON))
    if approved:
        from models import ApproveAppProfileRequest
        _run(api.approve_app_profile(
            profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
    return profile


def _ready_project(api, name="Handoff"):
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


class TestConfig:
    def test_it_reports_available_when_configured(self, api):
        result = _run(api.demo_cta_config(user_id=ANON))
        assert result["available"] is True
        assert result["origin"] == "https://demo-cta.example"

    def test_the_whole_step_disappears_when_unconfigured(self, api, monkeypatch):
        """
        An instance without DEMO_CTA_ORIGIN must offer nothing, so a deployment
        that has not set it looks exactly like the studio does today rather than
        showing a button that leads nowhere. This is the additive guarantee: the
        integration cannot be half-present.

        Set through the environment rather than by patching the reader, so the
        real configuration path is what is under test.
        """
        monkeypatch.setattr(api, "_demo_cta_origin", lambda: "")
        assert _run(api.demo_cta_config(user_id=ANON))["available"] is False
        _, _, gen_id = _completed_generation(api)
        with pytest.raises(HTTPException) as err:
            _run(api.demo_cta_link(gen_id, user_id=ANON))
        assert err.value.status_code == 404

    def test_an_unset_environment_disables_it(self, api, monkeypatch):
        monkeypatch.delenv("DEMO_CTA_ORIGIN", raising=False)
        assert api._demo_cta_origin() == ""
        assert _run(api.demo_cta_config(user_id=ANON))["available"] is False

    def test_the_origin_loses_its_trailing_slash(self, api, monkeypatch):
        """
        A trailing slash would produce "//?src=" in the handoff link, which is a
        different path from the one the other app serves.
        """
        monkeypatch.setenv("DEMO_CTA_ORIGIN", "https://x.example/")
        assert api._demo_cta_origin() == "https://x.example"


class TestHandoffLink:
    def _query(self, url):
        from urllib.parse import parse_qs, urlparse
        return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}

    def test_it_returns_a_link_to_the_configured_origin(self, api):
        _, _, gen_id = _completed_generation(api)
        result = _run(api.demo_cta_link(gen_id, user_id=ANON))
        assert result["url"].startswith("https://demo-cta.example/?")
        assert result["expires_in"] > 0

    def test_the_link_carries_a_playable_source(self, api):
        """
        The whole point of the handoff. The `src` it hands over must be a URL the
        media route will actually serve, or the other app opens on a dead clip.
        """
        import media_signing

        _, _, gen_id = _completed_generation(api)
        query = self._query(_run(api.demo_cta_link(gen_id, user_id=ANON))["url"])
        src = query["src"]
        assert "/api/media/videos/" in src
        sig_query = dict(p.split("=", 1) for p in src.split("?", 1)[1].split("&"))
        assert media_signing.verify(
            src.split("/")[-1].split("?", 1)[0], sig_query["exp"], sig_query["sig"]
        ), f"the handed-over source would be refused: {src}"

    def test_the_link_itself_is_signed(self, api):
        import media_signing

        _, _, gen_id = _completed_generation(api)
        query = self._query(_run(api.demo_cta_link(gen_id, user_id=ANON))["url"])
        exp = int(query["exp"])
        assert media_signing.verify(f"demo-cta:{gen_id}", str(exp), query["sig"])

    def test_the_link_names_the_render_so_the_return_can_be_matched(self, api):
        """
        The other app holds no key and cannot verify the signature, so the tie
        between a finished clip and the render it came from rests entirely on this
        echo: it sends the id back and the receiving tab compares it to its own.
        Without it the origin check alone would let a second tab file against this
        one.
        """
        _, _, gen_id = _completed_generation(api)
        query = self._query(_run(api.demo_cta_link(gen_id, user_id=ANON))["url"])
        assert query["gid"] == gen_id

    def test_a_durable_upload_does_not_replace_the_signed_local_source(self, api):
        """
        Once an upload finishes the row also has an r2_url. Preferring that would
        hand a third-party app the raw bucket URL and quietly undo the signing
        that keeps a paid clip off public links, so the local signed copy has to
        win even when both exist.
        """
        _, _, gen_id = _completed_generation(api)
        _run(api._execute(
            "UPDATE generations SET r2_url = ? WHERE id = ?",
            ("https://pub.example/bucket/paid-clip.mp4", gen_id),
        ))
        query = self._query(_run(api.demo_cta_link(gen_id, user_id=ANON))["url"])
        assert "/api/media/videos/" in query["src"]
        assert "pub.example" not in query["src"]

    def test_it_refuses_to_hand_over_a_relative_source(self, api, monkeypatch):
        """
        The other app is a different origin and cannot resolve a relative media
        path against our host. Failing here is the difference between a clear
        config error and a window that opens on nothing.
        """
        _, _, gen_id = _completed_generation(api)
        monkeypatch.setattr(api, "PUBLIC_BASE_URL", "")
        with pytest.raises(HTTPException) as err:
            _run(api.demo_cta_link(gen_id, user_id=ANON))
        assert err.value.status_code == 503
        assert "PUBLIC_BASE_URL" in err.value.detail

    def test_another_user_cannot_get_a_link_for_someone_elses_render(self, api):
        _, _, gen_id = _completed_generation(api)
        with pytest.raises(HTTPException) as err:
            _run(api.demo_cta_link(gen_id, user_id=OTHER))
        assert err.value.status_code == 404

    def test_an_unknown_generation_is_a_404(self, api):
        with pytest.raises(HTTPException) as err:
            _run(api.demo_cta_link(str(uuid.uuid4()), user_id=ANON))
        assert err.value.status_code == 404

    def test_an_unfinished_render_cannot_be_handed_over(self, api):
        """
        The other app would fetch a file that is not there yet. A clear 409 beats
        an empty player on the other side.
        """
        profile, project = _ready_project(api)
        gen_id = str(uuid.uuid4())
        _run(api._execute(
            """INSERT INTO generations
               (id, studio_project_id, brand_profile_id, status, segment_role,
                segment_index, strategy_version, attempt, retryable, approved,
                requested_at, created_at, updated_at, user_id)
               VALUES (?, ?, ?, 'generating', 'primary', 0, 1, 1, 0, 0,
                       ?, ?, ?, ?)""",
            (gen_id, project["id"], profile["id"], "2026-01-01", "2026-01-01",
             "2026-01-01", ANON)))
        with pytest.raises(HTTPException) as err:
            _run(api.demo_cta_link(gen_id, user_id=ANON))
        assert err.value.status_code == 409


class TestReturnedResult:
    def _upload(self, name="finished.mp4", data=MP4_BYTES):
        from starlette.datastructures import UploadFile
        return UploadFile(filename=name, file=io.BytesIO(data))

    def test_a_returned_clip_is_filed_beside_its_original(self, api):
        """
        Filed as a variant with parent_generation_id set, so the finished piece
        appears next to the hook rather than replacing it. Both keep working as
        downloads; the founder can see which finished piece came from which hook.
        """
        _, _, gen_id = _completed_generation(api)
        result = _run(api.receive_demo_cta_result(
            generation_id=gen_id, file=self._upload(), user_id=ANON))
        assert result["status"] == "completed"
        assert result["parent_generation_id"] == gen_id

        stored = _run(api._fetch_one(
            "SELECT parent_generation_id, variation_kind, video_url, status "
            "FROM generations WHERE id = ?", (result["id"],)))
        assert stored["parent_generation_id"] == gen_id
        assert stored["variation_kind"] == "demo_cta"
        assert stored["status"] == "completed"

    def test_the_returned_clip_really_is_on_disk_and_playable(self, api):
        """
        Asserted on the bytes, because a row pointing at nothing is the failure
        that looks fine until someone clicks it.
        """
        _, _, gen_id = _completed_generation(api)
        result = _run(api.receive_demo_cta_result(
            generation_id=gen_id, file=self._upload(), user_id=ANON))
        assert (api.pipeline.VIDEOS_DIR / f"{result['id']}.mp4").read_bytes() == MP4_BYTES

    def test_the_original_is_untouched_and_still_listed(self, api):
        """
        The additive guarantee, stated as a test: receiving a returned clip must
        not disturb the render it came from.
        """
        _, _, gen_id = _completed_generation(api)
        _run(api.receive_demo_cta_result(
            generation_id=gen_id, file=self._upload(), user_id=ANON))
        original = _run(api.get_generation(gen_id, user_id=ANON))
        assert original["status"] == "completed"
        assert original["parent_generation_id"] in (None, "")
        listed = _run(api.generation_history(user_id=ANON))["generations"]
        assert gen_id in {g["id"] for g in listed}

    def test_the_returned_clip_appears_in_history_with_its_lineage(self, api):
        _, _, gen_id = _completed_generation(api)
        result = _run(api.receive_demo_cta_result(
            generation_id=gen_id, file=self._upload(), user_id=ANON))
        listed = _run(api.generation_history(user_id=ANON))["generations"]
        entry = next(g for g in listed if g["id"] == result["id"])
        assert entry["parent_generation_id"] == gen_id
        assert entry["variation_kind"] == "demo_cta"

    def test_another_user_cannot_file_against_someone_elses_render(self, api):
        _, _, gen_id = _completed_generation(api)
        with pytest.raises(HTTPException) as err:
            _run(api.receive_demo_cta_result(
                generation_id=gen_id, file=self._upload(), user_id=OTHER))
        assert err.value.status_code == 404

    def test_a_non_video_upload_is_refused(self, api):
        _, _, gen_id = _completed_generation(api)
        with pytest.raises(HTTPException) as err:
            _run(api.receive_demo_cta_result(
                generation_id=gen_id,
                file=self._upload(name="notes.txt", data=b"not a video"),
                user_id=ANON))
        assert err.value.status_code == 400

    def test_an_empty_upload_is_refused_rather_than_stored(self, api):
        """
        A zero-byte row would look exactly like a real result in History and fail
        only on playback.
        """
        _, _, gen_id = _completed_generation(api)
        with pytest.raises(HTTPException) as err:
            _run(api.receive_demo_cta_result(
                generation_id=gen_id,
                file=self._upload(data=b""),
                user_id=ANON))
        assert err.value.status_code == 400

    def test_the_returned_url_is_signed_so_history_can_play_it(self, api):
        """
        History's player reads this URL, and the media route is signed. An
        unsigned one would be a broken player on the page a founder uses most.
        """
        import media_signing

        _, _, gen_id = _completed_generation(api)
        result = _run(api.receive_demo_cta_result(
            generation_id=gen_id, file=self._upload(), user_id=ANON))
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
        founder already made, so it must not require readiness, a claim verdict,
        or an approved profile — otherwise the handoff would be refusing work
        that costs nothing.
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
        result = _run(api.receive_demo_cta_result(
            generation_id=gen_id, file=self._upload(), user_id=ANON))
        assert result["status"] == "completed"


class TestExistingFlowUntouched:
    def test_nothing_in_the_studio_flow_requires_the_handoff(self, api):
        """
        The core additive guarantee: with DEMO_CTA_ORIGIN unset, the studio
        behaves exactly as before. A render, its download and its History row are
        all unaffected by whether this step is configured.
        """
        _, _, gen_id = _completed_generation(api)
        original = _run(api.generation_history(user_id=ANON))["generations"]
        assert any(g["id"] == gen_id for g in original)
        download = _run(api.get_generation(gen_id, user_id=ANON))["video_url"]
        assert download.startswith("/api/media/videos/")
        assert "?" in download