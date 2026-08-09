"""No-network contract tests for target-performance-preserving face swaps."""
import asyncio
from pathlib import Path

import ai_service


def _capture_generation(monkeypatch):
    """Replace image/file/network helpers and return captured provider arguments."""
    captured = {"encoded_paths": [], "cropped_paths": []}

    def fake_image_to_base64(path: Path) -> str:
        captured["encoded_paths"].append(path)
        return f"encoded-{path.name}"

    def fake_crop_face_from_path(path: Path) -> Path:
        captured["cropped_paths"].append(path)
        return path.with_name(f"{path.stem}-cropped{path.suffix}")

    async def fake_generate(payload, context, max_retries, timeout):
        captured.update(
            payload=payload,
            context=context,
            max_retries=max_retries,
            timeout=timeout,
        )
        return b"generated-image"

    monkeypatch.setattr(ai_service, "image_to_base64", fake_image_to_base64)
    monkeypatch.setattr(ai_service, "crop_face_from_path", fake_crop_face_from_path)
    monkeypatch.setattr(ai_service, "_call_image_generation_with_retry", fake_generate)
    return captured


def _assert_payload_contract(captured, target_path: Path, source_path: Path, context: str):
    cropped_source_path = source_path.with_name(f"{source_path.stem}-cropped{source_path.suffix}")
    payload = captured["payload"]
    prompt = payload["prompt"]

    assert captured["cropped_paths"] == [source_path]
    assert captured["encoded_paths"] == [target_path, cropped_source_path]
    assert captured["context"] == context
    assert captured["max_retries"] == 1
    assert captured["timeout"] == 600

    assert payload["model"] == ai_service.FACE_SWAP_MODEL
    assert payload["resolution"] == "2K"
    assert payload["aspect_ratio"] == "9:16"
    assert payload["n"] == 1
    assert payload["input_references"] == [
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,encoded-{target_path.name}"},
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,encoded-{cropped_source_path.name}"},
        },
    ]

    assert "IMAGE 1 IS THE IMMUTABLE TARGET SCENE AND FACIAL-PERFORMANCE REFERENCE" in prompt
    assert "facial expression and facial-muscle configuration" in prompt
    assert "gaze and iris/pupil direction" in prompt
    assert "eye opening or closure" in prompt
    assert "upper- and lower-eyelid aperture and placement" in prompt
    assert "blink or wink state" in prompt
    assert "mouth and lip pose" in prompt
    assert "jaw opening" in prompt
    assert "full intensity of the reaction or emotion" in prompt
    assert "mandatory and override every other instruction" in prompt
    assert "IMAGE 2 supplies identity only" in prompt
    assert "Do NOT transfer from the second image its facial expression" in prompt
    assert "Customization must never override the FIRST image's facial expression" in prompt


def test_generate_face_swap_preserves_target_performance_in_provider_payload(monkeypatch):
    captured = _capture_generation(monkeypatch)
    target_path = Path("target-frame.jpg")
    source_path = Path("source-person.png")

    result = asyncio.run(
        ai_service.generate_face_swap(
            target_image_path=target_path,
            source_face_path=source_path,
            session_id="session-1",
            customization_prompt="  change the jacket to red  ",
        )
    )

    assert result == b"generated-image"
    _assert_payload_contract(captured, target_path, source_path, "Face swap")
    prompt = captured["payload"]["prompt"]
    assert "CUSTOMIZATION: Apply this request only to the scene, clothing, environment, or visual style: change the jacket to red." in prompt
    assert prompt.index("mandatory and override every other instruction") < prompt.index("CUSTOMIZATION:")


def test_generate_customized_preview_preserves_target_performance_in_provider_payload(monkeypatch):
    captured = _capture_generation(monkeypatch)
    target_path = Path("hook-frame.jpg")
    source_path = Path("uploaded-person.png")

    result = asyncio.run(
        ai_service.generate_customized_preview(
            reference_frame_path=target_path,
            person_photo_path=source_path,
            mode="custom",
            customization_prompt="  change the jacket to red  ",
            session_id="session-2",
        )
    )

    assert result == b"generated-image"
    _assert_payload_contract(captured, target_path, source_path, "Customized preview generation")
    assert "CUSTOMIZATION: Apply this request only to the scene, clothing, environment, or visual style: change the jacket to red." in captured["payload"]["prompt"]


def test_non_custom_preview_discards_customization_without_weakening_target_contract(monkeypatch):
    captured = _capture_generation(monkeypatch)

    asyncio.run(
        ai_service.generate_customized_preview(
            reference_frame_path=Path("hook-frame.jpg"),
            person_photo_path=Path("uploaded-person.png"),
            mode="preserve",
            customization_prompt="make the target person's eyes closed",
            session_id="session-3",
        )
    )

    prompt = captured["payload"]["prompt"]
    assert "make the target person's eyes closed" not in prompt
    assert "IMAGE 1 IS THE IMMUTABLE TARGET SCENE AND FACIAL-PERFORMANCE REFERENCE" in prompt
    assert "Customization must never override the FIRST image's facial expression" in prompt
