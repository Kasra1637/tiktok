"""
Tests for deterministic overlay composition.

build_filter_graph is pure, so the geometry is asserted without rendering.
The escaping rules are the highest-risk part: they were wrong twice during
development (Windows drive-letter colons, and drawtext's deeper % parsing),
and both failures were silent or opaque. These tests pin the behaviour.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

import overlays

FFMPEG = shutil.which("ffmpeg")
needs_ffmpeg = pytest.mark.skipif(
    not FFMPEG, reason="ffmpeg not on PATH"
)


class TestEscaping:
    def test_percent_needs_a_double_backslash(self):
        """
        drawtext parses '%' one level deeper than the filtergraph parser, so a
        single backslash is consumed before drawtext sees it and the render
        fails with "Stray %". Verified against ffmpeg 9.0.2.
        """
        assert overlays._escape_drawtext("100% off") == "100\\\\% off"

    def test_colon_needs_a_single_backslash(self):
        assert overlays._escape_drawtext("note: hello") == "note\\: hello"

    def test_comma_and_semicolon_escaped(self):
        assert overlays._escape_drawtext("a, b; c") == "a\\, b\\; c"

    def test_backslash_is_escaped_first(self):
        """A literal backslash must not double-escape the escapes we add."""
        assert overlays._escape_drawtext("a\\b") == "a\\\\b"
        assert overlays._escape_drawtext("a\\%b") == "a\\\\\\\\%b"

    def test_quotes_are_removed(self):
        """A quote would terminate the filter argument."""
        assert "'" not in overlays._escape_drawtext("it's fine")

    def test_brackets_and_equals_escaped(self):
        out = overlays._escape_drawtext("a[b]c=d")
        assert "\\[" in out and "\\]" in out and "\\=" in out

    def test_empty_text(self):
        assert overlays._escape_drawtext("") == ""
        assert overlays._escape_drawtext(None) == ""

    def test_realistic_caption_with_percent_and_colon(self):
        out = overlays._escape_drawtext("100% offline: no signal needed")
        assert out.count("%") == 1
        assert "\\%" in out and "\\:" in out


class TestFilterPath:
    def test_windows_drive_colon_is_escaped(self):
        """
        'C:\\Windows\\Fonts\\x.ttf' breaks the graph outright unless the drive
        colon is escaped: the filtergraph parser reads it as an option name.
        """
        out = overlays._escape_filter_path(r"C:\Windows\Fonts\segoeuib.ttf")
        assert out.startswith("'") and out.endswith("'")
        assert "C\\:" in out
        assert "\\" not in out.replace("C\\:", "")

    def test_backslashes_become_forward_slashes(self):
        assert overlays._escape_filter_path(r"C:\a\b.ttf") == "'C\\:/a/b.ttf'"

    def test_posix_path_is_untouched_apart_from_quoting(self):
        assert overlays._escape_filter_path("/usr/share/x.ttf") == "'/usr/share/x.ttf'"


class TestWindowClamping:
    def test_window_is_clamped_to_duration(self):
        start, end = overlays._clamp_window(0, 30, 12)
        assert end <= 12

    def test_negative_start_is_floored(self):
        start, _ = overlays._clamp_window(-5, 4, 12)
        assert start >= 0

    def test_inverted_window_is_repaired(self):
        start, end = overlays._clamp_window(8, 3, 12)
        assert end > start

    def test_garbage_window_does_not_crash(self):
        start, end = overlays._clamp_window("abc", None, 12)
        assert end > start >= 0

    def test_window_never_exceeds_duration(self):
        for s, e in ((0, 100), (-10, 5), (11.9, 12), (20, 30)):
            start, end = overlays._clamp_window(s, e, 12)
            assert 0 <= start <= end <= 12


class TestFilterGraph:
    def test_base_is_scaled_and_padded(self):
        graph, _, _ = overlays.build_filter_graph({}, 12, None)
        assert "scale=1080:1920" in graph
        assert "pad=1080:1920" in graph

    def test_scale_and_pad_are_chained_not_forked(self):
        """
        Regression guard. Chaining two filters off the same '[0:v]' leaves
        the first output dangling, pad re-reads the raw input, and every
        overlay is silently orphaned -- ffmpeg still exits 0 and writes a file
        that looks fine until you look at a frame.

        The intermediate label is now suffixed per-output (canvas_fit_chain is
        shared with the plain-download rescale), so assert the chain shape
        rather than the literal label name.
        """
        graph, _, _ = overlays.build_filter_graph({}, 12, None)
        assert (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[scaled_bg0]" in graph
        )
        assert "[scaled_bg0]pad=1080:1920" in graph
        # pad must not read the raw input again
        assert graph.count("[0:v]") == 1

    def test_output_label_exists(self):
        graph, _, _ = overlays.build_filter_graph({}, 12, None)
        assert graph.rstrip().endswith("[outv]")
        assert "format=yuv420p[outv]" in graph

    def test_missing_font_returns_none_rather_than_bad_graph(self, monkeypatch, tmp_path):
        monkeypatch.delenv("OVERLAY_FONT", raising=False)
        spec = {"captions": [{"start": 0, "end": 3, "text": "hello"}]}
        graph, _, warnings = overlays.build_filter_graph(spec, 12, None)
        assert graph is None
        assert warnings

    def test_missing_file_is_skipped_with_a_warning(self, tmp_path):
        spec = {"images": [{"path": str(tmp_path / "nope.png"), "start": 0, "end": 5}]}
        graph, inputs, warnings = overlays.build_filter_graph(spec, 12, None)
        assert inputs == []
        assert any("not found" in w for w in warnings)

    def test_existing_file_becomes_an_input(self, tmp_path):
        png = tmp_path / "a.png"
        png.write_bytes(b"\x89PNG\r\n\x1a\n")
        spec = {"images": [{"path": str(png), "start": 0, "end": 5, "kind": "screenshot"}]}
        graph, inputs, warnings = overlays.build_filter_graph(spec, 12, None)
        assert inputs == [str(png)]
        assert warnings == []
        assert "[1:v]" in graph

    def test_logo_defaults_to_corner_and_small(self, tmp_path):
        png = tmp_path / "logo.png"
        png.write_bytes(b"\x89PNG")
        spec = {"images": [{"path": str(png), "start": 0, "end": 5, "kind": "logo"}]}
        graph, _, _ = overlays.build_filter_graph(spec, 12, None)
        # A logo must not dominate the frame: 0.14 of 1080 is ~151px.
        assert "scale=151" in graph
        # ...and it belongs out of the way, in the corner.
        assert "overlay=929:192" in graph or "overlay=8" in graph

    def test_logo_default_applies_without_the_planner(self, tmp_path):
        """
        The per-kind default must live in the graph builder, not only in
        build_spec_from_plan, or a hand-written spec renders a logo at 80%
        width across the whole frame.
        """
        png = tmp_path / "logo.png"
        png.write_bytes(b"\x89PNG")
        graph, _, _ = overlays.build_filter_graph(
            {"images": [{"path": str(png), "start": 0, "end": 5, "kind": "logo"}]}, 12, None)
        assert "scale=864" not in graph

    def test_screenshot_defaults_to_center_and_large(self, tmp_path):
        png = tmp_path / "s.png"
        png.write_bytes(b"\x89PNG")
        spec = {"images": [{"path": str(png), "start": 0, "end": 5, "kind": "screenshot"}]}
        graph, _, _ = overlays.build_filter_graph(spec, 12, None)
        assert "scale=864" in graph

    def test_video_layers_are_indexed_after_images(self, tmp_path):
        png = tmp_path / "s.png"
        png.write_bytes(b"\x89PNG")
        vid = tmp_path / "r.mp4"
        vid.write_bytes(b"\x00")
        spec = {
            "images": [{"path": str(png), "start": 0, "end": 5}],
            "videos": [{"path": str(vid), "start": 2, "end": 8}],
        }
        graph, inputs, _ = overlays.build_filter_graph(spec, 12, None)
        assert len(inputs) == 2
        # The video layer must reference input 2, not collide with the image.
        assert "[2:v]" in graph

    def test_enable_window_is_written(self, tmp_path):
        png = tmp_path / "s.png"
        png.write_bytes(b"\x89PNG")
        spec = {"images": [{"path": str(png), "start": 3, "end": 9}]}
        graph, _, _ = overlays.build_filter_graph(spec, 12, None)
        assert "between(t,3.0,9.0)" in graph

    def test_captions_use_measured_positioning(self, monkeypatch, tmp_path):
        """Long copy must not overflow, so x/y are ffmpeg expressions."""
        font = "C:/Windows/Fonts/arial.ttf"
        spec = {"captions": [{"start": 0, "end": 3, "text": "a very long caption indeed"}]}
        graph, _, _ = overlays.build_filter_graph(spec, 12, font)
        assert "x=(w-text_w)/2" in graph
        assert "h-text_h-" in graph

    def test_end_card_renders_heading_and_subtext(self):
        font = "C:/Windows/Fonts/arial.ttf"
        spec = {"end_card": {"start": 9, "end": 12, "text": "Try it free", "subtext": "3-day trial"}}
        graph, _, _ = overlays.build_filter_graph(spec, 12, font)
        assert graph.count("drawtext=") == 2
        assert "Try it free" in graph
        assert "3-day trial" in graph

    def test_empty_spec_still_produces_a_valid_graph(self):
        graph, inputs, _ = overlays.build_filter_graph({}, 10, None)
        assert graph and inputs == [] and "[outv]" in graph


class TestFfmpegCommand:
    def test_base_is_first_input(self, tmp_path):
        argv, _ = overlays.build_ffmpeg_command(
            tmp_path / "b.mp4", tmp_path / "o.mp4", {}, 10, None)
        assert argv[argv.index("-i") + 1].endswith("b.mp4")

    def test_each_input_is_declared_exactly_once(self, tmp_path):
        """
        Regression guard. Declaring a path twice (once bare, once with
        -loop) shifts every later input index and silently corrupts the graph.
        """
        png = tmp_path / "a.png"
        png.write_bytes(b"\x89PNG")
        spec = {"images": [{"path": str(png), "start": 0, "end": 5}]}
        argv, _ = overlays.build_ffmpeg_command(
            tmp_path / "b.mp4", tmp_path / "o.mp4", spec, 10, "C:/f.ttf")
        assert argv.count("-i") == 2  # base + one image
        assert argv.count(str(png)) == 1

    def test_images_are_looped(self, tmp_path):
        png = tmp_path / "a.png"
        png.write_bytes(b"\x89PNG")
        spec = {"images": [{"path": str(png), "start": 0, "end": 5}]}
        argv, _ = overlays.build_ffmpeg_command(
            tmp_path / "b.mp4", tmp_path / "o.mp4", spec, 10, "C:/f.ttf")
        assert "-loop" in argv

    def test_videos_are_not_looped(self, tmp_path):
        vid = tmp_path / "r.mp4"
        vid.write_bytes(b"\x00")
        spec = {"videos": [{"path": str(vid), "start": 0, "end": 5}]}
        argv, _ = overlays.build_ffmpeg_command(
            tmp_path / "b.mp4", tmp_path / "o.mp4", spec, 10, "C:/f.ttf")
        assert "-loop" not in argv

    def test_raises_when_graph_cannot_be_built(self, tmp_path):
        with pytest.raises(ValueError):
            overlays.build_ffmpeg_command(
                tmp_path / "b.mp4", tmp_path / "o.mp4",
                {"captions": [{"start": 0, "end": 3, "text": "x"}]}, 10, None)

    def test_output_is_h264_yuv420p(self, tmp_path):
        argv, _ = overlays.build_ffmpeg_command(
            tmp_path / "b.mp4", tmp_path / "o.mp4", {}, 10, None)
        assert "libx264" in argv and "yuv420p" in argv

    def test_audio_is_optional_mapped(self, tmp_path):
        argv, _ = overlays.build_ffmpeg_command(
            tmp_path / "b.mp4", tmp_path / "o.mp4", {}, 10, None)
        assert "0:a?" in argv


PLAN = {
    "overlays": [
        {"start": 0, "end": 3, "text": "one prompt"},
        {"start": 4, "end": 7, "text": "100% offline"},
    ],
    # Left in deliberately. The plan no longer carries a `cta`, but an old saved
    # project can still have the column populated, and reading it here would put
    # a closing beat into footage that is supposed to stop at the reach for the
    # phone. `test_a_stale_cta_column_is_never_composited` is the assertion that
    # it cannot.
    "cta": "Try it free",
}


class TestSpecFromPlan:
    def test_captions_come_from_the_plan(self):
        spec = overlays.build_spec_from_plan(PLAN)
        assert [c["text"] for c in spec["captions"]] == ["one prompt", "100% offline"]

    def test_there_is_no_end_card(self):
        """
        Was `test_end_card_uses_the_cta`: it asserted the end card was built
        FROM the plan's cta, over a duration passed in by the caller.

        There is no end card and no cta to build one from. A call to action is
        the founder's own, added in their editor after the demo they record; the
        generated piece is a hook and a middle and is meant to stop at the
        moment the viewer reaches for the app. A three-second card closing the
        file would overwrite exactly the frame that hands off to their footage.

        So the invariant is stronger than the one it replaced — the spec carries
        no closing beat under ANY plan, rather than a closing beat built from
        whatever cta happened to be on file.
        """
        spec = overlays.build_spec_from_plan(PLAN)
        assert spec["end_card"] is None

    def test_a_stale_cta_column_is_never_composited(self):
        """
        The `cta` column survives in the schema for rows written before it
        stopped being generated, so `PLAN` above still carries one. It must not
        become an end card: a founder who has already recorded their own close
        would get a second, generated one burnt into the footage they paid for.
        """
        spec = overlays.build_spec_from_plan({"overlays": [], "cta": "Try it free"})
        assert spec["end_card"] is None
        assert "Try it free" not in str(spec)

    def test_the_signature_takes_only_a_plan(self):
        """
        `cta` and `duration` used to be parameters. They are gone rather than
        ignored, so a caller still passing them gets a loud TypeError instead of
        believing it is still compositing a close — which is what silently
        accepting them would have looked like.
        """
        import inspect
        params = inspect.signature(overlays.build_spec_from_plan).parameters
        assert list(params) == ["plan"]
        with pytest.raises(TypeError):
            overlays.build_spec_from_plan(PLAN, cta="Try it free", duration=12)

    def test_attachments_never_enter_the_spec(self):
        """
        Face-only product: the character reference rides to the video model
        as an input reference, never as an overlay — and retired uploads are
        refused upstream. The spec carries captions only, no matter what
        attachment rows still exist.
        """
        spec = overlays.build_spec_from_plan(PLAN)
        assert spec["images"] == []
        assert spec["videos"] == []
        assert spec["audios"] == []
        assert [c["text"] for c in spec["captions"]] == ["one prompt", "100% offline"]

    def test_caption_text_is_length_capped(self):
        long_plan = {"overlays": [{"start": 0, "end": 3, "text": "x" * 500}]}
        spec = overlays.build_spec_from_plan(long_plan)
        assert len(spec["captions"][0]["text"]) <= 60

    def test_blank_overlay_text_is_dropped(self):
        spec = overlays.build_spec_from_plan(
            {"overlays": [{"start": 0, "end": 3, "text": "   "}]})
        assert spec["captions"] == []

    def test_no_new_copy_is_invented(self):
        """
        Copy written at composition time never passed the claim check, so the
        spec may only carry text the reviewed plan already contained.

        Was also asserting the cta surfaced in the spec. That text no longer
        reaches composition at all, so the assertion moved to
        `test_a_stale_cta_column_is_never_composited`; what is left here is the
        one-directional property — verified plan copy appears, and the only
        other thing in the blob is the spec's own skeleton.
        """
        spec = overlays.build_spec_from_plan(
            {"overlays": [{"start": 0, "end": 3, "text": "verified line"}], "cta": "Verified CTA"})
        blob = str(spec)
        assert "verified line" in blob
        assert "Verified CTA" not in blob

    def test_missing_plan_is_safe(self):
        spec = overlays.build_spec_from_plan({})
        assert spec["captions"] == [] and spec["end_card"] is None


class TestFontResolution:
    def test_resolves_a_font_on_this_machine(self):
        assert overlays.resolve_font() is not None

    def test_env_override_is_preferred(self, monkeypatch):
        import os
        real = overlays.resolve_font()
        monkeypatch.setenv("OVERLAY_FONT", real)
        assert overlays.resolve_font() == real
        del os


class TestCanvasRescale:
    """
    The plain "Download MP4" path has no captions, so before this existed it
    served the provider's native size. Grok Imagine Video renders at 720p and
    the platform expects 1080x1920, so a founder who skipped captions was
    posting below spec.
    """

    def test_upscale_command_targets_the_canvas(self):
        argv = overlays.build_upscale_command(Path("in.mp4"), Path("out.mp4"))
        graph = argv[argv.index("-filter_complex") + 1]
        assert "scale=1080:1920" in graph
        assert "pad=1080:1920" in graph

    def test_upscale_command_chains_scale_into_pad(self):
        """
        Same dangling-output trap as the caption graph: pad must read scale's
        output, not the raw input, or the chain silently produces nothing.
        """
        argv = overlays.build_upscale_command(Path("in.mp4"), Path("out.mp4"))
        graph = argv[argv.index("-filter_complex") + 1]
        assert graph.count("[0:v]") == 1
        assert "[scaled_outv]pad=1080:1920" in graph

    def test_upscale_command_copies_audio_optionally(self):
        """
        The providers disagree about audio: Hailuo 3 returns a native track and
        Grok does not. A hard "0:a" reference fails on the silent one, so the
optional form is the only one that works for both.
        """
        argv = overlays.build_upscale_command(Path("in.mp4"), Path("out.mp4"))
        assert "0:a?" in argv
        # And never the mandatory form, which fails on a silent clip.
        assert "0:a" not in argv

    def test_missing_source_is_a_soft_failure(self, tmp_path):
        missing = tmp_path / "gone.mp4"
        path, warnings = overlays.rescale_to_canvas_sync(missing)
        assert path is None
        assert warnings and "missing" in warnings[0].lower()

    def test_a_failed_rescale_keeps_the_original_clip(self, tmp_path, monkeypatch):
        """
        A founder must never lose a generated video because the canvas resize
        failed. The original stays in place and the caller is told why.
        """
        source = tmp_path / "clip.mp4"
        source.write_bytes(b"not really a video")
        monkeypatch.setattr(overlays.subprocess, "run", lambda *a, **k: type(
            "P", (), {"returncode": 1, "stderr": "Invalid data found"}
        )())
        path, warnings = overlays.rescale_to_canvas_sync(source)
        assert path is None
        assert warnings
        assert source.is_file()

    def test_no_temp_file_is_left_behind(self, tmp_path, monkeypatch):
        source = tmp_path / "clip.mp4"
        source.write_bytes(b"not really a video")
        monkeypatch.setattr(overlays.subprocess, "run", lambda *a, **k: type(
            "P", (), {"returncode": 1, "stderr": "boom"}
        )())
        overlays.rescale_to_canvas_sync(source)
        leftovers = [p.name for p in tmp_path.iterdir() if p.name.startswith(".")]
        assert leftovers == []


class TestHookMiddleCut:
    """
    The hook-to-middle cut: a zoom-punch with a lateral reframe at the hook
    boundary, ramped over a quarter second and held for the rest of the piece.

    One render covers the whole piece, so there is no edit point to cut at --
    without this the video sits on one static angle throughout. Done in ffmpeg
    rather than the prompt for the same reason captions are: the model cannot
    be trusted with frame-exact timing, and it either drifts or ignores the
    instruction.
    """

    def test_no_transition_key_means_no_cut(self):
        graph, _, _ = overlays.build_filter_graph({}, 12, None)
        assert "concat=" not in graph
        assert "[cut]" not in graph

    def test_zero_or_invalid_boundary_means_no_cut(self):
        for at in (0, -1, "", None, "soon"):
            graph, _, _ = overlays.build_filter_graph({"transition": {"at": at}}, 12, None)
            assert "[cut]" not in graph, f"at={at!r} produced a cut"

    def test_boundary_too_close_to_either_end_means_no_cut(self):
        """A move with no room on one side would start before the first frame
        or finish past the last one, so it is skipped, not rendered half."""
        for at in (0.1, 0.3, 11.7, 11.9, 12.0, 99):
            graph, _, _ = overlays.build_filter_graph({"transition": {"at": at}}, 12, None)
            assert "[cut]" not in graph, f"at={at} produced a cut"

    def test_cut_splits_at_the_boundary_and_rejoins(self):
        graph, _, _ = overlays.build_filter_graph({"transition": {"at": 3.0}}, 12, None)
        assert "[bg0]split=2[pre0][post0]" in graph
        assert "[pre0]trim=end=3.000,setpts=PTS-STARTPTS[pre]" in graph
        assert "[post0]trim=start=3.000,setpts=PTS-STARTPTS" in graph
        assert "[pre][post]concat=n=2:v=1:a=0[cut]" in graph

    def test_ramp_is_relative_to_the_cut_not_the_file(self):
        """
        The post-boundary half is re-based with setpts, so its timestamps start
        at zero. A ramp written against the absolute boundary time would fire
        the move seconds into the middle instead of on its first frame -- the
        one silent misplacement this whole feature exists to avoid.
        """
        graph, _, _ = overlays.build_filter_graph({"transition": {"at": 3.0}}, 12, None)
        assert "min(max(t/0.25,0),1)" in graph
        assert "t-3.000" not in graph

    def test_scale_reevaluates_every_frame(self):
        """Without eval=frame, scale evaluates its expressions once and the
        quarter-second ramp never runs -- the graph renders fine and the cut
        silently never happens."""
        graph, _, _ = overlays.build_filter_graph({"transition": {"at": 3.0}}, 12, None)
        assert ":eval=frame" in graph

    def test_punch_in_magnitude_is_seventeen_percent(self):
        """The hook-to-middle zoom-punch magnitude. Pinned so a retune is a
        conscious change, not a drift: the graph must carry the same factor as
        overlays.TRANSITION_ZOOM."""
        assert overlays.TRANSITION_ZOOM == 0.17
        graph, _, _ = overlays.build_filter_graph({"transition": {"at": 3.0}}, 12, None)
        assert f"1+{overlays.TRANSITION_ZOOM}*" in graph

    def test_cut_feeds_the_layers_downstream(self):
        """The cut reframes the footage, not the captions: layers drawn after
        it stay put while the camera appears to move."""
        spec = {
            "transition": {"at": 3.0},
            "captions": [{"text": "hi", "start": 0, "end": 12}],
        }
        graph, _, _ = overlays.build_filter_graph(spec, 12, "C:/f.ttf")
        assert "[cut]drawtext=" in graph

    def test_plan_hook_seconds_become_the_cut(self):
        spec = overlays.build_spec_from_plan({"hook_seconds": 3, "overlays": []})
        assert spec["transition"] == {"at": 3.0}

    def test_missing_hook_seconds_means_no_cut(self):
        for plan in ({}, {"hook_seconds": 0}, {"hook_seconds": "soon"}):
            spec = overlays.build_spec_from_plan({**plan, "overlays": []})
            assert spec["transition"] is None


@needs_ffmpeg
class TestHookMiddleCutRender:
    """
    The graph above is only half the proof: expressions can parse and still do
    the wrong thing on real frames. Rendered against synthetic footage with
    audio, asserting the cut lands where it should and touches nothing else.
    """

    def _clip(self, path: Path, seconds: float = 4.0):
        subprocess.run(
            [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size=540x960:rate=30",
             "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
             str(path)],
            check=True,
        )

    def _render(self, source: Path, out: Path, spec: dict, duration: float):
        argv, _ = overlays.build_ffmpeg_command(source, out, spec, duration, None)
        proc = subprocess.run(argv, capture_output=True, text=True)
        assert proc.returncode == 0, (proc.stderr or "")[-500:]
        assert out.is_file()

    def _frame(self, video: Path, at: float, size: str = "160x284") -> bytes:
        out = video.with_name(f"{video.stem}_{at}.raw")
        subprocess.run(
            [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
             "-ss", str(at), "-i", str(video),
             "-frames:v", "1", "-s", size, "-pix_fmt", "rgb24",
             "-f", "rawvideo", str(out)],
            check=True,
        )
        return out.read_bytes()

    @staticmethod
    def _difference(first: bytes, second: bytes) -> float:
        return sum(a != b for a, b in zip(first, second)) / len(first)

    def _has_audio(self, path: Path) -> bool:
        proc = subprocess.run(
            [shutil.which("ffprobe"), "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=codec_name",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True,
        )
        return bool((proc.stdout or "").strip())

    def test_cut_moves_the_frame_and_nothing_else(self, tmp_path):
        """
        Frames well before the boundary are pixel-identical to the uncut
        render (the hook plays untouched); frames after the ramp differ
        strongly (the angle visibly changed); duration and audio survive.
        """
        source = tmp_path / "src.mp4"
        self._clip(source)
        plain = tmp_path / "plain.mp4"
        cut = tmp_path / "cut.mp4"
        self._render(source, plain, {}, 4.0)
        self._render(source, cut, {"transition": {"at": 2.0}}, 4.0)

        assert overlays.probe_duration(cut) == pytest.approx(4.0, abs=0.1)
        assert self._has_audio(cut)

        before = self._difference(self._frame(plain, 0.5), self._frame(cut, 0.5))
        assert before < 0.02, f"hook frames changed before the cut: {before:.1%}"
        after = self._difference(self._frame(plain, 3.0), self._frame(cut, 3.0))
        assert after > 0.25, f"middle frames did not move after the cut: {after:.1%}"
