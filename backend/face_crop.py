"""
Face detection + cropping utility.

Uses OpenCV's FaceDetectorYN (YuNet model) to detect the primary face in an
image and crop it with appropriate padding so that ONLY the facial identity
(face + hair/forehead/chin context) is sent to the face-swap model — regardless
of how much body is visible in the original upload.

Graceful fallback: if no face is detected, returns the original image unchanged
so the pipeline doesn't break.
"""
import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Path to the bundled YuNet face detection model (int8 ONNX, ~100KB)
_MODEL_PATH = Path(__file__).parent / "models" / "face_detection_yunet_2023mar_int8.onnx"

# Detection confidence threshold
_MIN_CONFIDENCE = 0.5

# Padding ratios relative to the detected face bounding box dimensions.
# These ensure we capture the full head (face + hair + ears + chin/neck)
# for the AI to understand the person's complete identity including hair style,
# while excluding torso/arms/clothing.
_PAD_HORIZONTAL = 0.6    # 60% of face width on each side (captures ears + hair width)
_PAD_TOP = 1.0           # 100% above face (captures full hair/top of head)
_PAD_BOTTOM = 0.4        # 40% below face (chin + neck for skin tone reference)


def _detect_face(img_rgb: np.ndarray) -> tuple:
    """
    Detect the largest/most confident face in an RGB numpy array.

    Returns:
        (x, y, w, h, confidence) of the best face detection, or None if no face found.
    """
    if not _MODEL_PATH.exists():
        logger.warning(f"Face detection model not found at {_MODEL_PATH}. Skipping face crop.")
        return None

    h, w = img_rgb.shape[:2]

    detector = cv2.FaceDetectorYN_create(
        str(_MODEL_PATH), "", (w, h), _MIN_CONFIDENCE, 0.3, 5000
    )
    _, faces = detector.detect(img_rgb)

    if faces is None or len(faces) == 0:
        return None

    # Pick the detection with the highest confidence
    best_idx = int(np.argmax(faces[:, 14]))
    face = faces[best_idx]
    fx, fy, fw, fh = int(face[0]), int(face[1]), int(face[2]), int(face[3])
    confidence = float(face[14])

    return (fx, fy, fw, fh, confidence)


def _crop_face_region(img: Image.Image, bbox: tuple) -> Image.Image:
    """
    Crop the image around the detected face with padding for context.

    Args:
        img: PIL Image (RGB)
        bbox: (x, y, w, h, confidence) from _detect_face

    Returns:
        Cropped PIL Image containing the face region with padding.
    """
    x, y, w_face, h_face, _ = bbox
    img_w, img_h = img.size

    # Calculate padded crop boundaries
    pad_x = int(w_face * _PAD_HORIZONTAL)
    pad_top = int(h_face * _PAD_TOP)
    pad_bottom = int(h_face * _PAD_BOTTOM)

    crop_x1 = max(0, x - pad_x)
    crop_y1 = max(0, y - pad_top)
    crop_x2 = min(img_w, x + w_face + pad_x)
    crop_y2 = min(img_h, y + h_face + pad_bottom)

    return img.crop((crop_x1, crop_y1, crop_x2, crop_y2))


def count_faces_in_image(img_rgb: np.ndarray) -> Optional[int]:
    """
    Count confidently-detected faces in an RGB numpy array.

    Returns None when detection cannot run at all (model file missing), so
    callers can tell "unknown" apart from "zero faces found" — only the
    latter justifies warning the founder, since the provider's privacy
    filter fires on exactly the photos where no single face anchors the
    frame (or where several compete).
    """
    if not _MODEL_PATH.exists():
        logger.warning(f"Face detection model not found at {_MODEL_PATH}. Skipping face count.")
        return None

    h, w = img_rgb.shape[:2]

    detector = cv2.FaceDetectorYN_create(
        str(_MODEL_PATH), "", (w, h), _MIN_CONFIDENCE, 0.3, 5000
    )
    _, faces = detector.detect(img_rgb)

    if faces is None:
        return 0
    return int(len(faces))


def count_faces_from_path(image_path: Path) -> Optional[int]:
    """
    Count faces in an image file. Never raises: any failure (unreadable
    file, detector error) returns None, because a pre-flight check must
    never block an upload.
    """
    try:
        img = Image.open(image_path).convert("RGB")
        return count_faces_in_image(np.array(img))
    except Exception as e:
        logger.warning(f"Face count failed for {image_path.name} ({e}).")
        return None


def bound_for_submit(image_path: Path, max_side: int = 1024, quality: int = 85) -> Path:
    """
    Downscale and re-encode an image so its base64 form is bounded.

    The identity reference is embedded in the request as a base64 data URI, and
    base64 inflates by about a third. Nothing else bounded it: the upload
    ceiling is 200 MB, crop_face_from_path crops without resizing, and two of
    its three return paths hand back the original untouched — a no-face photo,
    or one where the face already dominates. A modern phone photo therefore
    arrives as several megabytes of data URI inside a JSON body, which is a
    request the provider can refuse for reasons that name neither the image nor
    a field we control.

    1024 on the long side at JPEG 85 keeps a face crop well above what identity
    conditioning needs while landing the encoded image in the low hundreds of
    KB. Written beside the source with a '_submit' suffix, and only when it
    actually helps, so a small photo is passed through untouched.

    Never raises: an image that cannot be re-encoded is returned as-is, because
    an oversized-but-valid reference is better than no render at all.
    """
    source = Path(image_path)
    if not source.is_file():
        return source
    if "_submit" in source.stem:
        return source
    try:
        img = Image.open(source)
        img.load()
        longest = max(img.size)
        # Only re-encode when there is something to gain. A PNG of a small crop
        # can be smaller than the JPEG it would become.
        if longest <= max_side and source.suffix.lower() in (".jpg", ".jpeg"):
            return source

        img = img.convert("RGB")
        if longest > max_side:
            ratio = max_side / float(longest)
            img = img.resize(
                (max(1, int(img.width * ratio)), max(1, int(img.height * ratio))),
                Image.LANCZOS,
            )
        target = source.with_name(f"{source.stem}_submit.jpg")
        img.save(target, format="JPEG", quality=quality, optimize=True)
        logger.info(
            f"Bounded {source.name} for submit: {img.size[0]}x{img.size[1]} "
            f"{source.stat().st_size // 1024}KB -> {target.stat().st_size // 1024}KB"
        )
        return target
    except Exception as e:
        logger.warning(f"Could not bound {source.name} for submit ({e}); sending as-is.")
        return source


def crop_face_from_path(image_path: Path) -> Path:
    """
    Detect and crop the face from an image file, saving the cropped version
    alongside the original with a '_face' suffix.

    If no face is detected, returns the original path unchanged (graceful fallback).

    Args:
        image_path: Path to the source image (the user's uploaded photo).

    Returns:
        Path to the cropped face image (or original if no face detected).
    """
    try:
        # Skip if this file is already a cropped face (avoid _face_face_face... chains)
        if "_face" in image_path.stem:
            logger.info(f"{image_path.name} is already a face crop — skipping.")
            return image_path

        img = Image.open(image_path).convert("RGB")
        img_np = np.array(img)

        bbox = _detect_face(img_np)

        if bbox is None:
            logger.info(
                f"No face detected in {image_path.name} — using original image as-is."
            )
            return image_path

        x, y, w_face, h_face, confidence = bbox
        img_w, img_h = img.size
        face_area_pct = (w_face * h_face) / (img_w * img_h) * 100

        logger.info(
            f"Face detected in {image_path.name}: "
            f"bbox=({x},{y},{w_face}x{h_face}), confidence={confidence:.2f}, "
            f"face covers {face_area_pct:.1f}% of image"
        )

        # If the face already dominates the image (>40%), skip cropping
        # — the image is likely already a close-up headshot
        if face_area_pct > 40:
            logger.info(
                f"Face already dominates image ({face_area_pct:.1f}% > 40%) — "
                f"skipping crop, using original."
            )
            return image_path

        # Crop the face region
        cropped = _crop_face_region(img, bbox)

        # Save cropped version alongside original
        stem = image_path.stem
        suffix = image_path.suffix or ".png"
        cropped_path = image_path.parent / f"{stem}_face{suffix}"
        cropped.save(cropped_path, quality=95)

        crop_w, crop_h = cropped.size
        logger.info(
            f"Face cropped: {img_w}x{img_h} -> {crop_w}x{crop_h} "
            f"(saved to {cropped_path.name})"
        )

        return cropped_path

    except Exception as e:
        logger.warning(
            f"Face crop failed for {image_path.name} ({e}) — using original image."
        )
        return image_path
