"""
Tests for the FLEXIBLE influencer flow: hook first, then as much extension as
the founder wants.

The claim under test: extending twice produces two DIFFERENT beats, the founder
chooses how much each extension adds, a sub-floor length is delivered at the
length they asked for rather than silently longer, and the declared intent
never invalidates work already done.
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
_TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c626001000000ffff0300000600055d3866680000000049454e44ae426082"
)


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-flex-")
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


def _mock_submit(api, monkeypatch):
    calls = []

    async def fake_generate_video(**kwargs):
        calls.append(kwargs)
        return {"id": f"job-{len(calls)}", "status": "queued", "usage": {"cost": 0.2}}

    monkeypatch.setattr(api, "generate_video", fake_generate_video)
    return calls


def _async_return(value):
    async def _inner(*_a, **_kw):
        return value
    return _inner


# A strategy shaped like a real one, with a full planned arc.
BEAT_SCRIPTS = {
    0: "I clocked out at 11:40. Every single night.",
    1: "One tap and the shift is logged. That is it.",
    2: "The break tracker caught the overrun I always miss.",
    3: "Before I worked here, nobody told me the policy changed.",
    4: "Now the hours are right before payroll, not after.",
    5: "I stopped checking my rota on my day off.",
    6: "Ask your charge nurse before you build a schedule by hand.",
    7: "Try it free — it took me an afternoon to set up.",
}


def _plan_strategy(api, project_id, *, beats=8):
    """Write a strategy with a full planned arc, directly, as the model would."""
    from ai_service import normalize_strategy

    segments = [
        {
            "index": i,
            "role": "cta" if i == beats - 1 else ("hook" if i == 0 else "continuation"),
            "seconds": 3,
            "goal": f"beat {i} goal",
            "script": BEAT_SCRIPTS[i],
            "action": f"beat {i} action",
        }
        for i in range(beats)
    ]
    strategy = normalize_strategy({
        "strategy_summary": "Show the one thing this app removes.",
        "audience_problem": "The paperwork is the whole problem.",
        "emotional_triggers": ["relief"],
        "hook_concept": "Open mid-motion, then the relief.",
        "hook_line": BEAT_SCRIPTS[0],
        "hook_promise": "Show the tap.",
        "hook_action": "Taps the phone once.",
        "hook_dialogue": "Low and quick.",
        "messaging_pillars": ["One tap"],
        "primary_feature": "One-tap shift logging",
        "desired_outcome": "Out on time",
        "differentiation_beat": "Built for shifts.",
        "cta_strategy": "Try it free",
        "character": {"appearance": "a nurse in teal scrubs", "facial_features": "round face",
                      "hairstyle": "low bun", "wardrobe": "teal scrubs",
                      "body_appearance": "average", "age_range": "late 20s",
                      "facial_expression": "tired smile", "styling_details": "none"},
        "scene": {"camera_angle": "eye level", "framing": "medium close-up",
                  "lighting": "cool fluorescents", "environment": "a corridor",
                  "background": "grey floor", "setting": "11pm",
                  "visual_style": "handheld UGC", "character_positioning": "centred",
                  "props": "a phone", "color_palette": "grey and teal"},
        "performance": {"movement": "one-handed", "voice_delivery": "low, quick"},
        "segments": segments,
        "continuity_contract": {"established": ["teal scrubs", "a corridor"],
                                "must_not_change": ["the face", "the scrubs"],
                                "do_not_repeat": [BEAT_SCRIPTS[0]]},
    })
    _run(api._execute(
        "UPDATE studio_projects SET strategy = ?, strategy_version = 1, status = 'draft'"
        " WHERE id = ?", (json.dumps(strategy), project_id)))
    return strategy


def _project(api, name, *, total=20, hook=4, with_strategy=True, beats=8):
    from models import (
        ApproveAppProfileRequest, BrandProfileCreateRequest,
        CreateStudioProjectRequest, now_iso,
    )
    profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
        brand_name=name, app_category="Productivity",
        core_features=["One-tap shift logging"],
        claims_approved=["Logs a shift in one tap"],
        claims_banned=["cures burnout"],
    ), user_id=ANON))
    _run(api.approve_app_profile(
        profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
    template = _run(api.list_templates(user_id=ANON))["templates"][0]
    project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
        brand_profile_id=profile["id"], template_id=template["id"],
        duration_seconds=total, hook_seconds=hook,
    ), user_id=ANON))

    face = Path(tempfile.mkdtemp(prefix="tiktok-face-")) / "face.png"
    face.write_bytes(_TINY_PNG)
    asset_id = str(uuid.uuid4())
    now = now_iso()
    _run(api._execute(
        "INSERT INTO assets (id, brand_profile_id, kind, name, file_path, label,"
        " created_at, updated_at, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (asset_id, profile["id"], "character_reference", "Founder face",
         str(face), "Founder face", now, now, ANON)))
    _run(api._execute(
        "UPDATE studio_projects SET assets = ? WHERE id = ?",
        (json.dumps([{"asset_id": asset_id, "kind": "character_reference",
                      "label": "Founder face", "file_path": str(face)}]),
         project["id"])))

    if with_strategy:
        _plan_strategy(api, project["id"], beats=beats)
    return _run(api.get_studio_project(project["id"], ANON))


def _hook_and_approve(api, monkeypatch, project, model="minimax-h3"):
    """Generate the hook, mark it completed, approve it, and make it extendable."""
    from models import ApproveSegmentRequest, GenerateHookRequest
    _mock_submit(api, monkeypatch)
    hook = _run(api.generate_project_hook(
        project_id=project["id"],
        payload=GenerateHookRequest(model=model, duration_seconds=3), user_id=ANON))
    _run(api._execute(
        "UPDATE generations SET status = 'completed', video_url = ? WHERE id = ?",
        ("https://provider.test/hook.mp4", hook["id"])))
    bridge = Path(tempfile.mkdtemp(prefix="tiktok-bridge-")) / "bridge.png"
    bridge.write_bytes(_TINY_PNG)
    api.pipeline.extract_last_frame = _async_return(bridge)
    _run(api.approve_generation(hook["id"], ApproveSegmentRequest(), ANON))
    return hook


def _extend(api, monkeypatch, parent, seconds, model="minimax-h3"):
    from models import StudioGenerationRequest
    calls = _mock_submit(api, monkeypatch)
    ext = _run(api.extend_generation(
        parent["id"], StudioGenerationRequest(
            duration_seconds=seconds, model=model), user_id=ANON))
    _run(api._execute(
        "UPDATE generations SET status = 'completed' WHERE id = ?", (ext["id"],)))
    _run(api.approve_generation(ext["id"], __import__("models").ApproveSegmentRequest(), ANON))
    return ext, calls[0]


# ---------------------------------------------------------------------------
# 1. The repeat bug: each extension must be a NEW beat
# ---------------------------------------------------------------------------
class TestEachExtensionIsANewBeat:
    def test_the_strategy_plans_a_sequence_not_two_segments(self):
        import ai_service
        body = '[{"index": 0, "role": "hook", "seconds": 3}' + \
            ai_service._continuation_segment_schema(3) + ']'
        arr = json.loads(body)
        assert len(arr) == 8, "a two-segment plan is what caused the repeat bug"
        assert arr[0]["role"] == "hook"
        assert arr[-1]["role"] == "cta", "the last beat must land the CTA"
        assert [s["index"] for s in arr] == list(range(8))

    def test_two_extensions_get_different_scripts(self, api, monkeypatch):
        """
        The regression. Extending twice used to replay the last planned beat
        verbatim, so the same words and the same action played twice.
        """
        project = _project(api, "Repeat Guard")
        hook = _hook_and_approve(api, monkeypatch, project)

        first, call1 = _extend(api, monkeypatch, hook, seconds=5)
        second, call2 = _extend(api, monkeypatch, first, seconds=5)

        assert BEAT_SCRIPTS[1] in call1["prompt"]
        assert BEAT_SCRIPTS[2] in call2["prompt"]
        assert BEAT_SCRIPTS[1] not in call2["prompt"], (
            "the second extension replayed the first one's script"
        )
        assert call1["prompt"] != call2["prompt"]

    def test_segment_lookup_never_borrows_another_beat(self):
        from generation_planning import _segment_for
        strategy = {"segments": [
            {"index": 0, "script": "a"}, {"index": 1, "script": "b"}]}
        assert _segment_for(strategy, 0)["script"] == "a"
        assert _segment_for(strategy, 1)["script"] == "b"
        # Past the end returns nothing rather than replaying the last beat.
        assert _segment_for(strategy, 2) == {}
        assert _segment_for({"segments": []}, 1) == {}

    def test_an_unplanned_beat_does_not_silence_the_prompt(self, api, monkeypatch):
        """
        If a gap ever reaches the prompt builder, it must still instruct the
        model forward rather than rendering an empty segment.
        """
        from generation_planning import build_segment_prompt
        strategy = {"segments": [{"index": 0, "script": "a"}],
                    "continuity_contract": {"do_not_repeat": ["a"]},
                    "character": {}, "scene": {}, "performance": {}}
        prompt = build_segment_prompt(
            strategy=strategy, profile={"brand_name": "App"}, template={},
            segment_index=1, duration=5, is_hook=False)
        assert "did not plan a specific beat" in prompt
        assert "Do not replay any earlier moment" in prompt


# ---------------------------------------------------------------------------
# 2. The founder chooses how much each extension adds
# ---------------------------------------------------------------------------
class TestExtensionLength:
    def test_the_requested_length_is_honoured(self, api, monkeypatch):
        project = _project(api, "Length Choice")
        hook = _hook_and_approve(api, monkeypatch, project)
        ext, call = _extend(api, monkeypatch, hook, seconds=8)
        assert call["duration"] == 8
        assert ext["trim_to_seconds"] == 0
        assert ext["length_plan"]["guarantee"] == "as_rendered"

    def test_a_sub_floor_length_is_rendered_longer_then_trimmed(self, api, monkeypatch):
        """
        "Extend by 3s" on a provider whose floor is 5s must be delivered at 3s,
        not quietly at 5s. Same resolution the hook already uses.
        """
        project = _project(api, "Sub Floor Extend")
        hook = _hook_and_approve(api, monkeypatch, project)
        ext, call = _extend(api, monkeypatch, hook, seconds=3)
        assert call["duration"] == 5, "the model must be asked for what it can render"
        assert ext["trim_to_seconds"] == 3, "but the delivered clip must be 3s"
        assert ext["duration"] == 3
        assert ext["length_plan"]["guarantee"] == "trimmed"

    def test_minimax_floor_of_five_applies_to_extensions_too(self, api, monkeypatch):
        project = _project(api, "H3 Extend")
        hook = _hook_and_approve(api, monkeypatch, project, model="minimax-h3")
        ext, call = _extend(api, monkeypatch, hook, seconds=4, model="minimax-h3")
        assert call["duration"] == 5
        assert ext["trim_to_seconds"] == 4

    def test_a_length_above_the_provider_ceiling_is_refused(self, api, monkeypatch):
        """
        Not clamped. A floor clamp is recoverable by a trim; a ceiling clamp
        silently hands back a different length than the one requested.
        """
        from models import StudioGenerationRequest
        project = _project(api, "Too Long")
        hook = _hook_and_approve(api, monkeypatch, project, model="minimax-h3")
        _mock_submit(api, monkeypatch)
        with pytest.raises(HTTPException) as err:
            _run(api.extend_generation(
                hook["id"], StudioGenerationRequest(
                    duration_seconds=60, model="minimax-h3"), user_id=ANON))
        assert err.value.status_code == 400
        assert "at most 15s" in str(err.value.detail)
        assert "60s" in str(err.value.detail)

    def test_an_unset_length_falls_back_to_a_sensible_default(self, api, monkeypatch):
        from models import StudioGenerationRequest
        project = _project(api, "Default Length")
        hook = _hook_and_approve(api, monkeypatch, project)
        calls = _mock_submit(api, monkeypatch)
        _run(api.extend_generation(
            hook["id"], StudioGenerationRequest(), user_id=ANON))
        assert calls[0]["duration"] == api.DEFAULT_EXTENSION_SECONDS


# ---------------------------------------------------------------------------
# 3. The plan is finite, and says so
# ---------------------------------------------------------------------------
class TestThePlanIsFinite:
    def test_extending_past_the_plan_is_refused_with_a_way_forward(self, api, monkeypatch):
        """
        The alternative to refusing was replaying a beat. The remedy is free:
        rebuilding the strategy costs no video generation.
        """
        project = _project(api, "Finite Plan", beats=3)
        hook = _hook_and_approve(api, monkeypatch, project)
        first, _ = _extend(api, monkeypatch, hook, seconds=5)
        second, _ = _extend(api, monkeypatch, first, seconds=5)
        _mock_submit(api, monkeypatch)
        with pytest.raises(HTTPException) as err:
            _run(api.extend_generation(
                second["id"], __import__("models").StudioGenerationRequest(
                    duration_seconds=5), user_id=ANON))
        assert err.value.status_code == 409
        message = str(err.value.detail)
        assert "you have used all of them" in message
        assert "repeat" in message
        assert "rebuild the strategy" in message.lower(), (
            "the refusal must name the remedy"
        )

    def test_a_full_eight_beat_plan_covers_a_normal_video(self, api, monkeypatch):
        """The default plan must not be the thing that stops a normal video."""
        project = _project(api, "Eight Beats", total=30, hook=4, beats=8)
        hook = _hook_and_approve(api, monkeypatch, project)
        parent = hook
        for i in range(3):
            parent, _ = _extend(api, monkeypatch, parent, seconds=8)
        # 4 + 3*8 = 28s of a 30s target, still inside the eight-beat plan.
        assert parent["segment_index"] == 3


# ---------------------------------------------------------------------------
# 4. Declared intent never invalidates anything
# ---------------------------------------------------------------------------
class TestExtendIntent:
    def test_a_new_project_intends_to_extend_by_default(self, api):
        from models import (
            ApproveAppProfileRequest, BrandProfileCreateRequest, CreateStudioProjectRequest,
        )
        profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
            brand_name="Intent Default", app_category="Productivity"), user_id=ANON))
        _run(api.approve_app_profile(
            profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
        template = _run(api.list_templates(user_id=ANON))["templates"][0]
        project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"], template_id=template["id"]), user_id=ANON))
        assert project["extend_intent"] is True, (
            "the hook is the opening of a video, so extending is the default path"
        )

    def test_toggling_intent_does_not_touch_the_strategy_version(self, api):
        """
        The whole reason the toggle is stored rather than derived: flipping it
        must never trigger the stale-strategy refusal or force a paid rebuild.
        """
        from models import UpdateStudioProjectRequest
        project = _project(api, "Intent Toggle")
        before = _run(api.get_studio_project(project["id"], ANON))
        assert before["strategy_version"] == 1

        off = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(extend_intent=False), user_id=ANON))
        assert off["extend_intent"] is False
        assert off["strategy_version"] == before["strategy_version"]
        assert off["strategy"]["hook_line"] == before["strategy"]["hook_line"]
        assert off["script_version"] == before["script_version"]

        on = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(extend_intent=True), user_id=ANON))
        assert on["extend_intent"] is True
        assert on["strategy_version"] == before["strategy_version"]

    def test_extending_is_still_possible_with_intent_off(self, api, monkeypatch):
        """
        "Just the hook for now" defers the decision, it does not remove the
        option. The whole point is that the founder can change their mind.
        """
        from models import UpdateStudioProjectRequest
        project = _project(api, "Intent Off Still Extends")
        _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(extend_intent=False), user_id=ANON))
        refreshed = _run(api.get_studio_project(project["id"], ANON))
        hook = _hook_and_approve(api, monkeypatch, refreshed)
        ext, call = _extend(api, monkeypatch, hook, seconds=5)
        assert ext["segment_index"] == 1
        assert call["duration"] == 5

    def test_intent_toggle_never_blocks_a_paid_call(self, api, monkeypatch):
        """Only hook generation, extension and assembly cost money; the toggle
        is a free preference and must behave like one."""
        from models import UpdateStudioProjectRequest
        project = _project(api, "Intent Free")
        for value in (False, True, False):
            _run(api.update_studio_project(
                project_id=project["id"],
                payload=UpdateStudioProjectRequest(extend_intent=value), user_id=ANON))
        assert _run(api.get_studio_project(project["id"], ANON))["extend_intent"] is False


# ---------------------------------------------------------------------------
# 5. The strategy reports its coverage so the UI can be honest
# ---------------------------------------------------------------------------
class TestStrategyCoverage:
    def test_the_endpoint_stores_planned_coverage_on_the_strategy(self, api, monkeypatch):
        """
        The UI must be able to say "the plan covers N more segments" BEFORE the
        founder commits to a length, or a 30s target quietly runs out of plan at
        segment 8.
        """
        from models import GenerateStrategyRequest

        project = _project(api, "Coverage", with_strategy=False)
        strategy = _plan_strategy(api, project["id"], beats=8)

        async def fake(**kwargs):
            return strategy

        monkeypatch.setattr(api, "generate_video_strategy", fake)
        updated = _run(api.generate_project_strategy(
            project_id=project["id"], payload=GenerateStrategyRequest(), user_id=ANON))
        assert updated["strategy"]["planned_segments"] == 8
        assert updated["strategy"]["max_planned_index"] == 7

    def test_a_short_plan_reports_its_shorter_coverage(self, api, monkeypatch):
        from models import GenerateStrategyRequest

        project = _project(api, "Short Coverage", with_strategy=False)
        strategy = _plan_strategy(api, project["id"], beats=3)

        async def fake(**kwargs):
            return strategy

        monkeypatch.setattr(api, "generate_video_strategy", fake)
        updated = _run(api.generate_project_strategy(
            project_id=project["id"], payload=GenerateStrategyRequest(), user_id=ANON))
        assert updated["strategy"]["planned_segments"] == 3
        assert updated["strategy"]["max_planned_index"] == 2

    def test_a_full_eight_beat_plan_survives_normalization(self):
        from ai_service import normalize_strategy
        strategy = normalize_strategy({"segments": [
            {"index": i, "role": "continuation", "seconds": 3, "script": f"s{i}"}
            for i in range(8)
        ]})
        assert len(strategy["segments"]) == 8
        assert max(int(s["index"]) for s in strategy["segments"]) == 7
