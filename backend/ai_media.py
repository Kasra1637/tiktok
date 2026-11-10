"""Image payload helpers for the OpenRouter adapter.

Pure (no HTTP/auth/persistence): encode a local image file to a data URI for
vision calls. Split out of `ai_service` by flow; `ai_service` re-exports
these names so existing callers and tests keep working.
"""
import base64
import mimetypes
from pathlib import Path


def image_to_base64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")
_IMAGE_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
def image_mime_type(path: Path) -> str:
    """The MIME type that actually matches the file's bytes.

    Every reference used to be labelled `image/png` regardless of what it was,
    so a .jpg phone photo went out as `data:image/png;base64,<JPEG bytes>`. A
    mislabelled data URI is invalid, which image_testing.md calls out by name.
    The tests never caught it because every fixture is a .png.
    """
    suffix = Path(path).suffix.lower()
    if suffix in _IMAGE_MIME_BY_SUFFIX:
        return _IMAGE_MIME_BY_SUFFIX[suffix]
    guessed, _encoding = mimetypes.guess_type(str(path))
    return guessed or "image/png"
def image_data_uri(path: Path) -> str:
    """A base64 data URI whose declared MIME matches the encoded bytes."""
    return f"data:{image_mime_type(path)};base64,{image_to_base64(path)}"
