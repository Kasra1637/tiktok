"""
DB-backed tests for feedback, research, and operations.

The properties worth pinning: feedback reasons must belong to their event,
research drafts must be unpublished and must never carry a source reference,
and manual performance must never be reported as verified.
"""
import asyncio
import importlib
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

import mp4_samples  # noqa: E402

ANON = "anonymous"
OTHER_USER = "other-user"


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-p8-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""

    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Keep generated-file side effects inside the temp tree, not real storage.
    # STORAGE_DIR moves WITH them: in production VIDEOS_DIR and ASSETS_DIR are
    # always underneath it, and served_media_path() derives the /api/media URL
    # by taking a path relative to it. Repointing only the children used to make
    # that helper return None for every clip written here, so the local-serving
    # fallback could not be exercised without tripping the fixture.
    server.pipeline.STORAGE_DIR = Path(tmpdir) / "storage"
    server.pipeline.VIDEOS_DIR = server.pipeline.STORAGE_DIR / "videos"
    server.pipeline.ASSETS_DIR = server.pipeline.STORAGE_DIR / "assets"
    server.pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    server.pipeline.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    asyncio.run(server.init_db())
    yield server
    sys.modules.pop("server", None)


def _run(coro):
    return asyncio.run(coro)


async def _no_rescale(local_path):
    """A canvas rescale that is a no-op, so these tests need no real mp4."""
    return None, []


async def _forbid_rescale(local_path):
    raise AssertionError("an already-persisted clip must not be rewritten")


def _fake_mp4():
    """
    A finished, playable MP4 for the storage paths to accept.

    A REAL encode, not a byte string. The completeness check now walks the box
    chain and then asks ffprobe whether any video packets decode, and neither
    question can be answered truthfully about a file containing no video. The
    previous hand-assembled fixture -- an ftyp box, some zeros and a moov -- was
    exactly the kind of file that let the real bug through: it satisfied a
    4KB-window substring probe while sharing none of the properties that made a
    genuine render get rejected.

    The index is deliberately not at the front. See mp4_samples.
    """
    return mp4_samples.real_mp4()


def _profile(api, name):
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
    return p


def _generation(api, profile, status="completed", **overrides):
    from models import CreateStudioProjectRequest, now_iso
    template = _run(api.list_templates(user_id=ANON))["templates"][0]
    project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
        brand_profile_id=profile["id"], template_id=template["id"],
        objective=overrides.pop("objective", "demonstrate_feature")), user_id=ANON))
    gen_id = str(uuid.uuid4())
    now = now_iso()
    _run(api._execute(
        """INSERT INTO generations
           (id, studio_project_id, brand_profile_id, template_id, template_version,
             model, duration, status, attempt,
             created_at, updated_at, started_at, completed_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, 20, ?, ?, ?, ?, ?, ?, ?)""",
        (gen_id, project["id"], profile["id"], template["id"], template["version"],
         overrides.pop("model", "minimax-h3"), status,
         overrides.pop("attempt", 1),
         now, now, overrides.pop("started_at", now), overrides.pop("completed_at", now),
         ANON)))
    return _run(api.get_generation(gen_id, ANON))


class TestDeleteAppProfile:
    def test_delete_cascades_and_removes_profile(self, api):
        profile = _profile(api, "Cascade Target")
        _generation(api, profile, status="completed")
        from models import now_iso
        _run(api._execute(
            "INSERT INTO feedback_events (id, brand_profile_id, event, created_at, user_id)"
            " VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), profile["id"], "video_approved", now_iso(), ANON)))

        result = _run(api.delete_app_profile(profile["id"], user_id=ANON))
        assert result["deleted"] is True
        assert result["generations_removed"] == 1

        with pytest.raises(HTTPException) as err:
            _run(api.get_app_profile(profile["id"], user_id=ANON))
        assert err.value.status_code == 404

        for table in ("content_angles", "studio_projects", "generations",
                      "assets",
                      "feedback_events", "asset_events"):
            rows = _run(api._fetch_all(
                f"SELECT id FROM {table} WHERE brand_profile_id = ?",
                (profile["id"],)))
            assert rows == [], table

    def test_delete_is_404_for_unknown_profile(self, api):
        with pytest.raises(HTTPException) as err:
            _run(api.delete_app_profile(str(uuid.uuid4()), user_id=ANON))
        assert err.value.status_code == 404

    def test_delete_refused_while_generation_in_flight(self, api):
        profile = _profile(api, "In Flight")
        _generation(api, profile, status="generating")
        with pytest.raises(HTTPException) as err:
            _run(api.delete_app_profile(profile["id"], user_id=ANON))
        assert err.value.status_code == 409


class TestApproveAppProfile:
    def test_approve_commits_status_with_no_pending_proposal(self, api):
        # A freshly researched profile carries no pending_research: the status
        # flip must commit on its own, otherwise the approval looks successful
        # while the row stays a draft — and data appears to vanish on relogin.
        from models import BrandProfileCreateRequest, ApproveAppProfileRequest
        profile = _run(api.create_brand(
            payload=BrandProfileCreateRequest(
        brand_name="No Pending",
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
        assert profile["status"] == "draft"
        approved = _run(api.approve_app_profile(
            profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
        assert approved["status"] == "approved"
        assert approved["approved_at"] is not None
        reread = _run(api.get_app_profile(profile["id"], user_id=ANON))
        assert reread["status"] == "approved"

    def test_approve_without_applying_pending_still_approves(self, api):
        from models import ApproveAppProfileRequest
        profile = _profile(api, "Skip Pending")
        approved = _run(api.approve_app_profile(
            profile_id=profile["id"],
            payload=ApproveAppProfileRequest(apply_pending=False),
            user_id=ANON))
        assert approved["status"] == "approved"

    def test_approve_unknown_profile_is_404(self, api):
        from models import ApproveAppProfileRequest
        with pytest.raises(HTTPException) as err:
            _run(api.approve_app_profile(
                profile_id=str(uuid.uuid4()),
                payload=ApproveAppProfileRequest(), user_id=ANON))
        assert err.value.status_code == 404


class TestFeedbackCatalog:
    def test_catalog_lists_events_with_reasons(self, api):
        catalog = _run(api.feedback_catalog())
        assert len(catalog["events"]) == 6
        for event in catalog["events"]:
            # Thumbs verdicts are standalone: the component is the context, so
            # they carry no reason vocabulary by design.
            if event["key"] in ("thumb_up", "thumb_down"):
                assert event["reasons"] == []
            else:
                assert event["reasons"], event["key"]
        import feedback as fb
        assert catalog["components"] == ["goal", "template", "plan", "script", "video"]

    def test_catalog_has_no_video_level_verdicts(self, api):
        """The finished video is never rated; only its components are."""
        keys = {e["key"] for e in _run(api.feedback_catalog())["events"]}
        for retired in ("video_approved", "generation_rejected",
                        "marked_successful", "marked_unsuccessful"):
            assert retired not in keys

    def test_every_reason_has_a_label(self, api):
        import feedback as fb
        for reasons in fb.REASONS.values():
            for reason in reasons:
                assert reason in fb.REASON_LABELS, reason


class TestRecordFeedback:
    def test_records_a_valid_pair(self, api):
        from models import FeedbackRequest
        profile = _profile(api, "FB OK")
        created = _run(api.record_feedback(
            FeedbackRequest(event="video_regenerated", reason="pacing_too_slow",
                           brand_profile_id=profile["id"]), ANON))
        assert created["event"] == "video_regenerated"
        assert created["reason"] == "pacing_too_slow"

    def test_unknown_event_is_rejected(self, api):
        from models import FeedbackRequest
        with pytest.raises(HTTPException) as err:
            _run(api.record_feedback(FeedbackRequest(event="nonsense", reason="x"), ANON))
        assert err.value.status_code == 400

    def test_reason_must_belong_to_the_event(self, api):
        """
        'too_promotional' is valid for an edited script but not for a rejected
        generation. Allowing it would put codes in the table that nothing
        could group meaningfully.

        It was 'cta_unclear' here, which was itself removed: a generated piece
        has no closing beat, so "the CTA was unclear" described something the
        product never produced. The event-scoped rule it demonstrated is
        unchanged, and the retired reason is asserted gone below.
        """
        from models import FeedbackRequest
        with pytest.raises(HTTPException) as err:
            _run(api.record_feedback(
                FeedbackRequest(event="video_regenerated", reason="too_promotional"), ANON))
        assert err.value.status_code == 400

    def test_the_retired_cta_reason_stays_retired(self, api):
        """
        'cta_unclear' is refused as an unknown reason, not merely unused.

        It was a selectable reason on script edits while no CTA was ever
        generated, so a founder could explain a rejection with a fact about the
        video that could not be true. Anything already stored under the code
        still reads back through its stored value; what must not come back is
        the ability to record new events under it.
        """
        from models import FeedbackRequest
        with pytest.raises(HTTPException) as err:
            _run(api.record_feedback(
                FeedbackRequest(event="script_edited", reason="cta_unclear"), ANON))
        assert err.value.status_code == 400

    def test_event_with_neither_signal_nor_reason_is_rejected(self, api):
        """
        Feedback with no half at all says nothing. A reason alone is still
        required to be valid, but it may now be omitted when a signal is
        present, so this is the only bare case that must fail.
        """
        from models import FeedbackRequest
        with pytest.raises(HTTPException):
            _run(api.record_feedback(FeedbackRequest(event="video_regenerated"), ANON))

    def test_detail_is_stored_but_not_aggregated(self, api):
        from models import FeedbackRequest
        _run(api.record_feedback(
            FeedbackRequest(event="template_rejected", reason="hook_too_weak",
                           detail="felt flat"), ANON))
        listed = _run(api.list_feedback(user_id=ANON))
        assert any(f.get("detail") == "felt flat" for f in listed["feedback"])
        # Only fixed reasons are counted in the summary.
        assert all("reason" in r for r in listed["summary"]["top_reasons"])

    def test_thumb_up_on_a_component_is_recorded(self, api):
        from models import FeedbackRequest
        profile = _profile(api, "FB THUMB")
        created = _run(api.record_feedback(
            FeedbackRequest(event="thumb_up", step="plan",
                            brand_profile_id=profile["id"],
                            detail="plan v3"), ANON))
        assert created["event"] == "thumb_up"
        assert created["step"] == "plan"
        listed = _run(api.list_feedback(user_id=ANON))
        assert listed["components"]["plan"]["up"] >= 1

    def test_thumb_on_an_unknown_component_is_rejected(self, api):
        from models import FeedbackRequest
        with pytest.raises(HTTPException) as err:
            _run(api.record_feedback(
                FeedbackRequest(event="thumb_up", step="final_video"), ANON))
        assert err.value.status_code == 400

    def test_thumb_without_a_step_is_rejected(self, api):
        from models import FeedbackRequest
        with pytest.raises(HTTPException) as err:
            _run(api.record_feedback(FeedbackRequest(event="thumb_down"), ANON))
        assert err.value.status_code == 400

    def test_thumb_with_a_signal_is_rejected(self, api):
        from models import FeedbackRequest
        with pytest.raises(HTTPException) as err:
            _run(api.record_feedback(
                FeedbackRequest(event="thumb_up", step="plan", signal="downloaded"), ANON))
        assert err.value.status_code == 400

    def test_component_verdicts_never_mix_and_never_pollute_signals(self):
        import feedback as fb
        rows = [
            {"event": "thumb_up", "step": "plan"},
            {"event": "thumb_down", "step": "plan"},
            {"event": "thumb_up", "step": "script"},
            {"event": "thumb_down", "step": "goal"},
            {"event": "thumb_down", "step": "final_video"},
            {"event": "video_regenerated", "signal": "regenerated"},
        ]
        per = fb.summarize_component_feedback(rows)
        assert per["plan"] == {"up": 1, "down": 1, "total": 2}
        assert per["script"] == {"up": 1, "down": 0, "total": 1}
        assert per["goal"] == {"up": 0, "down": 1, "total": 1}
        assert per["template"] == {"up": 0, "down": 0, "total": 0}
        assert fb.summarize(rows)["top_signals"] == [{"signal": "regenerated", "count": 1}]
        # Thumbs never leak into the shared profile aggregate other stages read.
        assert fb.summarize_profile_feedback(rows)["total"] == 1

    def test_each_stage_prompt_only_names_its_own_component(self):
        import feedback as fb
        per = fb.summarize_component_feedback([
            {"event": "thumb_down", "step": "script"},
            {"event": "thumb_down", "step": "script"},
            {"event": "thumb_up", "step": "video"},
        ])
        script = fb.build_component_feedback_section(per, "script")
        plan = fb.build_component_feedback_section(per, "plan")
        video = fb.build_component_feedback_section(per, "video")
        assert "spoken script" in script and "2 thumbs down" in script
        assert "none recorded" in plan
        assert "generated video" in video and "1 thumbs up" in video
        assert fb.build_component_feedback_section(per, "unknown") == ""

    def test_listing_is_scoped_to_user(self, api):
        from models import FeedbackRequest
        _run(api.record_feedback(
            FeedbackRequest(event="video_downloaded", reason="ready_to_post"), ANON))
        assert _run(api.list_feedback(user_id=OTHER_USER))["feedback"] == []

    def test_summary_counts_events(self, api):
        from models import FeedbackRequest
        _run(api.record_feedback(
            FeedbackRequest(event="script_edited", reason="too_promotional"), ANON))
        _run(api.record_feedback(
            FeedbackRequest(event="script_edited", reason="too_promotional"), ANON))
        summary = _run(api.list_feedback(user_id=ANON))["summary"]
        assert summary["by_event"]["script_edited"] >= 2


class TestGenerationVerdicts:
    """
    Saved thumb votes ride on generation payloads so the UI can restore the
    highlighted state after a reload or a return visit — the vote itself
    already worked, this is purely the visual restore.
    """

    def _thumb(self, api, event, step, profile, generation):
        from models import FeedbackRequest
        return _run(api.record_feedback(FeedbackRequest(
            event=event, step=step,
            brand_profile_id=profile["id"],
            generation_id=generation["id"]), ANON))

    def test_history_detail_and_list_carry_saved_verdicts(self, api):
        profile = _profile(api, "Verdicts Ride Along")
        gen = _generation(api, profile, status="completed")
        self._thumb(api, "thumb_up", "video", profile, gen)
        self._thumb(api, "thumb_down", "plan", profile, gen)
        row = next(
            g for g in _run(api.generation_history(user_id=ANON))["generations"]
            if g["id"] == gen["id"])
        assert row["verdicts"] == {"video": 1, "plan": -1}
        assert _run(api.get_generation(gen["id"], ANON))["verdicts"] == {
            "video": 1, "plan": -1}
        listed = _run(api.list_generations(user_id=ANON))["generations"]
        assert next(
            g for g in listed if g["id"] == gen["id"])["verdicts"] == {
            "video": 1, "plan": -1}

    def test_latest_vote_wins_per_generation_and_component(self, api):
        profile = _profile(api, "Verdicts Latest Wins")
        gen = _generation(api, profile, status="completed")
        self._thumb(api, "thumb_down", "video", profile, gen)
        self._thumb(api, "thumb_up", "video", profile, gen)
        row = next(
            g for g in _run(api.generation_history(user_id=ANON))["generations"]
            if g["id"] == gen["id"])
        assert row["verdicts"] == {"video": 1}

    def test_verdicts_stay_on_their_generation_and_user(self, api):
        profile = _profile(api, "Verdicts Scoped")
        voted = _generation(api, profile, status="completed")
        unvoted = _generation(api, profile, status="completed")
        self._thumb(api, "thumb_up", "video", profile, voted)
        rows = {g["id"]: g for g in
                _run(api.generation_history(user_id=ANON))["generations"]}
        assert rows[voted["id"]]["verdicts"] == {"video": 1}
        assert rows[unvoted["id"]]["verdicts"] == {}
        assert _run(api.generation_history(
            user_id=OTHER_USER))["generations"] == []
        stranger = _run(api.list_feedback(user_id=OTHER_USER))
        assert stranger["feedback"] == []

    def test_non_thumb_events_never_highlight_a_render(self, api):
        from models import FeedbackRequest
        profile = _profile(api, "Verdicts Ignore Signals")
        gen = _generation(api, profile, status="completed")
        _run(api.record_feedback(FeedbackRequest(
            event="video_downloaded", signal="downloaded",
            brand_profile_id=profile["id"],
            generation_id=gen["id"]), ANON))
        row = next(
            g for g in _run(api.generation_history(user_id=ANON))["generations"]
            if g["id"] == gen["id"])
        assert row["verdicts"] == {}


class TestRecordSignal:
    """
    Signals are the automatic half of the feedback loop: factual triggers the
    software observes, recorded without asking the founder anything.
    """

    def test_a_signal_alone_is_enough(self, api):
        from models import FeedbackRequest
        created = _run(api.record_feedback(
            FeedbackRequest(event="video_downloaded", signal="downloaded"), ANON))
        assert created["signal"] == "downloaded"
        assert created["reason"] == ""

    def test_a_signal_and_a_reason_can_travel_together(self, api):
        from models import FeedbackRequest
        created = _run(api.record_feedback(
            FeedbackRequest(event="video_downloaded", reason="ready_to_post"), ANON))
        assert created["reason"] == "ready_to_post"
        assert created["signal"] == ""

    def test_unknown_signal_is_rejected(self, api):
        from models import FeedbackRequest
        with pytest.raises(HTTPException) as err:
            _run(api.record_feedback(
                FeedbackRequest(event="video_downloaded", signal="teleported"), ANON))
        assert err.value.status_code == 400

    def test_signal_must_belong_to_the_event(self, api):
        """
        The point of keeping signal and event separate is that neither is
        inferred from the other. A mismatched pair means one of them is wrong,
        so it is refused rather than stored.
        """
        from models import FeedbackRequest
        with pytest.raises(HTTPException) as err:
            _run(api.record_feedback(
                FeedbackRequest(event="video_downloaded", signal="regenerated"), ANON))
        assert err.value.status_code == 400

    def test_every_signal_maps_to_a_known_event(self, api):
        import feedback as fb
        for signal, event in fb.SIGNALS.items():
            assert event in fb.EVENTS, signal
            assert fb.signal_event(signal) == event

    def test_signals_and_reasons_are_never_inferred_from_each_other(self, api):
        """
        A regenerate says nothing about *why*. Storing a guessed reason against
        a trigger would corrupt the "common regeneration reasons" aggregate
        with counterfactuals, so the reason column stays empty.
        """
        from models import FeedbackRequest
        # A dedicated user, so this test's summary is not diluted by the rows
        # every other test in this file leaves behind.
        solo = "signal-solo-user"
        created = _run(api.record_feedback(
            FeedbackRequest(event="video_regenerated", signal="regenerated"), solo))
        assert created["reason"] == ""
        summary = _run(api.list_feedback(user_id=solo))["summary"]
        assert summary["top_signals"] == [
            {"signal": "regenerated", "count": 1}
        ]
        assert summary["top_reasons"] == []

    def test_summary_separates_triggers_from_explanations(self, api):
        """
        Frequent-but-unexplained rework must be readable as such, not mistaken
        for an absence of problems.
        """
        from models import FeedbackRequest
        solo = "signal-summary-user"
        for _ in range(3):
            _run(api.record_feedback(
                FeedbackRequest(event="video_regenerated", signal="regenerated"), solo))
        _run(api.record_feedback(
            FeedbackRequest(event="video_regenerated", reason="pacing_too_slow"), solo))
        summary = _run(api.list_feedback(user_id=solo))["summary"]
        assert summary["total"] == 4
        assert summary["explained"] == 1
        assert summary["top_signals"][0]["count"] == 3

    def test_catalog_publishes_the_heavy_edit_threshold(self, api):
        """
        The heavy/light boundary is arbitrary, so it is published rather than
        hidden: both the backend and the frontend classifier must agree, and a
        reader can check what the number actually is.
        """
        import feedback as fb
        catalog = _run(api.feedback_catalog())
        assert catalog["heavy_edit"]["ratio"] == fb.HEAVY_EDIT_RATIO
        assert catalog["heavy_edit"]["min_chars"] == fb.HEAVY_EDIT_MIN_CHARS
        assert {s["key"] for s in catalog["signals"]} == set(fb.SIGNALS)


class TestClassifyScriptEdit:
    def test_no_change_is_not_an_edit(self):
        import feedback as fb
        assert fb.classify_script_edit("same text", "same text") == ""

    def test_a_large_rewrite_is_heavy(self):
        import feedback as fb
        original = "Open the app and tap the button to start your session today."
        rewritten = "Try it free for three days, then decide."
        assert fb.classify_script_edit(original, rewritten) == "script_edited_heavy"

    def test_a_one_character_tweak_is_light(self):
        import feedback as fb
        original = "Open the app and tap the button to start your session today."
        assert fb.classify_script_edit(original, original + "!") == "script_edited_light"

    def test_a_growing_script_counts_as_heavy_once_past_the_floor(self):
        """
        Length is measured on the longer text, so padding a short script is
        measured on what it became rather than on the tiny original.
        """
        import feedback as fb
        short = "Try it."
        padded = short + (" Very easy to use and very quick to set up." * 3)
        assert fb.classify_script_edit(short, padded) == "script_edited_heavy"


class TestMp4CompletenessCheck:
    """
    A file left truncated by a killed process is the case a size check waves
    through, and it must never be reused or persisted: the founder would get a
    clip that cannot play while being told the render was saved.
    """

    def _write(self, tmp_path, data):
        p = tmp_path / "clip.mp4"
        p.write_bytes(data)
        return p

    def test_a_complete_file_passes(self, api, tmp_path):
        assert api._is_complete_mp4(self._write(tmp_path, _fake_mp4()))

    def test_a_truncated_file_is_rejected(self, api, tmp_path):
        truncated = b"\x00\x00\x00\x18ftypmp42" + (b"\x00" * 512)
        assert not api._is_complete_mp4(self._write(tmp_path, truncated))

    def test_an_empty_file_is_rejected(self, api, tmp_path):
        assert not api._is_complete_mp4(self._write(tmp_path, b""))

    def test_a_missing_file_is_rejected(self, api, tmp_path):
        assert not api._is_complete_mp4(tmp_path / "nope.mp4")

    def test_an_error_page_is_not_mistaken_for_a_video(self, api, tmp_path):
        """
        A CDN that answers a dead link with an HTML body would otherwise be
        saved as a .mp4 and served to the video element.
        """
        assert not api._is_complete_mp4(self._write(tmp_path, b"<html>404</html>" * 60))

    def test_a_large_index_at_the_end_passes(self, api, tmp_path):
        """
        The regression this whole class was missing.

        The old check searched the first and last 4KB for the bytes "moov". Those
        four bytes are the START of the index box, and on a real render the index
        is thousands of bytes of sample tables -- so on any file big enough to
        matter the tag sat further than 4KB from the end, outside the window, and
        a finished playable clip was rejected as "truncated". The founder then saw
        "download was truncated (not a complete MP4)" on a render that played
        perfectly in a browser.

        The previous version of this test built an EIGHT-byte moov, which fits
        inside the tail window -- so it passed against the broken code and proved
        nothing. The index has to be realistically large for the test to mean
        anything.
        """
        big = mp4_samples.synthetic_mp4(moov_body=9000, media_bytes=200_000)
        # Assert the fixture is the shape that broke the old code, so this test
        # cannot quietly stop reproducing the bug.
        tag_at = big.rfind(b"moov")
        assert len(big) - tag_at > 4096, "fixture no longer has a distant index"
        assert b"moov" not in big[:4096] + big[-4096:], "the old probe would pass it"
        # The structural walk finds the index the window probe could not. Not
        # `is_usable_video`, which must still reject this one: it is a
        # well-formed container with no decodable video in it, and that
        # distinction is the next test's job.
        import storage_service
        assert storage_service.mp4_has_moov(self._write(tmp_path, big)) is True

    def test_a_well_formed_container_with_no_video_is_still_rejected(self, api, tmp_path):
        """
        The structural walk answers "is the index there", not "is there anything
        to play". A box chain that is perfectly valid but holds no decodable
        frames is what a transfer cut off mid-file can leave behind, and it has
        to be refused rather than uploaded as a finished render.
        """
        import storage_service
        hollow = mp4_samples.synthetic_mp4(moov_body=9000, media_bytes=200_000)
        path = self._write(tmp_path, hollow)
        assert storage_service.mp4_has_moov(path) is True, "precondition"
        assert storage_service.is_usable_video(path) is False

    def test_a_real_render_with_its_index_at_the_end_is_accepted(self, api, tmp_path):
        """
        The end-to-end version: a genuine encode, the layout the provider
        actually produces, through the check the download path uses.
        """
        assert api._is_complete_mp4(self._write(tmp_path, mp4_samples.real_mp4()))

    def test_a_truncated_real_render_is_rejected(self, api, tmp_path):
        """
        The depth check earning its place. A box walk cannot tell a clip that kept
        its index but lost its samples, so ffprobe is asked whether any video
        packets decode.
        """
        cut = mp4_samples.truncate(mp4_samples.real_mp4(), 0.4)
        assert not api._is_complete_mp4(self._write(tmp_path, cut))


class TestModelRequestLedger:
    USER = "ops-model-user"

    def test_success_and_failure_are_recorded(self, api):
        async def succeed():
            return {"ok": True}

        async def fail():
            raise RuntimeError("provider unavailable")

        result = _run(api._log_model_call(
            "ops-text-check", "text", "text-model", succeed, self.USER,
            brand_profile_id="profile-1",
        ))
        assert result["ok"] is True
        with pytest.raises(RuntimeError):
            _run(api._log_model_call(
                "ops-vision-check", "vision", "vision-model", fail, self.USER,
                brand_profile_id="profile-1",
            ))
        rows = _run(api._fetch_all(
            "SELECT operation, status, error, latency_ms FROM model_requests "
            "WHERE user_id = ? ORDER BY created_at",
            (self.USER,),
        ))
        assert [(r["operation"], r["status"]) for r in rows] == [
            ("ops-text-check", "completed"),
            ("ops-vision-check", "failed"),
        ]
        assert "unavailable" in rows[1]["error"]
        assert rows[0]["latency_ms"] >= 0

    def test_asset_events_are_persisted_for_their_owner(self, api):
        """
        Used to assert this through the Operations page. The page is gone, but
        what it was reading is a real invariant: these ledgers exist, they are
        written, and they are scoped to their owner. So they are asserted where
        they actually live.
        """
        _run(api._record_asset_event(
            "upload_rejected", "Uploaded file is empty.", self.USER,
            brand_profile_id="profile-1", asset_kind="audio", filename="empty.mp3",
        ))

        events = _run(api._fetch_all(
            "SELECT kind, reason FROM asset_events WHERE user_id = ?", (self.USER,)))
        assert any(e["kind"] == "upload_rejected" for e in events)

        # And they are scoped: another user sees none.
        assert _run(api._fetch_all(
            "SELECT id FROM asset_events WHERE user_id = ?", (OTHER_USER,))) == []

    def test_model_request_ledger_records_the_modality_actually_used(self, api):
        """
        The ledger's value is that a modality is attributable after the fact,
        so the recorded modality is asserted rather than assumed.
        """

        async def succeed():
            return {"ok": True}

        _run(api._log_model_call(
            "summary-text-check", "text", "text-model", succeed, self.USER))
        rows = _run(api._fetch_all(
            "SELECT operation, modality, status FROM model_requests WHERE user_id = ?",
            (self.USER,)))
        assert rows
        assert any(r["modality"] == "text" and r["status"] == "completed" for r in rows)

    def test_completed_generation_storage_failure_is_recorded_and_retryable(
        self, api, monkeypatch
    ):
        """
        A storage failure has to be recoverable, not just reported. With the
        Operations page gone there is no longer a view that surfaces it, so the
        record itself is what must carry it.
        """
        profile = _profile(api, "Ops Storage")
        gen = _generation(api, profile, "completed")
        local_path = api.pipeline.VIDEOS_DIR / f"{gen['id']}.mp4"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(_fake_mp4())
        _run(api._execute(
            "UPDATE generations SET r2_url = '', storage_error = ? WHERE id = ?",
            ("R2 upload failed", gen["id"]),
        ))

        # The failure is readable from the generation record itself, and it is
        # scoped to its owner.
        stored = _run(api.get_generation(gen["id"], ANON))
        assert stored["storage_error"] == "R2 upload failed"
        with pytest.raises(HTTPException):
            _run(api.get_generation(gen["id"], OTHER_USER))

        monkeypatch.setattr(api.storage_service, "is_configured", lambda: True)
        monkeypatch.setattr(
            api.storage_service, "upload_video",
            lambda user_id, job_id, path: "https://example.invalid/video.mp4",
        )
        retried = _run(api.retry_generation_storage(gen["id"], ANON))
        assert retried["r2_url"] == "https://example.invalid/video.mp4"
        assert retried["storage_error"] is None
        assert _run(api.get_generation(gen["id"], ANON))["storage_error"] is None

    def test_storage_retry_reports_a_row_with_nothing_left_to_work_from(self, api):
        """
        The one genuinely unrecoverable shape: no local copy AND no provider
        link. _generation stores neither, so there is nothing to fetch and
        nothing to upload, and saying so is the only honest answer.
        """
        profile = _profile(api, "Ops Missing Copy")
        gen = _generation(api, profile, "completed")
        local_path = api.pipeline.VIDEOS_DIR / f"{gen['id']}.mp4"
        if local_path.exists():
            local_path.unlink()
        _run(api._execute(
            "UPDATE generations SET video_url = '', openrouter_job_id = NULL WHERE id = ?",
            (gen["id"],),
        ))
        with pytest.raises(HTTPException) as err:
            _run(api.retry_generation_storage(gen["id"], ANON))
        assert err.value.status_code == 409
        assert "cannot be recovered" in err.value.detail

    def test_storage_retry_refetches_when_the_download_failed(self, api, monkeypatch):
        """
        The bug this endpoint could not previously service.

        A failed download deletes the partial file, so the row was left with no
        local copy at all -- and the old endpoint demanded one, answering 409 to
        the exact button the panel offers for that failure. The provider link is
        still on the row, so the retry must re-fetch rather than give up.
        """
        profile = _profile(api, "Ops Refetch")
        gen = _generation(api, profile, "completed")
        local_path = api.pipeline.VIDEOS_DIR / f"{gen['id']}.mp4"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        if local_path.exists():
            local_path.unlink()
        _run(api._execute(
            "UPDATE generations SET video_url = ?, openrouter_job_id = ?, r2_url = '', "
            "storage_error = ? WHERE id = ?",
            (
                "https://openrouter.ai/api/v1/videos/job-1/content?index=0",
                "job-1",
                "The provider clip could not be downloaded for durable storage "
                "(HTTP 401 Unauthorized).",
                gen["id"],
            ),
        ))

        fetched = {}

        async def fake_download(url, generation_id):
            fetched["url"] = url
            path = api.pipeline.VIDEOS_DIR / f"{generation_id}.mp4"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"refetched-video")
            return path, None

        monkeypatch.setattr(api, "_download_generation_video", fake_download)
        monkeypatch.setattr(api.overlays, "rescale_to_canvas", _no_rescale)
        monkeypatch.setattr(
            api.storage_service, "upload_video",
            lambda user_id, job_id, path: "https://example.invalid/refetched.mp4",
        )

        retried = _run(api.retry_generation_storage(gen["id"], ANON))
        assert fetched["url"] == "https://openrouter.ai/api/v1/videos/job-1/content?index=0"
        assert retried["r2_url"] == "https://example.invalid/refetched.mp4"
        # The alert the founder is looking at has to actually clear.
        assert retried["storage_error"] is None
        assert _run(api.get_generation(gen["id"], ANON))["storage_error"] is None

    def test_storage_retry_uses_the_content_url_when_none_was_stored(self, api, monkeypatch):
        """
        A row can have an empty video_url and still be repairable: the provider
        content endpoint is derivable from the job id. Without this the founder
        sees an unrecoverable error on a video the provider would happily serve.
        """
        profile = _profile(api, "Ops Derived URL")
        gen = _generation(api, profile, "completed")
        local_path = api.pipeline.VIDEOS_DIR / f"{gen['id']}.mp4"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        if local_path.exists():
            local_path.unlink()
        _run(api._execute(
            "UPDATE generations SET video_url = '', openrouter_job_id = 'job-77', r2_url = '', "
            "storage_error = ? WHERE id = ?",
            ("download failed", gen["id"]),
        ))

        seen = {}

        async def fake_download(url, generation_id):
            seen["url"] = url
            path = api.pipeline.VIDEOS_DIR / f"{generation_id}.mp4"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"derived-video")
            return path, None

        monkeypatch.setattr(api, "_download_generation_video", fake_download)
        monkeypatch.setattr(api.overlays, "rescale_to_canvas", _no_rescale)
        monkeypatch.setattr(
            api.storage_service, "upload_video",
            lambda user_id, job_id, path: "https://example.invalid/derived.mp4",
        )

        retried = _run(api.retry_generation_storage(gen["id"], ANON))
        assert seen["url"].endswith("/videos/job-77/content?index=0")
        assert retried["r2_url"] == "https://example.invalid/derived.mp4"

    def test_storage_retry_reuses_a_surviving_local_copy(self, api, monkeypatch):
        """
        An upload-only failure should cost one PUT, not a full re-fetch, and it
        must NOT re-trim or re-rescale: the canonical file is what an extension
        bridges its next segment from, so rewriting it twice is not free.
        """
        profile = _profile(api, "Ops Reuse Local")
        gen = _generation(api, profile, "completed")
        local_path = api.pipeline.VIDEOS_DIR / f"{gen['id']}.mp4"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(_fake_mp4())
        _run(api._execute(
            "UPDATE generations SET r2_url = '', storage_error = ? WHERE id = ?",
            ("R2 upload failed", gen["id"]),
        ))

        async def forbidden_download(url, generation_id):
            raise AssertionError("a surviving local copy must not be re-downloaded")

        monkeypatch.setattr(api, "_download_generation_video", forbidden_download)
        monkeypatch.setattr(api.overlays, "rescale_to_canvas", _forbid_rescale)
        monkeypatch.setattr(
            api.storage_service, "upload_video",
            lambda user_id, job_id, path: "https://example.invalid/reused.mp4",
        )

        retried = _run(api.retry_generation_storage(gen["id"], ANON))
        assert retried["r2_url"] == "https://example.invalid/reused.mp4"
        assert retried["storage_error"] is None

    def test_storage_retry_refetches_a_truncated_local_copy(self, api, monkeypatch):
        """
        "Present" is not "usable". A file left half-written by a killed process
        is exactly the case a size check waves through, and reusing it would
        upload a clip that cannot play while reporting the render as saved.
        """
        profile = _profile(api, "Ops Truncated")
        gen = _generation(api, profile, "completed")
        local_path = api.pipeline.VIDEOS_DIR / f"{gen['id']}.mp4"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 512)  # no moov
        _run(api._execute(
            "UPDATE generations SET video_url = ?, r2_url = '', storage_error = ? WHERE id = ?",
            ("https://openrouter.ai/api/v1/videos/job-9/content?index=0", "broken",
             gen["id"]),
        ))

        seen = {}

        async def fake_download(url, generation_id):
            seen["url"] = url
            path = api.pipeline.VIDEOS_DIR / f"{generation_id}.mp4"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(_fake_mp4())
            return path, None

        monkeypatch.setattr(api, "_download_generation_video", fake_download)
        monkeypatch.setattr(api.overlays, "rescale_to_canvas", _no_rescale)
        monkeypatch.setattr(
            api.storage_service, "upload_video",
            lambda user_id, job_id, path: "https://example.invalid/refetched.mp4",
        )

        retried = _run(api.retry_generation_storage(gen["id"], ANON))
        assert seen["url"].endswith("/content?index=0")
        assert retried["r2_url"] == "https://example.invalid/refetched.mp4"

    def test_storage_retry_falls_back_to_local_serving_when_r2_is_unconfigured(
        self, api, monkeypatch
    ):
        """
        This used to be a 409. It is not an error: the local copy survived and
        /api/media serves it, so the founder gets a watchable, downloadable
        video instead of a refusal they cannot act on. The message has to admit
        that this is a degraded save rather than a durable one.
        """
        profile = _profile(api, "Ops Unconfigured Storage")
        gen = _generation(api, profile, "completed")
        local_path = api.pipeline.VIDEOS_DIR / f"{gen['id']}.mp4"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(_fake_mp4())
        _run(api._execute(
            "UPDATE generations SET r2_url = '', storage_error = ? WHERE id = ?",
            ("R2 upload failed", gen["id"]),
        ))

        monkeypatch.setattr(api.storage_service, "is_configured", lambda: False)
        monkeypatch.setattr(api.storage_service, "upload_video", lambda *a, **k: None)

        retried = _run(api.retry_generation_storage(gen["id"], ANON))
        assert retried["r2_url"]
        assert "this server's storage" in retried["storage_error"]

    def test_storage_retry_refuses_a_row_still_in_flight(self, api):
        profile = _profile(api, "Ops Still Running")
        gen = _generation(api, profile, "generating")
        with pytest.raises(HTTPException) as err:
            _run(api.retry_generation_storage(gen["id"], ANON))
        assert err.value.status_code == 409


# The Dashboard page and GET /api/dashboard are gone. Its three tests went with
# the endpoint, and nothing they covered became untested:
#
#   profiles / profiles_awaiting_approval   GET /api/app-profiles; the same
#                                           approved-vs-draft split is asserted
#                                           in test_studio_api's picker tests
#   totals (videos_created, success rate)   GET /api/generations, which History
#                                           renders with its totals line and
#                                           per-row status badge
#   pending_template_drafts                  GET /api/templates by review_status
#   recent_failures                          GET /api/generations, which History
#                                           renders with a Failed badge and Retry


# The Analytics page and GET /api/analytics are gone. It reported this
# operator's own activity and what it cost them; the product does not meter
# that. Its remaining honesty rule — that operator-entered TikTok figures are
# never presented as platform-verified — still holds at the point the figures
# are entered, in test_variation_api's TestManualPerformance.


# The Settings page and GET /api/settings are gone. The three honesty notes it
# carried are each stated somewhere the user still is, so none of them went dark
# with the page:
#
#   never publishes          frontend/src/pages/CreateVideo.jsx (studio footer)
#   TikTok figures are by hand   frontend/src/pages/GenerationHistory.jsx
#   templates are not proven     frontend/src/pages/CreateVideo.jsx
#
# Integration status went with it. It was a read-only self-serve report, so
# nothing is stranded and no behaviour depended on the endpoint.


class TestLibraryDraftGating:
    """Unpublished drafts must stay invisible and unusable in the library."""

    def test_unpublished_drafts_are_excluded_from_recommendations(self, api):
        from models import CreateStudioProjectRequest, BrandProfileCreateRequest, ApproveAppProfileRequest
        profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
            brand_name="Draft Exclusion",
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
            profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
        tpl_id = str(uuid.uuid4())
        _run(api._execute(
            """INSERT INTO hook_templates (id, name, category, opening_structure,
               origin, review_status, archived, version, created_at, updated_at, user_id)
               VALUES (?, 'Hidden Draft', 'other', 'A structure', 'research_draft',
               'draft', 0, 1, '', '', ?)""", (tpl_id, ANON)))
        recs = _run(api.recommend_templates(profile_id=profile["id"], user_id=ANON))
        assert tpl_id not in [r["template"]["id"] for r in recs["recommendations"]]
        del CreateStudioProjectRequest

    def test_creating_a_project_with_a_draft_template_is_refused(self, api):
        from models import CreateStudioProjectRequest, BrandProfileCreateRequest, ApproveAppProfileRequest
        profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
            brand_name="Draft Project",
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
            profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
        tpl_id = str(uuid.uuid4())
        _run(api._execute(
            """INSERT INTO hook_templates (id, name, category, opening_structure,
               origin, review_status, archived, version, created_at, updated_at, user_id)
               VALUES (?, 'Hidden Draft 2', 'other', 'A structure', 'research_draft',
               'draft', 0, 1, '', '', ?)""", (tpl_id, ANON)))
        with pytest.raises(HTTPException) as err:
            _run(api.create_studio_project(payload=CreateStudioProjectRequest(
                brand_profile_id=profile["id"], template_id=tpl_id), user_id=ANON))
        assert err.value.status_code == 409


class TestNoPlatformAutomation:
    """
    The exclusions are structural: there is no code path in this app that
    posts, schedules, or authenticates against a social platform.
    """

    def test_no_video_publishing_endpoints_exist(self, api):
        """
        Note: POST /templates/{id}/publish DOES exist and is legitimate -- it
        publishes a template into the internal library, not a video to a
        platform. What must not exist is anything that sends a video out.
        """
        paths = {getattr(r, "path", "") for r in api.app.routes}
        for forbidden in ("/publish-video", "/post-video", "/tiktok/post",
                          "/share-to", "/engagement", "/schedule",
                          "/upload-to", "/queue-post"):
            assert not any(forbidden in p for p in paths), forbidden

    def test_no_generation_endpoint_publishes(self, api):
        """Nothing under /generations may hand a video to a platform."""
        for r in api.app.routes:
            path = getattr(r, "path", "")
            if path.startswith("/api/generations"):
                # Whole path segments, not substrings: "post-kit" and
                # "regenerate" are copy endpoints, not platform automation.
                segments = set(path.split("/"))
                assert not any(
                    w in segments for w in ("publish", "post", "share", "schedule")
                ), path

    def test_post_kit_regenerate_registered_once(self, api):
        """The post-kit router contributes exactly one POST regenerate route.

        Guards the extraction: no duplicate registration from both the router
        and the composition root, and no dropped prefix on the way through
        include_router.
        """
        hits = [
            (getattr(r, "path", ""), sorted(getattr(r, "methods", None) or []))
            for r in api.app.routes
            if getattr(r, "path", "") == "/api/generations/{generation_id}/post-kit/regenerate"
        ]
        assert hits == [("/api/generations/{generation_id}/post-kit/regenerate", ["POST"])], hits

    def test_legacy_creation_routes_are_unregistered(self, api):
        """
        Exact-match creation is disabled at the router boundary. The retired
        Discover / Saved Hooks / analysis / legacy-history pages took their
        endpoints with them (deleted outright, not merely unregistered), so
        only creation paths appear below; research and history went further
        and no longer exist as routes at all.
        """
        paths = {getattr(r, "path", "") for r in api.api_router.routes}
        for disabled in api.DISABLED_LEGACY_CREATION_ROUTES:
            assert f"/api{disabled}" not in paths, disabled
        app_paths = {getattr(r, "path", "") for r in api.app.routes}
        for disabled in api.DISABLED_LEGACY_CREATION_ROUTES:
            assert f"/api{disabled}" not in app_paths, disabled

    def test_retired_research_routes_are_gone(self, api):
        """
        The Discover, Saved Hooks, video-analysis, Trend Research, and
        legacy-history pages were removed along with their backends. Their
        routes must not be registered anywhere — a leftover route is a live
        paid-AI endpoint (analysis) or a dead page behind a bookmark.
        Website autofill (POST /brand/analyze-url) joined them: profiles are
        created from store listings only, so its route must stay gone too.
        """
        paths = {getattr(r, "path", "") for r in api.api_router.routes}
        for gone in (
            "/api/brand/analyze-url",
            "/api/niches",
            "/api/niches/{niche_key}/videos",
            "/api/niches/{niche_key}/trending",
            "/api/trending/search",
            "/api/videos/ingest",
            "/api/videos/{video_id}",
            "/api/videos/{video_id}/analyze-hook",
            "/api/videos/{video_id}/analysis",
            "/api/videos/{video_id}/hook-engine",
            "/api/hook-motion-styles",
            "/api/video-models",
            "/api/bookmarks",
            "/api/bookmarks/{template_id}",
            "/api/history",
            "/api/video-assets",
            "/api/video-assets/{job_id}",
            "/api/research/scan",
            "/api/research/runs",
            "/api/research/runs/{run_id}",
        ):
            assert gone not in paths, gone
        for retained in ("/api/studio/video-models",):
            assert retained in paths, retained

    def test_no_credential_capture_endpoints(self, api):
        paths = " ".join(getattr(r, "path", "") for r in api.app.routes)
        for forbidden in ("login", "cookie", "session-token", "credentials"):
            assert forbidden not in paths.lower()

    # The "publishing is manual" guarantee used to be asserted as a string in the
    # Operations payload. It is no longer asserted that way, because a copy-text
    # check on a sentence is worth nothing next to the three structural tests
    # above it, which prove there is no code path that can post a video at all.
    # The user-facing statement now lives on the Assets and Review screens.


class TestResearchRecordsOnlyWhatItRead:
    """
    A source that fails should not be recorded as one that was read.

    Only an all-sources-failed research raises, so a profile built from one of
    five URLs was stored with all five listed in research_sources. A founder
    reading that list had no way to know the other four were empty, and the
    detail view renders the list as though it were provenance.
    """

    def _research(self, api, monkeypatch, *, appstore=True, play=True):
        from models import AppProfileResearchRequest

        async def fake_fetch(url, max_chars):
            # Only the App Store listing resolves. Google Play is behind a bot check.
            if url.startswith("https://play.google.com"):
                return ""
            return "ShiftLog logs a shift in one tap. Built for night-shift nurses."

        async def fake_analyze(sources, notes):
            seen.append(dict(sources))
            return {
                "brand_name": "ShiftLog",
                "brand_description": "Shift logging for healthcare workers.",
                "app_category": "Productivity",
                "core_features": ["One-tap shift logging"],
                "usage_moments": ["Clocking on and off between shifts"],
                "target_audience": "hospital nurses",
                "tone_voice": "Warm",
                "claims_approved": ["Logs a shift in one tap"],
            }

        seen = []
        monkeypatch.setattr(api, "_fetch_url_text", fake_fetch)
        monkeypatch.setattr(api, "analyze_app_profile", fake_analyze)
        return _run(api.research_app_profile(payload=AppProfileResearchRequest(
            appstore_url="https://apps.apple.com/x" if appstore else "",
            play_url="https://play.google.com/y" if play else "",
        ), user_id=ANON)), seen

    def test_a_failed_source_is_not_recorded_as_read(self, api, monkeypatch):
        profile, seen = self._research(api, monkeypatch)
        # Already decoded by the row factory; only a hand-written or older row
        # arrives as a string.
        recorded = profile["research_sources"]
        if isinstance(recorded, str):
            import json as _json
            recorded = _json.loads(recorded or "[]")
        assert recorded == ["app_store"]
        # And the model was not handed an empty entry labelled as a source.
        assert list(seen[0]) == ["app_store"]
        assert all((v or "").strip() for v in seen[0].values())

    def test_a_partially_failed_research_still_succeeds(self, api, monkeypatch):
        """
        Losing one source is not losing the profile. The point is that the gap
        is recorded, not that partial research is refused.
        """
        profile, _ = self._research(api, monkeypatch, play=False)
        assert profile["brand_name"] == "ShiftLog"
        assert profile["status"] == "draft"
