"""
Cloudflare R2 object storage service for persisting generated videos.

R2 is S3-compatible, so we use boto3 with a custom endpoint URL. Videos are
stored at: {user_id}/{job_id}.mp4 — giving each user their own namespace.

Required environment variables:
    R2_ACCOUNT_ID       — Cloudflare account ID (32-char hex)
    R2_ACCESS_KEY_ID    — R2 API token access key
    R2_SECRET_ACCESS_KEY — R2 API token secret key
    R2_BUCKET_NAME      — Bucket name (e.g. "hookforge-videos")
    R2_PUBLIC_URL       — (Optional) Public storage locator. Playback uses
                          authenticated presigned reads even without a public
                          bucket; the account-endpoint fallback is private.

When R2 is not configured (env vars missing), all functions return None/False
gracefully so the app still works — videos just won't persist across deploys.
"""
import json
import logging
import os
import subprocess
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Configuration from environment
R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "").strip()
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "").strip()
R2_PUBLIC_URL = os.environ.get("R2_PUBLIC_URL", "").strip().rstrip("/")


def is_configured() -> bool:
    """Check whether R2 credentials are available."""
    return bool(R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME)


def _get_client():
    """Create a boto3 S3 client configured for Cloudflare R2."""
    if not is_configured():
        return None
    return boto3.client(
        "s3",
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(
            signature_version="s3v4",
            connect_timeout=10,
            read_timeout=30,
            retries={"max_attempts": 2, "mode": "standard"},
        ),
        region_name="auto",
    )


def _object_key(user_id: str, job_id: str) -> str:
    """Build the R2 object key: {user_id}/{job_id}.mp4"""
    return f"{user_id}/{job_id}.mp4"


def public_url(user_id: str, job_id: str) -> str:
    """Build a stable storage locator; private locators require signed reads."""
    key = _object_key(user_id, job_id)
    if R2_PUBLIC_URL:
        return f"{R2_PUBLIC_URL}/{key}"
    # This is a private S3 locator, NOT a public playback URL. Browser reads
    # must use signed app playback or signed_read_url(), never this raw URL.
    return f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com/{R2_BUCKET_NAME}/{key}"


def upload_video(user_id: str, job_id: str, video_path: Path) -> Optional[str]:
    """
    Upload a video file to R2.

    Args:
        user_id: The authenticated user's ID (namespace prefix).
        job_id: The video generation job ID (unique filename).
        video_path: Local path to the .mp4 file.

    Returns:
        A stable storage locator (not necessarily publicly readable), or None
        if upload failed or R2 is not configured.
    """
    if not is_configured():
        logger.debug("R2 not configured — skipping video upload")
        return None

    if not video_path or not video_path.exists():
        logger.warning(f"Cannot upload to R2: video file does not exist: {video_path}")
        return None

    client = _get_client()
    if not client:
        return None

    key = _object_key(user_id, job_id)
    try:
        client.upload_file(
            str(video_path),
            R2_BUCKET_NAME,
            key,
            ExtraArgs={
                "ContentType": video_content_type(video_path) or "video/mp4",
                "CacheControl": "public, max-age=31536000, immutable",
            },
        )
        url = public_url(user_id, job_id)
        logger.info(f"Uploaded video to R2: {key} ({video_path.stat().st_size} bytes)")
        return url
    except ClientError as e:
        logger.error(f"R2 upload failed for {key}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error uploading to R2 {key}: {e}")
        return None


def _poster_key(user_id: str, job_id: str) -> str:
    """Build the R2 object key for a poster: {user_id}/{job_id}.jpg"""
    return f"{user_id}/{job_id}.jpg"


def upload_poster(user_id: str, job_id: str, poster_path: Path) -> bool:
    """
    Upload a poster JPEG to R2 for durability across deploys.

    Returns True on success, False otherwise. Never raises for service
    errors: the local poster still serves History on this instance.
    """
    if not is_configured():
        return False
    try:
        if not poster_path or not Path(poster_path).is_file():
            return False
    except OSError:
        return False
    client = _get_client()
    if not client:
        return False
    key = _poster_key(user_id, job_id)
    try:
        client.upload_file(
            str(poster_path),
            R2_BUCKET_NAME,
            key,
            ExtraArgs={
                "ContentType": "image/jpeg",
                "CacheControl": "public, max-age=31536000, immutable",
            },
        )
        logger.info(f"Uploaded poster to R2: {key}")
        return True
    except ClientError as e:
        logger.error(f"R2 poster upload failed for {key}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error uploading poster to R2 {key}: {e}")
        return False


def download_poster(user_id: str, job_id: str, target: Path) -> bool:
    """Download a poster from R2 to `target`. Validates it is a JPEG."""
    client = _get_client()
    if client is None:
        return False
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.poster")
    try:
        client.download_file(R2_BUCKET_NAME, _poster_key(user_id, job_id), str(temp))
        try:
            if not temp.is_file() or temp.stat().st_size < 512:
                return False
            with temp.open("rb") as fh:
                head = fh.read(2)
            if head != b"\xff\xd8":
                return False
        except OSError:
            return False
        temp.replace(target)
        return True
    except ClientError as error:
        if _missing_object(error):
            return False
        raise
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def delete_poster(user_id: str, job_id: str) -> bool:
    """Delete a poster from R2. True if deleted or absent, False on error."""
    if not is_configured():
        return False
    client = _get_client()
    if not client:
        return False
    key = _poster_key(user_id, job_id)
    try:
        client.delete_object(Bucket=R2_BUCKET_NAME, Key=key)
        return True
    except ClientError as e:
        logger.error(f"R2 poster delete failed for {key}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error deleting poster from R2 {key}: {e}")
        return False


def is_managed_url(value: str) -> bool:
    """Recognize our stable cloud locators, including the private S3 endpoint."""
    try:
        parsed = urlsplit(value)
        if (parsed.hostname or "").endswith(".r2.cloudflarestorage.com"):
            return True
        if R2_PUBLIC_URL:
            base = urlsplit(R2_PUBLIC_URL)
            return parsed.netloc == base.netloc and parsed.path.startswith(base.path.rstrip("/") + "/")
    except ValueError:
        pass
    return False


def video_content_type(path: Path) -> Optional[str]:
    """Identify the container, including legacy WebM files named .mp4."""
    try:
        with Path(path).open("rb") as stream:
            head = stream.read(16)
        if head.startswith(b"\x1a\x45\xdf\xa3"):
            return "video/webm"
        if head[4:8] == b"ftyp":
            return "video/mp4"
    except OSError:
        pass
    return None


def mp4_has_moov(path: Path) -> bool:
    """
    Whether a file carries a top-level `moov` atom, found by walking the box
    chain rather than probing fixed windows.

    Why not a head/tail probe: `moov` is the sample index every player seeks
    through, and for a non-fragmented file the provider writes it LAST. The
    four bytes spelling "moov" are the first four bytes *of that atom*, so for a
    real render -- whose index runs to tens of kilobytes of sample tables -- the
    tag sits well before the last 4KB of the file. A tail probe therefore cannot
    see it, and every finished render was being rejected as "truncated" while
    being perfectly playable. One of those renders, with a 9KB index, is the
    reproduction in the tests for this function.

    Walking by declared size reads 8 bytes per box regardless of file size, so
    this stays cheap on a 50MB clip.

    Handles the three awkward forms the format allows: a 64-bit size (the 32-bit
    field reads 1 and the real length follows in 8 bytes), a size of 0 meaning
    "extends to end of file", and a truncated or nonsensical size, which stops
    the walk rather than trusting it.
    """
    try:
        size = Path(path).stat().st_size
    except OSError:
        return False
    if size < 8:
        return False

    offset = 0
    try:
        with Path(path).open("rb") as stream:
            while offset + 8 <= size:
                stream.seek(offset)
                header = stream.read(8)
                if len(header) < 8:
                    return False
                box_size = int.from_bytes(header[0:4], "big")
                box_type = header[4:8]
                if box_type == b"moov":
                    return True
                header_len = 8
                if box_size == 1:
                    if offset + 16 > size:
                        return False
                    extended = stream.read(8)
                    if len(extended) < 8:
                        return False
                    box_size = int.from_bytes(extended, "big")
                    header_len = 16
                elif box_size == 0:
                    box_size = size - offset
                if box_size < header_len:
                    # A box cannot be smaller than its own header. Trusting it
                    # here would let offset go backwards or stand still and spin.
                    return False
                offset += box_size
    except OSError:
        return False
    return False


def _probe_decodable_video_packets(path: Path) -> Optional[bool]:
    """
    Whether ffprobe counts decodable video packets, or None if it cannot say.

    None is a real answer and means "no opinion": ffprobe missing, not
    executable, or timed out. Callers decide what an unknown is worth, because
    the two containers do not treat it the same way (see is_usable_video).
    """
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-count_packets", "-show_entries", "stream=nb_read_packets",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    try:
        streams = json.loads(result.stdout or "{}").get("streams", [])
    except ValueError:
        return None
    if result.returncode != 0 or not streams:
        return False
    try:
        return int(streams[0].get("nb_read_packets") or 0) > 0
    except (TypeError, ValueError):
        return None


def is_usable_video(path: Path) -> bool:
    """Reject incomplete containers without relying on a filename suffix."""
    kind = video_content_type(path)
    if kind == "video/mp4":
        # Two independent questions, and both have to pass.
        #
        # Structural: is the index actually there? Found by walking the boxes,
        # because no fixed window can see a large index at the end of a file.
        #
        # Depth: does it contain media a player can decode? A box walk proves a
        # file is a well-formed MP4, not that it still has its samples -- and
        # that gap is the one this check historically described as covered.
        #
        # An unknown from ffprobe does NOT reject here, and the asymmetry with
        # WebM below is deliberate. MP4 has a real structural check standing
        # behind the probe, so a missing binary loses depth and keeps the file.
        # WebM has no equivalent -- MediaRecorder output can carry no duration
        # header at all -- so there the probe is the only evidence and an
        # unknown has to fail closed. Making ffprobe's absence able to discard a
        # finished, paid render would be a worse bug than the one being fixed.
        if not mp4_has_moov(path):
            return False
        return _probe_decodable_video_packets(path) is not False
    if kind == "video/webm":
        # MediaRecorder WebM can have no duration header. Decodable video
        # packets, rather than a duration or an EBML header alone, prove reuse
        # is safe. ffprobe is already required by this app's video pipeline.
        return _probe_decodable_video_packets(path) is True
    return False


def _missing_object(error: ClientError) -> bool:
    return str(error.response.get("Error", {}).get("Code")) in (
        "404", "NoSuchKey", "NotFound",
    )


def signed_read_url(user_id: str, job_id: str, ttl_seconds: int = 900) -> Optional[str]:
    """Authorize a bounded browser read of this owner's exact private object.

    A small ranged read both confirms existence and detects old WebM objects
    incorrectly uploaded with MP4 metadata. No whole-video buffering is needed.
    Service failures propagate; only a missing object/unconfigured store is None.
    """
    client = _get_client()
    if client is None:
        return None
    key = _object_key(user_id, job_id)
    try:
        response = client.get_object(Bucket=R2_BUCKET_NAME, Key=key, Range="bytes=0-15")
    except ClientError as error:
        if _missing_object(error):
            return None
        raise
    body = response["Body"]
    try:
        head = body.read(16)
    finally:
        body.close()
    content_type = "video/webm" if head.startswith(b"\x1a\x45\xdf\xa3") else "video/mp4"
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": R2_BUCKET_NAME, "Key": key,
                "ResponseContentType": content_type},
        ExpiresIn=max(60, min(int(ttl_seconds), 3600)),
    )


def restore_video(user_id: str, job_id: str, target: Path) -> tuple:
    """Restore exact stored bytes atomically, never destroying a surviving file."""
    client = _get_client()
    if client is None:
        return None, "Cloud storage is not configured."
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.restore")
    try:
        client.download_file(R2_BUCKET_NAME, _object_key(user_id, job_id), str(temp))
        if not is_usable_video(temp):
            return None, "The cloud copy is not a complete playable video."
        temp.replace(target)
        return target, None
    except ClientError as error:
        if _missing_object(error):
            return None, "Cloud copy not found."
        raise
    finally:
        temp.unlink(missing_ok=True)


def delete_video(user_id: str, job_id: str) -> bool:
    """
    Delete a video from R2.

    Returns True if deleted (or didn't exist), False on error.
    """
    if not is_configured():
        return False

    client = _get_client()
    if not client:
        return False

    key = _object_key(user_id, job_id)
    try:
        client.delete_object(Bucket=R2_BUCKET_NAME, Key=key)
        logger.info(f"Deleted video from R2: {key}")
        return True
    except ClientError as e:
        logger.error(f"R2 delete failed for {key}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error deleting from R2 {key}: {e}")
        return False


def video_exists(user_id: str, job_id: str) -> bool:
    """Check whether a video exists in R2."""
    if not is_configured():
        return False

    client = _get_client()
    if not client:
        return False

    key = _object_key(user_id, job_id)
    try:
        client.head_object(Bucket=R2_BUCKET_NAME, Key=key)
        return True
    except ClientError:
        return False
