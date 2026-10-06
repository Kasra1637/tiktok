"""
MP4 fixtures for the completeness checks.

Why this module exists
----------------------
The completeness check used to be a probe for the bytes "moov" in the first and
last 4KB of a file, which passed any hand-assembled byte string starting with an
ftyp box. That is exactly why the real bug survived: a synthetic fixture cannot
express the thing that broke.

A real provider render writes its sample index LAST, and the four bytes spelling
"moov" are the first four bytes *of that box*. On a 20-second 720x1280 clip the
index is about 7.7KB, so its tag sits further than 4KB from the end and the old
probe could not see it -- it reported a finished, playable render as truncated.
The fixture that would have caught that needs a realistically sized index, which
means a real encode.

So there are two kinds of fixture here, and they test different things:

  synthetic_mp4() - hand-built, well-formed atoms. Fast, deterministic, and used
                    to pin the box-walking edge cases (64-bit sizes, extends to
                    EOF, malformed sizes). Byte-exact, so an assertion about
                    structure can be made without ffmpeg.

  real_mp4()       - an actual H.264 encode, so "can a player decode this?" has
                    a truthful answer. Used wherever the code under test will run
                    ffprobe, because that question cannot be answered about a
                    file that contains no video.

Deliberately no `+faststart` on the real encode: the index goes at the end, which
is the layout that reproduced the bug.
"""

import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

# Big enough that the sample tables push the moov tag well past 4KB from EOF,
# which is the condition the old probe got wrong. A one-second clip's index fits
# inside the window and would pass either way, so it tests nothing here.
_REAL_ARGS = ["-f", "lavfi", "-i", "testsrc2=s=720x1280:d=20:r=30"]


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def box(kind: bytes, payload: bytes) -> bytes:
    """One well-formed MP4 atom: 4-byte big-endian size, type, then body."""
    if len(kind) != 4:
        raise ValueError(f"atom type must be 4 bytes, got {kind!r}")
    size = 8 + len(payload)
    if size >= 2 ** 32:
        raise ValueError("atom too large for this helper; use the 64-bit form")
    return size.to_bytes(4, "big") + kind + payload


def synthetic_mp4(moov_body: int = 64, media_bytes: int = 2048) -> bytes:
    """
    A structurally valid MP4 with ftyp first and moov LAST.

    `moov_body` sizes the index, which is the whole point: pass 9000 to build
    the layout that the old 4KB probe rejected and the box walker accepts.
    """
    ftyp = box(b"ftyp", b"isom" + b"\x00" * 12)
    mdat = box(b"mdat", b"\x00" * media_bytes)
    moov = box(b"moov", b"\x00" * moov_body)
    return ftyp + mdat + moov


@lru_cache(maxsize=1)
def _cached_real_mp4() -> bytes:
    """Encode once per test session; ffprobe will be run against this a lot."""
    if not ffmpeg_available():
        raise RuntimeError(
            "ffmpeg is not on PATH. The completeness check probes decodable "
            "packets, so tests that exercise it need a real encode."
        )
    with tempfile.TemporaryDirectory(prefix="mp4-fixture-") as tmp:
        target = Path(tmp) / "clip.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", *_REAL_ARGS,
             "-pix_fmt", "yuv420p", "-c:v", "libx264", str(target)],
            check=True,
            capture_output=True,
        )
        return target.read_bytes()


def real_mp4() -> bytes:
    """Bytes of a genuinely playable H.264 clip whose index is at the end."""
    return _cached_real_mp4()


def write_real_mp4(path) -> Path:
    """Write `real_mp4()` to `path` and return it, for the common case."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(real_mp4())
    return p


def truncate(data: bytes, fraction: float) -> bytes:
    """Cut a byte string mid-file, the way a transfer that stops early does."""
    return data[: max(1, int(len(data) * fraction))]