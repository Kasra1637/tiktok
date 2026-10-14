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


class TestCameraCutStandalone:
    """
    The hook-to-middle cut as its own finalize pass, not just a composition
    layer. Raw previews and downloads never passed through the composition,
    so a cut that only lived there was invisible at any magnitude.
    """

    def test_command_carries_the_configured_zoom_and_a_relative_ramp(self):
        # Pinned: the cut magnitude is a product decision, and a drift here is
        # invisible on a phone screen until someone A/Bs two renders.
        assert overlays.TRANSITION_ZOOM == 0.17
        argv = overlays.build_camera_cut_command(Path("in.mp4"), Path("out.mp4"), 3.0, 12.0)
        graph = argv[argv.index("-filter_complex") + 1]
        assert f"1+{overlays.TRANSITION_ZOOM}*" in graph
        assert "min(max(t/0.25,0),1)" in graph
        assert ":eval=frame" in graph
        # Relative to the cut (post half is re-based), never the file clock.
        assert "t-3.000" not in graph
        assert "[pre][post]concat=n=2:v=1:a=0" in graph

    def test_missing_source_is_a_skip_not_a_failure(self, tmp_path):
        path, warnings = overlays.apply_camera_cut_sync(tmp_path / "gone.mp4", 3.0)
        assert path is None
        assert warnings

    def test_edge_and_invalid_boundaries_are_skipped(self, tmp_path, monkeypatch):
        clip = tmp_path / "clip.mp4"
        clip.write_bytes(b"not really a video")
        monkeypatch.setattr(overlays, "probe_duration", lambda _path: 12.0)
        monkeypatch.setattr(overlays, "probe_video_dims", lambda _path: (1080, 1920))
        for at in (0.1, 0.3, 11.7, 11.9, 12.0, 99, 0, -1, "", None, "soon"):
            path, warnings = overlays.apply_camera_cut_sync(clip, at)
            assert path is None, f"at={at!r} produced a cut"
            assert warnings == [], f"at={at!r} warned on a clean skip"
        assert clip.is_file()

    def test_undersized_clip_is_skipped(self, tmp_path, monkeypatch):
        clip = tmp_path / "clip.mp4"
        clip.write_bytes(b"not really a video")
        monkeypatch.setattr(overlays, "probe_duration", lambda _path: 12.0)
        monkeypatch.setattr(overlays, "probe_video_dims", lambda _path: (720, 1280))
        path, warnings = overlays.apply_camera_cut_sync(clip, 3.0)
        assert path is None
        assert warnings

    @needs_ffmpeg
    def test_cut_renders_and_preserves_duration(self, tmp_path):
        # Canvas-sized, as the finalize path guarantees: the canvas resize
        # runs before the cut, and the crop window is the canvas throughout.
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

        path, warnings = overlays.apply_camera_cut_sync(source, 2.0)
        assert warnings == []
        assert path == source
        assert abs(overlays.probe_duration(source) - 4.0) < 0.3
        assert source.stat().st_size > 0
        # The reframe must actually move pixels after the boundary: a file
        # whose post-cut frames match the source would prove the cut silently
        # never ran, at any magnitude. Frames well before the boundary stay
        # effectively untouched — the hook plays as rendered. Compared by mean
        # absolute pixel difference, not byte identity: the halves are
        # re-encoded, so identical bytes are not the contract. Measured 0.10
        # pre-cut (encode noise) against 90.63 post-cut (reframe) on testsrc;
        # the margins below are wide on both sides.
        def mean_abs_diff(first: bytes, second: bytes) -> float:
            return sum(abs(a - b) for a, b in zip(first, second)) / len(first)

        assert frame(source, 3.0) != frame(before, 3.0)
        assert mean_abs_diff(frame(source, 3.0), frame(before, 3.0)) > 20
        pre_cut = mean_abs_diff(frame(source, 0.5), frame(before, 0.5))
        assert pre_cut < 2.0, f"hook frames changed before the cut: {pre_cut:.2f}"
