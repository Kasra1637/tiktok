"""
Tests for the app-specific AI influencer workflow.

The claim under test is specific and falsifiable: a hook generated for one app
must be strategically different from a hook for another app, the uploaded
person must be carried through the hook AND every extension, an extension must
preserve the scene and continue the same message, and any continuity the
provider cannot actually deliver must be reported rather than silently dropped.

OpenRouter is fully mocked, so these assert OUR rules and the exact requests we
build — not the quality of any model's output.
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

# A real 1x1 PNG so the identity resolver accepts the character reference.
_TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c626001000000ffff0300000600055d3866680000000049454e44ae426082"
)


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-influencer-")
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

    # Redirect the media directories too. pipeline.VIDEOS_DIR is a module-level
    # constant pointing at the real storage/videos, so without this the chain
    # tests would write stand-in clips straight into live storage.
    original_dirs = (server.pipeline.VIDEOS_DIR, server.pipeline.GENERATED_DIR)
    server.pipeline.VIDEOS_DIR = Path(tmpdir) / "videos"
    server.pipeline.GENERATED_DIR = Path(tmpdir) / "generated"
    server.pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    server.pipeline.GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    asyncio.run(server.init_db())
    try:
        yield server
    finally:
        server.pipeline.VIDEOS_DIR, server.pipeline.GENERATED_DIR = original_dirs
        sys.modules.pop("server", None)


def _run(coro):
    return asyncio.run(coro)


def _mock_submit(api, monkeypatch, response=None):
    """Replace the provider submit call, recording the kwargs it receives."""
    calls = []

    async def fake_generate_video(**kwargs):
        calls.append(kwargs)
        return response or {"id": f"job-{len(calls)}", "status": "queued", "usage": {"cost": 0.2}}

    monkeypatch.setattr(api, "generate_video", fake_generate_video)
    return calls


# ---------------------------------------------------------------------------
# Two genuinely different apps, so "app-specific" is testable rather than
# asserted in a comment.
# ---------------------------------------------------------------------------
NURSE_APP = {
    "brand_name": "ShiftLog",
    "app_category": "Productivity",
    "brand_description": "Shift logging for healthcare workers.",
    "target_audience": "hospital nurses working rotating shifts",
    "core_features": ["One-tap shift logging", "Automatic break tracking"],
    "primary_use_cases": ["Clocking on and off between shifts"],
    "problems_solved": ["Shift paperwork eats the end of a long shift"],
    "desired_outcomes": ["Leaving work on time"],
    "claims_approved": ["Logs a shift in one tap"],
    "claims_banned": ["cures burnout"],
    "tone_voice": "plain, tired, warm",
}

BUDGET_APP = {
    "brand_name": "Pennywise",
    "app_category": "Finance",
    "brand_description": "Automatic envelope budgeting from bank connections.",
    "target_audience": "first-time budgeters with irregular income",
    "core_features": ["Automatic envelope splits", "Subscription cancellation radar"],
    "primary_use_cases": ["Cancelling forgotten subscriptions before the next payday"],
    "problems_solved": ["Money disappears before payday with nothing to show for it"],
    "desired_outcomes": ["Knowing exactly what is safe to spend this week"],
    "claims_approved": ["Finds forgotten subscriptions"],
    "claims_banned": ["guarantees you will save money"],
    "tone_voice": "dry, wry, a bit conspiratorial",
}


def _make_project(api, spec, with_character=True):
    """An approved App Profile, a template, a project, and a character ref."""
    from models import (
        ApproveAppProfileRequest, BrandProfileCreateRequest,
        CreateStudioProjectRequest, now_iso,
    )
    profile = _run(api.create_brand(
        payload=BrandProfileCreateRequest(**spec), user_id=ANON))
    _run(api.approve_app_profile(
        profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
    template = _run(api.list_templates(user_id=ANON))["templates"][0]
    project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
        brand_profile_id=profile["id"], template_id=template["id"],
        duration_seconds=20,
    ), user_id=ANON))

    if with_character:
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
            (json.dumps([{
                "asset_id": asset_id, "kind": "character_reference",
                "label": "Founder face", "file_path": str(face),
            }]), project["id"])))
    return _run(api.get_studio_project(project["id"], ANON)), profile, template


def _store_strategy(api, project_id, hook_line, persona, scene, *, problem, feature, cta):
    """Write a strategy shaped like a real one from two different apps."""
    from ai_service import normalize_strategy
    strategy = normalize_strategy({
        "strategy_summary": f"{feature} for {persona['who']}.",
        "audience_problem": problem,
        "emotional_triggers": [persona["emotion"]],
        "hook_concept": persona["concept"],
        "hook_line": hook_line,
        "hook_promise": persona["promise"],
        "hook_action": persona["action"],
        "hook_dialogue": "direct to camera, mid-breath",
        "messaging_pillars": [feature],
        "primary_feature": feature,
        "desired_outcome": persona["outcome"],
        "differentiation_beat": persona["diff"],
        "cta_strategy": cta,
        "character": {
            "appearance": persona["who"],
            "facial_features": persona["face"],
            "hairstyle": persona["hair"],
            "wardrobe": persona["wardrobe"],
            "body_appearance": "average height, relaxed posture",
            "age_range": persona["age"],
            "facial_expression": persona["expression"],
            "styling_details": persona["styling"],
        },
        "scene": {
            "camera_angle": scene["camera"],
            "framing": scene["framing"],
            "lighting": scene["lighting"],
            "environment": scene["environment"],
            "background": scene["background"],
            "setting": scene["setting"],
            "visual_style": scene["style"],
            "character_positioning": scene["position"],
            "props": scene["props"],
            "color_palette": scene["palette"],
        },
        "performance": {
            "movement": persona["movement"],
            "voice_delivery": persona["voice"],
        },
        # A full planned arc, as generate_video_strategy now emits: the hook
        # plus seven continuations, the last landing the CTA. An earlier version
        # of this fixture planned only one continuation, which is exactly the
        # shape that made repeat extensions replay the same beat.
        "segments": [
            {"index": 0, "role": "hook", "seconds": 4, "goal": persona["promise"],
             "script": hook_line, "action": persona["action"]},
        ] + [
            {
                "index": i,
                "role": "cta" if i == 7 else "continuation",
                "seconds": 6,
                "goal": f"beat {i}: {persona['payoff'] if i == 1 else f'continue the story, step {i}'}",
                "script": persona["payoff"] if i == 1 else f"Beat {i}: {feature}, continued.",
                "action": persona["payoff_action"] if i == 1 else f"action for beat {i}",
            }
            for i in range(1, 8)
        ],
        "continuity_contract": {
            # Scene and delivery only. The contract used to list the presenter's
            # face, hair and wardrobe, which the strategy generator invents
            # because it never sees the photograph — so the contract was a third
            # channel carrying the same fabrication as the character block and
            # the prose fields.
            "established": [
                scene["environment"], scene["lighting"], scene["props"],
                persona["action"],
            ],
            "must_not_change": [
                scene["background"], scene["framing"],
            ],
            "do_not_repeat": [hook_line, persona["concept"]],
        },
    })
    _run(api._execute(
        "UPDATE studio_projects SET strategy = ?, strategy_version = 1, status = 'draft'"
        " WHERE id = ?",
        (json.dumps(strategy), project_id)))
    return strategy


NURSE_PERSONA = {
    # A role, not a face. The presenter is copied from the founder's photograph,
    # so a strategy describes who the video is FOR and never what the person
    # looks like. The appearance fields below are kept deliberately: they are
    # passed into the `character` block, which normalization now discards, and
    # the hook test asserts none of them reach the prompt.
    "who": "a hospital nurse working rotating shifts",
    "face": "round face, dark brows, tired eyes",
    "hair": "shoulder-length dark hair in a low bun",
    "wardrobe": "teal scrubs, silver badge, small hoop earrings",
    "age": "late 20s",
    "expression": "a tired half-smile that breaks into a real grin",
    "styling": "no glasses, no visible tattoos",
    "emotion": "relief at the end of a long shift",
    "concept": "open on the exhausted laugh of someone who just realised they already logged the shift",
    "promise": "show how the last twenty seconds of a shift get done",
    "action": "holds up a phone to camera, already logging",
    "outcome": "leaving the hospital on time",
    "diff": "no timesheet gymnastics between patients",
    "movement": "one-handed, small gestures, phone stays in frame",
    "voice": "low, quick, tired but warm",
    "payoff": "One tap and it is logged. That is the whole shift done.",
    "payoff_action": "taps the phone once, then pockets it",
}

BUDGET_PERSONA = {
    "who": "a freelancer tracking their own spending",
    "face": "narrow face, thin-rimmed glasses, unshaven",
    "hair": "messy dark curls pushed back with a band",
    "wardrobe": "faded grey hoodie, gold chain, one AirPod in the left ear",
    "age": "early 30s",
    "expression": "a flat, deadpan stare that breaks into a real laugh",
    "styling": "thin-rimmed glasses, no makeup",
    "emotion": "the specific relief of a number finally making sense",
    "concept": "open on deadpan-to-camera on the cost of three forgotten subscriptions",
    "promise": "show the money that quietly left the account",
    "action": "counts off on fingers, then turns the phone to show a number",
    "outcome": "knowing what is safe to spend before payday",
    "diff": "it finds the subscriptions you forgot you had",
    "movement": "seated, animated hands, phone rests on the bed",
    "voice": "dry, wry, conspiratorial",
    "payoff": "I cancelled three of them on Sunday. That is the whole video.",
    "payoff_action": "swipes the phone, then puts it face-down and laughs",
}

NURSE_SCENE = {
    "camera": "eye-level, phone held at arm's length",
    "framing": "medium close-up, head and shoulders",
    "lighting": "flat overhead corridor fluorescents, cool",
    "environment": "a hospital staff corridor outside a break room",
    "background": "grey vinyl floor, beige wall, a fire door",
    "setting": "late shift, 11pm",
    "style": "authentic handheld UGC",
    "position": "centred, phone at chest height",
    "props": "a phone only, no coffee cup",
    # Describes the room, not what the person is wearing. The palette used to
    # name the scrubs, which put the invented wardrobe back into the prompt
    # through a scene field.
    "palette": "cool greys, beige, fluorescent white",
}

BUDGET_SCENE = {
    "camera": "static, laptop-height, slightly below eye level",
    "framing": "medium shot, waist up, seated",
    "lighting": "warm single bedside lamp from frame left",
    "environment": "a small rented bedroom, evening",
    "background": "unmade single bed, a poster, a stack of unopened post",
    "setting": "Sunday evening, payday week",
    "style": "talking-head confession, natural",
    "position": "seated cross-legged, phone resting on the bed beside them",
    "props": "a phone and a mug of cold tea",
    "palette": "warm amber against grey",
}


# ---------------------------------------------------------------------------
# 1. The hooks are strategically different for two different apps
# ---------------------------------------------------------------------------
class TestAppSpecificity:
    def _hook_prompt(self, api, monkeypatch, spec, persona, scene, problem, feature, cta, hook_line):
        from models import GenerateHookRequest
        project, _profile, _template = _make_project(api, spec)
        _store_strategy(api, project["id"], hook_line, persona, scene,
                        problem=problem, feature=feature, cta=cta)
        calls = _mock_submit(api, monkeypatch)
        _run(api.generate_project_hook(
            project_id=project["id"], payload=GenerateHookRequest(), user_id=ANON))
        assert calls, "the hook generation never reached the provider"
        return calls[0]["prompt"]

    def test_two_apps_produce_strategically_different_hooks(self, api, monkeypatch):
        """
        The core product claim: the hook is built FOR the app.

        A generic talking-head template with the app name swapped in would
        share almost all of its prompt. These two must not.
        """
        nurse = self._hook_prompt(
            api, monkeypatch, NURSE_APP, NURSE_PERSONA, NURSE_SCENE,
            problem="Shift paperwork eats the end of a long shift",
            feature="One-tap shift logging", cta="Try it free",
            hook_line="I clocked out at 11:40. Every single night. Fixed it in one tap.")
        budget = self._hook_prompt(
            api, monkeypatch, BUDGET_APP, BUDGET_PERSONA, BUDGET_SCENE,
            problem="Money disappears before payday with nothing to show for it",
            feature="Automatic envelope splits", cta="Check what it finds",
            hook_line="Three subscriptions had been eating my account since March.")

        # The app's own problem, feature and CTA reach the hook prompt.
        assert "Shift paperwork eats the end of a long shift" in nurse
        assert "One-tap shift logging" in nurse
        assert "Try it free" in nurse
        assert "Shift paperwork" not in budget

        assert "Money disappears before payday" in budget
        assert "Automatic envelope splits" in budget
        assert "Check what it finds" in budget
        assert "One-tap shift logging" not in budget

        # Different scene, different visual strategy. The persona's appearance
        # used to be the differentiator here, via the invented wardrobe — that
        # is no longer sent, so app-specificity is carried by the scene and the
        # message, which is where it belongs. The message assertions above
        # already prove the two apps are not interchangeable.
        assert "hospital staff corridor" in nurse
        assert "hospital staff corridor" not in budget
        assert "bedside lamp" in budget and "bedside lamp" not in nurse

        # And they share only the boilerplate contract, not the content.
        nurse_lines = {line.strip() for line in nurse.splitlines() if line.strip()}
        budget_lines = {line.strip() for line in budget.splitlines() if line.strip()}
        overlap = nurse_lines & budget_lines
        shared_fraction = len(overlap) / max(len(nurse_lines), len(budget_lines))
        assert shared_fraction < 0.6, (
            f"hooks share {shared_fraction:.0%} of their lines — that reads as one "
            f"template with the app name swapped in, not an app-specific hook. "
            f"Shared: {sorted(overlap)[:6]}"
        )

    def test_hook_prompt_locks_the_scene_but_never_the_appearance(self, api, monkeypatch):
        """
        The hook must establish the scene and the delivery, but the on-camera
        person is copied from the founder's photograph.

        The appearance attributes used to be asserted as PRESENT. They were a
        model's guess at a face, hair, age and wardrobe written from the app
        profile -- the strategy call never sees the photograph -- and they were
        sent to the video model under a heading telling it both were locked.
        The provider was handed a real face and an invented one and told to
        honour both, which is how a founder's own face came back as somebody
        else's. The test asserted the opposite of what its own comment claimed,
        which is why it survived.
        """
        prompt = self._hook_prompt(
            api, monkeypatch, NURSE_APP, NURSE_PERSONA, NURSE_SCENE,
            problem="Shift paperwork eats the end of a long shift",
            feature="One-tap shift logging", cta="Try it free",
            hook_line="I clocked out at 11:40. Every single night.")

        # Scene and delivery are plan-level and conflict with nothing.
        for attribute in (
            "eye-level, phone held",        # camera angle
            "medium close-up",              # framing
            "corridor fluorescents",        # lighting
            "hospital staff corridor",      # environment / setting
            "grey vinyl floor",             # background
            "authentic handheld UGC",       # visual style
            "phone at chest height",        # character positioning
            "a phone only",                 # props
            "holds up a phone to camera",   # movement / action
            "low, quick, tired but warm",   # voice delivery
        ):
            assert attribute in prompt, f"hook prompt is missing: {attribute}"

        # The invented appearance is not, under any wording.
        for invented in (
            "late-20s night-shift nurse",   # appearance
            "round face, dark brows",       # facial features
            "low bun",                      # hairstyle
            "teal scrubs",                  # wardrobe
            "tired half-smile",             # facial expression
        ):
            assert invented not in prompt, (
                f"hook prompt invents the person's appearance: {invented}"
            )

        # And the photograph is named as the only authority on who they are.
        assert "The person on camera is the person in the attached character reference" in prompt
        assert "The image is the only authority on who they are" in prompt


# ---------------------------------------------------------------------------
# 2. The uploaded influencer is the same person across hook and extensions
# ---------------------------------------------------------------------------
class TestIdentityContinuity:
    def _chain(self, api, monkeypatch, model="seedance-2.5", with_bridge_frame=True):
        """Generate a hook, approve it, extend it. Returns every submit call."""
        from models import ApproveSegmentRequest, GenerateHookRequest, StudioGenerationRequest
        project, _profile, _template = _make_project(api, NURSE_APP)
        _store_strategy(api, project["id"],
                        "I clocked out at 11:40. Every single night.",
                        NURSE_PERSONA, NURSE_SCENE,
                        problem="Shift paperwork eats the end of a long shift",
                        feature="One-tap shift logging", cta="Try it free")

        calls = _mock_submit(api, monkeypatch)
        hook = _run(api.generate_project_hook(
            project_id=project["id"],
            payload=GenerateHookRequest(model=model), user_id=ANON))
        # A completed hook with a durable copy: poll normally downloads the
        # clip and records its URL, and the extension needs both to build the
        # strongest possible continuity request.
        _run(api._execute(
            "UPDATE generations SET status = 'completed', video_url = ? WHERE id = ?",
            ("https://provider.test/hook.mp4", hook["id"])))
        api.pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        (api.pipeline.VIDEOS_DIR / f"{hook['id']}.mp4").write_bytes(_TINY_PNG)

        if with_bridge_frame:
            # Stand in for the extracted final frame of the approved hook.
            bridge = Path(tempfile.mkdtemp(prefix="tiktok-bridge-")) / "bridge.png"
            bridge.write_bytes(_TINY_PNG)
            api.pipeline.extract_last_frame = _async_return(bridge)
        else:
            api.pipeline.extract_last_frame = _async_return(None)

        _run(api.approve_generation(hook["id"], ApproveSegmentRequest(), ANON))
        extension = _run(api.extend_generation(
            hook["id"], StudioGenerationRequest(duration_seconds=6), ANON))
        return project, hook, extension, calls

    def test_character_reference_rides_along_on_the_hook(self, api, monkeypatch):
        _project, _hook, _ext, calls = self._chain(api, monkeypatch)
        refs = calls[0].get("input_references") or []
        assert len(refs) == 1
        assert refs[0]["type"] == "image_url"
        assert refs[0]["image_url"]["url"].startswith("data:image/png;base64,")

    def test_extension_keeps_the_character_reference_and_adds_the_continuity_frame(
        self, api, monkeypatch
    ):
        """
        On a provider that can combine them, the extension carries the previous
        clip's final frame AND the founder's face.
        """
        _project, _hook, _ext, calls = self._chain(api, monkeypatch)
        assert calls[0].get("continuity_frame_path") is None, "the hook has nothing to continue from"
        assert calls[1].get("continuity_frame_path") is not None
        refs = calls[1].get("input_references") or []
        # The previous clip (for motion) plus the founder's face.
        assert any(r.get("type") == "video_url" for r in refs)
        assert any(
            r.get("type") == "image_url"
            and r["image_url"]["url"].startswith("data:image/png;base64,")
            for r in refs
        )

    def test_retired_attachment_is_refused_at_strategy_time(
        self, api, monkeypatch
    ):
        """
        The hard-error choice applies at every pipeline stage, strategy
        included: a project still holding a screenshot cannot even be
        planned until it is detached. No model call happens — the refusal
        precedes it, so no AI mock is needed.
        """
        from models import GenerateStrategyRequest
        project, _profile, _template = _make_project(api, NURSE_APP)
        _run(api._execute(
            "UPDATE studio_projects SET assets = ? WHERE id = ?",
            (json.dumps([{
                "asset_id": "old-shot", "kind": "screenshot",
                "label": "Old screenshot", "file_path": "gone.png",
            }]), project["id"])))
        with pytest.raises(HTTPException) as err:
            _run(api.generate_project_strategy(
                project_id=project["id"], payload=GenerateStrategyRequest(), user_id=ANON))
        assert err.value.status_code == 409
        assert "face-only" in str(err.value.detail)

    def test_missing_character_reference_is_refused_not_silently_anonymous(
        self, api, monkeypatch
    ):
        """
        A project without an uploaded face must not silently produce an
        anonymous influencer. Every template puts a person on camera, so the
        hook refuses loudly before the provider is called.
        """
        from models import GenerateHookRequest
        project, _profile, _template = _make_project(api, NURSE_APP, with_character=False)
        _store_strategy(api, project["id"], "I clocked out at 11:40.",
                        NURSE_PERSONA, NURSE_SCENE,
                        problem="Shift paperwork", feature="One-tap shift logging",
                        cta="Try it free")
        calls = _mock_submit(api, monkeypatch)
        with pytest.raises(HTTPException) as err:
            _run(api.generate_project_hook(
                project_id=project["id"], payload=GenerateHookRequest(), user_id=ANON))
        assert err.value.status_code == 409
        assert "character reference" in str(err.value.detail)
        assert not calls, "the provider was called despite the refusal"


# ---------------------------------------------------------------------------
# 3. Extensions preserve the scene and continue the same app message
# ---------------------------------------------------------------------------
class TestExtensionPreservesTheVideo:
    def test_extension_reproduces_environment_and_background(self, api, monkeypatch):
        """
        The scene and the delivery are restated as a lock, because a video
        model has no memory of the previous segment.

        Wardrobe, hair and identity used to be asserted here too. They came from
        the fabricated `character` block and are now supplied by the photograph
        and by the previous clip, both of which ride along in the same request
        as real visual inputs — so restating them as text was not continuity,
        it was a second, invented source of truth.
        """
        _project, _hook, _ext, calls = TestIdentityContinuity()._chain(api, monkeypatch)
        prompt = calls[1]["prompt"]
        for locked in (
            "a hospital staff corridor outside a break room",   # environment
            "grey vinyl floor, beige wall, a fire door",        # background
            "flat overhead corridor fluorescents, cool",        # lighting
            "medium close-up, head and shoulders",              # framing
            "a phone only, no coffee cup",                      # props
        ):
            assert locked in prompt, f"extension dropped the locked detail: {locked}"

        # Stated as a lock, not a suggestion.
        assert "THE SCENE AND THE DELIVERY ARE LOCKED" in prompt
        assert "not suggestions" in prompt

        # ...and the invented appearance is not restated as one.
        for invented in (
            "teal scrubs, silver badge, small hoop earrings",   # wardrobe
            "low bun",                                          # hairstyle
            "late-20s night-shift nurse in teal scrubs",        # appearance
        ):
            assert invented not in prompt, f"extension invented an appearance: {invented}"

        # The real continuity inputs are carried in the request, not described.
        refs = calls[1].get("input_references") or []
        assert any(r.get("type") == "video_url" for r in refs), "the previous clip carries the look"
        assert any(r.get("type") == "image_url" for r in refs), "the photograph carries the face"

    def test_extension_continues_the_app_specific_message(self, api, monkeypatch):
        _project, _hook, _ext, calls = TestIdentityContinuity()._chain(api, monkeypatch)
        prompt = calls[1]["prompt"]
        assert "Shift paperwork eats the end of a long shift" in prompt
        assert "One-tap shift logging" in prompt
        assert "Try it free" in prompt
        assert "One tap and it is logged" in prompt
        assert "THIS APP-SPECIFIC STRATEGY" in prompt

    def test_extension_does_not_restart_the_video(self, api, monkeypatch):
        """It must know what came before, and must not replay it."""
        _project, _hook, _ext, calls = TestIdentityContinuity()._chain(api, monkeypatch)
        prompt = calls[1]["prompt"]
        assert "CONTINUITY — what came before" in prompt
        assert "opening segment already established" in prompt
        assert "Do NOT repeat" in prompt
        assert "Do not re-introduce the app" in prompt
        assert "do not restart the opening framing" in prompt
        # The hook line is listed as already-delivered, not as the opening line.
        hook_line = "I clocked out at 11:40. Every single night."
        assert f"already seen or heard it: {hook_line}" in prompt

    def test_three_extensions_chain_in_order(self, api, monkeypatch):
        """Repeat extension keeps advancing the chain rather than forking it."""
        from models import ApproveSegmentRequest, GenerateHookRequest, StudioGenerationRequest
        project, _profile, _template = _make_project(api, NURSE_APP)
        _store_strategy(api, project["id"], "I clocked out at 11:40.",
                        NURSE_PERSONA, NURSE_SCENE,
                        problem="Shift paperwork", feature="One-tap shift logging",
                        cta="Try it free")
        _mock_submit(api, monkeypatch)
        hook = _run(api.generate_project_hook(
            project_id=project["id"], payload=GenerateHookRequest(), user_id=ANON))
        bridge = Path(tempfile.mkdtemp(prefix="tiktok-bridge-")) / "bridge.png"
        bridge.write_bytes(_TINY_PNG)
        api.pipeline.extract_last_frame = _async_return(bridge)
        api.pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

        parent = hook
        indices = []
        for _ in range(3):
            _run(api._execute(
                "UPDATE generations SET status = 'completed', video_url = ? WHERE id = ?",
                ("https://provider.test/seg.mp4", parent["id"])))
            (api.pipeline.VIDEOS_DIR / f"{parent['id']}.mp4").write_bytes(_TINY_PNG)
            _run(api.approve_generation(parent["id"], ApproveSegmentRequest(), ANON))
            parent = _run(api.extend_generation(
                parent["id"], StudioGenerationRequest(duration_seconds=6), ANON))
            indices.append(parent["segment_index"])
        assert indices == [1, 2, 3]


# ---------------------------------------------------------------------------
# 4. Unsupported continuity is reported, never silently accepted
# ---------------------------------------------------------------------------
class TestContinuityIsHonest:
    def test_seedance_reports_frame_exact_plus_refs(self, api, monkeypatch):
        _project, _hook, ext, _calls = TestIdentityContinuity()._chain(
            api, monkeypatch, model="seedance-2.5")
        assert ext["continuity"]["guarantee"] == "frame_exact_plus_refs"
        assert ext["continuity"]["use_frame"] is True
        assert ext["continuity"]["attached"] == ["frame", "clip", "identity"]
        assert ext["continuity"]["degraded"] == []

    def test_minimax_reports_it_cannot_pin_the_seam_frame(self, api, monkeypatch):
        """
        H3 reports no last-frame support and cannot combine a first frame with
        references. So it gets the previous clip as its single anchor, and both
        the frame and the identity reference are recorded as lost.
        """
        _project, _hook, ext, calls = TestIdentityContinuity()._chain(
            api, monkeypatch, model="minimax-h3")
        continuity = ext["continuity"]
        assert continuity["guarantee"] == "text_only"
        assert continuity["use_frame"] is False
        assert continuity["attached"] == ["clip"]
        dropped = {d["anchor"] for d in continuity["degraded"]}
        assert dropped == {"frame", "identity"}
        reasons = {d["anchor"]: d["reason"] for d in continuity["degraded"]}
        assert "no last-frame/first-frame continuation support" in reasons["frame"]
        assert all(reasons.values())
        # The face really was withheld, not merely reported as withheld.
        refs = calls[1].get("input_references") or []
        assert all(r.get("type") == "video_url" for r in refs)
        assert calls[1].get("continuity_frame_path") is None
        # And the prompt must not pretend a frame was supplied.
        assert "you have NOT been given the previous clip" in calls[1]["prompt"]
        assert "EXACT final frame" not in calls[1]["prompt"]

    def test_degraded_prompt_tells_the_model_to_take_the_written_lock_literally(
        self, api, monkeypatch
    ):
        _project, _hook, _ext, calls = TestIdentityContinuity()._chain(
            api, monkeypatch, model="minimax-h3")
        assert "could not receive every continuity reference" in calls[1]["prompt"]

    def test_no_bridge_frame_downgrades_to_text_only_and_says_so(self, api, monkeypatch):
        """
        If the previous clip's final frame cannot be extracted, the founder is
        told continuity is text-only. This is the difference between an honest
        warning and a silently different character.
        """
        _project, _hook, ext, calls = TestIdentityContinuity()._chain(
            api, monkeypatch, with_bridge_frame=False)
        continuity = ext["continuity"]
        assert continuity["guarantee"] == "text_only"
        assert continuity["use_frame"] is False
        assert continuity["attached"] == ["identity"]
        assert any("final frame could not be extracted" in d["reason"]
                   for d in continuity["degraded"])
        # The prompt must not claim the model can see the previous clip.
        assert "you have NOT been given the previous clip" in calls[1]["prompt"]
        assert "EXACT final frame" not in calls[1]["prompt"]
        # ...and the face is still anchored where possible.
        assert calls[1].get("input_references")

    def test_the_hook_is_never_told_its_character_reference_failed_to_arrive(
        self, api, monkeypatch
    ):
        """
        The hook has no previous clip, so it has no seam to miss. Its identity
        reference IS attached — and `degraded` is copied straight into the
        prompt — so listing the reference as dropped told the model the
        founder's face had not arrived, in the very request carrying it. That is
        a self-inflicted likeness loss on the one segment the founder judges.
        """
        _project, hook, _ext, calls = TestIdentityContinuity()._chain(api, monkeypatch)
        continuity = hook["continuity"]
        assert continuity["guarantee"] == "single_segment"
        assert continuity["attached"] == ["identity"]
        assert continuity["degraded"] == []
        # Nothing was lost, so the prompt must not claim anything was.
        assert "final frame could not be extracted" not in calls[0]["prompt"]
        assert "could not receive every continuity reference" not in calls[0]["prompt"]
        # And the face really is in the request, so the record above is true.
        assert any(r.get("type") == "image_url" for r in calls[0].get("input_references") or [])

    def test_continuity_record_is_readable_from_the_api(self, api, monkeypatch):
        _project, hook, ext, _calls = TestIdentityContinuity()._chain(api, monkeypatch)
        report = _run(api.get_generation_continuity(ext["id"], ANON))
        assert report["segment_index"] == 1
        assert report["guarantee"] == "frame_exact_plus_refs"
        assert report["attached"] == ["frame", "clip", "identity"]
        assert report["notes"]

    def test_video_editor_cannot_continue_a_chain(self, api, monkeypatch):
        """
        Aleph edits a clip; it cannot generate the next segment. That is a hard
        refusal with a stated reason, not a degraded attempt.
        """
        import video_providers

        os.environ["VIDEO_MODEL_ALLOWLIST"] = "seedance-2.5,aleph-2"
        try:
            plan = video_providers.continuity_plan(
                "aleph-2",
                has_bridge_frame=True,
                has_parent_clip_url=True,
                has_character_reference=True,
            )
        finally:
            os.environ.pop("VIDEO_MODEL_ALLOWLIST", None)
        assert plan["guarantee"] == "unsupported"
        assert plan["attached"] == []
        assert len(plan["degraded"]) == 3
        assert all("cannot generate" in d["reason"] for d in plan["degraded"])

    def test_an_editor_request_falls_back_to_a_generator_at_hook_time(self, api, monkeypatch):
        from models import ApproveSegmentRequest, GenerateHookRequest
        os.environ["VIDEO_MODEL_ALLOWLIST"] = "seedance-2.5,aleph-2"
        try:
            project, _profile, _template = _make_project(api, NURSE_APP)
            _store_strategy(api, project["id"], "I clocked out at 11:40.",
                            NURSE_PERSONA, NURSE_SCENE,
                            problem="Shift paperwork", feature="One-tap shift logging",
                            cta="Try it free")
            _mock_submit(api, monkeypatch)
            hook = _run(api.generate_project_hook(
                project_id=project["id"],
                payload=GenerateHookRequest(model="aleph-2"),
                user_id=ANON))
            assert hook["model"] == "seedance-2.5"
            assert "edits an existing clip" in hook["provider_reason"]
        finally:
            os.environ.pop("VIDEO_MODEL_ALLOWLIST", None)

    def test_generate_video_reports_what_it_actually_attached(self, api, monkeypatch):
        """The provider layer must not claim a frame it never sent."""
        import ai_service

        sent = {}

        class _Response:
            status_code = 200

            def json(self):
                return {"id": "job-1", "status": "queued"}

        class _Client:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, headers=None, json=None):
                sent["payload"] = json
                return _Response()

        monkeypatch.setattr(ai_service.httpx, "AsyncClient", _Client)
        monkeypatch.setattr(ai_service, "OPENROUTER_API_KEY", "test")
        frame = Path(tempfile.mkdtemp(prefix="tiktok-frame-")) / "f.png"
        frame.write_bytes(_TINY_PNG)

        result = _run(ai_service.generate_video(
            prompt="continue", duration=5, model="seedance-2.5",
            continuity_frame_path=frame,
            input_references=[{"type": "image_url",
                               "image_url": {"url": "data:image/png;base64,AAAA"}}],
        ))
        assert result["continuity"]["has_continuity_frame"] is True
        assert result["continuity"]["has_frame_images"] is True
        assert result["continuity"]["dropped_anchors"] == []
        # The frame really is in the request, as a first_frame.
        frames = sent["payload"]["frame_images"]
        assert len(frames) == 1 and frames[0]["frame_type"] == "first_frame"
        # ...and the reference was NOT dropped, because this provider can combine.
        assert sent["payload"]["input_references"]


def _async_return(value):
    async def _inner(*_args, **_kwargs):
        return value
    return _inner


# ---------------------------------------------------------------------------
# 5. Gates: the workflow cannot skip strategy, approval, or claim safety
# ---------------------------------------------------------------------------
class TestWorkflowGates:
    def test_hook_requires_a_strategy(self, api, monkeypatch):
        from models import GenerateHookRequest
        project, _p, _t = _make_project(api, NURSE_APP)
        _mock_submit(api, monkeypatch)
        with pytest.raises(HTTPException) as err:
            _run(api.generate_project_hook(
                project_id=project["id"], payload=GenerateHookRequest(), user_id=ANON))
        assert err.value.status_code == 400
        assert "strategy" in str(err.value.detail).lower()

    def test_strategy_requires_an_approved_app_profile(self, api, monkeypatch):
        """
        A profile that stops being approved must stop driving video work.
        (Project creation already refuses an unapproved profile, so the profile
        is approved first and then revoked.)
        """
        from models import (
            ApproveAppProfileRequest, BrandProfileCreateRequest,
            CreateStudioProjectRequest, GenerateStrategyRequest,
        )
        profile = _run(api.create_brand(
            payload=BrandProfileCreateRequest(brand_name="Revoked"), user_id=ANON))
        _run(api.approve_app_profile(
            profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
        template = _run(api.list_templates(user_id=ANON))["templates"][0]
        project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"], template_id=template["id"]), user_id=ANON))
        _run(api._execute(
            "UPDATE brand_profiles SET status = 'draft' WHERE id = ?", (profile["id"],)))
        with pytest.raises(HTTPException) as err:
            _run(api.generate_project_strategy(
                project_id=project["id"], payload=GenerateStrategyRequest(), user_id=ANON))
        assert err.value.status_code == 409
        assert "approve" in str(err.value.detail).lower()

    def test_a_banned_claim_in_the_strategy_blocks_the_hook(self, api, monkeypatch):
        """
        The strategy is where the spoken words live, so it goes through the same
        claim check as the script. A banned claim must not reach a paid render.
        """
        from models import GenerateHookRequest
        project, _p, _t = _make_project(api, NURSE_APP)
        _store_strategy(api, project["id"], "This app cures burnout overnight.",
                        NURSE_PERSONA, NURSE_SCENE,
                        problem="Shift paperwork", feature="One-tap shift logging",
                        cta="Try it free")
        _mock_submit(api, monkeypatch)
        with pytest.raises(HTTPException) as err:
            _run(api.generate_project_hook(
                project_id=project["id"], payload=GenerateHookRequest(), user_id=ANON))
        assert err.value.status_code == 409
        assert "cures burnout" in str(err.value.detail)

    def test_approval_requires_a_completed_generation(self, api, monkeypatch):
        from models import ApproveSegmentRequest, GenerateHookRequest
        project, _p, _t = _make_project(api, NURSE_APP)
        _store_strategy(api, project["id"], "I clocked out at 11:40.",
                        NURSE_PERSONA, NURSE_SCENE,
                        problem="Shift paperwork", feature="One-tap shift logging",
                        cta="Try it free")
        _mock_submit(api, monkeypatch)
        hook = _run(api.generate_project_hook(
            project_id=project["id"], payload=GenerateHookRequest(), user_id=ANON))
        with pytest.raises(HTTPException) as err:
            _run(api.approve_generation(hook["id"], ApproveSegmentRequest(), ANON))
        assert err.value.status_code == 409

    def test_editing_the_strategy_bumps_its_version(self, api):
        from models import UpdateStudioProjectRequest
        project, _p, _t = _make_project(api, NURSE_APP)
        _store_strategy(api, project["id"], "Original hook line.",
                        NURSE_PERSONA, NURSE_SCENE,
                        problem="Shift paperwork", feature="One-tap shift logging",
                        cta="Try it free")
        before = _run(api.get_studio_project(project["id"], ANON))
        updated = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(strategy={"hook_line": "Edited hook line."}),
            user_id=ANON))
        assert before["strategy_version"] == 1
        assert updated["strategy_version"] == 2
        assert updated["strategy"]["hook_line"] == "Edited hook line."
        # The rest of the strategy survives a partial edit.
        assert updated["strategy"]["primary_feature"] == "One-tap shift logging"


# ---------------------------------------------------------------------------
# 6. The assembled deliverable
# ---------------------------------------------------------------------------
class TestChainAssembly:
    def test_assemble_reports_skipped_segments_rather_than_dropping_them(self, api, monkeypatch):
        from models import ApproveSegmentRequest, GenerateHookRequest, StudioGenerationRequest
        from models import AssembleChainRequest
        project, _p, _t = _make_project(api, NURSE_APP)
        _store_strategy(api, project["id"], "I clocked out at 11:40.",
                        NURSE_PERSONA, NURSE_SCENE,
                        problem="Shift paperwork", feature="One-tap shift logging",
                        cta="Try it free")
        _mock_submit(api, monkeypatch)
        hook = _run(api.generate_project_hook(
            project_id=project["id"], payload=GenerateHookRequest(), user_id=ANON))
        _run(api._execute(
            "UPDATE generations SET status = 'completed', video_url = ? WHERE id = ?",
            ("https://provider.test/hook.mp4", hook["id"])))
        api.pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        (api.pipeline.VIDEOS_DIR / f"{hook['id']}.mp4").write_bytes(_TINY_PNG)
        bridge = Path(tempfile.mkdtemp(prefix="tiktok-bridge-")) / "bridge.png"
        bridge.write_bytes(_TINY_PNG)
        api.pipeline.extract_last_frame = _async_return(bridge)
        _run(api.approve_generation(hook["id"], ApproveSegmentRequest(), ANON))
        ext = _run(api.extend_generation(
            hook["id"], StudioGenerationRequest(duration_seconds=6), ANON))
        # The extension is still generating, so it must be reported as skipped
        # rather than quietly dropped from the assembled video. The approved,
        # completed hook is still usable.
        result = _run(api.assemble_generation_chain(
            ext["id"], AssembleChainRequest(), ANON))
        assert [s["reason"] for s in result["skipped"]] == ["status is 'generating'"]
        assert result["segment_count"] == 1
        assert result["segments"][0]["id"] == hook["id"]
        assert result["segments"][0]["segment_index"] == 0

    def test_assemble_refuses_when_nothing_is_usable(self, api, monkeypatch):
        from models import GenerateHookRequest, AssembleChainRequest
        project, _p, _t = _make_project(api, NURSE_APP)
        _store_strategy(api, project["id"], "I clocked out at 11:40.",
                        NURSE_PERSONA, NURSE_SCENE,
                        problem="Shift paperwork", feature="One-tap shift logging",
                        cta="Try it free")
        _mock_submit(api, monkeypatch)
        hook = _run(api.generate_project_hook(
            project_id=project["id"], payload=GenerateHookRequest(), user_id=ANON))
        _run(api._execute("UPDATE generations SET status = 'completed' WHERE id = ?", (hook["id"],)))
        with pytest.raises(HTTPException) as err:
            _run(api.assemble_generation_chain(hook["id"], AssembleChainRequest(), ANON))
        assert err.value.status_code == 409


# ---------------------------------------------------------------------------
# 7. Strategy normalization, unit level
# ---------------------------------------------------------------------------
class TestStrategyNormalization:
    def test_missing_keys_become_empty_not_absent(self):
        from ai_service import normalize_strategy
        strategy = normalize_strategy({"hook_line": "Hi"})
        for field in ("camera_angle", "framing", "lighting", "environment", "background"):
            assert field in strategy["scene"]
        for field in ("movement", "voice_delivery"):
            assert field in strategy["performance"]
        for field in ("established", "must_not_change", "do_not_repeat"):
            assert field in strategy["continuity_contract"]

    def test_a_character_section_cannot_be_stored(self):
        """
        Even if the model returns one — an older prompt, a cached completion, a
        hand-edited payload — it must not survive normalization. A stored
        character block is a fabricated description of a face, and
        character_scene_lock() would otherwise restate it as a locked value
        beside the founder's actual photograph.
        """
        from ai_service import normalize_strategy
        strategy = normalize_strategy({
            "hook_line": "Hi",
            "character": {
                "appearance": "a late-20s night-shift nurse in teal scrubs",
                "facial_features": "round face, dark brows",
                "hairstyle": "shoulder-length dark hair in a low bun",
                "wardrobe": "teal scrubs, silver badge",
                "age_range": "late 20s",
            },
        })
        assert "character" not in strategy

    def test_a_huge_payload_is_truncated_not_stored_whole(self):
        from ai_service import normalize_strategy
        strategy = normalize_strategy({"hook_line": "x" * 5000})
        assert len(strategy["hook_line"]) <= 200

    def test_segments_default_to_a_single_hook(self):
        from ai_service import normalize_strategy
        strategy = normalize_strategy({"segments": []})
        assert len(strategy["segments"]) == 1
        assert strategy["segments"][0]["role"] == "hook"

    def test_wrong_types_are_coerced_not_crashed_on(self):
        from ai_service import normalize_strategy
        strategy = normalize_strategy({
            "scene": None, "segments": "nope",
            "emotional_triggers": "a single trigger",
            "continuity_contract": ["not", "a", "dict"],
        })
        assert strategy["scene"]["framing"] == ""
        assert strategy["emotional_triggers"] == ["a single trigger"]
        assert strategy["continuity_contract"]["established"] == []
        assert len(strategy["segments"]) == 1


# ---------------------------------------------------------------------------
# 7. Strategy prompt directives: the creative plan replaces uploaded assets
# ---------------------------------------------------------------------------
class TestStrategyPromptDirectives:
    """
    The creative plan is what generates environment and on-screen context
    from App Profile facts instead of compositing uploads. These pin the
    directives that make it do that, capturing the prompt by stubbing
    _chat_json — no network, no model.
    """

    def _capture_prompt(self, monkeypatch):
        import ai_service
        captured = {}

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            captured["system"] = system_message
            captured["prompt"] = prompt
            return {
                "strategy_summary": "s", "audience_problem": "p",
                "emotional_triggers": ["t"], "hook_concept": "c",
                "hook_line": "h", "hook_promise": "p", "hook_action": "a",
                "hook_dialogue": "d", "messaging_pillars": ["m"],
                "primary_feature": "f", "desired_outcome": "o",
                "differentiation_beat": "b", "cta_strategy": "c",
                "character": {"__note": "omit"},
                "scene": {"environment": "kitchen"},
                "performance": {"movement": "still"},
                "segments": [{
                    "index": 0, "role": "hook", "seconds": 3,
                    "goal": "g", "script": "s", "action": "a",
                }],
                "continuity_contract": {
                    "established": [], "must_not_change": [], "do_not_repeat": [],
                },
            }

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        return captured

    def _run_strategy(self, monkeypatch):
        import ai_service
        captured = self._capture_prompt(monkeypatch)
        result = asyncio.run(ai_service.generate_video_strategy(
            profile={"brand_name": "Taskly", "core_features": ["timer"]},
            template={
                "name": "Stop Doing This",
                "content_slots": {"mistake": "the behaviour to stop"},
                "required_assets": ["character_reference"],
            },
            angle=None,
            objective="address_user_problem",
            hook_seconds=2,
            total_duration=15,
            tone="",
            brand_voice="",
            profile_feedback={},
        ))
        assert result["template_name"] == "Stop Doing This"
        return captured

    def test_content_slots_must_be_filled_from_facts(self, monkeypatch):
        captured = self._run_strategy(monkeypatch)
        assert "Fill every content_slot" in captured["prompt"]

    def test_environment_is_invented_from_facts_not_composited(self, monkeypatch):
        captured = self._run_strategy(monkeypatch)
        assert "Invent the environment" in captured["prompt"]
        assert "composited afterwards" not in captured["prompt"]

    def test_generated_scene_is_framed_as_illustrative(self, monkeypatch):
        captured = self._run_strategy(monkeypatch)
        assert "illustrative" in captured["prompt"]
        assert "screen recording" in captured["prompt"]

    def test_appearance_is_never_described(self, monkeypatch):
        captured = self._run_strategy(monkeypatch)
        assert "appearance is never" in captured["system"]
        assert "must_not_change must cover the background" in captured["prompt"]
