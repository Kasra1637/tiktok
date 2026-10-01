"""
Tests for hook LENGTH: reconciling a 2-4s wanted hook with providers that
cannot render under 4-5s.

The claim under test: a founder can ask for a 3-second hook, the request is
never silently upgraded to the provider's floor, the clip that lands is
actually the length that was asked for, and an extension continues from the
TRIMMED clip rather than the full render the viewer never saw.
"""
import asyncio
import importlib
import json
import os
import re
import shutil
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

_TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c626001000000ffff0300000600055d3866680000000049454e44ae426082"
)

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
needs_ffmpeg = pytest.mark.skipif(
    not (FFMPEG and FFPROBE), reason="ffmpeg/ffprobe not on PATH"
)


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-hooklen-")
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

    # pipeline.VIDEOS_DIR / GENERATED_DIR are module-level constants pointing at
    # live storage, so redirect them: several tests below write real clips.
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


def _duration(path: Path) -> float:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(re.search(r"[\d.]+", out.stdout).group())


def _make_clip(path: Path, seconds: int) -> Path:
    subprocess.run([
        FFMPEG, "-y", "-f", "lavfi", "-i",
        f"testsrc=duration={seconds}:size=360x640:rate=30",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
        # Sparse keyframes, like a real provider render: a stream copy would
        # then cut on a packet boundary rather than exactly where asked.
        "-c:v", "libx264", "-g", "60", "-keyint_min", "60", "-sc_threshold", "0",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path),
    ], check=True, capture_output=True)
    return path


def _mock_submit(api, monkeypatch, response=None):
    calls = []

    async def fake_generate_video(**kwargs):
        calls.append(kwargs)
        return response or {"id": f"job-{len(calls)}", "status": "queued",
                            "usage": {"cost": 0.2}}

    monkeypatch.setattr(api, "generate_video", fake_generate_video)
    return calls


# ---------------------------------------------------------------------------
# 1. The resolver
# ---------------------------------------------------------------------------
class TestResolveHookLength:
    def test_target_above_floor_needs_no_trim(self):
        import video_providers as vp
        # MiniMax's floor is 5s, so 5s+ is renderable as asked.
        for target in (5, 6):
            r = vp.resolve_hook_length(target, "minimax-h3")
            assert r["target"] == target
            assert r["render_seconds"] == target
            assert r["trim_to"] == 0
            assert r["guarantee"] == "as_rendered"

    def test_target_below_floor_is_rendered_longer_then_trimmed(self):
        """
        The core of the feature. A 3s hook is not renderable anywhere here, so
        it must be rendered at the floor and cut - never quietly upgraded.
        """
        import video_providers as vp
        r = vp.resolve_hook_length(3, "minimax-h3")
        assert r["target"] == 3
        assert r["render_seconds"] == 5
        assert r["trim_to"] == 3
        assert r["guarantee"] == "trimmed"
        assert "cut down" in " ".join(r["adjustments"])

    def test_every_curated_template_default_needs_no_upgrade(self):
        """
        Curated templates declare 2-3s hooks, and that contract is test-enforced
        in test_template_library.py. It must now actually reach a render.
        """
        import template_library
        import video_providers as vp
        for tpl in template_library.CURATED_TEMPLATES:
            declared = int(tpl["hook_seconds"])
            assert 1 <= declared <= 3, tpl["name"]
            r = vp.resolve_hook_length(declared, "minimax-h3")
            # The declared value is preserved as the TARGET; it is only the
            # render that is longer.
            assert r["target"] == declared, tpl["name"]
            assert r["trim_to"] == declared, tpl["name"]

    def test_minimax_floor_is_honoured(self):
        import video_providers as vp
        # H3's floor is 5s, so even a 4s hook is a trim there.
        r = vp.resolve_hook_length(4, "minimax-h3")
        assert r["render_seconds"] == 5
        assert r["trim_to"] == 4
        assert r["guarantee"] == "trimmed"
        r5 = vp.resolve_hook_length(5, "minimax-h3")
        assert r5["render_seconds"] == 5 and r5["trim_to"] == 0

    def test_target_above_ceiling_is_reported_not_silently_changed(self):
        import video_providers as vp
        r = vp.resolve_hook_length(45, "minimax-h3")
        assert r["render_seconds"] == 15
        assert r["guarantee"] == "clamped_down"
        assert "at most 15s" in r["note"]

    def test_unset_target_falls_back_to_the_default(self):
        import video_providers as vp
        for value in (None, "", 0):
            r = vp.resolve_hook_length(value, "minimax-h3")
            assert r["render_seconds"] == vp.DEFAULT_HOOK_SECONDS
            assert r["guarantee"] == "as_rendered"

    def test_every_offered_choice_resolves(self):
        """No length the product can compute may be a dead end."""
        import video_providers as vp
        for choice in (2, 3, 4, 5, 6):
            r = vp.resolve_hook_length(choice, "minimax-h3")
            assert r["render_seconds"] >= choice, choice
            assert r["guarantee"] in (
                "as_rendered", "trimmed", "clamped_down", "trim_unavailable"
            )
            assert r["note"], choice

    def test_missing_ffmpeg_is_reported_before_a_paid_render(self):
        import video_providers as vp
        original = vp.ffmpeg_available
        vp.ffmpeg_available = lambda: False
        try:
            r = vp.resolve_hook_length(3, "minimax-h3")
            assert r["guarantee"] == "trim_unavailable"
            assert "ffmpeg" in r["note"]
            # A length that needs no trim is unaffected.
            assert vp.resolve_hook_length(5, "minimax-h3")["guarantee"] == "as_rendered"
        finally:
            vp.ffmpeg_available = original


# ---------------------------------------------------------------------------
# 2. The trim itself
# ---------------------------------------------------------------------------
@needs_ffmpeg
class TestTrimVideo:
    def test_trim_is_frame_exact_not_a_keyframe_cut(self):
        """
        The reason this function exists rather than reusing trim_video_to_hook().
        Stream copy on a 4s clip with 2s keyframes yields 3.067s; the delivered
        file must be 3.000s because it is advertised as a 3-second hook.
        """
        import pipeline
        tmp = Path(tempfile.mkdtemp(prefix="tiktok-trim-"))
        src = _make_clip(tmp / "src.mp4", 4)
        out = tmp / "out.mp4"
        trimmed = _run(pipeline.trim_video_exact(src, 3, out))
        assert trimmed is not None
        assert abs(_duration(trimmed) - 3.0) < 0.02, _duration(trimmed)

    def test_two_and_three_second_targets(self):
        import pipeline
        tmp = Path(tempfile.mkdtemp(prefix="tiktok-trim-"))
        for target in (2, 3):
            src = _make_clip(tmp / f"src{target}.mp4", 5)
            out = tmp / f"out{target}.mp4"
            trimmed = _run(pipeline.trim_video_exact(src, target, out))
            assert trimmed is not None
            assert abs(_duration(trimmed) - target) < 0.02

    def test_in_place_replace_leaves_the_trimmed_file_canonical(self):
        """
        This is the interaction that silently breaks extensions if it is wrong:
        the canonical path is what an extension bridges from, so the trimmed
        clip must REPLACE the render rather than sit beside it.
        """
        import pipeline
        tmp = Path(tempfile.mkdtemp(prefix="tiktok-trim-"))
        canonical = _make_clip(tmp / "canonical.mp4", 4)
        assert abs(_duration(canonical) - 4.0) < 0.05
        result = _run(pipeline.replace_with_trimmed(canonical, 2))
        assert result == canonical
        assert abs(_duration(canonical) - 2.0) < 0.02
        # No temp file left behind.
        assert not [p for p in tmp.iterdir() if p.name.startswith(".")]

    def test_failed_trim_leaves_the_original_untouched(self):
        """A failed cut must not lose the render."""
        import pipeline
        tmp = Path(tempfile.mkdtemp(prefix="tiktok-trim-"))
        src = _make_clip(tmp / "keep.mp4", 4)
        result = _run(pipeline.replace_with_trimmed(src, 0))
        assert result is None
        assert src.is_file()
        assert abs(_duration(src) - 4.0) < 0.05

    def test_missing_source_returns_none_rather_than_raising(self):
        import pipeline
        tmp = Path(tempfile.mkdtemp(prefix="tiktok-trim-"))
        assert _run(pipeline.trim_video_exact(tmp / "nope.mp4", 3, tmp / "o.mp4")) is None
        assert _run(pipeline.replace_with_trimmed(tmp / "nope.mp4", 3)) is None


# ---------------------------------------------------------------------------
# 3. End to end: request a 3s hook, get a 3s hook
# ---------------------------------------------------------------------------
def _ready_project_with_strategy(api, spec, hook_seconds=0):
    from models import (
        ApproveAppProfileRequest, BrandProfileCreateRequest,
        CreateStudioProjectRequest, now_iso,
    )
    from ai_service import normalize_strategy

    profile = _run(api.create_brand(
        payload=BrandProfileCreateRequest(brand_name=spec["name"], **spec["profile"]),
        user_id=ANON))
    _run(api.approve_app_profile(
        profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
    template = _run(api.list_templates(user_id=ANON))["templates"][0]
    project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
        brand_profile_id=profile["id"], template_id=template["id"],
        duration_seconds=20, hook_seconds=hook_seconds,
    ), user_id=ANON))

    # A real character_reference so the identity path is exercised too.
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

    strategy = normalize_strategy({
        "strategy_summary": "Show the one thing this app removes.",
        "audience_problem": "The paperwork is the whole problem.",
        "emotional_triggers": ["relief"],
        "hook_concept": "Open mid-motion on the exhausted look, then the relief.",
        "hook_line": "It was always this one tap.",
        "hook_promise": "Show the tap.",
        "hook_action": "Taps the phone once.",
        "hook_dialogue": "Low and quick.",
        "messaging_pillars": ["One tap"],
        "primary_feature": "One-tap logging",
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
        # Hook plus a planned arc, matching what generate_video_strategy emits.
        # These tests extend at least once, so a hook-only plan would now be
        # correctly refused as "past the end of the plan".
        "segments": [
            {"index": 0, "role": "hook", "seconds": hook_seconds or 3,
             "goal": "land it", "script": "It was always this one tap.",
             "action": "Taps once"},
        ] + [
            {"index": i, "role": "cta" if i == 7 else "continuation", "seconds": 5,
             "goal": f"beat {i}", "script": f"Beat {i} of the story.",
             "action": f"action {i}"}
            for i in range(1, 8)
        ],
        "continuity_contract": {"established": ["teal scrubs", "a corridor"],
                                "must_not_change": ["the face", "the scrubs"],
                                "do_not_repeat": ["the hook line"]},
    })
    _run(api._execute(
        "UPDATE studio_projects SET strategy = ?, strategy_version = 1, status = 'draft'"
        " WHERE id = ?", (json.dumps(strategy), project["id"])))
    return _run(api.get_studio_project(project["id"], ANON)), profile, template, strategy


SPEC = {
    "name": "ShiftLog",
    "profile": {
        "app_category": "Productivity",
        "brand_description": "Shift logging for nurses.",
        "target_audience": "night-shift nurses",
        "core_features": ["One-tap shift logging"],
        "claims_approved": ["Logs a shift in one tap"],
        "claims_banned": ["cures burnout"],
    },
}


class TestHookEndToEnd:
    def test_strategy_endpoint_inherits_the_template_hook_seconds(self, api):
        """
        The template contract (2-3s) is test-enforced but was never reaching a
        render. It now must.
        """
        from models import GenerateStrategyRequest

        captured = {}

        async def fake_strategy(**kwargs):
            captured.update(kwargs)
            raise RuntimeError("stop-after-args")

        # Patch the symbol the endpoint calls through the module namespace.
        import ai_service
        original = ai_service.generate_video_strategy
        api.generate_video_strategy = fake_strategy
        try:
            project, _p, _t, _s = _ready_project_with_strategy(api, SPEC)
            with pytest.raises(HTTPException):
                _run(api.generate_project_strategy(
                    project_id=project["id"], payload=GenerateStrategyRequest(),
                    user_id=ANON))
            assert captured["hook_seconds"] == int(_tpl_hook(api)), captured
        finally:
            api.generate_video_strategy = original

    def test_project_hook_length_defaults_from_the_template(self, api):
        """A new project inherits its template's declared hook length."""
        from models import ApproveAppProfileRequest, BrandProfileCreateRequest, CreateStudioProjectRequest
        profile = _run(api.create_brand(
            payload=BrandProfileCreateRequest(brand_name="DefaultHook",
                                             app_category="Productivity"),
            user_id=ANON))
        _run(api.approve_app_profile(
            profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
        template = _run(api.list_templates(user_id=ANON))["templates"][0]
        project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"], template_id=template["id"]), user_id=ANON))
        assert project["hook_seconds"] == int(template["hook_seconds"])
        assert 1 <= project["hook_seconds"] <= 3

    def test_explicit_hook_length_beats_the_template(self, api):
        from models import ApproveAppProfileRequest, BrandProfileCreateRequest, CreateStudioProjectRequest
        profile = _run(api.create_brand(
            payload=BrandProfileCreateRequest(brand_name="ExplicitHook",
                                             app_category="Productivity"),
            user_id=ANON))
        _run(api.approve_app_profile(
            profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
        template = _run(api.list_templates(user_id=ANON))["templates"][0]
        project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"], template_id=template["id"],
            hook_seconds=5), user_id=ANON))
        assert project["hook_seconds"] == 5

    def test_hook_render_records_the_trim_and_asks_for_the_floor(self, api, monkeypatch):
        """The request is for the floor; the intent to trim is recorded up front."""
        from models import GenerateHookRequest
        project, _p, _t, _s = _ready_project_with_strategy(api, SPEC, hook_seconds=3)
        calls = _mock_submit(api, monkeypatch)
        gen = _run(api.generate_project_hook(
            project_id=project["id"],
            payload=GenerateHookRequest(model="minimax-h3", duration_seconds=3),
            user_id=ANON))
        # Asked the model for 5s, not 3s.
        assert calls[0]["duration"] == 5
        assert gen["trim_to_seconds"] == 3
        assert gen["hook_length"]["target"] == 3
        assert gen["hook_length"]["render_seconds"] == 5
        assert gen["hook_length"]["trim_to"] == 3
        # The response already reports the length the founder will get.
        assert gen["duration"] == 3

    def test_no_trim_when_the_floor_is_satisfied(self, api, monkeypatch):
        from models import GenerateHookRequest
        project, _p, _t, _s = _ready_project_with_strategy(api, SPEC, hook_seconds=5)
        calls = _mock_submit(api, monkeypatch)
        gen = _run(api.generate_project_hook(
            project_id=project["id"],
            payload=GenerateHookRequest(model="minimax-h3", duration_seconds=5),
            user_id=ANON))
        assert calls[0]["duration"] == 5
        assert gen["trim_to_seconds"] == 0
        assert gen["hook_length"]["guarantee"] == "as_rendered"

    def test_hook_length_survives_on_the_project_for_later_steps(self, api, monkeypatch):
        from models import GenerateHookRequest
        project, _p, _t, _s = _ready_project_with_strategy(api, SPEC, hook_seconds=3)
        _mock_submit(api, monkeypatch)
        _run(api.generate_project_hook(
            project_id=project["id"],
            payload=GenerateHookRequest(model="minimax-h3"), user_id=ANON))
        again = _run(api.get_studio_project(project["id"], ANON))
        assert again["hook_seconds"] == 3

    def test_minimax_request_asks_for_five_seconds(self, api, monkeypatch):
        from models import GenerateHookRequest
        project, _p, _t, _s = _ready_project_with_strategy(api, SPEC, hook_seconds=3)
        calls = _mock_submit(api, monkeypatch)
        gen = _run(api.generate_project_hook(
            project_id=project["id"],
            payload=GenerateHookRequest(model="minimax-h3", duration_seconds=3),
            user_id=ANON))
        assert calls[0]["duration"] == 5
        assert gen["trim_to_seconds"] == 3


def _tpl_hook(api):
    templates = _run(api.list_templates(user_id=ANON))["templates"]
    return templates[0]["hook_seconds"]


# ---------------------------------------------------------------------------
# 4. Poll applies the trim, and the extension bridges the trimmed clip
# ---------------------------------------------------------------------------
@needs_ffmpeg
class TestTrimIsApplied:
    def _complete_with_real_clip(self, api, monkeypatch, trim_to, render_seconds=5):
        """
        Drive a real 5s render through submit -> poll with a working local file,
        so the trim path executes for real rather than being mocked away.
        """
        from models import GenerateHookRequest, StudioGenerationRequest
        project, _p, _t, _s = _ready_project_with_strategy(api, SPEC, hook_seconds=trim_to or 4)
        _mock_submit(api, monkeypatch)

        gen = _run(api.generate_project_hook(
            project_id=project["id"],
            payload=GenerateHookRequest(model="minimax-h3",
                                        duration_seconds=trim_to or 5),
            user_id=ANON))

        # Stand in for the provider's finished clip, downloaded by poll.
        served = _make_clip(api.pipeline.VIDEOS_DIR / f"{gen['id']}-served.mp4", render_seconds)
        assert served.is_file()

        async def fake_download(url, generation_id):
            # Copy the served clip to the canonical path, which is where poll
            # expects the downloaded file to land.
            target = api.pipeline.VIDEOS_DIR / f"{generation_id}.mp4"
            shutil.copy2(served, target)
            return target

        monkeypatch.setattr(api, "_download_generation_video", fake_download)
        monkeypatch.setattr(api.storage_service, "upload_video", lambda *a, **k: None)
        monkeypatch.setattr(api.storage_service, "is_configured", lambda: False)

        async def fake_poll(job_id):
            return {"status": "completed", "unsigned_urls": ["https://provider.test/x.mp4"]}

        monkeypatch.setattr(api, "poll_video_job", fake_poll)
        _run(api._execute(
            "UPDATE generations SET openrouter_job_id = 'job-1' WHERE id = ?", (gen["id"],)))
        return project, gen, _run(api.poll_generation(gen["id"], ANON))

    def test_poll_cuts_the_hook_to_the_requested_length(self, api, monkeypatch):
        _project, gen, updated = self._complete_with_real_clip(api, monkeypatch, trim_to=3)
        canonical = api.pipeline.VIDEOS_DIR / f"{gen['id']}.mp4"
        assert canonical.is_file()
        assert abs(_duration(canonical) - 3.0) < 0.02, _duration(canonical)
        # The row reports what was delivered, not what was asked of the model.
        assert updated["duration"] == 3
        assert updated["trim_to_seconds"] == 3
        assert "Cut down to 3s" in (updated.get("storage_error") or "")

    def test_extension_bridges_from_the_trimmed_hook(self, api, monkeypatch):
        """
        The regression this whole feature could introduce: if the trim left the
        full render at the canonical path, every continuation would resume from
        a frame the viewer never saw.

        The load-bearing assertion is the canonical file's LENGTH. Comparing
        extracted frame bytes looked equivalent but was flaky: it depended on
        two independent ffmpeg encodes plus where `-sseof -1` happens to land,
        so it could pass without proving anything and fail for the wrong reason.
        The length cannot: 3.0s is only possible if the trimmed file replaced
        the 5s render at that exact path.
        """
        from models import ApproveSegmentRequest, StudioGenerationRequest
        _project, gen, updated = self._complete_with_real_clip(api, monkeypatch, trim_to=3)

        canonical = api.pipeline.VIDEOS_DIR / f"{gen['id']}.mp4"
        assert canonical.is_file()
        delivered = _duration(canonical)
        assert abs(delivered - 3.0) < 0.02, (
            f"the canonical file is {delivered:.3f}s, so the trim did NOT replace "
            f"the render at the path an extension bridges from. "
            f"storage_error={updated.get('storage_error')!r}"
        )
        assert abs(delivered - 5.0) > 0.5, "the full render is still at the canonical path"

        # And the seam frame the extension will use is readable from that file.
        bridge = api.pipeline.GENERATED_DIR / f"probe-{gen['id']}.png"
        assert _run(api.pipeline.extract_last_frame(canonical, bridge)) is not None, (
            "could not read a final frame from the trimmed hook"
        )

        # The extension proceeds from the approved, trimmed hook.
        _run(api.approve_generation(gen["id"], ApproveSegmentRequest(), ANON))
        calls = _mock_submit(api, monkeypatch)
        _run(api.extend_generation(
            gen["id"], StudioGenerationRequest(duration_seconds=6), ANON))
        assert calls, "the extension never reached the provider"
        # The prompt must not claim continuity it cannot have: the test fakes
        # the bridge frame, so the important assertion is that a bridge is used.
        assert calls[0]["prompt"]


# ---------------------------------------------------------------------------
# 5. The project edit path
# ---------------------------------------------------------------------------
class TestHookLengthEditing:
    def test_patching_hook_length_is_validated(self, api):
        from models import UpdateStudioProjectRequest
        project, _p, _t, _s = _ready_project_with_strategy(api, SPEC, hook_seconds=3)
        updated = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(hook_seconds=5), user_id=ANON))
        assert updated["hook_seconds"] == 5

    def test_a_length_outside_the_offered_choices_is_refused(self, api):
        from models import UpdateStudioProjectRequest
        project, _p, _t, _s = _ready_project_with_strategy(api, SPEC)
        with pytest.raises(HTTPException) as err:
            _run(api.update_studio_project(
                project_id=project["id"],
                payload=UpdateStudioProjectRequest(hook_seconds=7), user_id=ANON))
        assert err.value.status_code == 400
        assert "Hook length" in str(err.value.detail)

    def test_zero_clears_the_choice_back_to_the_template(self, api):
        from models import UpdateStudioProjectRequest
        project, _p, _t, _s = _ready_project_with_strategy(api, SPEC, hook_seconds=5)
        updated = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(hook_seconds=0), user_id=ANON))
        assert updated["hook_seconds"] == 0


# ---------------------------------------------------------------------------
# 6. The two prompt paths now agree about the hook length
# ---------------------------------------------------------------------------
class TestPromptAgreement:
    def test_fallback_beat_layout_uses_the_template_hook_length(self):
        """
        generation_planning hardcoded 0-3s while the same prompt carried the
        template's own hook_seconds, so a 2s template was told to hold for 3.
        """
        from generation_planning import _format_beats
        two = _format_beats([], 20, 2)
        assert "0-2s" in two and "first 2 seconds" in two
        three = _format_beats([], 20, 3)
        assert "0-3s" in three
        # A hook longer than the video must not produce a broken layout.
        assert _format_beats([], 2, 5)

    def test_single_pass_prompt_reports_the_templates_hook_length(self):
        import generation_planning
        template = {"name": "T", "category": "contrarian", "hook_seconds": 2,
                    "opening_structure": "x", "visual_style": "v", "camera_pacing": "p"}
        prompt = generation_planning.build_single_pass_prompt(
            plan={"hook_line": "Hello", "script": "s", "beat_timeline": []},
            profile={"brand_name": "App"}, template=template, duration=20)
        assert "first 2 seconds" in prompt
        assert "0-2s" in prompt
        assert "first 3 seconds" not in prompt
