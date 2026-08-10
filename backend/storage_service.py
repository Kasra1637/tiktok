"""
Cloudflare R2 object storage service for persisting generated videos.

R2 is S3-compatible, so we use boto3 with a custom endpoint URL. Videos are
stored at: {user_id}/{job_id}.mp4 — giving each user their own namespace.

Required environment variables:
    R2_ACCOUNT_ID       — Cloudflare account ID (32-char hex)
    R2_ACCESS_KEY_ID    — R2 API token access key
    R2_SECRET_ACCESS_KEY — R2 API token secret key
    R2_BUCKET_NAME      — Bucket name (e.g. "hookforge-videos")
    R2_PUBLIC_URL       — (Optional) Custom domain or public bucket URL for
                          serving videos. If unset, generates a path-style URL
                          from the account endpoint.

When R2 is not configured (env vars missing), all functions return None/False
gracefully so the app still works — videos just won't persist across deploys.
"""
import logging
import os
from pathlib import Path
from typing import Optional

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
            retries={"max_attempts": 2, "mode": "standard"},
        ),
        region_name="auto",
    )


def _object_key(user_id: str, job_id: str) -> str:
    """Build the R2 object key: {user_id}/{job_id}.mp4"""
    return f"{user_id}/{job_id}.mp4"


def public_url(user_id: str, job_id: str) -> str:
    """Build the public URL for a stored video."""
    key = _object_key(user_id, job_id)
    if R2_PUBLIC_URL:
        return f"{R2_PUBLIC_URL}/{key}"
    # Fallback: R2 dev endpoint (requires bucket to have public access enabled)
    return f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com/{R2_BUCKET_NAME}/{key}"


def upload_video(user_id: str, job_id: str, video_path: Path) -> Optional[str]:
    """
    Upload a video file to R2.

    Args:
        user_id: The authenticated user's ID (namespace prefix).
        job_id: The video generation job ID (unique filename).
        video_path: Local path to the .mp4 file.

    Returns:
        The public URL of the uploaded video, or None if upload failed or R2
        is not configured.
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
                "ContentType": "video/mp4",
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
