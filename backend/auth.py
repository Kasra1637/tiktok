"""
Clerk JWT authentication for HookForge's FastAPI backend.

Every authenticated route declares a dependency on `get_current_user_id` which:
1. Extracts the Bearer token from the Authorization header.
2. Validates it against Clerk's JWKS endpoint (public keys are cached).
3. Returns the Clerk `sub` claim (the stable user ID, e.g. "user_2x...").

Public routes (niches, trending, video-models, proxy-thumb) simply don't
declare this dependency and remain unauthenticated.

Environment variable required:
  CLERK_JWKS_URL — your Clerk instance's JWKS endpoint, e.g.
  https://<your-frontend-api>.clerk.accounts.dev/.well-known/jwks.json

  Find it in the Clerk Dashboard -> API Keys -> Advanced -> JWKS URL.

IMPORTANT (event loop): PyJWKClient performs a *synchronous* HTTPS fetch the
first time it needs Clerk's signing keys (and again whenever the cache
expires or a key rotates). Calling that directly from an `async def`
dependency blocks the entire event loop — on a single-worker deployment that
stalls every other in-flight request and can make the platform's health check
time out and recycle the instance (surfacing to users as a 502). All
verification therefore runs in a worker thread via `run_in_threadpool`.
"""
import logging
import os
from typing import Optional

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError
from fastapi import Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CLERK_JWKS_URL = os.environ.get("CLERK_JWKS_URL", "").strip()

# Keep this well under any upstream proxy timeout so a slow Clerk response
# fails fast with a clear error instead of hanging the request.
JWKS_FETCH_TIMEOUT_SECONDS = 8.0

# How long a fetched key set stays valid before it's re-fetched.
JWKS_CACHE_LIFESPAN_SECONDS = 600

if not CLERK_JWKS_URL:
    logger.warning(
        "CLERK_JWKS_URL is not set. Authentication is DISABLED — every request "
        "is treated as user 'anonymous'. Set CLERK_JWKS_URL to your Clerk "
        "instance's JWKS endpoint to enable per-user data isolation."
    )


def _hosted_without_auth() -> bool:
    """True when this process looks hosted but has no Clerk key.

    Reads the environment fresh (not the import-time CLERK_JWKS_URL) so the
    boot guard answers for the process as launched, and so tests can drive
    it with monkeypatched env. Render sets RENDER/RENDER_SERVICE_NAME
    itself — the same signal the database backend uses to tell a dev
    laptop from hosted infra. ENVIRONMENT/APP_ENV covers other hosts.
    """
    if os.environ.get("CLERK_JWKS_URL", "").strip():
        return False
    if os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_NAME"):
        return True
    return os.environ.get(
        "ENVIRONMENT", os.environ.get("APP_ENV", "")).strip().lower() in ("production", "prod")


def ensure_auth_configured() -> None:
    """Refuse to boot hosted without auth. Called once at server boot.

    Anonymous mode exists for local dev and tests, never for production:
    serving every request as 'anonymous' there would merge all users' data.
    Raises RuntimeError naming the fix; local dev and tests (no hosted
    signals) pass through untouched.
    """
    if _hosted_without_auth():
        raise RuntimeError(
            "Refusing to boot: CLERK_JWKS_URL is not set and this looks like a "
            "hosted environment (RENDER/RENDER_SERVICE_NAME present or "
            "ENVIRONMENT/APP_ENV=production). Without it every request is "
            "served as user 'anonymous'. Set CLERK_JWKS_URL to the Clerk "
            "JWKS endpoint."
        )

# PyJWKClient caches the fetched key set in-process, so the blocking fetch
# normally happens only once per lifespan window.
_jwks_client: Optional[PyJWKClient] = None
if CLERK_JWKS_URL:
    _jwks_client = PyJWKClient(
        CLERK_JWKS_URL,
        cache_keys=True,
        cache_jwk_set=True,
        lifespan=JWKS_CACHE_LIFESPAN_SECONDS,
        timeout=JWKS_FETCH_TIMEOUT_SECONDS,
    )

# auto_error=False so a missing header reaches our own handler and produces a
# consistent JSON error shape instead of FastAPI's default 403.
_bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHENTICATED = HTTPException(
    status_code=401,
    detail="Not authenticated. Please sign in.",
    headers={"WWW-Authenticate": "Bearer"},
)


# ---------------------------------------------------------------------------
# Token verification (blocking — always call via run_in_threadpool)
# ---------------------------------------------------------------------------
def _verify_clerk_token_blocking(token: str) -> dict:
    """
    Verify a Clerk-issued RS256 JWT against the instance's public keys.

    Runs in a worker thread because the JWKS fetch is synchronous I/O.
    """
    if not _jwks_client:
        raise HTTPException(status_code=500, detail="Auth is not configured on the server.")

    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
    except PyJWKClientConnectionError as e:
        # We genuinely couldn't reach Clerk. That's our problem, not the
        # user's — 503 tells the client this is transient and retryable.
        logger.error(f"Could not reach Clerk JWKS endpoint: {e}")
        raise HTTPException(
            status_code=503,
            detail="Could not reach the authentication service. Please try again.",
        )
    except (PyJWKClientError, jwt.InvalidTokenError) as e:
        # Malformed token, or its `kid` isn't in this instance's key set (e.g.
        # a token minted by a different Clerk instance). That's a bad
        # credential, so 401 — not 503.
        logger.warning(f"Rejected token, could not match a signing key: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Unexpected error resolving Clerk signing key: {e!r}")
        raise HTTPException(
            status_code=503,
            detail="Could not verify your session right now. Please try again.",
        )

    try:
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={
                # Clerk session tokens don't carry an `aud` by default, and the
                # issuer is implicitly trusted because the signing key came
                # from that instance's own JWKS endpoint.
                "verify_aud": False,
                "verify_iss": False,
            },
            leeway=10,  # tolerate small clock drift between us and Clerk
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Your session expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def _decode(token: str) -> dict:
    """Verify off the event loop so blocking I/O can't stall other requests."""
    return await run_in_threadpool(_verify_clerk_token_blocking, token)


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------
async def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> str:
    """
    Return the authenticated Clerk user ID (the token's `sub` claim).

    When CLERK_JWKS_URL is unset the whole app runs in no-auth mode and this
    returns "anonymous", which keeps local development working without keys.
    When it IS set, a missing or invalid token raises 401.
    """
    if not CLERK_JWKS_URL:
        return "anonymous"

    if credentials is None or not credentials.credentials:
        raise _UNAUTHENTICATED

    payload = await _decode(credentials.credentials)

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
    Like `get_current_user_id`, but returns None instead of raising when the
    caller isn't authenticated. For routes that work signed in or out.
    """
    if not CLERK_JWKS_URL:
        return "anonymous"

    if credentials is None or not credentials.credentials:
        return None

    try:
        payload = await _decode(credentials.credentials)
    except HTTPException:
        return None

    return payload.get("sub")
