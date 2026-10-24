"""
Structured request logs, export outcome counters, and the metrics read.

What these pin: every request logs one line carrying its request id and its
duration; a completed Demo + CTA export save bumps `export_completed` and a
rejected one bumps `export_failed`; and `GET /api/metrics` exposes both next
to request volume. Counters are observability only — they never gate a save.
"""
import asyncio
import importlib
import io
import logging
import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

ANON = "anonymous"

MP4_BYTES = bytes(range(256)) * 8


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-observability-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""
    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    server.pipeline.VIDEOS_DIR = Path(tmpdir) / "videos"
    server.pipeline.GENERATED_DIR = Path(tmpdir) / "generated"
    server.pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    server.pipeline.GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    asyncio.run(server.init_db())
    try:
        yield server
    finally:
        sys.modules.pop("server", None)


@pytest.fixture(autouse=True)
def _fresh_counters(api):
    api.observability.reset_metrics()
    yield


def _run(coro):
    return asyncio.run(coro)


def _upload(name="hookforge-demo-cta.mp4", data=MP4_BYTES):
    from starlette.datastructures import UploadFile

    return UploadFile(filename=name, file=io.BytesIO(data))


def _fake_request(path="/api/health", method="GET", request_id=None):
    from starlette.requests import Request

    headers = [(b"x-request-id", request_id.encode())] if request_id else []
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers,
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }

    async def receive():
        return {"type": "http.disconnect"}

    return Request(scope, receive)


class TestRouterRegistration:
    def test_health_and_metrics_are_served_once_from_the_router(self, api):
        """Guards the extraction: one GET each, no duplicate registration
        from both the router and the composition root, no dropped prefix."""
        for path in ("/api/health", "/api/metrics"):
            hits = [
                (getattr(r, "path", ""), sorted(getattr(r, "methods", None) or []))
                for r in api.app.routes
                if getattr(r, "path", "") == path
            ]
            assert hits == [(path, ["GET"])], (path, hits)


class TestRequestLogging:
    def test_each_request_logs_one_line_with_id_and_duration(self, api, caplog):
        from starlette.responses import JSONResponse

        async def call_next(request):
            return JSONResponse({"ok": True})

        with caplog.at_level(logging.INFO, logger="hookforge.requests"):
            response = _run(
                api.observability.request_logging_middleware(
                    _fake_request("/api/health"), call_next
                )
            )
        assert response.status_code == 200
        lines = [
            r for r in caplog.records if r.name == "hookforge.requests"
        ]
        assert len(lines) == 1
        message = lines[0].getMessage()
        assert "request_id=" in message
        assert "duration_ms=" in message
        assert "method=GET" in message
        assert "path=/api/health" in message
        assert "status=200" in message
        assert api.observability.get_metrics()["requests_total"] == 1

    def test_a_caller_supplied_request_id_is_honored_and_echoed(self, api, caplog):
        from starlette.responses import JSONResponse

        async def call_next(request):
            return JSONResponse({"ok": True})

        with caplog.at_level(logging.INFO, logger="hookforge.requests"):
            response = _run(
                api.observability.request_logging_middleware(
                    _fake_request("/api/metrics", request_id="repro-123"),
                    call_next,
                )
            )
        assert response.headers["X-Request-ID"] == "repro-123"
        logged = [
            r.getMessage()
            for r in caplog.records
            if r.name == "hookforge.requests"
        ]
        assert logged and "request_id=repro-123" in logged[0]

    def test_a_minted_request_id_is_echoed_back(self, api):
        from starlette.responses import JSONResponse

        async def call_next(request):
            return JSONResponse({"ok": True})

        response = _run(
            api.observability.request_logging_middleware(
                _fake_request("/api/health"), call_next
            )
        )
        assert response.headers["X-Request-ID"]

    def test_failures_still_log_before_propagating(self, api, caplog):
        async def boom(request):
            raise RuntimeError("downstream blew up")

        with caplog.at_level(logging.INFO, logger="hookforge.requests"):
            with pytest.raises(RuntimeError):
                _run(
                    api.observability.request_logging_middleware(
                        _fake_request("/api/demo-cta-result"), boom
                    )
                )
        logged = [
            r.getMessage()
            for r in caplog.records
            if r.name == "hookforge.requests"
        ]
        assert logged and "request_id=" in logged[0] and "duration_ms=" in logged[0]


class TestExportCounters:
    def test_a_completed_export_increments_completed(self, api):
        result = _run(
            api.save_demo_cta_export(file=_upload(), user_id=ANON)
        )
        assert result["status"] == "completed"
        snapshot = api.observability.get_metrics()
        assert snapshot["export_completed"] == 1
        assert snapshot["export_failed"] == 0

    def test_a_rejected_export_increments_failed_not_completed(self, api):
        with pytest.raises(HTTPException):
            _run(
                api.save_demo_cta_export(
                    file=_upload(name="notes.txt", data=b"not a video"),
                    user_id=ANON,
                )
            )
        snapshot = api.observability.get_metrics()
        assert snapshot["export_completed"] == 0
        assert snapshot["export_failed"] == 1

    def test_an_empty_export_also_counts_as_failed(self, api):
        with pytest.raises(HTTPException):
            _run(api.save_demo_cta_export(file=_upload(data=b""), user_id=ANON))
        assert api.observability.get_metrics()["export_failed"] == 1

    def test_metrics_read_reports_counters_next_to_request_volume(self, api):
        _run(api.save_demo_cta_export(file=_upload(), user_id=ANON))
        with pytest.raises(HTTPException):
            _run(
                api.save_demo_cta_export(
                    file=_upload(name="notes.txt", data=b"not a video"),
                    user_id=ANON,
                )
            )
        out = _run(api.read_metrics(user_id=ANON))
        assert out["export_completed"] == 1
        assert out["export_failed"] == 1
        assert isinstance(out["uptime_seconds"], (int, float))
