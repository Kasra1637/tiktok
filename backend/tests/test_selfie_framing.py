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


def test_angle_promise_strips_a_phone_in_one_hand():
    # The selected angle's FIRST 3 SECONDS PROMISE said "with a phone in one
    # hand", and the template Shape printed it verbatim. In a handheld selfie
    # the phone IS the camera, so no second phone can be held — the strategy
    # stripped it downstream, but the card the founder clicked promised it.
    # The promise is setup-blind, so it must never name a phone in hand, the
    # same way screen clauses are owned at storage time.
    import angle_scene
    from angle_policy import normalize_content_angles
    angle = {"hook_promise": "The person leans against porch railing with a phone in one hand"}
    shape = angle_scene.opening_shape(angle, {"opening_structure": "Ignored."})
    assert "phone" not in shape.lower(), shape
    assert "leans against porch railing" in shape.lower(), shape
    angles = normalize_content_angles(
        [{
            "kind": "problem_solution", "target_audience": "a", "user_problem": "p",
            "hook_promise": "The person leans against porch railing with a phone in one hand",
            "app_feature": "f",
        }],
        6, {"core_features": ["f"]},
    )
    assert "phone" not in angles[0]["hook_promise"].lower(), angles[0]["hook_promise"]
    assert "leans against porch railing" in angles[0]["hook_promise"].lower()


def test_serialized_angle_row_strips_a_phone_in_one_hand():
    # Rows stored before the promise strip still name the device; the
    # serialized row is the picker's view, so the phone phrase is stripped
    # here too — the same read-time repair the screen clause already gets.
    from routers.brands import _serialize_angle_row
    out = _serialize_angle_row({
        "id": "a1", "kind": "problem_solution",
        "hook_promise": "The person leans against porch railing with a phone in one hand",
    })
    assert "phone" not in out["hook_promise"].lower(), out["hook_promise"]
    assert "leans against porch railing" in out["hook_promise"].lower()


def test_template_development_strips_the_phone_held_ending():
    # Template cards said "... then ends as the phone is held", promising the
    # old fixed-camera handoff. Handheld ends on a physical beat with no
    # phone, so the displayed development must not end on a held phone.
    import angle_scene
    angle = {"hook_promise": "The person leans against porch railing"}
    template = {
        "middle_structure": (
            "Then the person describes waking with racing thoughts and the overwhelm "
            "of complex journal apps that add typing friction, then ends as the phone "
            "is held"
        ),
    }
    development = angle_scene.opening_development(angle, template)
    assert "phone" not in development.lower(), development
    assert "describes waking" in development.lower(), development


def test_bare_steady_becomes_subtle_sway_for_handheld():
    # "Straight-on and steady" and "steady selfie shot" survived the handheld
    # rewrites (only "steady camera/shot" was caught), contradicting the
    # required subtle sway. A handheld strategy must not say "steady".
    import scene_consistency
    strategy = {
        "camera_setup": "handheld",
        "scene": {
            "camera_angle": "Eye-level handheld selfie at arm's length, straight-on and steady",
            "framing": "Mid-chest up with full head and headroom, room for hand gestures",
            "visual_style": "Natural amateur handheld camera footage with a calm look",
        },
    }
    scene_consistency.camera_setup_wording(strategy)
    blob = " ".join(strategy["scene"].values()).lower()
    assert "steady" not in blob, strategy["scene"]
    assert "sway" in blob, strategy["scene"]
    strategy2 = {
        "camera_setup": "handheld",
        "scene": {"camera_angle": "steady selfie shot, eye level"},
    }
    scene_consistency.camera_setup_wording(strategy2)
    assert "steady" not in strategy2["scene"]["camera_angle"].lower(), strategy2["scene"]


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
