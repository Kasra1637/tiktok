import pytest

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
