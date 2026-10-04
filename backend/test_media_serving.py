"""
Byte-range serving for generated clips.

A video element is the only media consumer that REQUIRES `Accept-Ranges` and a
`206`. Without them Chrome renders the first frame, reports 0:00, and leaves
the play button inert — while "Download MP4" beside it, a plain GET that saves
bytes, works fine. That was not a bad file: every clip under /api/media is
served by a StaticFiles mount that has no range support at all, so the route in
server.py exists to answer the headers a player needs.

These call the route function directly with a hand-built Request, because the
suite has no HTTP client and adding one for four header assertions would be a
larger change than the behaviour under test.
"""
import asyncio
import importlib
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

ANON = "anonymous"

# Deliberately not a real mp4: nothing here decodes the file, and the bytes
# have to be exactly checkable so a partial response can be proven byte-exact
# rather than merely "some bytes".
CLIP_BYTES = bytes(range(256)) * 8  # 2048 bytes, every value distinct enough


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-media-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""

    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # The route resolves against pipeline.VIDEOS_DIR, which is a module
    # constant pointing at the real storage/videos. Redirect it so a test clip
    # never lands there.
    original_dir = server.pipeline.VIDEOS_DIR
    server.pipeline.VIDEOS_DIR = Path(tmpdir) / "videos"
    server.pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

    asyncio.run(server.init_db())
    try:
        yield server
    finally:
        server.pipeline.VIDEOS_DIR = original_dir
        sys.modules.pop("server", None)


def _run(coro):
    return asyncio.run(coro)


def _request(range_header=None):
    raw = [(b"host", b"testserver"), (b"user-agent", b"pytest")]
    if range_header is not None:
        raw.append((b"range", range_header.encode()))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/media/videos/clip.mp4",
        "raw_path": b"/api/media/videos/clip.mp4",
        "query_string": b"",
        "root_path": "",
        "headers": raw,
        "client": ("test", 1),
        "server": ("testserver", 80),
    }
    return Request(scope)


def _write_clip(api, name="clip.mp4", data=CLIP_BYTES):
    path = api.pipeline.VIDEOS_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


async def _body(response):
    """
    Collect the bytes this response would send.

    A StreamingResponse (the 206 path) carries its iterator already, so it is
    consumed directly. FileResponse (the 200 path) only builds its iterator
    when called, and driving it through ASGI is the honest way to see what a
    player receives — so that is done instead, rather than reading the file a
    second time and assuming the response would have sent it.
    """
    iterator = getattr(response, "body_iterator", None)
    if iterator is not None:
        chunks = []
        async for chunk in iterator:
            chunks.append(chunk if isinstance(chunk, bytes) else str(chunk).encode())
        return b"".join(chunks)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/media/videos/clip.mp4",
        "raw_path": b"/api/media/videos/clip.mp4",
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("test", 1),
        "server": ("testserver", 80),
    }
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await response(scope, receive, send)
    return b"".join(
        m.get("body", b"")
        for m in messages
        if m["type"] == "http.response.body"
    )


def _serve(api, filename="clip.mp4", range_header=None):
    return _run(_serve_async(api, filename, range_header))


async def _serve_async(api, filename, range_header):
    response = await api.serve_video(filename, _request(range_header))
    body = await _body(response)
    return response, body


class TestRangeServing:
    def test_a_plain_request_gets_the_whole_file_and_learns_ranges_exist(self, api):
        """
        The plain case still has to advertise ranges. A player decides it can
        seek from this header alone, so omitting it is what produced the dead
        play button even on requests that "worked".
        """
        _write_clip(api)
        response, body = _serve(api)
        assert response.status_code == 200
        assert response.headers["accept-ranges"] == "bytes"
        assert response.headers["content-type"] == "video/mp4"
        assert body == CLIP_BYTES

    def test_a_range_request_returns_206_and_exactly_those_bytes(self, api):
        _write_clip(api)
        response, body = _serve(api, range_header="bytes=0-99")
        assert response.status_code == 206
        assert response.headers["content-range"] == f"bytes 0-99/{len(CLIP_BYTES)}"
        assert response.headers["accept-ranges"] == "bytes"
        assert int(response.headers["content-length"]) == 100
        assert body == CLIP_BYTES[:100]

    def test_an_open_ended_range_runs_to_the_end_of_the_file(self, api):
        _write_clip(api)
        start = len(CLIP_BYTES) - 10
        response, body = _serve(api, range_header=f"bytes={start}-")
        assert response.status_code == 206
        assert response.headers["content-range"] == f"bytes {start}-{len(CLIP_BYTES) - 1}/{len(CLIP_BYTES)}"
        assert body == CLIP_BYTES[start:]

    def test_a_suffix_range_returns_the_tail(self, api):
        _write_clip(api)
        response, body = _serve(api, range_header="bytes=-16")
        assert response.status_code == 206
        assert body == CLIP_BYTES[-16:]

    def test_a_range_past_the_end_is_refused_and_says_how_long_the_file_is(self, api):
        """
        416, not a 200. Answering an unsatisfiable range with the whole file
        would hand the player a body it did not ask for and let it believe the
        request succeeded; `Content-Range: bytes */total` is what tells it the
        real file length so it can retry sanely.
        """
        _write_clip(api)
        response, _ = _serve(api, range_header="bytes=99999-100000")
        assert response.status_code == 416
        assert response.headers["content-range"] == f"bytes */{len(CLIP_BYTES)}"

    def test_an_end_before_the_start_is_refused(self, api):
        _write_clip(api)
        response, _ = _serve(api, range_header="bytes=100-10")
        assert response.status_code == 416

    def test_a_multi_range_request_falls_back_to_the_whole_file(self, api):
        """
        Answering only the first range of a multi-range request would be worse
        than not answering it: the client asked for two pieces and would be sent
        one. The whole file is a valid answer to a range it can ignore.
        """
        _write_clip(api)
        response, body = _serve(api, range_header="bytes=0-9,20-29")
        assert response.status_code == 200
        assert body == CLIP_BYTES

    def test_a_nonsense_range_falls_back_to_the_whole_file(self, api):
        _write_clip(api)
        response, body = _serve(api, range_header="bytes=not-a-number")
        assert response.status_code == 200
        assert body == CLIP_BYTES


class TestAccessAndSafety:
    def test_a_traversing_filename_is_refused(self, api):
        """
        The route resolves a name from the URL, so the name itself has to be
        validated rather than trusted to the filesystem. A 404 (not a 403) so
        the route does not confirm whether the target exists.
        """
        for name in (
            "../secrets.env",
            "..%2Fsecrets.env",
            "nested/clip.mp4",
            "clip.mp4.txt",
            "",
        ):
            with pytest.raises(HTTPException) as err:
                _serve(api, filename=name)
            assert err.value.status_code == 404, name

    def test_a_missing_clip_is_a_404(self, api):
        with pytest.raises(HTTPException) as err:
            _serve(api, filename=f"{uuid.uuid4()}.mp4")
        assert err.value.status_code == 404

    def test_an_empty_clip_is_a_404_rather_than_an_empty_200(self, api):
        """
        A zero-byte body with a video content type gives the player a file it
        cannot decode, which is the same dead control in a different guise.
        """
        _write_clip(api, name="empty.mp4", data=b"")
        with pytest.raises(HTTPException) as err:
            _serve(api, filename="empty.mp4")
        assert err.value.status_code == 404

    def test_the_clip_is_cached_hard_because_its_bytes_never_change(self, api):
        """
        The id is the filename, so the content is immutable. This replaced the
        provider's unsigned URL, which expired — the reason the panel warns that
        a durable copy matters.
        """
        _write_clip(api)
        response, _ = _serve(api)
        assert "immutable" in response.headers["cache-control"]


class TestRangeParsing:
    @pytest.mark.parametrize(
        "header,total,expected",
        [
            ("bytes=0-0", 10, ("ok", (0, 0))),
            ("bytes=0-", 10, ("ok", (0, 9))),
            ("bytes=9-9", 10, ("ok", (9, 9))),
            ("bytes=-1", 10, ("ok", (9, 9))),
            # An end past the file is clamped, not refused: the client asked for
            # "up to here" and there is simply nothing beyond the end.
            ("bytes=5-999", 10, ("ok", (5, 9))),
            # A suffix longer than the file is the whole file.
            ("bytes=-999", 10, ("ok", (0, 9))),
            ("bytes=10-20", 10, ("unsatisfiable", None)),
            ("bytes=20-30", 10, ("unsatisfiable", None)),
            ("bytes=8-2", 10, ("unsatisfiable", None)),
            ("", 10, ("none", None)),
            ("items=0-1", 10, ("none", None)),
            ("bytes=abc-def", 10, ("none", None)),
            ("bytes=0-1,4-5", 10, ("none", None)),
            ("bytes=-", 10, ("none", None)),
        ],
    )
    def test_classification(self, api, header, total, expected):
        assert api._parse_byte_range(header, total) == expected