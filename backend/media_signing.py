"""
Short-lived signed URLs for the rendered-clip media route.

Why this exists
---------------
`/api/media/videos/{filename}.mp4` is a `<video>` source and a download href,
which means it cannot carry an Authorization header. That made the route
unauthenticated, and because the filename IS the generation id, every rendered
clip was world-readable to anyone who could guess or scrape an id. Those are
paid renders: the whole point of the three spend gates is that a model call
costs money, and handing the output to anyone defeats that.

A query-string signature is the standard answer for a media URL that must be
usable from a plain `<video src>` or an `<a download>`, and it is what this
adds. The signature proves "this caller was issued this file" without the
browser having to attach a header it has no way to attach.

What it deliberately does NOT do
--------------------------------
It does not replace the per-user ownership check that already guards every
App Profile and project route. This is a second, independent lock on the one
route that had none: even a valid signature is scoped to one filename and one
expiry, so it cannot be replayed against another generation.

Secret handling
---------------
`MEDIA_URL_SECRET` is the signing key. It is required in production and, when
absent in a local/dev process, a per-process random key is generated. That
local fallback is deliberate: it means every restart invalidates outstanding
links, which is the safe direction to fail, and it means nobody can accidentally
run production on a hardcoded default. `is_configured()` reports which mode is
active so the startup log can say so plainly rather than leaving it to be
inferred from mysterious 401s.
"""

import hashlib
import hmac
import os
import secrets
import time

# How long a signed media link stays valid.
#
# Long enough that a `<video>` element can seek and a download can complete on a
# slow connection or a phone that fetched the page and then sat on it, short
# enough that a URL pasted into a chat window stops working the same day.
DEFAULT_TTL_SECONDS = 60 * 60 * 12  # 12 hours

_SIG_PARAM = "sig"
_EXP_PARAM = "exp"

_PROCESS_KEY = None


def _env_secret() -> str:
    return (os.environ.get("MEDIA_URL_SECRET") or "").strip()


def _process_key() -> bytes:
    """
    The key used for signing, generated once per process.

    A per-process key when MEDIA_URL_SECRET is unset means links die on restart.
    That is the correct failure mode: an unreproducible key cannot leak, and it
    cannot be guessed by anyone reading the source.
    """
    global _PROCESS_KEY
    if _PROCESS_KEY is None:
        _PROCESS_KEY = secrets.token_bytes(32)
    return _PROCESS_KEY


def is_configured() -> bool:
    """True when a real, persistent signing key is in use."""
    return bool(_env_secret())


def _sign(payload: str) -> str:
    secret = _env_secret()
    key = secret.encode("utf-8") if secret else _process_key()
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def make_signature(filename: str, expires_at: int) -> str:
    """The signature binding one filename to one expiry."""
    return _sign(f"{filename}:{expires_at}")


def build_signed_path(filename: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> str:
    """
    The media path for `filename`, carrying its own signature and expiry.

    Returns a path rather than a whole URL so callers can hand it to their own
    base URL (mediaUrl() does this today) without this module needing to know
    how the frontend is hosted.
    """
    expires_at = int(time.time()) + int(ttl_seconds)
    return f"/api/media/videos/{filename}?{_EXP_PARAM}={expires_at}&{_SIG_PARAM}={make_signature(filename, expires_at)}"


def build_signed_poster_path(filename: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> str:
    """
    The poster path for `filename` (e.g. `{id}.jpg`), carrying its own
    signature and expiry.

    Posters are thumbnails of paid renders, so they are signed like clips:
    a `<img src>` cannot carry an Authorization header either. The signature
    scheme is identical (filename:expiry); only the route prefix differs.
    """
    expires_at = int(time.time()) + int(ttl_seconds)
    return f"/api/media/posters/{filename}?{_EXP_PARAM}={expires_at}&{_SIG_PARAM}={make_signature(filename, expires_at)}"


def sign_stored_path(stored: str | None, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> str | None:
    """
    Re-sign a media path that was persisted unsigned.

    Needed because these paths are stored in the database, not just returned
    once. A signature written into a row would outlive its own expiry and the
    row would then hand out a dead link forever. So the stored value stays
    unsigned and is signed on the way out, every time it is read.

    Anything that is not an unexpired-style media path is passed through
    untouched, so this is safe to apply to a nullable column.
    """
    if not stored:
        return stored
    path = str(stored)
    prefix = "/api/media/videos/"
    if not path.startswith(prefix):
        return path
    filename = path[len(prefix):].split("?", 1)[0]
    if not filename:
        return path
    return build_signed_path(filename, ttl_seconds)


def verify(filename: str, expires_at: str | None, signature: str | None) -> bool:
    """
    Whether this signature authorises this file at this moment.

    Every failure is the same answer to the caller — a bare False, turned into a
    404 by the route — because distinguishing "expired" from "forged" from
    "never issued" tells an attacker which of those they achieved.
    """
    if not signature or not expires_at:
        return False
    try:
        expiry = int(str(expires_at))
    except (TypeError, ValueError):
        return False
    if expiry < int(time.time()):
        return False
    expected = make_signature(filename, expiry)
    # compare_digest, not == : a timing side channel on a MAC comparison is a
    # real thing and the fix is free.
    return hmac.compare_digest(expected, str(signature))