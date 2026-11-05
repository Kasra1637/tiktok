"""
Structured request logs plus export outcome counters.

Two pieces of operational visibility the app was missing:

1. Every request logs one line with its method, path, status, duration and a
   request id (honoring an incoming ``X-Request-ID`` when the caller supplies
   one). Fail-loud debugging starts with knowing which line in the log was
   *your* request and how long it took.

2. Native Demo + CTA export outcomes are counted in memory
   (``export_completed`` / ``export_failed``) and readable through the
   health-adjacent ``GET /api/metrics``. A rising failure count next to flat
   completions is the signal that the export path broke, without grepping.

Both are observability only: the middleware never changes a response body or
status (it only adds the echoed ``X-Request-ID`` header), and the counters
never gate anything. Counters are process-local on purpose — this deploys as
one worker, and a deploy resets them the same way it resets everything else.
"""
import contextvars
import functools
import logging
import time
import uuid

request_logger = logging.getLogger("hookforge.requests")

_boot_time = time.time()

# Correlation id for the in-flight request. Set by the middleware, readable
# anywhere (including deep in _submit_generation) via current_request_id().
_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)

_counters = {
    "requests_total": 0,
    "export_completed": 0,
    "export_failed": 0,
}


def current_request_id() -> str:
    """Return the id of the in-flight request, or '' outside one."""
    return _request_id_var.get()


def set_request_id(request_id: str) -> contextvars.Token:
    """Bind a request id for the current context. Returns a reset token."""
    return _request_id_var.set(request_id or "")


def reset_request_id(token: contextvars.Token) -> None:
    try:
        _request_id_var.reset(token)
    except Exception:
        pass


def reset_metrics() -> None:
    """Zero every counter. Tests only — production counts from boot."""
    for key in _counters:
        _counters[key] = 0


def record_export_result(success: bool) -> None:
    """Count one finished Demo + CTA export save, success or failure."""
    _counters["export_completed" if success else "export_failed"] += 1


def get_metrics() -> dict:
    """Snapshot of counters plus process uptime. Pure read, safe to expose."""
    return {
        **_counters,
        "uptime_seconds": round(time.time() - _boot_time, 1),
    }


def track_demo_cta_export(func):
    """Count every Demo + CTA export save as completed or failed.

    Applied to the save handler, not the route: validation rejections
    (HTTPException) and unexpected errors both count as failed, a returned
    row counts as completed. Reraises everything, so happy paths behave
    exactly as before — this only observes.
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            result = await func(*args, **kwargs)
        except Exception:
            record_export_result(False)
            raise
        record_export_result(True)
        return result

    return wrapper


async def request_logging_middleware(request, call_next):
    """One structured log line per request: method, path, status, id, time.

    The id comes from the caller's ``X-Request-ID`` when present so a browser
    repro can be matched to its server line; otherwise a random 12-hex id is
    minted. The same id is echoed back as a response header.
    """
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    token = set_request_id(request_id)
    try:
        request.state.request_id = request_id
    except Exception:
        pass
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        request_logger.info(
            "request method=%s path=%s status=500 request_id=%s duration_ms=%.1f",
            request.method,
            request.url.path,
            request_id,
            duration_ms,
        )
        raise
    finally:
        reset_request_id(token)
    duration_ms = (time.perf_counter() - start) * 1000
    _counters["requests_total"] += 1
    request_logger.info(
        "request method=%s path=%s status=%s request_id=%s duration_ms=%.1f",
        request.method,
        request.url.path,
        response.status_code,
        request_id,
        duration_ms,
    )
    try:
        response.headers["X-Request-ID"] = request_id
    except Exception:
        pass
    return response
