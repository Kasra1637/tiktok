"""Face counting must not call a hair blob a second person.

YuNet fires on head-shaped non-faces (a messy hair bun is its favourite) at
marginal confidence. Counting raw detections turned a solo portrait of one
woman with a topknot into "2 faces detected", which told the founder to
upload a solo shot of a photo that already was one. The filter keeps only
detections that carry a comparable face: confidence, relative size, and
plausible landmarks (eyes spread roughly half the box width, not collapsed
onto a point).
"""
import io
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import face_crop

SAMPLE = Path(__file__).resolve().parent.parent / "storage" / "samples" / "test_portrait.jpg"


def _portrait() -> Image.Image:
    return Image.open(SAMPLE).convert("RGB")


def _recompressed(img: Image.Image, quality: int) -> Image.Image:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


@pytest.mark.parametrize("quality", [95, 85, 70])
def test_solo_portrait_counts_one_despite_hair_blob(quality):
    # At JPEG q85/q70 the detector's hair-blob hit crosses the 0.5 threshold
    # (0.55-0.60) and the raw count reads 2 for one woman. The plausible-face
    # filter rejects it on all three checks.
    img = _recompressed(_portrait(), quality)
    assert face_crop.count_faces_in_image(np.array(img)) == 1


def test_two_people_still_counts_two():
    # Loosening the filter must not drop a real second face: the same
    # portrait tiled twice carries two comparable faces, both of which clear
    # the confidence, size, and landmark checks.
    img = _portrait()
    w, h = img.size
    double = Image.new("RGB", (w * 2, h), "black")
    double.paste(img, (0, 0))
    double.paste(img, (w, 0))
    assert face_crop.count_faces_in_image(np.array(double)) == 2


def test_blank_counts_zero():
    assert face_crop.count_faces_in_image(np.full((120, 120, 3), 128, dtype=np.uint8)) == 0


def _face(confidence, x, y, w, h, eye_span_ratio):
    # YuNet row: bbox(4) + 5 landmarks (10) + score. Only the confidence,
    # box area, and left/right-eye x positions matter to the filter.
    row = np.zeros(15, dtype=np.float32)
    row[0], row[1], row[2], row[3] = x, y, w, h
    row[4] = x + w * 0.3
    row[6] = x + w * (0.3 + eye_span_ratio)
    row[14] = confidence
    return row


def test_hair_blob_detection_is_not_a_face():
    # The exact hair-bun detection the model emits on the portrait: 0.60
    # confidence, 6% of the main face's area, eyes 0.11 of the box width.
    main = _face(0.894, 260, 365, 270, 350, 0.48)
    blob = _face(0.596, 475, 146, 65, 91, 0.11)
    faces = np.array([main, blob])
    dominant = max(float(f[2]) * float(f[3]) for f in faces)
    assert face_crop._is_plausible_face(main, dominant) is True
    assert face_crop._is_plausible_face(blob, dominant) is False


def _count(faces) -> int:
    faces = np.asarray(faces)
    dominant = face_crop._dominant_index(faces)
    dominant_area = float(faces[dominant][2]) * float(faces[dominant][3])
    others = sum(
        1 for i, f in enumerate(faces)
        if i != dominant and face_crop._is_plausible_face(f, dominant_area)
    )
    return 1 + others


def test_marginal_single_face_still_counts_one():
    # A realistic portrait YuNet scores marginal — side profile, sunglasses,
    # phone noise — has one detection, but at 0.55 confidence with collapsed
    # landmarks it fails every plausible-face check. Gating the first face
    # turned that into "No face detected", which is the more expensive
    # error: the founder is told the provider will refuse a photo that
    # already shows one face. The dominant detection always counts.
    assert _count([_face(0.55, 10, 10, 100, 130, 0.10)]) == 1


def test_hair_blob_pair_counts_one():
    assert _count([
        _face(0.894, 260, 365, 270, 350, 0.48),
        _face(0.596, 475, 146, 65, 91, 0.11),
    ]) == 1


def test_second_real_face_counts_two():
    assert _count([
        _face(0.894, 0, 0, 270, 350, 0.48),
        _face(0.894, 300, 0, 270, 350, 0.48),
    ]) == 2


def test_largest_box_is_dominant_even_at_lower_confidence():
    # Area wins over confidence when picking the anchor: a big marginal face
    # is still the face, not the small confident blob next to it.
    faces = np.array([
        _face(0.9, 0, 0, 50, 65, 0.48),
        _face(0.6, 100, 100, 200, 260, 0.48),
    ])
    assert face_crop._dominant_index(faces) == 1
