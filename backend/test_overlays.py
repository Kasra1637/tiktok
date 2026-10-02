"""
Tests for deterministic overlay composition.

build_filter_graph is pure, so the geometry is asserted without rendering.
The escaping rules are the highest-risk part: they were wrong twice during
development (Windows drive-letter colons, and drawtext's deeper % parsing),
and both failures were silent or opaque. These tests pin the behaviour.
"""
from pathlib import Path

import pytest

import overlays


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
        """
        graph, _, _ = overlays.build_filter_graph({}, 12, None)
        assert "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[scaled]" in graph
        assert "[scaled]pad=1080:1920" in graph
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
