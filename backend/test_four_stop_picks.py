"""The four-stop unification (Nov 27 2026, Kasra's rule).

Every fixed setting toggle carries exactly four real, functional
choices. The new stops under test:

  * Shape gains "command" — the hook as a direct imperative dare,
    steered and enforced on the same path as question/statement.
  * Opening gains "reaction" — the hook opens on the presenter's
    facial reaction, in the same steering block as action/feeling.
  * Camera gains "auto" (resolves per angle at generation, else
    handheld) and "walking" (a selfie take while the presenter
    walks), wired through the plan/strategy/prompt chain. Fixed
    stays indoor-only exactly as before.
  * Voice gains "auto" (talking unless the angle/profile carries a
    silent direction) and "voiceover" (silent-lipped presenter, the
    spoken line delivered as the video model's own narration audio
    over the segment — the only audio path the app has).
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
HOOK = "I'm trying to clear my head before bed but my thoughts race."
COMMAND_HOOK = "Try naming the tight feeling before it slips away tonight."
assert len(HOOK.split()) == 12
assert len(COMMAND_HOOK.split()) <= 12


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-fourstop-")
    os.environ.pop("TURSO_DATABASE_URL", None)
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""
    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    original = (server.pipeline.VIDEOS_DIR, server.pipeline.GENERATED_DIR)
    server.pipeline.VIDEOS_DIR = Path(tmpdir) / "videos"
    server.pipeline.GENERATED_DIR = Path(tmpdir) / "generated"
    server.pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    server.pipeline.GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    asyncio.run(server.init_db())
    try:
        yield server
    finally:
        server.pipeline.VIDEOS_DIR, server.pipeline.GENERATED_DIR = original
        sys.modules.pop("server", None)


def _run(coro):
    return asyncio.run(coro)


PROFILE_FACTS = {
    "name": "Vocolens",
    "category": "Wellness",
    "description": "Speak your journal entry instead of writing it.",
    "platforms": [],
    "features": ["Voice entries"],
    "use_cases": ["Winding down after work"],
    "problems": [],
    "desired_outcomes": ["Clearing the day's thoughts out loud"],
    "outcome_statements": [],
    "differentiators": "",
    "known_limitations": "",
}


def _profile(api, name):
    from models import ApproveAppProfileRequest, BrandProfileCreateRequest
    profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
        brand_name=name, app_category="Wellness",
        brand_description="Speak your journal entry instead of writing it.",
        target_audience="people too tired to write at night",
        core_features=["Voice entries", "Emotion check-ins"],
        usage_moments=["Winding down after work"],
        outcome_statements=[{
            "outcome": "Clearing the day's thoughts out loud",
            "who_feels_it": "people too tired to write",
            "from_feature": "Voice entries",
            "how_it_helps": "Talking replaces writing the entry",
        }],
    ), user_id=ANON))
    _run(api.approve_app_profile(
        profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
    return profile


def _hook_cta(api, name):
    from models import CreateHookCtaProjectRequest
    profile = _profile(api, name)
    project = _run(api.create_hook_cta_project(payload=CreateHookCtaProjectRequest(
        brand_profile_id=profile["id"],
    ), user_id=ANON))
    return project, profile


def _stub_chat(monkeypatch, replies):
    import ai_service
    queue = list(replies)
    calls = []

    async def fake_chat(**kwargs):
        calls.append(kwargs)
        return queue.pop(0) if queue else {}

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat)
    return calls


def _draft_calls(calls):
    return [c for c in calls if c.get("context") == "Hook line"]


def _hook_reply(**overrides):
    reply = {
        "hook_line": HOOK,
        "hook_action": "Jerks upright in her chair, both hands flying up as the thought lands.",
        "closing_action": "Leans in, eyebrows up, holding the look straight at the camera.",
        "location": "A quiet bedroom in the evening",
    }
    reply.update(overrides)
    return reply


def _plan_reply():
    return {
        "hook_line": "Naming the feeling never worked.",
        "script": (
            "The suggestions helped me find the words for what I was "
            "feeling. I understood myself better after speaking the "
            "entry, and my chest felt lighter."),
        "beat_timeline": [
            {"start": 0, "end": 3, "label": "hook",
             "text": "Naming the feeling never worked."},
            {"start": 3, "end": 15, "label": "middle", "text": "script"},
        ],
        "visual_direction": "A person reflecting at their desk.",
        "demo_brief": "Record the emotion suggestions.",
        "voice_direction": "Conversational.",
        "sound_direction": "Voice only.",
        "claims_used": [],
    }


def _hook_project(**overrides):
    project = {
        "id": "hook-cta-1",
        "kind": "video",
        "surface": "hook_cta",
        "duration_seconds": 5,
        "camera_setup": "handheld",
        "location": "",
        "visual_direction": "",
    }
    project.update(overrides)
    return project


# ------------------------------------------------------------ the sets

class TestTheSetsCarryFourStops:
    def test_shape_opening_camera_voice_sets(self):
        import ai_service
        import generation_planning
        import server
        assert ai_service.HOOK_SHAPE_PICKS == ("auto", "question", "statement", "command")
        assert ai_service.HOOK_OPENING_PICKS == ("auto", "action", "feeling", "reaction")
        assert generation_planning.CAMERA_SETUPS == ("auto", "handheld", "walking", "fixed")
        assert server.VOICE_MODES == ("auto", "talking", "voiceover", "silent")


# ------------------------------------------------------- shape: command

class TestCommandShape:
    def test_the_steering_block_carries_the_command_instruction(self):
        import ai_service
        block = ai_service._hook_steering_block(
            _hook_project(hook_shape="command"), PROFILE_FACTS)
        assert "SHAPE: a command" in block
        assert "imperative" in block
        assert "dare" in block

    def test_a_command_pick_normalizes_and_unknown_reads_auto(self):
        import ai_service
        assert ai_service._hook_shape_pick({"hook_shape": "command"}) == "command"
        assert ai_service._hook_shape_pick({"hook_shape": "bogus"}) == "auto"

    def test_a_first_person_reply_is_charged_and_corrected(self, monkeypatch):
        import ai_service
        calls = _stub_chat(monkeypatch, [
            _hook_reply(hook_line=HOOK),
            _hook_reply(hook_line=COMMAND_HOOK),
        ])
        out = _run(ai_service.generate_hook_line(
            _hook_project(hook_shape="command"), PROFILE_FACTS))
        drafts = _draft_calls(calls)
        assert "SHAPE: a command" in drafts[0]["prompt"]
        assert len(drafts) == 2
        assert "command hook" in str(drafts[1])
        assert out["hook_line"] == COMMAND_HOOK

    def test_a_command_reply_passes_the_gate_in_one_draft(self, monkeypatch):
        import ai_service
        calls = _stub_chat(monkeypatch, [_hook_reply(hook_line=COMMAND_HOOK)])
        out = _run(ai_service.generate_hook_line(
            _hook_project(hook_shape="command"), PROFILE_FACTS))
        assert out["hook_line"] == COMMAND_HOOK
        assert len(_draft_calls(calls)) == 1

    def test_the_rewrite_carries_the_command_steering(self, monkeypatch):
        import ai_service
        calls = _stub_chat(monkeypatch, [
            {"hook_line": COMMAND_HOOK},
        ])
        out = _run(ai_service.rewrite_hook_line(
            PROFILE_FACTS, None, HOOK, hook_shape="command"))
        assert out == COMMAND_HOOK
        assert "command hook" in calls[0]["prompt"]


# ----------------------------------------------------- opening: reaction

class TestReactionOpening:
    def test_the_steering_block_carries_the_reaction_instruction(self):
        import ai_service
        block = ai_service._hook_steering_block(
            _hook_project(hook_opening="reaction"), PROFILE_FACTS)
        assert "OPENING: reaction" in block
        assert "face" in block

    def test_the_hook_prompt_carries_the_reaction_pick(self, monkeypatch):
        import ai_service
        calls = _stub_chat(monkeypatch, [_hook_reply()])
        _run(ai_service.generate_hook_line(
            _hook_project(hook_opening="reaction"), PROFILE_FACTS))
        assert "OPENING: reaction" in calls[0]["prompt"]
        assert ai_service._hook_opening_pick({"hook_opening": "reaction"}) == "reaction"


# ------------------------------------------------------------- camera

class TestCameraResolution:
    def test_auto_resolves_to_handheld_without_an_angle_direction(self):
        import generation_planning
        assert generation_planning.resolve_camera_setup("auto") == "handheld"
        assert generation_planning.resolve_camera_setup("") == "handheld"
        assert generation_planning.resolve_camera_setup(None) == "handheld"

    def test_auto_resolves_to_the_angles_own_direction(self):
        import generation_planning
        angle = {"camera_setup": "fixed"}
        assert generation_planning.resolve_camera_setup("auto", angle) == "fixed"
        angle = {"camera_setup": "walking"}
        assert generation_planning.resolve_camera_setup("auto", angle) == "walking"

    def test_explicit_picks_resolve_to_themselves(self):
        import generation_planning
        for pick in ("handheld", "walking", "fixed"):
            assert generation_planning.resolve_camera_setup(pick) == pick
            assert generation_planning.resolve_camera_setup(
                pick, {"camera_setup": "fixed"}) == pick

    def test_normalize_strategy_accepts_walking_and_refuses_auto(self):
        import ai_strategy
        strategy = ai_strategy.normalize_strategy({"camera_setup": "walking"})
        assert strategy["camera_setup"] == "walking"
        with pytest.raises(ValueError, match="handheld, walking or fixed"):
            ai_strategy.normalize_strategy({"camera_setup": "auto"})

    def test_walking_starting_shot_and_camera_move(self):
        import generation_planning
        shot = generation_planning.starting_shot("walking")
        assert "Walking selfie" in shot
        move = generation_planning.camera_move_section(
            {"camera_setup": "walking",
             "camera_beat": {"direction": "right", "gesture": ""}})
        assert "Walking selfie for the whole take" in move
        # Fixed is untouched by the new stops.
        assert generation_planning.starting_shot("fixed") == (
            generation_planning.FIXED_STARTING_SHOT)

    def test_the_two_section_schema_writes_a_walking_middle(self):
        import ai_strategy
        schema = ai_strategy._two_section_schema(10, "walking")
        assert "while walking steadily through the scene" in schema
        fixed_schema = ai_strategy._two_section_schema(10, "fixed")
        assert "while walking" not in fixed_schema

    def test_the_plan_prompt_carries_the_walking_rule(self, monkeypatch):
        import ai_service
        calls = _stub_chat(monkeypatch, [_plan_reply() for _ in range(6)])
        _run(ai_service.generate_creative_plan(
            PROFILE_FACTS, {}, camera_setup="walking"))
        prompt = calls[0]["prompt"]
        assert "WALKING:" in prompt
        assert "walking steadily through" in prompt

    def test_the_plan_prompt_resolves_auto_before_writing(self, monkeypatch):
        import ai_service
        calls = _stub_chat(monkeypatch, [_plan_reply() for _ in range(6)])
        _run(ai_service.generate_creative_plan(
            PROFILE_FACTS, {}, camera_setup="auto"))
        prompt = calls[0]["prompt"]
        # Resolved to handheld: the selfie rule stands, no walking or
        # fixed rule is written for the pick itself.
        assert "WALKING:" not in prompt
        assert "SELFIE:" in prompt


# -------------------------------------------------------------- voice

class TestVoiceResolution:
    def test_auto_talks_without_a_silent_direction(self, api):
        assert api.resolve_voice_mode("auto") == "talking"
        assert api.resolve_voice_mode("") == "talking"
        assert api.resolve_voice_mode(None) == "talking"
        assert api.resolve_voice_mode("bogus") == "talking"

    def test_auto_resolves_silent_from_an_angle_or_profile_direction(self, api):
        assert api.resolve_voice_mode(
            "auto", angle={"voice_delivery": "silent"}) == "silent"
        assert api.resolve_voice_mode(
            "auto", profile={"voice_mode": "silent"}) == "silent"

    def test_explicit_picks_resolve_to_themselves(self, api):
        for pick in ("talking", "voiceover", "silent"):
            assert api.resolve_voice_mode(pick) == pick
            assert api.resolve_voice_mode(
                pick, angle={"voice_delivery": "silent"}) == pick


# ------------------------------------------------------ API validation

class TestPickValidation:
    def test_the_new_voice_stops_save(self, api):
        from models import UpdateStudioProjectRequest
        project, _ = _hook_cta(api, "Four Stop Voice Saves")
        for value in ("auto", "voiceover", "talking"):
            out = _run(api.update_studio_project(
                project["id"], UpdateStudioProjectRequest(voice_mode=value), ANON))
            assert out["voice_mode"] == value

    def test_an_unknown_voice_value_is_still_refused(self, api):
        from models import UpdateStudioProjectRequest
        project, _ = _hook_cta(api, "Four Stop Voice Refused")
        with pytest.raises(HTTPException) as exc:
            _run(api.update_studio_project(
                project["id"], UpdateStudioProjectRequest(voice_mode="loud"), ANON))
        assert exc.value.status_code == 400
        assert "voiceover" in exc.value.detail

    def test_the_new_shape_and_opening_stops_save(self, api):
        from models import UpdateStudioProjectRequest
        project, _ = _hook_cta(api, "Four Stop Hook Picks Save")
        out = _run(api.update_studio_project(
            project["id"], UpdateStudioProjectRequest(hook_shape="command"), ANON))
        assert out["hook_shape"] == "command"
        out = _run(api.update_studio_project(
            project["id"], UpdateStudioProjectRequest(hook_opening="reaction"), ANON))
        assert out["hook_opening"] == "reaction"

    def test_a_fresh_wizard_project_opens_on_the_apps_choice_camera(self, api):
        from models import CreateStudioProjectRequest
        profile = _profile(api, "Four Stop Camera Fresh")
        wizard = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"]), user_id=ANON))
        assert wizard["camera_setup"] == "auto"

    def test_the_camera_stops_save_and_bogus_values_are_refused(self, api):
        from models import CreateStudioProjectRequest, UpdateStudioProjectRequest
        profile = _profile(api, "Four Stop Camera Saves")
        wizard = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"]), user_id=ANON))
        for value in ("walking", "fixed", "handheld", "auto"):
            out = _run(api.update_studio_project(
                wizard["id"], UpdateStudioProjectRequest(camera_setup=value), ANON))
            assert out["camera_setup"] == value
        with pytest.raises(Exception):
            UpdateStudioProjectRequest(camera_setup="orbit")


# ------------------------------------------------- submit: the voiceover

def _attach_face(api, project):
    from models import now_iso
    face = Path(tempfile.mkdtemp(prefix="tiktok-fourstop-face-")) / "face.png"
    face.write_bytes(bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c626001000000ffff0300000600055d3866680000000049454e44ae426082"))
    asset_id = str(uuid.uuid4())
    now = now_iso()
    _run(api._execute(
        "INSERT INTO assets (id, brand_profile_id, kind, name, file_path, label,"
        " created_at, updated_at, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (asset_id, project["brand_profile_id"], "character_reference",
         "Founder face", str(face), "Founder face", now, now, ANON)))
    assets = [{"asset_id": asset_id, "kind": "character_reference",
               "label": "Founder face", "file_path": str(face)}]
    _run(api._execute(
        "UPDATE studio_projects SET assets = ? WHERE id = ?",
        (json.dumps(assets), project["id"])))
    return assets


def _mock_submit(api, monkeypatch):
    calls = []

    async def fake_generate_video(**kwargs):
        calls.append(kwargs)
        return {"id": f"job-{len(calls)}", "status": "queued",
                "usage": {"cost": 0.05}}

    monkeypatch.setattr(api, "generate_video", fake_generate_video)
    return calls


def _silence_poster(api, monkeypatch):
    async def no_poster(background_tasks, generation_id, user_id):
        return None

    monkeypatch.setattr(api, "_schedule_poster", no_poster)


def _ready_hook(api, monkeypatch, name):
    from models import GenerateHookLineRequest
    project, _ = _hook_cta(api, name)

    async def fake_hook_line(project_arg, profile_arg):
        return _hook_reply()

    monkeypatch.setattr(api.ai_service, "generate_hook_line", fake_hook_line)
    _run(api.generate_hook_cta_hook(
        project["id"], GenerateHookLineRequest(), ANON))
    _attach_face(api, project)
    return project


class TestVoiceSubmit:
    def test_a_voiceover_hook_submits_audio_on_with_the_voiceover_direction(
            self, api, monkeypatch):
        from models import GenerateHookRequest, UpdateStudioProjectRequest
        project = _ready_hook(api, monkeypatch, "Four Stop Voiceover Submit")
        _run(api.update_studio_project(
            project["id"], UpdateStudioProjectRequest(voice_mode="voiceover"), ANON))
        calls = _mock_submit(api, monkeypatch)
        _silence_poster(api, monkeypatch)
        generation = _run(api.generate_hook_cta(
            project["id"], GenerateHookRequest(), ANON))
        # Audio is billed and requested — the model's own narration is
        # the voiceover — and the prompt separates it from silence:
        # silent-lipped presenter, off-camera narrator voice.
        assert calls[0]["generate_audio"] is True
        prompt = calls[0]["prompt"]
        assert "VOICEOVER PERFORMANCE" in prompt
        assert "mouth stays closed and still" in prompt
        assert "off-camera narrator" in prompt
        assert "SILENT PERFORMANCE" not in prompt
        row = _run(api._fetch_one(
            "SELECT voice_mode FROM generations WHERE id = ?",
            (generation["id"],)))
        assert row["voice_mode"] == "voiceover"

    def test_an_auto_hook_resolves_to_talking_at_submit(self, api, monkeypatch):
        from models import GenerateHookRequest, UpdateStudioProjectRequest
        project = _ready_hook(api, monkeypatch, "Four Stop Auto Submit")
        _run(api.update_studio_project(
            project["id"], UpdateStudioProjectRequest(voice_mode="auto"), ANON))
        calls = _mock_submit(api, monkeypatch)
        _silence_poster(api, monkeypatch)
        generation = _run(api.generate_hook_cta(
            project["id"], GenerateHookRequest(), ANON))
        assert calls[0]["generate_audio"] is not False
        assert "VOICEOVER PERFORMANCE" not in calls[0]["prompt"]
        assert "SILENT PERFORMANCE" not in calls[0]["prompt"]
        row = _run(api._fetch_one(
            "SELECT voice_mode FROM generations WHERE id = ?",
            (generation["id"],)))
        assert row["voice_mode"] == "talking"

    def test_a_silent_hook_records_silent_on_the_row(self, api, monkeypatch):
        from models import GenerateHookRequest, UpdateStudioProjectRequest
        project = _ready_hook(api, monkeypatch, "Four Stop Silent Submit")
        _run(api.update_studio_project(
            project["id"], UpdateStudioProjectRequest(voice_mode="silent"), ANON))
        calls = _mock_submit(api, monkeypatch)
        _silence_poster(api, monkeypatch)
        generation = _run(api.generate_hook_cta(
            project["id"], GenerateHookRequest(), ANON))
        assert calls[0]["generate_audio"] is False
        row = _run(api._fetch_one(
            "SELECT voice_mode FROM generations WHERE id = ?",
            (generation["id"],)))
        assert row["voice_mode"] == "silent"
