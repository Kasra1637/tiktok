"""
Tests for the canvas and camera-cut utilities.

The caption/image/audio composition machinery is gone with burned-in
captions, so what remains is the canvas fit, the canvas rescale, and the
hook-to-middle cut that finalize bakes into every finished render.
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


class TestCanvasRescale:
    """
    Every clip ships at the canvas size. Providers render below it (Grok
    Imagine Video at 720p) and the platform expects 1080x1920, so the
    finalize pass rescales before the camera cut and the upload.
    """

    def test_upscale_command_targets_the_canvas(self):
        argv = overlays.build_upscale_command(Path("in.mp4"), Path("out.mp4"))
        graph = argv[argv.index("-filter_complex") + 1]
        assert "scale=1080:1920" in graph
        assert "pad=1080:1920" in graph

    def test_upscale_command_uses_lanczos(self):
        """
        Pinned: most studio renders arrive below the canvas and are scaled up
        (Grok at 720p, H3 Max and HeyGen at 768p), and a bilinear up-scale is
        visibly mushier than lanczos. A silent regression to the default scaler
        is invisible in the output metadata -- the frame size is identical -- so
        it has to be asserted here.
        """
        argv = overlays.build_upscale_command(Path("in.mp4"), Path("out.mp4"))
        graph = argv[argv.index("-filter_complex") + 1]
        assert "flags=lanczos" in graph

    def test_upscale_command_chains_scale_into_pad(self):
        """
        Pad must read scale's output, not the raw input, or the chain silently
        produces nothing.
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


class TestCameraMoveStandalone:
    """
    The hook-boundary camera move as its own finalize pass, not just a
    composition layer. Raw previews and downloads never passed through the
    composition, so a move that only lived there was invisible at any magnitude.
    """

    def test_command_carries_the_configured_magnification_and_a_relative_ramp(self):
        # Pinned: the move's size is a product decision, and a drift here is
        # invisible on a phone screen until someone A/Bs two renders.
        assert overlays.TRANSITION_ZOOM == 0.07
        assert overlays.TRANSITION_ARC == 0.09
        # The arc is paid for in magnification: sliding the crop window by ARC
        # needs half the width-slack on the chosen side, which is (M-1)/2.
        # This is the assertion that catches a zoom traded down without the arc
        # being re-derived, which silently halves the move instead of failing.
        assert overlays.TRANSITION_MAGNIFICATION == pytest.approx(1.25)
        argv = overlays.build_camera_move_command(
            Path("in.mp4"), Path("out.mp4"), 2.1, 12.0,
        )
        graph = argv[argv.index("-filter_complex") + 1]
        assert f"(1+{overlays.TRANSITION_MAGNIFICATION - 1:.4f}*" in graph
        assert f"min(max(t/{overlays.TRANSITION_RAMP_SECONDS},0),1)" in graph
        # Smoothstep, not a linear slide: a move that starts and stops at full
        # speed is what reads as an effect applied afterwards.
        assert ")*(3-2*(" in graph
        assert ":eval=frame" in graph
        # Relative to the cut (post half is re-based), never the file clock.
        assert "t-2.100" not in graph
        assert "[pre][post]concat=n=2:v=1:a=0" in graph

    def test_the_move_is_snappy_but_leaves_room_on_both_sides(self):
        """
        Pinned as a pair: a move long enough to read as a gesture, and an edge
        margin that is at least as long as it. A margin thinner than the ramp is
        a boundary the move cannot complete without rendering half of itself.
        """
        assert 0.5 <= overlays.TRANSITION_RAMP_SECONDS <= 0.8
        assert overlays.TRANSITION_EDGE_MARGIN >= overlays.TRANSITION_RAMP_SECONDS

    def test_the_arc_travels_a_ninth_of_the_frame_and_symmetrically(self):
        """
        The reason this is a measurement and not a constant read off the module:
        the move used to slide 27 pixels, which is 2.5% of a 1080 frame and
        invisible on a phone -- a piece built around this transition read as "it
        only zooms". Both directions must travel the same distance, or half the
        generations lean further than the other half.
        """
        for direction in (1, -1):
            centred_x, _ = overlays.crop_target(0.5, 0.5, direction)
            # Where her face lands, as a fraction of frame width, and how far it
            # moved from dead centre.
            landed = overlays.TRANSITION_MAGNIFICATION * 0.5 - centred_x / overlays.CANVAS_WIDTH
            assert landed == pytest.approx(0.5 + direction * overlays.TRANSITION_ARC, abs=1e-3)

    def test_her_face_rests_just_above_centre_with_its_head_at_the_top_edge(self):
        """
        The lean-in, measured where it matters: magnification grows AROUND HER
        face, so it comes to rest above the horizontal centre line rather than
        the frame's own middle. Vertical centring is what makes a zoom read as a
        crop, and it is also what leaves her whole head floating in the middle of
        the picture instead of close to the lens.

        Measured across the face heights a talking head actually arrives at; the
        clamp that handles the rest is covered by the unreachable-face test.
        """
        for face_y in (0.4, 0.5, 0.55):
            _, crop_y = overlays.crop_target(0.5, face_y, 1)
            landed = (
                overlays.TRANSITION_MAGNIFICATION * face_y
                - crop_y / overlays.CANVAS_HEIGHT
            )
            assert landed == pytest.approx(overlays.TRANSITION_FACE_REST_Y, abs=1e-6)
        assert overlays.TRANSITION_FACE_REST_Y < 0.5

    def test_the_anchor_follows_her_face_not_the_frame_middle(self):
        """
        Pinned because nothing else can see it: the crop offset is a solved
        number, so moving her within the frame has to move it, or every render is
        re-framed around a fixed point regardless of where the model put her.
        """
        left, left_y = overlays.crop_target(0.3, 0.4, 1)
        middle, middle_y = overlays.crop_target(0.5, 0.4, 1)
        right, _ = overlays.crop_target(0.7, 0.4, 1)
        assert left < middle < right
        # And vertically, independently: a face low in frame needs a different
        # window than the same face high in frame.
        _, high = overlays.crop_target(0.5, 0.25, 1)
        _, low = overlays.crop_target(0.5, 0.55, 1)
        assert high < middle_y < low

    def test_an_unreachable_face_cannot_push_the_window_off_its_own_frame(self):
        """
        A subject already hard against an edge must not produce a crop offset
        outside the magnified frame. ffmpeg clamps, but only after the ramp has
        been following a target it cannot reach -- which shows as the move
        sticking to the edge and then catching up.
        """
        slack_x = (overlays.TRANSITION_MAGNIFICATION - 1) * overlays.CANVAS_WIDTH
        slack_y = (overlays.TRANSITION_MAGNIFICATION - 1) * overlays.CANVAS_HEIGHT
        for face_x in (0.0, 0.05, 0.5, 0.95, 1.0):
            for face_y in (0.0, 0.5, 1.0):
                x, y = overlays.crop_target(face_x, face_y, 1)
                assert 0.0 <= x <= slack_x
                assert 0.0 <= y <= slack_y

    def test_direction_is_stable_per_generation_and_varies_across_them(self):
        """
        Reproducible, so a re-run of one generation frames identically, and
        varied, so a founder's feed does not lean the same way every time --
        which is what made the arc read as a template rather than a shot.
        """
        seen = {overlays.move_direction_for(f"gen-{n}") for n in range(50)}
        assert seen == {1, -1}
        for name in ("gen-1", "gen-2", "a-real-uuid-like-id"):
            assert overlays.move_direction_for(name) == overlays.move_direction_for(name)
        # A missing id must still produce a usable direction, not crash a render.
        assert overlays.move_direction_for("") in (1, -1)
        assert overlays.move_direction_for(None) in (1, -1)

    def test_missing_source_is_a_skip_not_a_failure(self, tmp_path):
        path, warnings = overlays.apply_camera_move_sync(tmp_path / "gone.mp4", 2.1)
        assert path is None
        assert warnings

    def test_edge_and_invalid_boundaries_are_skipped(self, tmp_path, monkeypatch):
        clip = tmp_path / "clip.mp4"
        clip.write_bytes(b"not really a video")
        monkeypatch.setattr(overlays, "probe_duration", lambda _path: 12.0)
        monkeypatch.setattr(overlays, "probe_video_dims", lambda _path: (1080, 1920))
        monkeypatch.setattr(overlays, "detect_face_center", lambda *a, **k: None)
        for at in (0.1, 0.6, 11.4, 11.9, 12.0, 99, 0, -1, "", None, "soon"):
            path, warnings = overlays.apply_camera_move_sync(clip, at)
            assert path is None, f"at={at!r} produced a move"
            assert warnings == [], f"at={at!r} warned on a clean skip"
        assert clip.is_file()

    def test_undersized_clip_is_skipped(self, tmp_path, monkeypatch):
        clip = tmp_path / "clip.mp4"
        clip.write_bytes(b"not really a video")
        monkeypatch.setattr(overlays, "probe_duration", lambda _path: 12.0)
        monkeypatch.setattr(overlays, "probe_video_dims", lambda _path: (720, 1280))
        path, warnings = overlays.apply_camera_move_sync(clip, 2.1)
        assert path is None
        assert warnings

    def test_a_clip_with_no_detectable_face_is_still_moved(self, tmp_path, monkeypatch):
        """
        The face pivot is an improvement, not a precondition. A clip the detector
        cannot find a face in must still get the move, framed on the frame's own
        centre, or a failed detection would silently drop the transition.
        """
        clip = tmp_path / "clip.mp4"
        clip.write_bytes(b"not really a video")
        monkeypatch.setattr(overlays, "probe_duration", lambda _path: 12.0)
        monkeypatch.setattr(overlays, "probe_video_dims", lambda _path: (1080, 1920))
        monkeypatch.setattr(overlays, "detect_face_center", lambda *a, **k: None)
        captured = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            return type("P", (), {"returncode": 1, "stderr": "boom"})()

        monkeypatch.setattr(overlays.subprocess, "run", fake_run)
        path, warnings = overlays.apply_camera_move_sync(clip, 2.1)
        # ffmpeg failed here, but the argv proves the move was still attempted,
        # centred rather than skipped.
        graph = captured["argv"][captured["argv"].index("-filter_complex") + 1]
        centre_x, _ = overlays.crop_target(0.5, 0.5, 1)
        assert f":x='{centre_x}*" in graph
        assert path is None and warnings

    @needs_ffmpeg
    def test_move_renders_and_preserves_duration(self, tmp_path, monkeypatch):
        # Canvas-sized, as the finalize path guarantees: the canvas resize
        # runs before the move, and the crop window is the canvas throughout.
        # No face in testsrc, so this exercises the centre fallback against real
        # ffmpeg rather than a stubbed pivot.
        monkeypatch.setattr(overlays, "detect_face_center", lambda *a, **k: None)
        source = tmp_path / "src.mp4"
        subprocess.run(
            [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "testsrc=duration=4:size=1080x1920:rate=30",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
             str(source)],
            check=True,
        )
        before = tmp_path / "before.mp4"
        before.write_bytes(source.read_bytes())

        def frame(path, at):
            proc = subprocess.run(
                [FFMPEG, "-hide_banner", "-loglevel", "error",
                 "-ss", str(at), "-i", str(path),
                 "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                capture_output=True, check=True,
            )
            return proc.stdout

        path, warnings = overlays.apply_camera_move_sync(source, 2.0)
        assert warnings == []
        assert path == source
        assert abs(overlays.probe_duration(source) - 4.0) < 0.3
        assert source.stat().st_size > 0
        # The reframe must actually move pixels after the boundary: a file
        # whose post-move frames match the source would prove the move silently
        # never ran, at any magnitude. Frames well before the boundary stay
        # effectively untouched -- the hook plays as rendered. Compared by mean
        # absolute pixel difference, not byte identity: the halves are
        # re-encoded, so identical bytes are not the contract. Measured 0.10
        # pre-move (encode noise) against 90.63 post-move (reframe) on testsrc;
        # the margins below are wide on both sides.
        def mean_abs_diff(first: bytes, second: bytes) -> float:
            return sum(abs(a - b) for a, b in zip(first, second)) / len(first)

        assert frame(source, 3.0) != frame(before, 3.0)
        assert mean_abs_diff(frame(source, 3.0), frame(before, 3.0)) > 20
        pre_move = mean_abs_diff(frame(source, 0.5), frame(before, 0.5))
        assert pre_move < 2.0, f"hook frames changed before the move: {pre_move:.2f}"


class TestCameraBeat:
    """
    The second the move lands on, shared by the prompt and the reframe.

    There is no per-phrase speech timing in this system and no usable audio to
    find one in, so the beat is committed to in advance. That commitment is
    only worth anything if both readers get the same number, which is what
    these pin.
    """

    def test_it_lands_inside_the_hook_and_scales_with_it(self):
        for hook in (2, 3, 4):
            at = overlays.camera_beat_seconds(hook)
            assert 0 < at <= hook
            assert at == pytest.approx(overlays.CAMERA_BEAT_FRACTION * hook)

    def test_a_strategy_with_no_beat_gets_the_same_number(self):
        # The omitted case the strategy prompt can produce, and the case an
        # older saved project always is.
        for strategy in (None, {}, {"camera_beat": {}}, {"camera_beat": None}):
            assert overlays.camera_beat_seconds(3, strategy) == pytest.approx(2.1)

    def test_a_beat_outside_the_hook_is_pulled_back_into_it(self):
        # A model that invented "at 99" costs the beat, not the render, and a
        # stale value from an edited project cannot move the reframe past the
        # hook it is supposed to land in.
        assert overlays.camera_beat_seconds(3, {"camera_beat": {"at": 99}}) == pytest.approx(2.1)
        assert overlays.camera_beat_seconds(3, {"camera_beat": {"at": -4}}) == pytest.approx(2.1)
        assert overlays.camera_beat_seconds(3, {"camera_beat": {"at": "soon"}}) == pytest.approx(2.1)

    def test_a_stored_beat_is_the_one_used_when_it_is_sane(self):
        assert overlays.camera_beat_seconds(4, {"camera_beat": {"at": 1.4}}) == pytest.approx(1.4)

    def test_it_always_leaves_the_move_room_to_run(self):
        # The move is skipped when the boundary has no room, so the beat the
        # strategy stamps must always clear the margin for every legal hook.
        for hook in (2, 3, 4):
            assert overlays.camera_beat_seconds(hook) > overlays.TRANSITION_EDGE_MARGIN
