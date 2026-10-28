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
        # Total magnification is the setting, never 1 + an arc allowance.
        assert overlays.TRANSITION_MAGNIFICATION == 1.10
        assert not hasattr(overlays, "TRANSITION_ARC")
        argv = overlays.build_camera_move_command(
            Path("in.mp4"), Path("out.mp4"), 2.1, 12.0,
        )
        graph = argv[argv.index("-filter_complex") + 1]
        assert "(1+(1.1-1)*" in graph
        assert f"min(max(T/{overlays.TRANSITION_RAMP_SECONDS},0),1)" in graph
        # Smoothstep, not a linear slide: a move that starts and stops at full
        # speed is what reads as an effect applied afterwards.
        assert ")*(3-2*(" in graph
        assert graph.count("geq=") == 1
        assert "scale=" not in graph and "crop=" not in graph
        assert "(X-W/2)/" in graph and "+W/2" in graph
        assert "(Y-H/2)/" in graph and "+H/2" in graph
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

    @pytest.mark.parametrize("magnification", [1.08, 1.10, 1.12])
    def test_total_magnification_has_no_sideways_allowance(self, magnification):
        argv = overlays.build_camera_move_command(
            Path("in.mp4"), Path("out.mp4"), 2.1, 12.0, magnification,
        )
        graph = argv[argv.index("-filter_complex") + 1]
        assert f"(1+({magnification!r}-1)*" in graph
        assert graph.count("geq=") == 1
        assert "scale=" not in graph and "crop=" not in graph
        assert "(X-W/2)/" in graph and "+W/2" in graph
        assert "(Y-H/2)/" in graph and "+H/2" in graph

    @pytest.mark.parametrize("magnification", [0.07, 1.0, 1.079, 1.121, 1.25])
    def test_out_of_range_total_magnification_is_refused(self, magnification):
        with pytest.raises(ValueError, match="1.08 to 1.12"):
            overlays.build_camera_move_command(
                Path("in.mp4"), Path("out.mp4"), 2.1, 12.0, magnification,
            )

    def test_missing_source_is_a_skip_not_a_failure(self, tmp_path):
        path, warnings = overlays.apply_camera_move_sync(tmp_path / "gone.mp4", 2.1)
        assert path is None
        assert warnings

    def test_edge_and_invalid_boundaries_are_skipped(self, tmp_path, monkeypatch):
        clip = tmp_path / "clip.mp4"
        clip.write_bytes(b"not really a video")
        monkeypatch.setattr(overlays, "probe_duration", lambda _path: 12.0)
        monkeypatch.setattr(overlays, "probe_video_dims", lambda _path: (1080, 1920))
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

    def test_centered_zoom_needs_no_face_detection(self, tmp_path, monkeypatch):
        """
        The centered zoom no longer needs a face detector or direction input.
        A processing failure must preserve the original and report a warning.
        """
        clip = tmp_path / "clip.mp4"
        clip.write_bytes(b"not really a video")
        monkeypatch.setattr(overlays, "probe_duration", lambda _path: 12.0)
        monkeypatch.setattr(overlays, "probe_video_dims", lambda _path: (1080, 1920))
        captured = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            return type("P", (), {"returncode": 1, "stderr": "boom"})()

        monkeypatch.setattr(overlays.subprocess, "run", fake_run)
        path, warnings = overlays.apply_camera_move_sync(clip, 2.1)
        # ffmpeg failed here, but the argv proves the move was still attempted,
        # centred rather than skipped.
        graph = captured["argv"][captured["argv"].index("-filter_complex") + 1]
        assert "(X-W/2)/" in graph and "(Y-H/2)/" in graph
        assert path is None and warnings

    @needs_ffmpeg
    def test_zoom_pixels_are_centered_exact_eased_and_held(self, tmp_path):
        import numpy as np

        source = tmp_path / "grid.mp4"
        subprocess.run([
            FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=black:s=1080x1920:r=30:d=4",
            "-vf", "drawgrid=w=120:h=120:t=4:c=white",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
        ], check=True)
        at = overlays.camera_beat_seconds(3)
        path, warnings = overlays.apply_camera_move_sync(source, at)
        assert path == source and not warnings
        assert overlays.probe_video_dims(source) == (1080, 1920)
        assert overlays.probe_duration(source) == pytest.approx(4, abs=0.04)
        for frame_number in (60, 63, 66, 69, 72, 75, 78, 81, 90, 119):
            result = subprocess.run([
                FFMPEG, "-hide_banner", "-loglevel", "error",
                "-i", str(source), "-vf", f"select=eq(n\\,{frame_number})",
                "-frames:v", "1", "-pix_fmt", "gray", "-f", "rawvideo", "-",
            ], capture_output=True, check=True)
            frame = np.frombuffer(result.stdout, dtype=np.uint8).reshape(1920, 1080)
            progress = min(max((frame_number / 30 - at) / 0.6, 0), 1)
            magnification = 1 + 0.10 * progress ** 2 * (3 - 2 * progress)
            # Measure both axes against a static grid, not implementation text.
            # Each source grid line is 4px wide, centred at 1.5 + k*120.
            for extent, profile in (
                (1080, frame[400:500].mean(axis=0)),
                (1920, frame[:, 400:500].mean(axis=1)),
            ):
                indices = np.flatnonzero(profile > 150)
                groups = np.split(indices, np.flatnonzero(np.diff(indices) > 1) + 1)
                actual = np.array([group.mean() for group in groups if len(group)])
                expected = np.array([
                    extent / 2 + magnification * (1.5 + k * 120 - extent / 2)
                    for k in range(extent // 120)
                ])
                expected = expected[(expected >= 4) & (expected < extent - 4)]
                for position in expected:
                    assert min(abs(actual - position)) < 1.6, (
                        f"frame {frame_number}, extent {extent}: expected centred line at "
                        f"{position:.2f}, got {actual.tolist()}"
                    )
                assert np.median(np.diff(actual)) / 120 == pytest.approx(
                    magnification, abs=0.006,
                )

    @needs_ffmpeg
    def test_move_renders_and_preserves_duration(self, tmp_path, monkeypatch):
        # Canvas-sized, as the finalize path guarantees: the canvas resize
        # runs before the move, and the crop window is the canvas throughout.
        # Exercise the centered zoom through the real processing entry point.
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
    Processing starts zoom at 70% of hook duration and ends 0.6s later.
    Generated orbit/gesture timing is qualitative, not spoken-word synced.
    """

    def test_zoom_starts_at_seventy_percent_of_the_hook(self):
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
        # Legacy timestamps never affect the processing ratio.
        assert overlays.camera_beat_seconds(3, {"camera_beat": {"at": 99}}) == pytest.approx(2.1)
        assert overlays.camera_beat_seconds(3, {"camera_beat": {"at": -4}}) == pytest.approx(2.1)
        assert overlays.camera_beat_seconds(3, {"camera_beat": {"at": "soon"}}) == pytest.approx(2.1)

    def test_a_legacy_stored_timestamp_never_overrides_the_ratio(self):
        assert overlays.camera_beat_seconds(4, {"camera_beat": {"at": 1.4}}) == pytest.approx(2.8)

    def test_it_always_leaves_the_move_room_to_run(self):
        # The move is skipped when the boundary has no room, so the beat the
        # processing computes must always clear the margin for every legal hook.
        for hook in (2, 3, 4):
            assert overlays.camera_beat_seconds(hook) > overlays.TRANSITION_EDGE_MARGIN
