"""Whole-video verdicts: one verdict per finished video, frozen bundle, steering.

Seams (ADR 0124):
- POST /generations/{id}/verdict sets, replaces or clears the founder's
  one verdict on a whole video, freezing a bundle of what went out;
- later edits to the project or its post kit never rewrite a bundle;
- plan and strategy prompts learn from verdict bundles only — silent
  below 3 verdicts — and per-element thumbs no longer reach generation.
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

ANON = "anonymous"


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="verdicts-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""
    os.environ.pop("VIDEO_MODEL_DEFAULT", None)
    os.environ.pop("VIDEO_MODEL_ALLOWLIST", None)

    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(server.init_db())
    try:
        yield server
    finally:
        sys.modules.pop("server", None)


def _run(coro):
    return asyncio.run(coro)


def _insert_project(api, user_id=ANON, **fields):
    from models import now_iso

    project_id = str(uuid.uuid4())
    now = now_iso()
    columns = {"id": project_id, "user_id": user_id,
               "created_at": now, "updated_at": now}
    columns.update(fields)
    names = ", ".join(columns)
    marks = ", ".join("?" for _ in columns)
    _run(api._execute(
        f"INSERT INTO studio_projects ({names}) VALUES ({marks})",
        tuple(columns.values()),
    ))
    return project_id


def _insert_generation(api, user_id=ANON, **fields):
    from models import now_iso

    generation_id = str(uuid.uuid4())
    now = now_iso()
    columns = {"id": generation_id, "user_id": user_id, "status": "completed",
               "created_at": now, "updated_at": now}
    columns.update(fields)
    names = ", ".join(columns)
    marks = ", ".join("?" for _ in columns)
    _run(api._execute(
        f"INSERT INTO generations ({names}) VALUES ({marks})",
        tuple(columns.values()),
    ))
    return generation_id


def _set_verdict(api, generation_id, verdict, user_id=ANON):
    from models import VideoVerdictRequest

    return _run(api.set_generation_video_verdict(
        generation_id, VideoVerdictRequest(verdict=verdict), user_id))


def _stored_bundle(api, generation_id, user_id=ANON):
    row = _run(api._fetch_one(
        "SELECT verdict, bundle FROM video_verdicts "
        "WHERE generation_id = ? AND user_id = ?", (generation_id, user_id)))
    if not row:
        return None
    return {"verdict": row["verdict"], "bundle": json.loads(row["bundle"])}


POST_KIT = {
    "caption": "The blank page loses again. Try it free.",
    "hashtags": ["#focus", "#productivity", "#adhdtok", "#studytok"],
    "cover_text": "Stop staring at blank pages",
}


def _rated_render(api, user_id=ANON, **generation_fields):
    """A completed render with a project behind it, ready to be judged."""
    project_id = _insert_project(
        api, user_id=user_id,
        brand_profile_id=generation_fields.get("brand_profile_id"),
        hook_line="Stop writing empty pages",
        script="One short prompt, and the page is moving again.",
        objective="demonstrate_feature",
        voice_direction="Warm, unhurried",
        sound_direction="Lo-fi bed",
    )
    generation_id = _insert_generation(
        api, user_id=user_id,
        studio_project_id=project_id,
        template_id="tmpl-stop-doing-this",
        template_version=3,
        model="Kling 2.1",
        model_id="kling-2.1",
        duration=18,
        segment_role="hook_story",
        post_kit=json.dumps(POST_KIT),
        **generation_fields,
    )
    return generation_id, project_id


class TestVerdictStore:
    def test_verdict_round_trips_in_detail_and_history(self, api):
        generation_id, _project_id = _rated_render(api)
        updated = _set_verdict(api, generation_id, "up")
        assert updated["video_verdict"] == "up"

        detail = _run(api.get_generation(generation_id, ANON))
        assert detail["video_verdict"] == "up"
        history = _run(api.generation_history(user_id=ANON))
        row = next(g for g in history["generations"] if g["id"] == generation_id)
        assert row["video_verdict"] == "up"

    def test_bundle_freezes_what_went_out(self, api):
        generation_id, _project_id = _rated_render(api)
        _set_verdict(api, generation_id, "up")
        stored = _stored_bundle(api, generation_id)
        assert stored["verdict"] == "up"
        bundle = stored["bundle"]
        # The spoken words, from the render's project.
        assert bundle["hook_line"] == "Stop writing empty pages"
        assert bundle["script"] == "One short prompt, and the page is moving again."
        # The post copy, from the generation's own frozen post kit.
        assert bundle["caption"] == POST_KIT["caption"]
        assert bundle["hashtags"] == POST_KIT["hashtags"]
        assert bundle["cover_text"] == POST_KIT["cover_text"]
        # The opening visual: poster asset plus the template it rendered.
        assert bundle["opening_visual"]["template_id"] == "tmpl-stop-doing-this"
        assert bundle["opening_visual"]["template_version"] == 3
        assert bundle["opening_visual"]["poster_path"] == \
            f"/api/media/posters/{generation_id}.jpg"
        # The audio identity: the render's model plus the project's voice.
        assert bundle["audio"]["model"] == "Kling 2.1"
        assert bundle["audio"]["model_id"] == "kling-2.1"
        assert bundle["audio"]["voice_direction"] == "Warm, unhurried"
        assert bundle["audio"]["sound_direction"] == "Lo-fi bed"
        # Context: objective stands in for the goal — there is no goal_id
        # anywhere in the schema, so the bundle must not invent one.
        assert bundle["context"]["objective"] == "demonstrate_feature"
        assert bundle["context"]["duration_seconds"] == 18
        assert "goal_id" not in bundle["context"]

    def test_setting_replaces_and_clearing_removes(self, api):
        generation_id, _project_id = _rated_render(api)
        _set_verdict(api, generation_id, "up")
        _set_verdict(api, generation_id, "down")
        rows = _run(api._fetch_all(
            "SELECT * FROM video_verdicts WHERE generation_id = ?", (generation_id,)))
        assert len(rows) == 1
        assert rows[0]["verdict"] == "down"

        updated = _set_verdict(api, generation_id, None)
        assert updated["video_verdict"] is None
        assert _stored_bundle(api, generation_id) is None
        detail = _run(api.get_generation(generation_id, ANON))
        assert detail["video_verdict"] is None

    def test_bundle_survives_later_project_edits_and_new_post_kit(self, api):
        generation_id, project_id = _rated_render(api)
        _set_verdict(api, generation_id, "up")
        frozen = _stored_bundle(api, generation_id)["bundle"]

        # The founder rewrites the project's words and regenerates the
        # post kit after the verdict. The bundle describes the video that
        # was judged, so neither change may reach it.
        _run(api._execute(
            "UPDATE studio_projects SET hook_line = ?, script = ? WHERE id = ?",
            ("A completely different opening", "A completely different script.",
             project_id)))
        _run(api._execute(
            "UPDATE generations SET post_kit = ? WHERE id = ?",
            (json.dumps({"caption": "New caption", "hashtags": ["#new"],
                         "cover_text": "New cover"}), generation_id)))
        assert _stored_bundle(api, generation_id)["bundle"] == frozen

    def test_another_users_render_is_not_found(self, api):
        generation_id, _project_id = _rated_render(api)
        with pytest.raises(HTTPException) as exc:
            _set_verdict(api, generation_id, "up", user_id="someone-else")
        assert exc.value.status_code == 404

    def test_missing_generation_is_not_found(self, api):
        with pytest.raises(HTTPException) as exc:
            _set_verdict(api, "no-such-generation", "up")
        assert exc.value.status_code == 404

    @pytest.mark.parametrize("payload", [
        {"verdict": "sideways"}, {"verdict": 1}, {"verdict": True},
    ])
    def test_http_refuses_a_verdict_that_is_not_up_down_or_null(self, api, payload):
        import httpx

        generation_id, _project_id = _rated_render(api)

        async def request():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=api.app), base_url="http://test"
            ) as client:
                return await client.post(
                    f"/api/generations/{generation_id}/verdict", json=payload)

        assert _run(request()).status_code == 422

    def test_history_verdict_summary_counts_and_shares(self, api):
        profile_id = str(uuid.uuid4())
        for verdict in ("up", "up", "down"):
            generation_id, _p = _rated_render(api, brand_profile_id=profile_id)
            _set_verdict(api, generation_id, verdict)
        history = _run(api.generation_history(
            brand_profile_id=profile_id, user_id=ANON))
        summary = history["verdict_summary"]
        assert summary["total"] == 3
        assert summary["up"] == 2
        assert summary["down"] == 1
        assert summary["ready"] is True
        # Both worked bundles rendered the same template: that is what
        # they share, and the summary names it.
        assert summary["shared"]["templates"] == ["tmpl-stop-doing-this"]
        assert summary["shared"]["objectives"] == ["demonstrate_feature"]


def _bundle(hook, template_id="tmpl-a"):
    return {
        "hook_line": hook,
        "script": f"Script for {hook}",
        "caption": f"Caption for {hook}",
        "hashtags": ["#focus"],
        "cover_text": None,
        "opening_visual": {"poster_url": None, "poster_path": "/api/media/posters/x.jpg",
                           "template_id": template_id, "template_version": 1},
        "audio": {"model": "Kling 2.1", "model_id": "kling-2.1",
                  "voice_direction": None, "sound_direction": None},
        "context": {"angle_id": None, "angle_kind": "problem",
                    "objective": "demonstrate_feature", "duration_seconds": 18,
                    "segment_role": "hook_story"},
    }


class TestVerdictSteeringSection:
    def test_two_verdicts_stay_silent(self):
        import feedback as feedback_mod

        summary = feedback_mod.summarize_video_verdicts([
            {"verdict": "up", "bundle": _bundle("Hook one")},
            {"verdict": "down", "bundle": _bundle("Hook two")},
        ])
        assert summary["total"] == 2
        assert summary["ready"] is False
        assert feedback_mod.build_verdict_feedback_section(summary) == ""

    def test_three_verdicts_present_whole_bundles(self):
        import feedback as feedback_mod

        summary = feedback_mod.summarize_video_verdicts([
            {"verdict": "up", "bundle": _bundle("Hook one")},
            {"verdict": "up", "bundle": _bundle("Hook two")},
            {"verdict": "down", "bundle": _bundle("Hook three", "tmpl-b")},
        ])
        assert summary["ready"] is True
        section = feedback_mod.build_verdict_feedback_section(summary)
        # Words travel WITH their visual/template context, as one bundle.
        assert "Hook one" in section and "tmpl-a" in section
        assert "Hook three" in section and "tmpl-b" in section
        assert "VIDEOS THAT WORKED" in section
        assert "VIDEOS THAT DIDN'T WORK" in section
        # The honesty note: patterns firm up around 5–7, so this is a lean.
        assert "5–7 verdicts" in section


class TestVerdictObjectiveEvidence:
    """The goal card's verdict axis (ADR 0126): the same whole-video
    verdicts, tallied per objective from each bundle's frozen context —
    the goal the video was actually made for when it was judged."""

    def _row(self, verdict, objective):
        bundle = _bundle("Hook")
        bundle["context"] = {**bundle["context"], "objective": objective}
        return {"verdict": verdict, "bundle": bundle}

    def test_tallies_verdicts_per_objective(self):
        import feedback as feedback_mod

        evidence = feedback_mod.verdict_objective_evidence([
            self._row("up", "demonstrate_feature"),
            self._row("up", "demonstrate_feature"),
            self._row("down", "demonstrate_feature"),
            self._row("up", "create_curiosity"),
        ])
        assert evidence["demonstrate_feature"] == {
            "wins": 2, "flops": 1, "adoptions": 0, "posted": 0, "views": 0}
        assert evidence["create_curiosity"] == {
            "wins": 1, "flops": 0, "adoptions": 0, "posted": 0, "views": 0}

    def test_rows_that_cannot_speak_for_a_goal_are_skipped(self):
        import feedback as feedback_mod

        no_context = _bundle("Hook")
        no_context["context"] = {}
        evidence = feedback_mod.verdict_objective_evidence([
            {"verdict": "up", "bundle": no_context},
            {"verdict": "sideways", "bundle": _bundle("Hook")},
            {"verdict": "up", "bundle": None},
            {"verdict": "down"},
            "not a row",
        ])
        assert evidence == {}

    def test_no_rows_means_no_evidence(self):
        import feedback as feedback_mod

        assert feedback_mod.verdict_objective_evidence([]) == {}
        assert feedback_mod.verdict_objective_evidence(None) == {}


class _Stop(Exception):
    pass


class TestVerdictPromptWiring:
    """The verdict section must reach both prompts, and nothing else may."""

    def _capture(self, monkeypatch):
        import ai_service

        captured = {}

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            captured[context] = prompt
            raise _Stop()

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        return captured

    def _summary(self, feedback_mod, count):
        verdicts = [("up", "Worked hook one"), ("up", "Worked hook two"),
                    ("down", "Flopped hook three")]
        return feedback_mod.summarize_video_verdicts([
            {"verdict": verdict, "bundle": _bundle(hook)}
            for verdict, hook in verdicts[:count]
        ])

    def test_three_verdicts_reach_plan_and_strategy_prompts(self, monkeypatch):
        import ai_service
        import feedback as feedback_mod

        captured = self._capture(monkeypatch)
        profile = {"brand_name": "Taskly", "core_features": ["Task timer"]}
        template = {"name": "Stop Doing This", "category": "pain-point-question"}
        summary = self._summary(feedback_mod, 3)
        with pytest.raises(_Stop):
            _run(ai_service.generate_creative_plan(
                profile=profile, template=template, verdict_feedback=summary))
        with pytest.raises(_Stop):
            _run(ai_service.generate_video_strategy(
                profile=profile, template=template, verdict_feedback=summary))
        prompts = list(captured.values())
        assert len(prompts) == 2
        for prompt in prompts:
            assert "FOUNDER VERDICTS ON WHOLE FINISHED VIDEOS" in prompt
            assert "Worked hook one" in prompt
            assert "Flopped hook three" in prompt
            # The old fragmented sections are gone from both prompts.
            assert "PROFILE FEEDBACK" not in prompt
            assert "PAST FEEDBACK FOR THIS APP" not in prompt
            assert "FOUNDER VERDICTS on the" not in prompt
            assert "Posted results so far" not in prompt

    def test_two_verdicts_reach_neither_prompt(self, monkeypatch):
        import ai_service
        import feedback as feedback_mod

        captured = self._capture(monkeypatch)
        profile = {"brand_name": "Taskly", "core_features": ["Task timer"]}
        template = {"name": "Stop Doing This", "category": "pain-point-question"}
        summary = self._summary(feedback_mod, 2)
        with pytest.raises(_Stop):
            _run(ai_service.generate_creative_plan(
                profile=profile, template=template, verdict_feedback=summary))
        with pytest.raises(_Stop):
            _run(ai_service.generate_video_strategy(
                profile=profile, template=template, verdict_feedback=summary))
        for prompt in captured.values():
            assert "FOUNDER VERDICTS ON WHOLE FINISHED VIDEOS" not in prompt
            assert "Worked hook one" not in prompt


FAKE_PLAN = {
    "hook_line": "Stop writing empty pages",
    "script": "Taskly gives you one short prompt and a reminder. It works offline.",
    "beat_timeline": [
        {"start": 0, "end": 3, "label": "hook", "text": "Stop writing empty pages"},
        {"start": 3, "end": 15, "label": "middle", "text": "The blank page loses its grip"},
    ],
    "visual_direction": "Close on hands, then a real desk with clean space for overlays.",
    "demo_brief": "Record yourself tapping the timer once, hands only.",
    "overlays": [{"start": 0, "end": 3, "text": "one prompt"}],
    "voice_direction": "Warm, unhurried",
    "sound_direction": "Lo-fi bed, rights-safe",
    "cta": "Try the 3-day free trial",
}


def _approved_profile(api, name):
    from models import BrandProfileCreateRequest, ApproveAppProfileRequest

    profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
        brand_name=name,
        app_category="Productivity",
        brand_description="A focus timer for people who stall on starting.",
        core_features=["Task timer", "Reminders"],
        usage_moments=["Starting a task they have been avoiding"],
        outcome_statements=[{
            "outcome": "Starting without stalling on setup",
            "who_feels_it": "people who stall on starting",
            "from_feature": "Task timer",
            "how_it_helps": "The timer starts in one tap so there is nothing to set up",
        }],
        ctas=["Try it free"],
    ), user_id=ANON))
    _run(api.approve_app_profile(
        profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
    return _run(api.get_app_profile(profile["id"], ANON))


def _a_project(api, profile):
    from models import CreateStudioProjectRequest

    template = _run(api.list_templates(q="Stop Doing This", user_id=ANON))["templates"][0]
    return _run(api.create_studio_project(payload=CreateStudioProjectRequest(
        brand_profile_id=profile["id"],
        template_id=template["id"],
        objective="demonstrate_feature",
    ), user_id=ANON))


def _seed_verdicts(api, profile_id, verdicts):
    for verdict in verdicts:
        generation_id, _p = _rated_render(api, brand_profile_id=profile_id)
        _set_verdict(api, generation_id, verdict)


class TestStudioVerdictWiring:
    """The handlers hand verdict bundles — and only verdict bundles — over."""

    def test_plan_receives_verdict_feedback_at_three(self, api, monkeypatch):
        from models import GeneratePlanRequest

        profile = _approved_profile(api, "Verdict Plan")
        project = _a_project(api, profile)
        _seed_verdicts(api, profile["id"], ["up", "up", "down"])
        seen = {}

        async def fake_plan(**kwargs):
            seen.update(kwargs)
            return dict(FAKE_PLAN)

        monkeypatch.setattr(api, "generate_creative_plan", fake_plan)
        _run(api.generate_plan(project_id=project["id"],
                               payload=GeneratePlanRequest(), user_id=ANON))
        assert seen["verdict_feedback"]["total"] == 3
        assert seen["verdict_feedback"]["ready"] is True
        assert seen["verdict_feedback"]["up"] == 2
        assert "profile_feedback" not in seen
        assert "component_feedback" not in seen

    def test_plan_stays_unsteered_at_two(self, api, monkeypatch):
        from models import GeneratePlanRequest

        profile = _approved_profile(api, "Verdict Plan Two")
        project = _a_project(api, profile)
        _seed_verdicts(api, profile["id"], ["up", "down"])
        seen = {}

        async def fake_plan(**kwargs):
            seen.update(kwargs)
            return dict(FAKE_PLAN)

        monkeypatch.setattr(api, "generate_creative_plan", fake_plan)
        _run(api.generate_plan(project_id=project["id"],
                               payload=GeneratePlanRequest(), user_id=ANON))
        assert seen["verdict_feedback"]["total"] == 2
        assert seen["verdict_feedback"]["ready"] is False

    def test_strategy_receives_verdict_feedback_at_three(self, api, monkeypatch):
        from models import GenerateStrategyRequest

        profile = _approved_profile(api, "Verdict Strategy")
        project = _a_project(api, profile)
        _seed_verdicts(api, profile["id"], ["up", "down", "down"])
        seen = {}

        async def fake_strategy(**kwargs):
            seen.update(kwargs)
            raise _Stop()

        monkeypatch.setattr(api, "generate_video_strategy", fake_strategy)
        # The handler wraps a model failure as a 502; the capture is what
        # this test is about, and it is already filled by then.
        with pytest.raises(HTTPException):
            _run(api.generate_project_strategy(
                project_id=project["id"], payload=GenerateStrategyRequest(),
                user_id=ANON))
        assert seen["verdict_feedback"]["total"] == 3
        assert seen["verdict_feedback"]["ready"] is True
        assert "profile_feedback" not in seen
        assert "component_feedback" not in seen

    def test_old_thumbs_no_longer_reach_generation(self, api, monkeypatch):
        """The refine path is gone: recorded per-element thumbs — including
        plan thumbs-down, the old refine trigger — change nothing the
        generators receive. Only whole-video verdicts arrive."""
        from models import FeedbackRequest, GeneratePlanRequest

        profile = _approved_profile(api, "Verdict Old Thumbs")
        project = _a_project(api, profile)
        for component, event in (("plan", "thumb_down"), ("script", "thumb_down"),
                                 ("goal", "thumb_up"), ("template", "thumb_down")):
            _run(api.record_feedback(FeedbackRequest(
                event=event, step=component,
                brand_profile_id=profile["id"],
                studio_project_id=project["id"]), ANON))
        seen = {}

        async def fake_plan(**kwargs):
            seen.update(kwargs)
            return dict(FAKE_PLAN)

        monkeypatch.setattr(api, "generate_creative_plan", fake_plan)
        _run(api.generate_plan(project_id=project["id"],
                               payload=GeneratePlanRequest(), user_id=ANON))
        assert seen["verdict_feedback"]["total"] == 0
        assert "profile_feedback" not in seen
        assert "component_feedback" not in seen
