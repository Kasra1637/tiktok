"""
Clerk JWT authentication for HookForge's FastAPI backend.

Every authenticated route declares a dependency on `get_current_user_id` which:
1. Extracts the Bearer token from the Authorization header.
2. Validates it against Clerk's JWKS endpoint (caches the public keys).
3. Returns the Clerk `sub` claim (the stable user ID, e.g. "user_2x...").

Public routes (niches, trending, video-models, proxy-thumb) simply don't
declare this dependency and remain unauthenticated.

Environment variable required:
  CLERK_JWKS_URL — your Clerk instance's JWKS endpoint, e.g.
  https://<your-frontend-api>.clerk.accounts.dev/.well-known/jwks.json

  You can find this in your Clerk Dashboard -> API Keys -> Advanced -> JWKS URL.
"""
import logging
import os
from typing import Optional

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CLERK_JWKS_URL = os.environ.get("CLERK_JWKS_URL", "")

if not CLERK_JWKS_URL:
    logger.warning(
        "CLERK_JWKS_URL is not set. Authentication will be DISABLED — all requests "
        "will be treated as user 'anonymous'. Set CLERK_JWKS_URL to your Clerk "
        "instance's JWKS endpoint to enable per-user data isolation."
    )

# PyJWKClient fetches and caches the JWKS keys from Clerk's well-known endpoint.
_jwks_client: Optional[PyJWKClient] = None
if CLERK_JWKS_URL:
    _jwks_client = PyJWKClient(CLERK_JWKS_URL, cache_keys=True)

# HTTPBearer extracts the token from the Authorization header; auto_error=False
# lets us handle missing tokens gracefully in dev mode.
_bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------
def _verify_clerk_token(token: str) -> dict:
    """
    Verify a Clerk-issued JWT and return its payload.

    Clerk tokens are short-lived RS256 JWTs signed with the instance's private
    key. We verify them against the public keys served from the JWKS endpoint.
    """
    if not _jwks_client:
        raise HTTPException(status_code=500, detail="Auth not configured on server.")

    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={
                "verify_aud": False,  # Clerk tokens don't always have an audience claim
                "verify_iss": False,  # We trust the JWKS endpoint implicitly
                "leeway": 10,         # 10 seconds clock drift tolerance
            },
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# FastAPI Dependencies
# ---------------------------------------------------------------------------
async def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> str:
    """
    FastAPI dependency that returns the authenticated Clerk user ID.

    If CLERK_JWKS_URL is not configured (local dev without Clerk), returns
    "anonymous" so the app remains functional for development.

    If CLERK_JWKS_URL IS configured but the request has no valid token,
    raises 401.
    """
    # Dev/unconfigured mode: no auth enforcement
    if not CLERK_JWKS_URL:
        return "anonymous"

    # Auth is configured but token is missing
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated. Please sign in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify the token and extract user ID
    payload = _verify_clerk_token(credentials.credentials)

    # The `sub` claim is the stable Clerk user ID (e.g. "user_2xABC...")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid token: missing user identifier.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_id


async def get_optional_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Optional[str]:
    """
    Like get_current_user_id but returns None instead of raising 401 when
    the user is not authenticated. Used for routes that work both ways
    (e.g. public discovery feed that can optionally scope results).
    """
    if not CLERK_JWKS_URL:
        return "anonymous"

    if credentials is None:
        return None

    try:
        payload = _verify_clerk_token(credentials.credentials)
        return payload.get("sub")
    except HTTPException:
        return None
