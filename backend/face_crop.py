"""
Face detection + cropping utility.

Uses OpenCV's FaceDetectorYN (YuNet model) to detect the primary face in an
image, crop it with appropriate padding, and defocus everything that is not the
person so that the ONLY thing this file hands a video model is facial identity
— face, hair and skin — and not the room the photograph was taken in.

Both halves are needed. The crop alone is not enough: it bounds the person but
keeps the room down each side, the light above the hair and the garment below
the neck, and an image-conditioned model copies what it can see. Renders came
back with the uploaded kitchen in them. So the surroundings are blurred and
partly desaturated as well, which costs nothing in likeness (the head is
returned untouched) and removes the copyable scene.

Graceful fallback: if no face is detected, returns the original image unchanged
so the pipeline doesn't break.
"""
import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageFilter

logger = logging.getLogger(__name__)

# Path to the bundled YuNet face detection model (int8 ONNX, ~100KB)
_MODEL_PATH = Path(__file__).parent / "models" / "face_detection_yunet_2023mar_int8.onnx"

# Detection confidence threshold
_MIN_CONFIDENCE = 0.5

# A name-photo warning only fires when a second detection is visible to a
# person. YuNet fires on head-shaped non-faces — a messy hair bun is its
# favourite — at marginal confidence, and count_faces used to take that raw
# length, so a solo portrait of one woman with a topknot read "2 faces" and
# told the founder to upload a solo shot of a photo that already was one.
# The hair blobs this detector produces fail all three checks at once:
# confidence far below the dominant face, a fraction of its area, and
# landmarks that cannot be a face (both "eyes" collapse onto one point,
# where a real face's eyes span roughly half the box width). A real second
# person carries a comparable face, at a comparable confidence, with a
# comparable eye span — the checks were validated against a tiled two-person
# composite of the same portrait, which clears all three.
_COUNT_MIN_CONFIDENCE = 0.65
_COUNT_MIN_AREA_REL = 0.15
_COUNT_MIN_EYE_SPAN_RATIO = 0.30

# Padding ratios relative to the detected face bounding box dimensions.
# These capture the full head (face + hair + ears + chin/neck) with margin to
# spare, because this crop can BECOME the opening frame: first-frame models
# open the video on this image, so a headshot-tight reference opens the video
# too close and the render stays there. The extra room costs nothing in
# likeness — the head is still returned untouched — and it leaks nothing: the
# room and the garment inside this box are what defocus_outside_person is for.
_PAD_HORIZONTAL = 0.9    # 90% of face width on each side (ears + hair + side margin)
_PAD_TOP = 1.4           # 140% above face (full hair plus headroom)
_PAD_BOTTOM = 0.9        # 90% below face (neck plus shoulder margin)

# The render is vertical 9:16, so the reference is too. A crop wider than that
# is center-cropped by the provider to fit — cutting the sides of the head off
# an already tight headshot — so the box is expanded (never shrunk) to 9:16
# before the pixels are cut, and a headshot that skips the crop is padded to
# 9:16 instead of being returned in the upload's own aspect.
_TARGET_ASPECT = 9 / 16

# How hard the reference is defocused outside the person, and over how much of
# the frame that is applied.
#
# The crop above bounds the person; it never REMOVES what surrounds them. At
# those pads a portrait keeps the room down both sides, above the hair, and the
# neck and top of the garment below the chin — so the uploaded room, its light
# and the founder's own clothes all still reach the model as pixels. The
# person-anchor prompt says that image is authority on the person and "not the
# place", but a text instruction does not remove pixels: an image-conditioned
# video model copies what it can see, and it sees a kitchen. That is why renders
# come back partly on the planned scene and partly in the uploaded room — the
# prompt wins where it is the only signal, and the photograph wins where it is
# still a photograph.
#
# So the image is made to match the claim. Everything outside the head and
# hair is blurred past recognition and partly desaturated, which leaves nothing
# for the model to copy: no wall, no window, no colour temperature, no garment.
# A blur rather than a cut or a matte, because a hard-edged silhouette reads as
# a composite and some models reproduce the edge as an object.
#
# The radius scales with the crop so it is severe at any upload size, and the
# shoulder band is excluded for the same reason the crop is: wardrobe is chosen
# by the scene and locked there, and a sharp garment in the reference fights
# that lock instead of supporting it.
_DEFOUS_RADIUS_RATIO = 0.09
_DEFOUS_DESATURATE = 0.55
# The person's own region, as multiples of the face box. Hair sits above the
# detected face, so the head ellipse reaches well past it; the mask stops at the
# base of the neck because everything below is the garment.
_PERSON_TOP_FACTOR = 0.95
_PERSON_SIDE_FACTOR = 0.85
_PERSON_BOTTOM_FACTOR = 0.30
# The blur is feathered in over this fraction of the person's own radius, so the
# boundary never reads as a cut line. Kept small on purpose: the feather is
# measured against the same normalised distance as the head, so a large value
# does not soften the edge — it inflates the whole person region, and at 0.55
# the "person" grew to cover most of the frame and left the garment sharp.
_MASK_FEATHER = 0.25


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


def _crop_box(bbox: tuple, img_w: int, img_h: int) -> tuple:
    """
    The padded face box, expanded to vertical 9:16, clamped to the image.

    One function so `_crop_face_region` and `_bbox_in` cannot disagree about
    where the crop starts: both call this, one to cut pixels and one to move
    the face box into the cropped frame.
    """
    x, y, w_face, h_face, _ = bbox

    # Padded boundaries from the face box.
    pad_x = int(w_face * _PAD_HORIZONTAL)
    pad_top = int(h_face * _PAD_TOP)
    pad_bottom = int(h_face * _PAD_BOTTOM)

    x1 = max(0, x - pad_x)
    y1 = max(0, y - pad_top)
    x2 = min(img_w, x + w_face + pad_x)
    y2 = min(img_h, y + h_face + pad_bottom)

    return _expand_to_vertical(x1, y1, x2, y2, img_w, img_h)


def _expand_to_vertical(x1: int, y1: int, x2: int, y2: int,
                        img_w: int, img_h: int) -> tuple:
    """
    Grow a crop box to vertical 9:16 without leaving the image.

    Only the short side grows, split across both ends; whatever one side loses
    to the image edge is given to the other, so a face near the top still gets
    a full-height box. Never shrinks: a box already at 9:16 keeps its pixels,
    and a box the image cannot contain at 9:16 takes the closest it can.
    """
    w, h = x2 - x1, y2 - y1
    if w <= 0 or h <= 0:
        return (x1, y1, x2, y2)
    if w / h <= _TARGET_ASPECT:
        want_w = min(img_w, int(round(h * _TARGET_ASPECT)))
        extra = want_w - w
        if extra <= 0:
            return (x1, y1, x2, y2)
        nx1 = x1 - extra // 2
        nx2 = x2 + (extra - extra // 2)
        if nx1 < 0:
            nx2 = min(img_w, nx2 - nx1)
            nx1 = 0
        if nx2 > img_w:
            nx1 = max(0, nx1 - (nx2 - img_w))
            nx2 = img_w
        return (nx1, y1, nx2, y2)
    want_h = min(img_h, int(round(w / _TARGET_ASPECT)))
    extra = want_h - h
    if extra <= 0:
        return (x1, y1, x2, y2)
    ny1 = y1 - extra // 2
    ny2 = y2 + (extra - extra // 2)
    if ny1 < 0:
        ny2 = min(img_h, ny2 - ny1)
        ny1 = 0
    if ny2 > img_h:
        ny1 = max(0, ny1 - (ny2 - img_h))
        ny2 = img_h
    return (x1, ny1, x2, ny2)


def _crop_face_region(img: Image.Image, bbox: tuple) -> Image.Image:
    """
    Crop the image around the detected face with padding for context.

    Args:
        img: PIL Image (RGB)
        bbox: (x, y, w, h, confidence) from _detect_face

    Returns:
        Cropped PIL Image containing the face region with padding, expanded
        to vertical 9:16 so no provider-side center-crop bites into the head.
    """
    img_w, img_h = img.size
    return img.crop(_crop_box(bbox, img_w, img_h))


def _bbox_in(bbox: tuple, img_w: int, img_h: int) -> tuple:
    """
    The same face box, expressed in a cropped frame's coordinates.

    `_crop_face_region` is called with the box on the original, and the result
    is a different image, so the box has to move with it. Recomputing it by
    re-detecting would be a second model call for a number the caller already
    has, and the crop box here is the same one the crop used, so the origin
    is recovered from the same arithmetic instead.
    """
    x, y, w_face, h_face, confidence = bbox
    crop_x1, crop_y1, _, _ = _crop_box(bbox, img_w, img_h)
    return (
        x - crop_x1,
        y - crop_y1,
        w_face,
        h_face,
        confidence,
    )


def _person_mask(size: tuple, bbox: tuple) -> "np.ndarray":
    """
    A float mask, 1.0 over the person and 0.0 everywhere else.

    Built from the detected face box rather than a segmentation model, because
    this only has to separate a head from a room, and the face is already the
    one thing the pipeline can find reliably. The ellipse is sized generously
    around the head because hair is identity — under-sizing it would blur away
    the hairstyle the anchor tells the model to copy exactly, which would trade a
    scene leak for a worse likeness.

    Feathered rather than hard: a crisp boundary is read as a pasted edge, and
    some models render that edge as a real object in frame.
    """
    width, height = size
    x, y, w_face, h_face, _ = bbox
    cx = x + w_face / 2.0
    # The vertical extent is stated against the face box rather than as a
    # radius, so "how much below the chin stays sharp" is a readable number:
    # the neck is identity, the garment is not.
    top = y - h_face * _PERSON_TOP_FACTOR
    bottom = y + h_face * (1.0 + _PERSON_BOTTOM_FACTOR)
    cy = (top + bottom) / 2.0
    ry = max((bottom - top) / 2.0, 1.0)
    rx = max(w_face * _PERSON_SIDE_FACTOR, 1.0)

    yy, xx = np.ogrid[0:height, 0:width]
    dist = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    edge = 1.0 + _MASK_FEATHER
    mask = np.clip((edge - dist) / max(_MASK_FEATHER, 1e-6), 0.0, 1.0)
    # Smoothstep for a gentler shoulder on the falloff than a linear ramp.
    return mask * mask * (3.0 - 2.0 * mask)


def defocus_outside_person(img: Image.Image, bbox: tuple) -> Image.Image:
    """
    Blur and partly desaturate everything that is not the person's head.

    The identity reference's job is the face, the hair and the skin. The room
    behind it and the garment below it are not identity, and every render that
    leaked an uploaded kitchen leaked it through here: the crop bounds the person
    but never removes the surroundings, so the model is handed a photograph and
    asked in text to use only the face. It uses the face AND the room, because
    pixels outrank instructions.

    The subject stays fully sharp — the mask is 1.0 across the head — so this
    costs nothing in likeness. It only removes the copyable scene, which is the
    part the strategy's locked scene was supposed to own.

    Graceful by construction: any failure returns the image untouched, so a
    render is never lost to a preprocessing step.
    """
    try:
        width, height = img.size
        if width < 16 or height < 16:
            return img
        radius = max(2.0, min(width, height) * _DEFOUS_RADIUS_RATIO)
        # Twice, and only to the background. One pass leaves coarse structure
        # behind — a high-contrast wall still reads as a wall after a single
        # blur — and the point of this step is that there is nothing left to
        # copy, not merely that it is softer.
        blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
        blurred = blurred.filter(ImageFilter.GaussianBlur(radius=radius))
        mask = _person_mask(img.size, bbox)[:, :, None]
        # Desaturate only what is being blurred, so the person keeps full
        # colour and the background loses the colour cues that read as "this
        # room's lighting".
        grey = Image.blend(
            blurred.convert("RGB"), blurred.convert("L").convert("RGB"),
            _DEFOUS_DESATURATE,
        )
        grey_np = np.asarray(grey, dtype=np.float32)
        base = np.asarray(img.convert("RGB"), dtype=np.float32)
        # Lerp the person out of the defocused background and the background out
        # of the person, in one pass.
        merged = base * mask + grey_np * (1.0 - mask)
        return Image.fromarray(np.clip(merged, 0, 255).astype(np.uint8))
    except Exception as e:  # never fail a render over preprocessing
        logger.warning(f"Background defocus failed ({e}) — using the image as-is.")
        return img


def _pad_to_vertical(img: Image.Image, bbox: tuple) -> tuple:
    """
    Pad an image out to vertical 9:16, returning (image, bbox).

    For the headshot branch, which skips the crop: a tight square or landscape
    upload returned as-is becomes a close-up first frame with no headroom, and
    the provider center-crops its width to fit 9:16 on top of that. The upload
    is centered on a blurred cover-fill of itself instead, so the head keeps
    its pixels and gains margin in an aspect no provider has to crop.

    The fill is blurred past recognition and partly desaturated — the same
    treatment as defocus_outside_person — so it reads as backdrop, not as a
    room to copy. An image already at (or taller than) 9:16 is returned
    untouched. Never raises: any failure returns the inputs unchanged.
    """
    try:
        width, height = img.size
        if width <= 0 or height <= 0:
            return (img, bbox)
        if width / height <= _TARGET_ASPECT + 1e-6:
            return (img, bbox)
        new_h = int(round(width / _TARGET_ASPECT))
        if new_h <= height:
            return (img, bbox)
        fill = img.convert("RGB").resize((width, new_h), Image.BILINEAR)
        radius = max(2.0, min(width, new_h) * _DEFOUS_RADIUS_RATIO)
        fill = fill.filter(ImageFilter.GaussianBlur(radius=radius))
        fill = fill.filter(ImageFilter.GaussianBlur(radius=radius))
        fill = Image.blend(
            fill, fill.convert("L").convert("RGB"), _DEFOUS_DESATURATE,
        )
        top = (new_h - height) // 2
        fill.paste(img.convert("RGB"), (0, top))
        x, y, w_face, h_face, confidence = bbox
        return (fill, (x, y + top, w_face, h_face, confidence))
    except Exception as e:  # never fail a render over preprocessing
        logger.warning(f"Vertical padding failed ({e}) — using the image as-is.")
        return (img, bbox)


def _is_plausible_face(face, dominant_area: float) -> bool:
    """One detection survives as a face for counting purposes. See the
    _COUNT_* note above: a hair blob is marginal, tiny next to the main
    face, and has degenerate landmarks; a real person is none of those."""
    if float(face[14]) < _COUNT_MIN_CONFIDENCE:
        return False
    if dominant_area > 0 and (float(face[2]) * float(face[3])) / dominant_area < _COUNT_MIN_AREA_REL:
        return False
    eye_span = abs(float(face[6]) - float(face[4])) / max(float(face[2]), 1.0)
    return eye_span >= _COUNT_MIN_EYE_SPAN_RATIO


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

    if faces is None or len(faces) == 0:
        return 0
    dominant_area = max(float(f[2]) * float(f[3]) for f in faces)
    return int(sum(1 for f in faces if _is_plausible_face(f, dominant_area)))


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
            # Still defocused, and padded to vertical. Skipping the crop is
            # about framing, not about what the reference is allowed to
            # contain: a tight selfie against a busy wall is the same leak as
            # a full-body shot in a kitchen, and returning it untouched was how
            # a close-up kept its own background. Padding first, so the head
            # gains headroom in an aspect no provider has to center-crop — a
            # square close-up returned as-is opens a first-frame video too
            # close, with its sides cut off to fit 9:16.
            img, bbox = _pad_to_vertical(img, bbox)
            cleaned = defocus_outside_person(img, bbox)
            stem = image_path.stem
            suffix = image_path.suffix or ".png"
            cleaned_path = image_path.parent / f"{stem}_face{suffix}"
            cleaned.save(cleaned_path, quality=95)
            logger.info(
                f"Background defocused on a headshot: {img_w}x{img_h} -> "
                f"{cleaned.size[0]}x{cleaned.size[1]} (saved to {cleaned_path.name})"
            )
            return cleaned_path

        # Crop the face region
        cropped = _crop_face_region(img, bbox)

        # Then take the room out of what is left. Order matters: the crop
        # decides how much of the frame the person occupies, so the mask and the
        # blur radius are computed against the cropped frame rather than the
        # upload.
        cropped = defocus_outside_person(cropped, _bbox_in(bbox, img_w, img_h))

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
