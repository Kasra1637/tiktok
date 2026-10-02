"""
Tests for hook LENGTH: reconciling a 2-4s wanted hook with providers that
cannot render under 4-5s.

The claim under test: a founder can ask for a 3-second hook, the request is
never silently upgraded to the provider's floor, the clip that lands is
actually the length that was asked for, and where the middle begins is a
choice they control inside a named window.

A hook length is DIRECTORIAL now, not a render length. There is no separately
rendered hook to trim: the piece is one render, hook and middle together, so
`hook_seconds` says where the middle starts and nothing is cut. The resolver
and the frame-exact trim below still exist because generations recorded before
that change carry a non-zero trim and must still be trimmed on poll.
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


def _ready_project_with_strategy(api, spec, hook_seconds=0):
    from models import (
        ApproveAppProfileRequest, BrandProfileCreateRequest,
        CreateStudioProjectRequest, now_iso,
    )
    from ai_service import normalize_strategy

    profile = _run(api.create_brand(
        payload=BrandProfileCreateRequest(**{
            "brand_name": spec["name"],
            # Defaults the case does not override. Approval now refuses a profile
            # with no description, features or usage moments, so a helper that
            # only forwarded the case's own fields would build a profile the
            # product will not let anyone approve.
            "brand_description": "A focus timer for people who stall on starting.",
            "core_features": ["Task timer", "Reminders"],
            "usage_moments": ["Starting a task they have been avoiding"],
            **spec["profile"],
        }),
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
        # Exactly two sections, as generate_video_strategy now emits: the hook,
        # then the middle that develops it and stops at the reach for the phone.
        # `cta_strategy`, `continuity_contract` and the seven-beat arc are gone
        # and normalization drops them — the founder's demo and their call to
        # action are their own footage.
        "segments": [
            {"index": 0, "role": "hook", "seconds": hook_seconds or 3,
             "goal": "land it", "script": "It was always this one tap.",
             "action": "Taps once"},
            {"index": 1, "role": "middle", "seconds": 8,
             "goal": "show what it costs to keep doing it by hand",
             "script": "It used to be four taps and a phone call.",
             "action": "shows the paperwork, then picks the phone up"},
        ],
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


def _tpl_hook(api):
    templates = _run(api.list_templates(user_id=ANON))["templates"]
    return templates[0]["hook_seconds"]


# ---------------------------------------------------------------------------
# 4. The project edit path
# ---------------------------------------------------------------------------
class TestHookLengthEditing:
    def test_patching_hook_length_is_validated(self, api):
        """
        The hook length is where the middle begins, inside a named 2-4s window:
        4s is the ceiling because the first four seconds are the only window a
        viewer decides in, and 2s is the floor because a hook has to have room
        to land.
        """
        from models import UpdateStudioProjectRequest
        project, _p, _t, _s = _ready_project_with_strategy(api, SPEC, hook_seconds=3)
        updated = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(hook_seconds=4), user_id=ANON))
        assert updated["hook_seconds"] == 4

    def test_a_length_outside_the_window_is_clamped_not_refused(self, api):
        """
        Was `test_a_length_outside_the_offered_choices_is_refused`, and it
        asserted a 400.

        Clamping, not refusing. hook_seconds is directorial rather than a render
        length, and the render is one pass either way — so a hand-typed 7s would
        leave the middle nothing to film and cost the founder the whole video,
        while refusing would cost them only the one field. Moving the boundary
        to a length a hook can actually land in is strictly better than either
        outcome, and 7 is not a mistake worth a dead end.

        The window is asserted at both ends so a clamp can never quietly become
        "anything goes".
        """
        import template_library as tl
        from models import UpdateStudioProjectRequest
        project, _p, _t, _s = _ready_project_with_strategy(api, SPEC)
        for wanted, expected in (
            (7, tl.MAX_HOOK_SECONDS),
            (1, tl.MIN_HOOK_SECONDS),
            (-4, tl.MIN_HOOK_SECONDS),
        ):
            updated = _run(api.update_studio_project(
                project_id=project["id"],
                payload=UpdateStudioProjectRequest(hook_seconds=wanted), user_id=ANON))
            assert updated["hook_seconds"] == expected, wanted
        assert tl.MIN_HOOK_SECONDS <= expected <= tl.MAX_HOOK_SECONDS

    def test_zero_clears_the_choice_back_to_the_template(self, api):
        """
        0 still means "follow the template". Clamping must not swallow it, or
        every project would silently pin a boundary nobody chose.
        """
        from models import UpdateStudioProjectRequest
        project, _p, _t, _s = _ready_project_with_strategy(api, SPEC, hook_seconds=4)
        updated = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(hook_seconds=0), user_id=ANON))
        assert updated["hook_seconds"] == 0


# ---------------------------------------------------------------------------
# 5. The two prompt paths now agree about the hook length
# ---------------------------------------------------------------------------
class TestPromptAgreement:
    def test_fallback_beat_layout_uses_the_template_hook_length(self):
        """
        generation_planning hardcoded 0-3s while the same prompt carried the
        template's own hook_seconds, so a 2s template was told to hold for 3.

        The fallback no longer says "first N seconds" at all — the whole video
        is two sections and the second one has to be described too, so the
        layout names both boundaries. What still has to hold is that it splits
        at the hook length it was handed rather than at a constant, and that it
        tells the model not to film the app or ask for anything.
        """
        from generation_planning import _format_beats
        two = _format_beats([], 20, 2)
        assert "0-2s" in two and "2-20s" in two
        assert "the only part of this 20s video with 2s to stop the scroll" in two
        assert "Do NOT film the app working" in two
        assert "do not ask for anything" in two
        three = _format_beats([], 20, 3)
        assert "0-3s" in three and "3-20s" in three
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
