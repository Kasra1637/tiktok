import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import generation_planning
import video_providers


@pytest.mark.parametrize("camera_setup", ["handheld", "fixed"])
def test_handheld_selfie_framing_has_no_orbit(camera_setup):
    strategy = {"camera_setup": camera_setup, "camera_beat": {"direction": "right"}}
    section = generation_planning.camera_move_section(strategy)
    if camera_setup == "handheld":
        assert "orbit" not in section.lower()
        assert "straight-on" in section.lower()
    else:
        assert "no sway, orbit" in section.lower()


def test_handheld_selfie_camera_wording_matches_starting_shot():
    starting = generation_planning.starting_shot("handheld")
    assert "straight-on" in starting.lower()
    assert "no 3/4 angle" in starting.lower() or "no orbit" in starting.lower()
    strategy = {"camera_setup": "handheld", "camera_beat": {"direction": "right"}}
    assert "orbit" not in generation_planning.camera_move_section(strategy).lower()


def test_every_studio_model_has_resolved_identity_routing():
    for model in video_providers.STUDIO_ELIGIBLE:
        cap = video_providers.capability(model)
        assert "identity_via_first_frame" in cap or "max_reference_images" in cap, model


def test_heygen_photo_is_first_frame_pinned():
    cap = video_providers.capability("heygen-video-1")
    assert cap.get("identity_via_first_frame") is True
    assert video_providers.accepts_identity_reference("heygen-video-1") is True


def test_handheld_framing_forbids_cropping_the_head():
    # Renders came back with the forehead or chin cut off: "upper chest up"
    # is a close-up, and the 1.10x processing zoom crops 4.5% per edge on top
    # of it. The starting shot must ask wider than chest-up and forbid the
    # crop by name, not merely ask for "headroom".
    framing = generation_planning.HANDHELD_SELFIE_FRAMING
    assert "upper chest up" not in framing.lower()
    assert "never crop" in framing.lower()
    assert "forehead" in framing.lower()
    assert "chin" in framing.lower()


def test_handheld_camera_move_holds_distance_without_tightening():
    # "Keep the full head and chin visible" states a result with no margin,
    # so a tight opening that technically shows the chin still passes. The
    # hold must forbid tightening/cropping, in both budget modes.
    strategy = {"camera_setup": "handheld", "camera_beat": {"direction": "right"}}
    for condensed in (False, True):
        section = generation_planning.camera_move_section(strategy, condensed=condensed)
        lowered = section.lower()
        assert "never" in lowered and ("crop" in lowered or "tighten" in lowered), (
            f"condensed={condensed}: {section!r}"
        )


def test_face_reference_is_wider_than_a_tight_headshot():
    # The identity reference hands the model a headshot where the face is
    # ~42% of the frame height; on first-frame models that crop IS the
    # opening frame, so the video starts too close and stays there. The
    # reference must leave the head clearly smaller in frame.
    import face_crop
    from PIL import Image
    img = Image.new("RGB", (1080, 1920), (20, 90, 160))
    bbox = (390, 500, 300, 400, 0.99)
    cropped = face_crop._crop_face_region(img, bbox)
    crop_w, crop_h = cropped.size
    assert 400 / crop_h < 0.35, (
        f"face is {400 / crop_h:.0%} of the reference height "
        f"({crop_w}x{crop_h}); too tight to open a video on"
    )
    assert 300 / crop_w < 0.40, (
        f"face is {300 / crop_w:.0%} of the reference width "
        f"({crop_w}x{crop_h}); too tight to open a video on"
    )


def test_face_reference_expands_to_vertical_9_16():
    # The crop's native aspect (~0.69) is wider than the 9:16 render (0.56),
    # so the provider center-crops 18%+ of its width to fit — cutting ears
    # and hair off an already tight headshot. The reference must arrive
    # already vertical, so no provider-side crop bites into the head.
    import face_crop
    from PIL import Image
    img = Image.new("RGB", (1080, 1920), (20, 90, 160))
    cropped = face_crop._crop_face_region(img, (390, 500, 300, 400, 0.99))
    crop_w, crop_h = cropped.size
    assert abs(crop_w / crop_h - 9 / 16) < 0.05, (
        f"reference is {crop_w}x{crop_h} (aspect {crop_w / crop_h:.2f}), "
        "not vertical 9:16; the provider will center-crop it tighter"
    )


def test_headshot_reference_pads_to_vertical_instead_of_staying_tight():
    # The face-dominates branch returns a tight upload (possibly square) as
    # the reference; as a first frame that is a close-up with no headroom.
    # It must be padded out to vertical with margin around the head.
    import tempfile
    from pathlib import Path
    import face_crop
    from PIL import Image
    img = Image.new("RGB", (600, 600), (20, 90, 160))
    bbox = (120, 100, 360, 420, 0.99)
    assert (bbox[2] * bbox[3]) / (600 * 600) * 100 > 40
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "headshot.png"
        img.save(path)
        orig_detect = face_crop._detect_face
        face_crop._detect_face = lambda a: bbox
        try:
            out_path = face_crop.crop_face_from_path(path)
        finally:
            face_crop._detect_face = orig_detect
        assert out_path != path, "the tight upload was returned untouched"
        with Image.open(out_path) as opened:
            opened.load()
            out_w, out_h = opened.size
    assert abs(out_w / out_h - 9 / 16) < 0.05, (
        f"headshot reference is {out_w}x{out_h} (aspect {out_w / out_h:.2f}), "
        "not vertical 9:16; a square close-up opens the video too close"
    )
