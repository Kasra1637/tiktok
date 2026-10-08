"""
Tests for the app-specific AI influencer workflow.

The claim under test is specific and falsifiable: a video generated for one app
must be strategically different from one generated for another app, the uploaded
person must be carried into the render, both of the two generated sections must
be present and distinct, and any rule the App Profile records as absolute must
reach the prompt that could break it.

A video is now ONE render with exactly TWO sections — a hook and a middle that
develops it and ends at the moment the presenter reaches for their phone. There
is no per-segment approval gate and no chain, so what used to be "the hook" and
"every extension" is one prompt for the whole piece.

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
    "outcome_statements": [{
        "outcome": "Leaving work on time",
        "who_feels_it": "hospital nurses working rotating shifts",
        "from_feature": "One-tap shift logging",
        "how_it_helps": "One tap logs the whole shift so handover writes itself",
    }],
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
    "outcome_statements": [{
        "outcome": "Knowing exactly what is safe to spend this week",
        "who_feels_it": "first-time budgeters with irregular income",
        "from_feature": "Subscription cancellation radar",
        "how_it_helps": "It hunts forgotten subscriptions so the leftover figure is real",
    }],
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


def _approved_project(api, script="", hook_line="", version=1):
    """A project the studio accepts, with a saved plan of the given shape."""
    project, _profile, _template = _make_project(api, NURSE_APP)
    _run(api._execute(
        "UPDATE studio_projects SET script = ?, hook_line = ?, script_version = ?,"
        " beat_timeline = ?, safety_report = ? WHERE id = ?",
        (script, hook_line, version, "[]", json.dumps(_CLEAN_REPORT), project["id"]),
    ))
    return project["id"]


# What a passing claim-safety report looks like on the row. generate_plan writes
# the real one; tests that only need to get past the gate write this.
_CLEAN_REPORT = {"passed": True, "blocking": [], "claims_used": [],
                 "risk_warnings": [], "sources_used": []}


def _mark_ready(api, project_id, script="A plain line about the shift, no promises."):
    """
    Put a project in the state the single generation endpoint requires.

    The hook used to be its own endpoint and its own, cheaper gate — a project
    could reach a render of the opening without a script at all. There is
    one render now, so the piece goes through the same ready gate as any
    generation: a script on the project, and a claim report that passes.

    A clean report is written only when there is none. A project whose strategy
    was stored with a banned claim already has a FAILING report, and replacing
    it with a clean one would quietly disarm the gate this fixture exists to
    exercise.
    """
    _run(api._execute(
        "UPDATE studio_projects SET script = ?, status = 'ready_for_generation',"
        " safety_report = COALESCE(NULLIF(safety_report, ''), ?) WHERE id = ?",
        (script, json.dumps(_CLEAN_REPORT), project_id),
    ))
    return project_id


def _store_strategy(api, project_id, hook_line, persona, scene, *, problem, feature, cta):
    """Write a strategy shaped like a real one from two different apps.

    `cta` is still accepted and ignored: it was a required strategy key when this
    fixture was written, and callers pass it. A generated video has no call to
    action now, so `normalize_strategy` drops the field.

    The claim-safety report is written in the same statement, which is what
    generate_project_strategy does — the strategy carries the words that will
    actually be spoken, so a banned claim in it has to be stored as failing or
    the generation gate would never see it.
    """
    import claim_safety
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
        # Exactly two sections, as generate_video_strategy now emits: the hook,
        # then the middle that develops it and ends at the reach. The middle's
        # action deliberately stops at picking the phone up, because filming the
        # app working is the founder's own recording, not ours.
        "segments": [
            {"index": 0, "role": "hook", "seconds": 4, "goal": persona["promise"],
             "script": hook_line, "action": persona["action"]},
            {"index": 1, "role": "middle", "seconds": 6, "goal": persona["payoff"],
             "script": persona["payoff"], "action": persona["payoff_action"]},
        ],
    })
    report = claim_safety.build_safety_report(
        {"strategy": strategy},
        _run(api._fetch_one(
            "SELECT * FROM brand_profiles WHERE id = ("
            "  SELECT brand_profile_id FROM studio_projects WHERE id = ?)",
            (project_id,))),
    )
    _run(api._execute(
        "UPDATE studio_projects SET strategy = ?, strategy_version = 1,"
        " strategy_script_version = script_version, safety_report = ?,"
        " safety_summary = ?, status = 'draft' WHERE id = ?",
        (json.dumps(strategy), json.dumps(report), claim_safety.summarize(report),
         project_id)))
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
    def _render_prompt(self, api, monkeypatch, spec, persona, scene,
                       problem, feature, cta, hook_line):
        """
        The prompt the video model is actually given, captured off a real
        submit. There is no separate hook endpoint any more: the piece is one
        render, so this goes through the same gate as any generation.
        """
        from models import StudioGenerationRequest
        project, _profile, _template = _make_project(api, spec)
        _store_strategy(api, project["id"], hook_line, persona, scene,
                        problem=problem, feature=feature, cta=cta)
        _mark_ready(api, project["id"])
        calls = _mock_submit(api, monkeypatch)
        _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert calls, "the generation never reached the provider"
        return calls[0]["prompt"]

    def test_two_apps_produce_strategically_different_videos(self, api, monkeypatch):
        """
        The core product claim: the video is built FOR the app.

        A generic talking-head template with the app name swapped in would
        share almost all of its prompt. These two must not.
        """
        nurse = self._render_prompt(
            api, monkeypatch, NURSE_APP, NURSE_PERSONA, NURSE_SCENE,
            problem="Shift paperwork eats the end of a long shift",
            feature="One-tap shift logging", cta="Try it free",
            hook_line="I clocked out at 11:40. Every single night. Fixed it in one tap.")
        budget = self._render_prompt(
            api, monkeypatch, BUDGET_APP, BUDGET_PERSONA, BUDGET_SCENE,
            problem="Money disappears before payday with nothing to show for it",
            feature="Automatic envelope splits", cta="Check what it finds",
            hook_line="Three subscriptions had been eating my account since March.")

        # The app's own problem and feature reach the render prompt.
        assert "Shift paperwork eats the end of a long shift" in nurse
        assert "One-tap shift logging" in nurse
        assert "Shift paperwork" not in budget

        assert "Money disappears before payday" in budget
        assert "Automatic envelope splits" in budget
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
            f"prompts share {shared_fraction:.0%} of their lines — that reads as one "
            f"template with the app name swapped in, not an app-specific video. "
            f"Shared: {sorted(overlap)[:6]}"
        )

    def test_the_render_tells_the_model_not_to_show_the_app_working(self, api, monkeypatch):
        """
        The one directive the whole two-section architecture exists to enforce:
        the generated footage stops at the reach, because the product demo and
        the call to action are the founder's own.

        Stated up front rather than left to the beat list, since a video model has
        a strong prior towards resolving a promo on camera.
        """
        prompt = self._render_prompt(
            api, monkeypatch, NURSE_APP, NURSE_PERSONA, NURSE_SCENE,
            problem="Shift paperwork eats the end of a long shift",
            feature="One-tap shift logging", cta="Try it free",
            hook_line="I clocked out at 11:40. Every single night.")
        lowered = prompt.lower()
        assert "do not film the app being used" in lowered
        assert "do not show a screen or interface" in lowered
        assert "do not ask the viewer to download" in lowered
        assert "reaches for their phone" in lowered

    def test_the_two_sections_are_present_and_distinct(self, api, monkeypatch):
        """
        Both, in order, and doing different work. The middle is not the hook
        restated with more words — a strategy whose middle could be cut without
        losing the hook has not written a middle.
        """
        prompt = self._render_prompt(
            api, monkeypatch, NURSE_APP, NURSE_PERSONA, NURSE_SCENE,
            problem="Shift paperwork eats the end of a long shift",
            feature="One-tap shift logging", cta="Try it free",
            hook_line="I clocked out at 11:40. Every single night.")
        assert "exactly TWO sections" in prompt
        # Each heading states its own job as a full clause. The phrasing is
        # asserted because these are instructions, not labels: a malformed one
        # ("its job is to stops the scroll") is read as a broken instruction
        # rather than a short one.
        assert "HOOK — 3s, and its job is to stop the scroll" in prompt
        assert "MIDDLE — 12s, and its job is to develop the hook and end at the reach" in prompt
        # The hook's own words and the middle's own words are both present, and
        # they are not the same line.
        assert "I clocked out at 11:40. Every single night." in prompt
        assert NURSE_PERSONA["payoff"] in prompt
        assert NURSE_PERSONA["payoff"] not in NURSE_PERSONA["action"]

    def test_render_prompt_locks_the_scene_but_never_the_appearance(self, api, monkeypatch):
        """
        The video must establish the scene and the delivery, but the on-camera
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
        prompt = self._render_prompt(
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
            assert attribute in prompt, f"render prompt is missing: {attribute}"

        # The invented appearance is not, under any wording.
        for invented in (
            "late-20s night-shift nurse",   # appearance
            "round face, dark brows",       # facial features
            "low bun",                      # hairstyle
            "teal scrubs",                  # wardrobe
            "tired half-smile",             # facial expression
        ):
            assert invented not in prompt, (
                f"render prompt invents the person's appearance: {invented}"
            )

        # And the photograph is named as the only authority on who they are.
        assert "The person on camera is the person in the attached character reference" in prompt
        assert "The image is the only authority on who they are" in prompt

    def test_a_project_with_no_strategy_is_refused(self, api, monkeypatch):
        """
        A render without an app-specific strategy is refused.

        This was once `test_hook_requires_a_strategy`, which asserted the same
        thing, then was inverted to assert the opposite -- that the endpoint
        logs "less specific to this app" and renders from the plan alone. That
        inversion is what let a direct API caller, a stale client bundle, and
        the retry path each buy a generic take with the app's name in it, and it
        contradicted build_single_pass_prompt's own description of the fallback.

        Refusing costs nothing real: the studio builds the strategy for the
        founder one click earlier in the same flow, so the reachable case is only
        a caller that skipped it.
        """
        from models import StudioGenerationRequest
        project, _profile, _template = _make_project(api, NURSE_APP)
        _mark_ready(api, project["id"],
                    script="I clocked out at 11:40. Every single night.")
        calls = _mock_submit(api, monkeypatch)
        with pytest.raises(HTTPException) as err:
            _run(api.submit_project_generation(
                project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert err.value.status_code == 409
        # Nothing reached the provider, so nothing was spent.
        assert calls == []


class TestMustNotShowIsEnforced:
    """
    The App Profile's must_not_show list, attached to the render that could
    violate it.

    It used to be known_limitations, a single advisory text field whose UI label
    promised "Must never be contradicted by promos" while nothing checked it:
    it reached the plan and strategy prompts as loose context and never reached
    a video prompt at all. A founder who wrote "never show a hospital corridor"
    had no way of knowing whether the model honoured it.
    """

    FORBIDDEN = [
        "a hospital corridor",
        "a competitor's app icon",
    ]

    def _profile(self):
        return {"brand_name": "ShiftLog", "must_not_show": list(self.FORBIDDEN)}

    def test_the_single_pass_prompt_carries_it(self):
        import generation_planning
        prompt = generation_planning.build_single_pass_prompt(
            plan={"hook_line": "h", "script": "s", "cta": "c"},
            profile=self._profile(),
        )
        assert "MUST NOT APPEAR" in prompt
        for item in self.FORBIDDEN:
            assert item in prompt

    def test_every_segment_carries_it(self):
        """
        On the whole piece, not just the opening.

        Was a loop over segment_index, because a separately rendered extension
        re-imagines the scene from the strategy brief and a forbidden detail can
        reappear at the seam even when the opening honoured it. There is no seam
        now — there is one render — so the property is that the rule is in the
        single prompt that films both sections, and appears once rather than
        being restated per segment.
        """
        import generation_planning
        from ai_service import normalize_strategy
        strategy = normalize_strategy({
            "strategy_summary": "s", "audience_problem": "p",
            "emotional_triggers": ["t"], "hook_concept": "c",
            "hook_line": "h", "hook_promise": "p", "hook_action": "a",
            "messaging_pillars": ["m"], "primary_feature": "f",
            "desired_outcome": "o", "differentiation_beat": "b",
            "scene": {"environment": "kitchen"},
            "performance": {"movement": "still"},
            "segments": [
                {"index": 0, "role": "hook", "seconds": 3, "goal": "g",
                 "script": "s", "action": "a"},
                {"index": 1, "role": "middle", "seconds": 9, "goal": "g2",
                 "script": "s2", "action": "a2"},
            ],
        })
        prompt = generation_planning.build_segment_prompt(
            strategy=strategy, profile=self._profile(),
            duration=12, plan={"hook_seconds": 3},
        )
        assert prompt.count("MUST NOT APPEAR") == 1
        for item in self.FORBIDDEN:
            assert item in prompt, f"the rule lost {item}"
        # And it is stated as an instruction, not as context.
        assert "Do not depict any of them" in prompt

    def test_a_profile_with_none_records_no_rule(self):
        """
        No empty rule in the prompt for the majority of profiles. An instruction
        with nothing after it trains the model to skim instruction blocks.
        """
        import generation_planning
        for profile in (
            {"brand_name": "ShiftLog"},
            {"brand_name": "ShiftLog", "must_not_show": []},
            {"brand_name": "ShiftLog", "must_not_show": ""},
            {"brand_name": "ShiftLog", "must_not_show": None},
            {"brand_name": "ShiftLog", "must_not_show": ["  ", ""]},
        ):
            prompt = generation_planning.build_single_pass_prompt(
                plan={"hook_line": "h", "script": "s"}, profile=profile,
            )
            assert "MUST NOT APPEAR" not in prompt, f"empty rule emitted for {profile}"

    def test_a_newline_separated_string_is_accepted(self):
        """
        A founder typing free text into a textarea produces a string, not a
        list. Both shapes must reach the prompt, or the field silently stops
        working for exactly the people who wrote it by hand.
        """
        import generation_planning
        prompt = generation_planning.build_single_pass_prompt(
            plan={"hook_line": "h", "script": "s"},
            profile={
                "brand_name": "ShiftLog",
                "must_not_show": "a hospital corridor\na competitor's app icon",
            },
        )
        assert "a hospital corridor" in prompt
        assert "a competitor's app icon" in prompt

    def test_the_endpoint_sends_the_profile_it_stored(self, api, monkeypatch):
        """The wiring: a saved must_not_show must reach a real submit call."""
        from models import StudioGenerationRequest
        import server
        project, _profile, _template = _make_project(api, NURSE_APP)
        _store_strategy(
            api, project["id"], "I clocked out at 11:40.",
            NURSE_PERSONA, NURSE_SCENE,
            problem="Shift paperwork", feature="One-tap shift logging",
            cta="Try it free",
        )
        # The list lives on the App Profile, not the project: the prompt builder
        # reads it from `profile`, which _submit_generation resolves from
        # brand_profile_id.
        _run(api._execute(
            "UPDATE brand_profiles SET must_not_show = ? WHERE id = ?",
            (json.dumps(["a hospital corridor"]), project["brand_profile_id"]),
        ))
        _mark_ready(api, project["id"])
        calls = _mock_submit(api, monkeypatch)
        _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert "a hospital corridor" in calls[0]["prompt"]
        assert calls[0]["prompt"].count("MUST NOT APPEAR") == 1


def _async_return(value):
    async def _inner(*_args, **_kwargs):
        return value
    return _inner


# ---------------------------------------------------------------------------
# 5. Gates: the workflow cannot skip strategy, approval, or claim safety
# ---------------------------------------------------------------------------
class TestWorkflowGates:
    def test_generation_requires_a_ready_project(self, api, monkeypatch):
        """
        The gate that replaced the hook endpoint's own. A project still in draft
        has not been reviewed, so nothing is submitted and nothing is spent.
        """
        from models import StudioGenerationRequest
        project, _p, _t = _make_project(api, NURSE_APP)
        _store_strategy(api, project["id"], "I clocked out at 11:40.",
                        NURSE_PERSONA, NURSE_SCENE,
                        problem="Shift paperwork", feature="One-tap shift logging",
                        cta="Try it free")
        _mock_submit(api, monkeypatch)
        with pytest.raises(HTTPException) as err:
            _run(api.submit_project_generation(
                project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert err.value.status_code == 409
        assert "ready" in str(err.value.detail).lower()

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
            payload=BrandProfileCreateRequest(
                brand_name="Revoked",
                brand_description="Shift logging for healthcare workers.",
                core_features=["One-tap shift logging"],
                usage_moments=["Clocking on and off between shifts"],
                outcome_statements=[{
                    "outcome": "Leaving work on time",
                    "who_feels_it": "hospital nurses working rotating shifts",
                    "from_feature": "One-tap shift logging",
                    "how_it_helps": "One tap logs the whole shift so handover writes itself",
                }],
            ),
            user_id=ANON))
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

    def test_a_banned_claim_in_the_strategy_blocks_the_render(self, api, monkeypatch):
        """
        The strategy is where the spoken words live, so it goes through the same
        claim check as the script. A banned claim must not reach a render.

        Asserted at the only paid endpoint there is now: one render, gated on the
        stored report, which generate_project_strategy recomputed when it wrote
        the strategy.
        """
        from models import StudioGenerationRequest
        project, _p, _t = _make_project(api, NURSE_APP)
        _store_strategy(api, project["id"], "This app cures burnout overnight.",
                        NURSE_PERSONA, NURSE_SCENE,
                        problem="Shift paperwork", feature="One-tap shift logging",
                        cta="Try it free")
        _mark_ready(api, project["id"], script="Nothing here is a promise.")
        calls = _mock_submit(api, monkeypatch)
        with pytest.raises(HTTPException) as err:
            _run(api.submit_project_generation(
                project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert err.value.status_code == 409
        assert "cures burnout" in str(err.value.detail)
        assert calls == [], "a banned claim must not reach the provider"

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
# 7. Strategy normalization, unit level
# ---------------------------------------------------------------------------
class TestStrategyNormalization:
    def test_missing_keys_become_empty_not_absent(self):
        """
        The scene and performance blocks are re-asserted by name in the prompt,
        so a missing key has to read as empty rather than vanish — that is what
        lets the founder see exactly which attributes were pinned and which were
        left open.

        `continuity_contract` used to be the third block asserted here. There is
        no such block: a continuity contract governed the seam between two
        separately rendered clips, and there is no seam. The two sections
        themselves are what replace it, so they are asserted instead.
        """
        from ai_service import normalize_strategy
        strategy = normalize_strategy({"hook_line": "Hi"})
        for field in ("camera_angle", "framing", "lighting", "environment", "background"):
            assert field in strategy["scene"]
        for field in ("movement", "voice_delivery"):
            assert field in strategy["performance"]
        assert [s["role"] for s in strategy["segments"]] == ["hook", "middle"]
        assert "continuity_contract" not in strategy

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

    def test_segments_always_become_a_hook_and_a_middle(self):
        """
        Was `test_segments_default_to_a_single_hook`, which asserted one section
        when the model returned none.

        A video is now ONE render with exactly two sections, so the count is
        structural rather than a default: a hook and a middle, always, with the
        roles assigned by position rather than trusted. A model returning the old
        eight-beat shape has beats 2-8 dropped and beat 8's "cta" role replaced,
        which is what stops a call to action being inherited by the middle.
        """
        from ai_service import SECTION_ROLES, normalize_strategy
        assert SECTION_ROLES == ("hook", "middle")
        strategy = normalize_strategy({"segments": []})
        assert len(strategy["segments"]) == 2
        assert [s["role"] for s in strategy["segments"]] == ["hook", "middle"]
        assert [s["index"] for s in strategy["segments"]] == [0, 1]

        eight = normalize_strategy({"segments": [
            {"index": i, "role": "cta" if i == 7 else "continuation",
             "seconds": 5, "goal": f"g{i}", "script": f"s{i}", "action": f"a{i}"}
            for i in range(8)
        ]})
        assert len(eight["segments"]) == 2
        assert [s["role"] for s in eight["segments"]] == ["hook", "middle"]
        assert eight["segments"][0]["script"] == "s0"
        # Beat 8's CTA is not inherited by the middle.
        assert eight["segments"][1]["script"] == "s1"

    def test_the_retired_fields_are_dropped_not_stored_whole(self):
        """
        A strategy saved before this change still carries `cta_strategy` and a
        `continuity_contract`, and a model reading a cached older prompt still
        emits them. Both govern something that no longer exists — a closing ask
        and a seam — so neither may survive normalization into a new prompt.
        """
        from ai_service import normalize_strategy
        strategy = normalize_strategy({
            "hook_line": "Hi",
            "cta_strategy": "Ask them to install it",
            "continuity_contract": {
                "established": ["teal scrubs"],
                "must_not_change": ["the face"],
                "do_not_repeat": ["the hook line"],
            },
        })
        assert "cta_strategy" not in strategy
        assert "continuity_contract" not in strategy
        assert "Ask them to install it" not in str(strategy)

    def test_wrong_types_are_coerced_not_crashed_on(self):
        from ai_service import normalize_strategy
        strategy = normalize_strategy({
            "scene": None, "segments": "nope",
            "emotional_triggers": "a single trigger",
            "continuity_contract": ["not", "a", "dict"],
        })
        assert strategy["scene"]["framing"] == ""
        assert strategy["emotional_triggers"] == ["a single trigger"]
        assert "continuity_contract" not in strategy
        assert len(strategy["segments"]) == 2


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
            # No "character" key: the schema does not ask for one and the
            # rules forbid describing the presenter, so a compliant reply
            # omits it. This is the exact shape that used to fail validation
            # with "missing required fields: {'character'}" — the prompt told
            # the model to omit the key while validation demanded it.
            # No "hook_dialogue" either: it is enrichment the model may drop,
            # and every consumer tolerates its absence.
            # Nor "cta_strategy" or "continuity_contract": neither is in the
            # schema any more, so a compliant reply cannot contain them.
            return {
                "strategy_summary": "s", "audience_problem": "p",
                "emotional_triggers": ["t"], "hook_concept": "c",
                "hook_line": "h", "hook_promise": "p", "hook_action": "a",
                "messaging_pillars": ["m"],
                "primary_feature": "f", "desired_outcome": "o",
                "mechanism_beat": "mb", "payoff_beat": "pb",
                "differentiation_beat": "b",
                "scene": {"environment": "kitchen"},
                "performance": {"movement": "still"},
                "segments": [
                    {"index": 0, "role": "hook", "seconds": 2,
                     "goal": "g", "script": "s", "action": "a"},
                    {"index": 1, "role": "middle", "seconds": 13,
                     "goal": "g2", "script": "s2", "action": "a2"},
                ],
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

    def test_the_selected_template_middle_reaches_the_prompt(self, monkeypatch):
        """
        The hook mechanism is handed to the strategy as fixed material, so its
        middle structure has to actually arrive. It did not: the prompt read a
        retired `continuation_structure` key, which no template has carried since
        a video became one render, so EVERY strategy was told
        "continuation_structure: (unstated)" and "cta_pattern: (unstated)" while
        the curated middle — the thing that tells the model what the middle is
        for — was silently dropped.

        The cta_pattern half is the worse of the two: it asked for a closing beat
        in the same prompt that forbids a call to action three rules later.
        """
        import ai_service
        captured = self._capture_prompt(monkeypatch)
        asyncio.run(ai_service.generate_video_strategy(
            profile={"brand_name": "Taskly", "core_features": ["timer"]},
            template={
                "name": "Stop Doing This",
                "content_slots": {"mistake": "the behaviour to stop"},
                "required_assets": ["character_reference"],
                "middle_structure": "Name what the habit costs, then stop at the reach.",
            },
            angle=None, objective="address_user_problem",
            hook_seconds=2, total_duration=15, tone="", brand_voice="",
            profile_feedback={},
        ))
        prompt = captured["prompt"]
        assert "Name what the habit costs, then stop at the reach." in prompt
        assert '"middle_structure"' in prompt
        assert '"continuation_structure"' not in prompt
        assert "cta_pattern" not in prompt

    def test_a_retired_structure_field_still_migrates_into_the_mechanism(self, monkeypatch):
        """
        A template row written before the rename carries only
        `continuation_structure`. It must not read as an unstated mechanism: the
        row has something to say, and dropping it would leave a curated template
        with no middle at all.
        """
        import ai_service
        captured = self._capture_prompt(monkeypatch)
        asyncio.run(ai_service.generate_video_strategy(
            profile={"brand_name": "Taskly", "core_features": ["timer"]},
            template={"name": "Old Row", "content_slots": {},
                      "continuation_structure": "Name the cost, then stop at the reach."},
            angle=None, objective="address_user_problem",
            hook_seconds=2, total_duration=15, tone="", brand_voice="",
            profile_feedback={},
        ))
        assert "Name the cost, then stop at the reach." in captured["prompt"]
        assert '"middle_structure"' in captured["prompt"]

    def test_environment_is_invented_from_facts_not_composited(self, monkeypatch):
        captured = self._run_strategy(monkeypatch)
        assert "Invent the environment" in captured["prompt"]
        assert "composited afterwards" not in captured["prompt"]

    def test_generated_scene_is_framed_as_illustrative(self, monkeypatch):
        captured = self._run_strategy(monkeypatch)
        assert "illustrative" in captured["prompt"]
        assert "screen recording" in captured["prompt"]

    def test_appearance_is_never_described(self, monkeypatch):
        """
        Two halves, both load-bearing. The system message forbids describing the
        presenter at all; the prompt rules forbid it again per field, AND say the
        scene lock must cover the whole piece while explicitly excluding the
        appearance — because that exclusion is the fix for a founder's own face
        coming back as somebody else's.

        The continuity-contract half of the old assertion is gone: there is no
        contract. What holds the two sections together is the scene lock, and it
        has to be stated as applying to both of them.

        Clothing is the one thing the exclusion does NOT cover. It is chosen by
        the strategy to suit the setting, so it has to appear in the very same
        "holds for both sections" list — otherwise the rule that keeps the scene
        consistent would silently exclude the wardrobe from consistency too.
        """
        captured = self._run_strategy(monkeypatch)
        assert "appearance is never" in captured["system"]
        assert "do not describe the presenter's face" in captured["prompt"]
        assert "The scene must hold for BOTH sections" in captured["prompt"]
        assert "Never the face, hair, skin, age, build or facial hair" in captured["prompt"]
        assert "framing, wardrobe, props and delivery it locks" in captured["prompt"]

    def test_no_section_beyond_the_two_is_requested(self, monkeypatch):
        """
        The schema is the whole budget. A third section would be the product
        demo, which is the founder's own recording, and the prompt has to say so
        in the same breath as forbidding a demonstration inside the two.
        """
        captured = self._run_strategy(monkeypatch)
        assert "There are exactly TWO sections and they are the whole video" in captured["prompt"]
        assert "Never return a third section" in captured["prompt"]
        assert "NEVER put a product demonstration in either section" in captured["prompt"]
        assert "NEVER write a call to action" in captured["prompt"]

    def test_the_middle_ends_at_the_usage_moment_not_the_demo(self, monkeypatch):
        """
        The two-section shape only works if the middle knows where to stop.

        usage_moments is the specific moment this app is reached for, and it is
        the seam the founder's own demo continues from. So the middle develops
        towards that moment and ends on the reach — and the prompt has to say so,
        or the middle spends its whole budget resolving a problem the demo is
        supposed to resolve.
        """
        captured = self._run_strategy(monkeypatch)
        assert "The middle must end AT the usage moment" in captured["prompt"]
        assert "reaching for the app, not using it" in captured["prompt"]
        # And the schema says the same thing about the middle's action, so it
        # holds even if the prose rule is skimmed.
        assert "ending on the reach for the phone" in captured["prompt"]

    def test_hook_seconds_is_clamped_where_the_strategy_is_built(self, api, monkeypatch):
        """
        A hook boundary outside 2-4s is refused at the project endpoints, and
        the strategy endpoint has to hold the same line.

        It seeds the strategy's own segment budget, so an unclamped value would
        let the hook the founder reviews disagree with the boundary the render
        uses. And a hook_seconds at or beyond the piece's length collapses the
        middle to a single second. The default matters too: it used to fall
        back to the provider floor of 5s, a leftover from when the hook was a
        separately-rendered sub-floor clip, and one second past the maximum.
        """
        from models import GenerateStrategyRequest, UpdateStudioProjectRequest

        async def fake_strategy(**kwargs):
            # Everything under test happens before the model is called, so this
            # never runs against a network. It returns a minimal valid strategy
            # purely so the endpoint has something to normalise.
            from ai_service import normalize_strategy
            return normalize_strategy({
                "strategy_summary": "s", "audience_problem": "p",
                "hook_concept": "c", "hook_line": "You do not have a focus problem.",
                "hook_promise": "p", "hook_action": "a", "messaging_pillars": ["m"],
                "primary_feature": "f", "desired_outcome": "o",
                "differentiation_beat": "b",
                "scene": {}, "performance": {},
                "segments": [
                    {"index": 0, "role": "hook", "seconds": 3, "goal": "g",
                     "script": "line", "action": "a"},
                    {"index": 1, "role": "middle", "seconds": 6, "goal": "g",
                     "script": "more", "action": "a"},
                ],
            })
        monkeypatch.setattr(api, "generate_video_strategy", fake_strategy)

        project_id = _approved_project(api, script="The line.", version=1)
        # A value past the ceiling is brought to it rather than refused, so a
        # hand-typed 9s leaves a boundary a hook can actually land in.
        _run(api.update_studio_project(
            project_id=project_id,
            payload=UpdateStudioProjectRequest(hook_seconds=30),
            user_id=ANON))
        assert _run(api.get_studio_project(project_id, ANON))["hook_seconds"] == 4

        for asked, expected in ((99, 4), (1, 2), (3, 3)):
            _run(api.update_studio_project(
                project_id=project_id,
                payload=UpdateStudioProjectRequest(hook_seconds=expected),
                user_id=ANON))
            strategy = _run(api.generate_project_strategy(
                project_id=project_id,
                payload=GenerateStrategyRequest(hook_seconds=asked),
                user_id=ANON))
            assert strategy["hook_seconds"] == expected, f"asked for {asked}s"

    def test_values_forbid_double_quotes(self, monkeypatch):
        """
        The likeliest systematic source of unparseable replies: hook lines
        phrased as questions and dialogue written with quotation marks, both
        of which break the JSON with unescaped quotes. The prompt says so
        explicitly, with the consequence attached.
        """
        captured = self._run_strategy(monkeypatch)
        assert "double-quote" in captured["prompt"]

    def test_a_reply_without_character_validates(self, monkeypatch):
        """
        Regression: the prompt forbids a "character" key, so a compliant
        reply omits it — and validation used to fail the whole strategy with
        "missing required fields: {'character'}", surfacing in the UI as "AI
        strategy generation failed. Please try again." No retry could ever
        fix it, because the model was doing what it was told.
        Same for "hook_dialogue": enrichment the model may drop, tolerated
        everywhere it is read — which the shared fake above proves by omitting
        both keys in every capture test.
        """
        import ai_service
        captured = self._capture_prompt(monkeypatch)
        result = asyncio.run(ai_service.generate_video_strategy(
            profile={"brand_name": "Taskly", "core_features": ["timer"]},
            template={"name": "Stop Doing This", "content_slots": {}},
            angle=None,
            objective="address_user_problem",
            hook_seconds=2,
            total_duration=15,
            tone="",
            brand_voice="",
            profile_feedback={},
        ))
        assert "character" not in result
        assert result["hook_dialogue"] == ""
        assert result["scene"]["environment"] == "kitchen"
        assert 'There is no "character" key in this schema' in captured["prompt"]


class TestStrategyFollowsTheApprovedPlan:
    """
    The founder reads and edits the script on the Review step, before any video
    is rendered. The strategy then has to produce THAT video.

    It did not. The plan and the strategy were two independent generations and
    neither read the other, so the founder approved a script and got a
    render of a different one: different hook line, different beats, and a CTA
    that never reached the video at all.
    """

    _PLAN = {
        "hook_line": "You do not have a focus problem.",
        "script": "You do not have a focus problem. You have too many lists.",
        # The founder's brief for the demo they record themselves. Deliberately
        # NOT passed on: handing it to the strategy would be the route by which a
        # feature instruction reached the render. Asserted absent below.
        "demo_brief": "Record yourself clearing one list by hand.",
        "visual_direction": "Close, 9:16, desk.",
        "voice_direction": "Calm.",
        "sound_direction": "Room tone.",
        # Two beats, as the plan schema now demands: the hook, then the middle.
        "beat_timeline": [
            {"start": 0, "end": 3, "label": "hook",
             "text": "You do not have a focus problem."},
            {"start": 3, "end": 12, "label": "middle",
             "text": "You have too many lists."},
        ],
    }

    def _capture(self, monkeypatch):
        import ai_service
        captured = {}

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            captured["prompt"] = prompt
            return {
                "strategy_summary": "s", "audience_problem": "p",
                "emotional_triggers": ["t"], "hook_concept": "c",
                "hook_line": "h", "hook_promise": "p", "hook_action": "a",
                "messaging_pillars": ["m"], "primary_feature": "f",
                "desired_outcome": "o", "mechanism_beat": "mb",
                "payoff_beat": "pb", "differentiation_beat": "b",
                "scene": {"environment": "kitchen"},
                "performance": {"movement": "still"},
                "segments": [
                    {"index": 0, "role": "hook", "seconds": 5,
                     "goal": "g", "script": "s", "action": "a"},
                    {"index": 1, "role": "middle", "seconds": 7,
                     "goal": "g2", "script": "s2", "action": "a2"},
                ],
            }

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        return captured

    def _run(self, monkeypatch, plan):
        import ai_service
        captured = self._capture(monkeypatch)
        result = asyncio.run(ai_service.generate_video_strategy(
            profile={"brand_name": "Taskly", "core_features": ["timer"]},
            template={"name": "Stop Doing This", "content_slots": {}},
            angle=None,
            objective="address_user_problem",
            hook_seconds=5,
            total_duration=20,
            tone="",
            brand_voice="",
            profile_feedback={},
            plan=plan,
        ))
        return captured, result

    def test_the_approved_words_reach_the_prompt(self, monkeypatch):
        captured, _ = self._run(monkeypatch, self._PLAN)
        prompt = captured["prompt"]
        assert "APPROVED CREATIVE PLAN" in prompt
        assert "You do not have a focus problem." in prompt
        # Both beats, in order — the plan is the video's spine.
        assert "You have too many lists." in prompt
        assert prompt.index("You do not have a focus problem.") < prompt.index(
            "You have too many lists."
        )

    def test_the_demo_brief_is_never_passed_on(self, monkeypatch):
        """
        The CTA and feature_emphasis assertions this replaces are gone for a
        reason, and this is the same rule stated against the field that replaced
        one of them.

        `demo_brief` exists so the founder knows what to record for their own
        demo. Passing it to the strategy would put "record yourself doing the
        thing" in front of a model that is told not to describe the app working,
        and the result would reach the render. So the plan section carries the
        founder's words and directions, and nothing that is an instruction about
        a demonstration.
        """
        captured, _ = self._run(monkeypatch, self._PLAN)
        prompt = captured["prompt"]
        assert "Record yourself clearing one list by hand." not in prompt
        # The directions that ARE the video's shape still travel.
        assert "Close, 9:16, desk." in prompt

    def test_the_plan_wins_over_the_models_own_hook(self, monkeypatch):
        """
        The directive matters as much as the data. Without it the model sees an
        approved hook line and its own instruction to write the strongest hook
        for this app, and will usually write its own.
        """
        captured, _ = self._run(monkeypatch, self._PLAN)
        assert "The founder wrote it and reviewed it" in captured["prompt"]
        assert "hook_line must be that hook line" in captured["prompt"]
        assert "do not replace its words" in captured["prompt"]

    def test_the_strategy_still_adds_what_a_plan_cannot_express(self, monkeypatch):
        """
        The approved words are fixed material, so what the strategy is FOR is
        everything a plan cannot state: what the person physically does, and the
        locked scene.

        "the continuity contract" is gone from that sentence along with the
        contract. There is no seam between two renders to keep consistent, so
        the scene is what holds the two sections together instead.
        """
        captured, _ = self._run(monkeypatch, self._PLAN)
        assert "the on-camera action for each section" in captured["prompt"]
        assert "the scene, and the performance" in captured["prompt"]
        assert "continuity contract" not in captured["prompt"]

    def test_no_plan_means_no_plan_section_and_no_directive(self, monkeypatch):
        """
        A project with no plan still has to produce a strategy, and must not be
        told to obey a plan that does not exist.
        """
        captured, result = self._run(monkeypatch, None)
        assert "APPROVED CREATIVE PLAN" not in captured["prompt"]
        assert "hook_line must be that hook line" not in captured["prompt"]
        assert result["template_name"] == "Stop Doing This"

    def test_an_empty_plan_is_treated_as_no_plan(self, monkeypatch):
        captured, _ = self._run(monkeypatch, {
            "script": "", "hook_line": "", "demo_brief": "", "beat_timeline": [],
        })
        assert "APPROVED CREATIVE PLAN" not in captured["prompt"]

    def test_the_endpoint_passes_the_approved_plan(self, api, monkeypatch):
        """
        The wiring, not just the prompt. A project with a saved script must hand
        that script to the strategy; the endpoint used to pass no plan at all.
        """
        import server

        seen = {}

        async def fake_strategy(**kwargs):
            seen.update(kwargs)
            return {
                "strategy_summary": "s", "audience_problem": "p",
                "emotional_triggers": ["t"], "hook_concept": "c",
                "hook_line": "h", "hook_promise": "p", "hook_action": "a",
                "messaging_pillars": ["m"], "primary_feature": "f",
                "desired_outcome": "o", "mechanism_beat": "mb",
                "payoff_beat": "pb", "differentiation_beat": "b",
                "scene": {"environment": "kitchen"},
                "performance": {"movement": "still"},
                "segments": [
                    {"index": 0, "role": "hook", "seconds": 5,
                     "goal": "g", "script": "s", "action": "a"},
                    {"index": 1, "role": "middle", "seconds": 7,
                     "goal": "g2", "script": "s2", "action": "a2"},
                ],
            }

        monkeypatch.setattr(server, "generate_video_strategy", fake_strategy)

        project_id = _approved_project(api, script="You do not have a focus problem.", hook_line="You do not have a focus problem.")
        _run(api.generate_project_strategy(
            project_id=project_id, payload=server.GenerateStrategyRequest(), user_id=ANON))

        plan = seen.get("plan")
        assert plan, "the endpoint built a strategy with no plan at all"
        assert plan["hook_line"] == "You do not have a focus problem."
        assert plan["script"] == "You do not have a focus problem."
        # The founder's demo brief is not part of what the strategy is told to
        # deliver. `cta` and `feature_emphasis` used to be, and both were the
        # route by which a closing beat and a product demo reached the render.
        assert "demo_brief" not in plan

    def test_an_unplanned_project_passes_no_plan(self, api, monkeypatch):
        import server

        seen = {}

        async def fake_strategy(**kwargs):
            seen.update(kwargs)
            return {
                "strategy_summary": "s", "audience_problem": "p",
                "emotional_triggers": ["t"], "hook_concept": "c",
                "hook_line": "h", "hook_promise": "p", "hook_action": "a",
                "messaging_pillars": ["m"], "primary_feature": "f",
                "desired_outcome": "o", "mechanism_beat": "mb",
                "payoff_beat": "pb", "differentiation_beat": "b",
                "scene": {"environment": "kitchen"},
                "performance": {"movement": "still"},
                "segments": [
                    {"index": 0, "role": "hook", "seconds": 5,
                     "goal": "g", "script": "s", "action": "a"},
                    {"index": 1, "role": "middle", "seconds": 7,
                     "goal": "g2", "script": "s2", "action": "a2"},
                ],
            }

        monkeypatch.setattr(server, "generate_video_strategy", fake_strategy)
        project_id = _approved_project(api, script="", version=0)
        _run(api.generate_project_strategy(
            project_id=project_id, payload=server.GenerateStrategyRequest(), user_id=ANON))
        assert seen.get("plan") is None


class TestStrategyGoesStaleWhenTheScriptIsEdited:
    """
    Chaining the plan into the strategy made the strategy only true of that
    plan's words — and a script edit left it describing a hook line the founder
    had already replaced, with nothing detecting it.

    The strategy is stamped with the script_version it was built from, and
    `strategy_is_current` on the project says whether it still is. The stamp is
    what makes the mismatch visible at all: the founder watches a video built
    from a script they deleted, and the result cannot explain the mismatch.

    What changed with the architecture: the two paid endpoints that used to
    REFUSE a mismatch are gone — there is one render now, and no hook-then-extend
    chain for a stale strategy to be quietly re-used by. Detection moved with
    them and is what the studio reads before spending. So the property pinned
    here is detection, and that a rebuild clears it.
    """

    async def _fake_strategy(self, **kwargs):
        """The strategy the endpoint will await, as a real coroutine."""
        return {
            "strategy_summary": "s", "audience_problem": "p",
            "emotional_triggers": ["t"], "hook_concept": "c",
            "hook_line": "You do not have a focus problem.",
            "hook_promise": "p", "hook_action": "a",
            "messaging_pillars": ["m"], "primary_feature": "f",
            "desired_outcome": "o", "differentiation_beat": "b",
            "scene": {"environment": "kitchen"},
            "performance": {"movement": "still"},
            "segments": [
                {"index": 0, "role": "hook", "seconds": 5,
                 "goal": "g", "script": "You do not have a focus problem.",
                 "action": "a"},
                {"index": 1, "role": "middle", "seconds": 7,
                 "goal": "g2", "script": "s2", "action": "a2"},
            ],
        }

    def test_the_strategy_stamps_the_script_version_it_built_from(self, api, monkeypatch):
        import server
        monkeypatch.setattr(server, "generate_video_strategy", self._fake_strategy)
        project_id = _approved_project(
            api, script="You do not have a focus problem.",
            hook_line="You do not have a focus problem.", version=3)
        result = _run(api.generate_project_strategy(
            project_id=project_id, payload=server.GenerateStrategyRequest(), user_id=ANON))
        assert result["strategy_script_version"] == 3
        assert result["strategy_is_current"] is True

    def test_editing_the_script_marks_the_strategy_stale(self, api, monkeypatch):
        import server
        from models import UpdateStudioProjectRequest
        monkeypatch.setattr(server, "generate_video_strategy", self._fake_strategy)
        project_id = _approved_project(api, script="The original hook line.", version=2)
        _run(api.generate_project_strategy(
            project_id=project_id, payload=server.GenerateStrategyRequest(), user_id=ANON))

        # A content edit bumps script_version, which is exactly the event the
        # stamp exists to catch.
        edited = _run(api.update_studio_project(
            project_id=project_id,
            payload=UpdateStudioProjectRequest(hook_line="A completely new hook line."),
            user_id=ANON))
        assert edited["script_version"] == 3
        assert edited["strategy_is_current"] is False

    def test_a_generation_refuses_a_stale_strategy(self, api, monkeypatch):
        """
        A plan edit invalidates the strategy, and the spend is refused until the
        founder rebuilds it.

        This was `test_a_generation_reads_the_stale_strategy_and_the_studio_is_
        told`, which asserted the render still went ahead on the strength of a
        warning the studio displayed. The reasoning was that a hard 409 "lived
        on the two endpoints that no longer exist" -- but the single-render
        generate endpoint is exactly where that protection belongs. Warning
        before spending still spends: the founder approved one hook line while
        the strategy carried another, so what rendered was not what they read.
        """
        from models import StudioGenerationRequest, UpdateStudioProjectRequest
        import server
        monkeypatch.setattr(server, "generate_video_strategy", self._fake_strategy)
        project_id = _approved_project(api, script="The original hook line.", version=2)
        _run(api.generate_project_strategy(
            project_id=project_id, payload=server.GenerateStrategyRequest(), user_id=ANON))
        _run(api.update_studio_project(
            project_id=project_id,
            payload=UpdateStudioProjectRequest(hook_line="A completely new hook line."),
            user_id=ANON))
        _mark_ready(api, project_id)
        calls = _mock_submit(api, monkeypatch)

        with pytest.raises(HTTPException) as err:
            _run(api.submit_project_generation(
                project_id=project_id, payload=StudioGenerationRequest(), user_id=ANON))
        assert err.value.status_code == 409
        assert "Rebuild it" in str(err.value.detail)
        # Nothing reached the provider, so nothing was spent.
        assert calls == []

        # The staleness is still visible on the project payload, so the studio can
        # explain the refusal rather than only surfacing a 409.
        stale = _run(api.get_studio_project(project_id, ANON))
        assert stale["strategy_is_current"] is False
        assert stale["strategy"]["hook_line"] == "You do not have a focus problem."
        assert stale["hook_line"] == "A completely new hook line."

    def test_rebuilding_the_strategy_clears_the_stale_flag(self, api, monkeypatch):
        """The route out has to actually work, or the warning is noise."""
        from models import StudioGenerationRequest, UpdateStudioProjectRequest
        import server
        monkeypatch.setattr(server, "generate_video_strategy", self._fake_strategy)
        project_id = _approved_project(api, script="The original hook line.", version=2)
        _run(api.generate_project_strategy(
            project_id=project_id, payload=server.GenerateStrategyRequest(), user_id=ANON))
        _run(api.update_studio_project(
            project_id=project_id,
            payload=UpdateStudioProjectRequest(hook_line="A completely new hook line."),
            user_id=ANON))
        assert _run(api.get_studio_project(
            project_id, ANON))["strategy_is_current"] is False
        calls = _mock_submit(api, monkeypatch)

        rebuilt = _run(api.generate_project_strategy(
            project_id=project_id, payload=server.GenerateStrategyRequest(), user_id=ANON))
        assert rebuilt["strategy_is_current"] is True
        _mark_ready(api, project_id)
        generation = _run(api.submit_project_generation(
            project_id=project_id, payload=StudioGenerationRequest(), user_id=ANON))
        assert generation["status"] in ("submitted", "generating")
        assert calls, "the generation did not reach the provider after a rebuild"

    def test_an_unstamped_strategy_is_not_treated_as_stale(self, api, monkeypatch):
        """
        strategy_script_version 0 means "built before this was recorded", not
        "stale". Existing drafts must keep generating rather than being warned
        about by a migration default.
        """
        from models import StudioGenerationRequest
        import server
        monkeypatch.setattr(server, "generate_video_strategy", self._fake_strategy)
        project_id = _approved_project(api, script="The original hook line.", version=2)
        _run(api.generate_project_strategy(
            project_id=project_id, payload=server.GenerateStrategyRequest(), user_id=ANON))
        # Simulate a row written before the column existed.
        _run(api._execute(
            "UPDATE studio_projects SET strategy_script_version = 0, script_version = 9 "
            "WHERE id = ?", (project_id,)))
        _mark_ready(api, project_id)
        _mock_submit(api, monkeypatch)
        generation = _run(api.submit_project_generation(
            project_id=project_id, payload=StudioGenerationRequest(), user_id=ANON))
        assert generation["status"] in ("submitted", "generating")
        assert _run(api.get_studio_project(
            project_id, ANON))["strategy_is_current"] is True

    def test_a_strategy_built_from_no_script_is_not_stale(self, api, monkeypatch):
        """
        script_version 0 on the strategy side means it was built with no plan to
        follow. Nothing to have gone stale.
        """
        import server
        monkeypatch.setattr(server, "generate_video_strategy", self._fake_strategy)
        project_id = _approved_project(api, script="", version=0)
        result = _run(api.generate_project_strategy(
            project_id=project_id, payload=server.GenerateStrategyRequest(), user_id=ANON))
        assert result["strategy_script_version"] == 0
        assert result["strategy_is_current"] is True


class TestUsageMomentsAndProofMoment:
    """
    The strategy schema asks for a scene and a hook action, and until these two
    fields existed no profile field supplied either.

    The model was inventing a setting -- a kitchen at 7am, for every app
    regardless of what the app was -- and being told to "show the feature in
    use" with nothing telling it what that looks like. Both are product facts
    the app's own copy usually states, which is why they are research-filled
    rather than founder-entered.

    usage_moments survives into the two-section architecture because the middle
    needs a setting AND needs an ending. proof_moment does not: filming it would
    be the product demo, which is the founder's own recording.
    """

    def _capture(self, monkeypatch, **overrides):
        import ai_service
        captured = {}

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            captured["prompt"] = prompt
            return {
                "strategy_summary": "s", "audience_problem": "p",
                "emotional_triggers": ["t"], "hook_concept": "c",
                "hook_line": "h", "hook_promise": "p", "hook_action": "a",
                "messaging_pillars": ["m"], "primary_feature": "f",
                "desired_outcome": "o", "mechanism_beat": "mb",
                "payoff_beat": "pb", "differentiation_beat": "b",
                "scene": {"environment": "kitchen"},
                "performance": {"movement": "still"},
                "segments": [
                    {"index": 0, "role": "hook", "seconds": 5,
                     "goal": "g", "script": "s", "action": "a"},
                    {"index": 1, "role": "middle", "seconds": 10,
                     "goal": "g2", "script": "s2", "action": "a2"},
                ],
            }

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        profile = {
            "brand_name": "ShiftLog",
            "core_features": ["One-tap shift logging"],
            "usage_moments": ["End of a night shift", "Handover at 7am"],
            "proof_moment": "One tap and the shift is on the log",
        }
        profile.update(overrides)
        asyncio.run(ai_service.generate_video_strategy(
            profile=profile,
            template={"name": "Stop Doing This", "content_slots": {}},
            angle=None, objective="address_user_problem",
            hook_seconds=5, total_duration=20, tone="", brand_voice="",
            profile_feedback={},
        ))
        return captured

    def test_usage_moments_reach_the_strategy_prompt(self, monkeypatch):
        """
        Was `test_both_reach_the_strategy_prompt`, which also asserted
        `proof_moment` did. It does not, and that is the point — see
        `test_proof_moment_is_not_a_generation_input`.

        usage_moments still grounds the scene, which is why it exists: without it
        the model invented a setting, a kitchen at 7am, for every app regardless
        of what the app was.
        """
        captured = self._capture(monkeypatch)
        assert "End of a night shift" in captured["prompt"]
        assert "Handover at 7am" in captured["prompt"]

    def test_proof_moment_is_not_a_generation_input(self, monkeypatch):
        """
        `proof_moment` is the one moment the camera must film to make the claim
        believable — which is the product demo, and the demo is recorded by the
        founder and attached after this footage ends.

        Supplying it here was the route by which "show this happening" reached a
        prompt that is not allowed to show the app happening. It stays on the App
        Profile as a brief for that recording, and it must not appear in a
        generation prompt under any circumstances.
        """
        captured = self._capture(monkeypatch)
        assert "One tap and the shift is on the log" not in captured["prompt"]
        assert "proof_moment" not in captured["prompt"]

    def test_they_are_obligations_not_suggestions(self, monkeypatch):
        """
        The directive matters as much as the data. A field the model may use or
        ignore is the same as no field, and this one exists because the model
        was defaulting to a plausible generic setting.

        usage_moments now does double duty: it grounds the middle's setting AND
        it is where the piece ends. The middle develops towards one of these
        moments and stops at the reach — that stop is the seam the founder's own
        demo picks up from, so it has to be an obligation rather than a hint.
        """
        captured = self._capture(monkeypatch)
        assert "scene.setting must come from usage_moments" in captured["prompt"]
        assert "The middle must end AT the usage moment from usage_moments" in captured["prompt"]
        assert "not using it" in captured["prompt"]

    def test_an_empty_profile_does_not_invent_a_setting_silently(self, monkeypatch):
        """
        With nothing recorded, the prompt has to say the moment is unspecified
        rather than letting a default through. "Unstated" is the honest value
        and the directive tells the model to pass it on.
        """
        captured = self._capture(
            monkeypatch, usage_moments=[], proof_moment="",
        )
        assert '"usage_moments": []' in captured["prompt"]
        assert "state that the moment is unspecified" in captured["prompt"]


class TestProvedHooksReachThePrompt:
    """
    The founder's own recorded numbers, aggregated per template.

    Everything else on the App Profile is scraped once and then goes stale, so
    the model has no way to learn which openings work for THIS app. This is the
    one signal that improves with use, and until now it was displayed on a page
    and read by no prompt.
    """

    def test_no_history_says_so_explicitly(self):
        """
        Silence is the honest output for a new app, and the sentence matters:
        "nothing recorded yet, do not assume anything is proven" is the correct
        instruction. An invented best performer would be indistinguishable from
        a real one by the time it reached generation.
        """
        import feedback
        text = feedback.build_proved_hooks_section(
            feedback.summarize_proved_hooks([])
        )
        assert "none recorded" in text
        assert "do not" in text and "proven" in text

    def test_ranking_is_by_views_and_names_the_underperformer(self, monkeypatch):
        import ai_service
        import feedback
        rows = [
            {"template_id": "t-win", "views": 5000, "likes": 400, "comments": 20,
             "shares": 90, "saves": 300, "source": "manual"},
            {"template_id": "t-lose", "views": 200, "likes": 2, "comments": 0,
             "shares": 1, "saves": 0, "source": "manual"},
        ]
        summary = feedback.summarize_proved_hooks(rows)
        assert summary["has_signal"] is True
        assert summary["top"][0]["template_id"] == "t-win"
        assert summary["bottom"][0]["template_id"] == "t-lose"

        captured = {}

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            captured["prompt"] = prompt
            return {
                "strategy_summary": "s", "audience_problem": "p",
                "emotional_triggers": ["t"], "hook_concept": "c",
                "hook_line": "h", "hook_promise": "p", "hook_action": "a",
                "messaging_pillars": ["m"], "primary_feature": "f",
                "desired_outcome": "o", "mechanism_beat": "mb",
                "payoff_beat": "pb", "differentiation_beat": "b",
                "cta_strategy": "c", "scene": {"environment": "kitchen"},
                "performance": {"movement": "still"},
                "segments": [{"index": 0, "role": "hook", "seconds": 5,
                              "goal": "g", "script": "s", "action": "a"}],
                "continuity_contract": {
                    "established": [], "must_not_change": [], "do_not_repeat": [],
                },
            }

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        asyncio.run(ai_service.generate_video_strategy(
            profile={"brand_name": "ShiftLog"},
            template={"name": "T", "content_slots": {}},
            angle=None, objective="address_user_problem",
            hook_seconds=5, total_duration=20, tone="", brand_voice="",
            profile_feedback={}, proved_hooks=summary,
        ))
        assert "PAST PERFORMANCE" in captured["prompt"]
        assert "t-win" in captured["prompt"]
        assert "t-lose" in captured["prompt"]
        # Says what the evidence is and is not, so the model does not treat a
        # view count as proof that a template is better.
        assert "not a claim that one template is better" in captured["prompt"]

    def test_a_zero_view_entry_is_not_ranked(self):
        """
        A like with no view count cannot be turned into a rate, and treating it
        as one would invent a ratio. A new profile full of unmeasured videos must
        report no signal rather than a best performer.
        """
        import feedback
        summary = feedback.summarize_proved_hooks([
            {"template_id": "t1", "views": 0, "likes": 5, "comments": 0,
             "shares": 0, "saves": 1, "source": "manual"},
        ])
        assert summary["has_signal"] is False
        assert summary["top"] == []

    def test_a_non_manual_entry_is_excluded(self):
        """
        A future automated import must not be able to quietly become an input to
        generation. Only the founder's own numbers qualify.
        """
        import feedback
        summary = feedback.summarize_proved_hooks([
            {"template_id": "t1", "views": 9000, "likes": 0, "comments": 0,
             "shares": 0, "saves": 0, "source": "apify"},
        ])
        assert summary["has_signal"] is False

    def test_the_endpoint_joins_performance_to_the_template(self, api, monkeypatch):
        """
        The wiring, and the join. performance_entries has no template_id of its
        own -- an entry is a number against a render, and the render is what
        knows its template -- so the aggregation is a join, not a read.
        """
        from models import now_iso
        async def fake_strategy(**kwargs):
            seen.update(kwargs)
            return {
                "strategy_summary": "s", "audience_problem": "p",
                "emotional_triggers": ["t"], "hook_concept": "c",
                "hook_line": "h", "hook_promise": "p", "hook_action": "a",
                "messaging_pillars": ["m"], "primary_feature": "f",
                "desired_outcome": "o", "mechanism_beat": "mb",
                "payoff_beat": "pb", "differentiation_beat": "b",
                "cta_strategy": "c", "scene": {"environment": "kitchen"},
                "performance": {"movement": "still"},
                "segments": [{"index": 0, "role": "hook", "seconds": 5,
                              "goal": "g", "script": "s", "action": "a"}],
                "continuity_contract": {
                    "established": [], "must_not_change": [], "do_not_repeat": [],
                },
            }

        seen = {}
        import server
        monkeypatch.setattr(server, "generate_video_strategy", fake_strategy)

        project, _profile, template = _make_project(api, NURSE_APP)
        _run(api._execute(
            "INSERT INTO generations (id, studio_project_id, brand_profile_id, "
            "template_id, status, created_at, updated_at, user_id) "
            "VALUES ('g1', ?, ?, ?, 'completed', '', '', ?)",
            (project["id"], project["brand_profile_id"], template["id"], ANON),
        ))
        _run(api._execute(
            "INSERT INTO performance_entries (id, generation_id, brand_profile_id, "
            "views, saves, source, created_at, updated_at, user_id) "
            "VALUES ('e1', 'g1', ?, 4200, 120, 'manual', ?, ?, ?)",
            (project["brand_profile_id"], now_iso(), now_iso(), ANON),
        ))
        _run(api.generate_project_strategy(
            project_id=project["id"],
            payload=server.GenerateStrategyRequest(), user_id=ANON))

        proved = seen.get("proved_hooks")
        assert proved, "no performance signal reached the strategy call"
        assert proved["has_signal"] is True
        assert proved["top"][0]["template_id"] == template["id"]
        assert proved["top"][0]["views"] == 4200


class TestFirstPersonClaimsAreFlagged:
    """
    Nothing in the system records the presenter's real relationship to the
    product, so any first-person experience claim is invented. A founder-entered
    relationship field was considered and dropped: asking a model for a fact
    only a person can supply is how you get a confident wrong answer, and gating
    on a field it might contradict is worse than forbidding the claim.
    """

    def _report(self, script):
        import claim_safety as cs
        return cs.build_safety_report({"script": script}, {})

    def test_invented_experience_is_flagged(self):
        for script in (
            "I have used this every shift for two years.",
            "I rely on this app daily.",
            "As a nurse, I use this on every ward round.",
            "I built this app for my patients.",
        ):
            report = self._report(script)
            reasons = [w["reason"] for w in report["risk_warnings"]]
            assert any(
                "first-person experience claim" in r for r in reasons
            ), f"not flagged: {script}"

    def test_it_is_a_warning_not_a_block(self):
        """Editorial control stays with the founder, like every other risk tier."""
        report = self._report("I use this every day.")
        assert report["passed"] is True
        assert report["risk_warnings"]

    def test_ordinary_copy_is_untouched(self):
        for script in (
            "One tap and the shift is logged.",
            "Try it and see the difference.",
            "Your notes, in your voice.",
        ):
            reasons = [w["reason"] for w in self._report(script)["risk_warnings"]]
            assert not any("first-person" in r for r in reasons), script
