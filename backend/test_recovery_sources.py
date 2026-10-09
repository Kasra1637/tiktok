"""
Where a lost render's bytes could still come from, and which of them is tried.

The bug this exists for
-----------------------
`_recovery_sources` returned ONE provider URL, preferring the `video_url` stored
on the row. That stored link is the temporary one, and it expires -- while the
content endpoint re-derivable from `openrouter_job_id` keeps working. So a row
whose stored link had lapsed failed the repair outright, and the error said
"could not be downloaded", indistinguishable from a video that was genuinely
gone. The repair never tried the source that would have worked.

So there are three sources, they die independently, and the repair has to walk
them in order. The dry run's report is pinned here too, because it used to
decide "would repair" from whether a URL STRING was non-empty -- reporting a
live-looking answer for rows that had already lost their only link.
"""

import asyncio
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

# The pure decision module, NOT repair_failed_saves: importing the script loads
# .env and boots the server at module scope, so a test of its logic would run
# against whatever OPENROUTER_API_KEY the developer's machine happened to hold.
# That is not hypothetical -- it made the auth assertion below fail for a
# reason that had nothing to do with the code.
import recovery_report  # noqa: E402


@pytest.fixture(scope="module")
def api():
    """The real module, but never a real network or provider."""
    import importlib
    import os
    import tempfile

    tmpdir = tempfile.mkdtemp(prefix="tiktok-sources-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""
    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    server.pipeline.STORAGE_DIR = Path(tmpdir) / "storage"
    server.pipeline.VIDEOS_DIR = server.pipeline.STORAGE_DIR / "videos"
    server.pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    asyncio.run(server.init_db())
    yield server
    sys.modules.pop("server", None)


def provider_row(**overrides):
    row = {
        "id": "gen-1",
        "video_url": "https://cdn.example/stored.mp4",
        "openrouter_job_id": "job-1",
        "variation_kind": None,
        "r2_url": "",
    }
    row.update(overrides)
    return row


class TestCandidateOrder:
    def test_sources_are_preferred_freshest_first(self, api):
        got = api.provider_download_candidates(provider_row(), "https://cdn.example/fresh.mp4")
        assert [label for label, _ in got] == [
            "fresh poll link",
            "stored provider link",
            "provider content endpoint",
        ]

    def test_the_derived_endpoint_is_built_from_the_job_id(self, api):
        got = dict((label, url) for label, url in api.provider_download_candidates(provider_row()))
        assert got["provider content endpoint"].endswith("/videos/job-1/content?index=0")

    def test_the_same_url_is_not_offered_twice(self, api):
        """
        A fresh poll URL is very often byte-identical to the stored one, and
        retrying a dead link three times before falling through is exactly the
        wasted time the ordered list exists to remove.

        The FIRST label is the one kept, deliberately: when both describe the
        same bytes, "fresh poll link" is the fresher attestation of them, and
        the label is what a failure message will name.
        """
        got = api.provider_download_candidates(
            provider_row(video_url="https://cdn.example/same.mp4"),
            "https://cdn.example/same.mp4",
        )
        urls = [url for _, url in got]
        assert urls.count("https://cdn.example/same.mp4") == 1
        assert [label for label, _ in got] == [
            "fresh poll link", "provider content endpoint",
        ]

    def test_a_row_with_only_a_stored_link_still_offers_the_derived_one(self, api):
        """The case the old code lost: no fresh URL, stored link dead."""
        got = api.provider_download_candidates(provider_row(video_url=""))
        assert [label for label, _ in got] == ["provider content endpoint"]

    def test_a_native_export_has_no_provider_source_at_all(self, api):
        """
        Load-bearing: a Demo + CTA export has no provider rendition, and
        substituting its parent render would hand back a different video than
        the founder exported.
        """
        assert api.provider_download_candidates(provider_row(variation_kind="demo_cta")) == []

    def test_an_app_local_path_is_never_offered_as_a_download(self, api):
        got = api.provider_download_candidates(
            provider_row(video_url="/api/media/videos/gen-1.mp4")
        )
        assert all("/api/media/videos/" not in url for _, url in got)

    def test_a_row_with_nothing_to_go_on_offers_nothing(self, api):
        assert api.provider_download_candidates(
            provider_row(video_url="", openrouter_job_id="")
        ) == []

    def test_recovery_sources_agrees_with_the_candidate_list(self, api):
        """
        The pre-check and the repair must not disagree about what exists, which
        is what happened when one asked for a single URL and the other walked a
        list.
        """
        row = provider_row(video_url="https://cdn.example/stored.mp4")
        durable, first = api._recovery_sources(row)
        assert durable == ""
        assert first == api.provider_download_candidates(row)[0][1]
        assert api._recovery_sources(provider_row(video_url="", openrouter_job_id="")) == ("", "")


class _Recorder:
    """Stands in for the downloader, with a per-URL answer."""

    def __init__(self, answers, real):
        self.answers = answers
        self.real = real
        self.tried = []

    async def __call__(self, url, generation_id):
        self.tried.append(url)
        return self.answers.get(url, (None, "HTTP 404 Not Found"))


@pytest.fixture
def repair_pipeline(api, monkeypatch):
    """Exercise _persist_generation_clip's source walk without any network."""

    def build(answers, **row_overrides):
        row = provider_row(**row_overrides)
        local = api.pipeline.VIDEOS_DIR / f"{row['id']}.mp4"
        # No usable local copy, and no cloud storage, so the walk is reached.
        local.write_bytes(b"not a video")
        recorder = _Recorder(answers, None)
        monkeypatch.setattr(api, "_download_generation_video", recorder)
        monkeypatch.setattr(api.storage_service, "is_configured", lambda: False)
        monkeypatch.setattr(api.storage_service, "is_usable_video", lambda path: False)
        return row, local, recorder

    return build


class TestTheWalkFallsThrough:
    def test_a_dead_stored_link_falls_through_to_the_next_source(self, api, repair_pipeline):
        """
        The bug. The stored link is dead, the derived endpoint is not, and the
        repair used to stop at the first one and report the video as lost.
        """
        derived = api.ai_service.video_content_url("job-1")
        row, _local, recorder = repair_pipeline({
            "https://cdn.example/stored.mp4": (None, "HTTP 403 Forbidden"),
            derived: ("/tmp/recovered.mp4", None),
        })
        stored, error, _ = asyncio.run(api._persist_generation_clip(row, "anonymous"))
        assert recorder.tried == ["https://cdn.example/stored.mp4", derived]
        assert stored is None or isinstance(stored, str)
        # Whatever the upload step did afterwards, the walk itself succeeded.
        assert error is None or "could not be downloaded" not in error

    def test_the_walk_stops_at_the_first_success(self, api, repair_pipeline):
        """
        No point spending a full download on sources behind one that worked.
        """
        derived = api.ai_service.video_content_url("job-1")
        row, _local, recorder = repair_pipeline({
            "https://cdn.example/stored.mp4": ("/tmp/recovered.mp4", None),
            derived: ("/tmp/also.mp4", None),
        })
        asyncio.run(api._persist_generation_clip(row, "anonymous"))
        assert recorder.tried == ["https://cdn.example/stored.mp4"]

    def test_when_every_source_refuses_the_error_names_each_one(self, api, repair_pipeline):
        """
        One flattened sentence cannot distinguish "wait and retry" from "this is
        gone", which are the only two things a founder can do about it.
        """
        row, _local, recorder = repair_pipeline({})
        stored, error, _ = asyncio.run(api._persist_generation_clip(row, "anonymous"))
        assert stored is None
        assert "stored provider link" in error
        assert "provider content endpoint" in error
        assert len(recorder.tried) == 2

    def test_a_native_export_never_reaches_for_a_provider(self, api, repair_pipeline):
        row, _local, recorder = repair_pipeline({}, variation_kind="demo_cta")
        _stored, error, _ = asyncio.run(api._persist_generation_clip(row, "anonymous"))
        assert recorder.tried == []
        assert "cannot be recovered" in error


class TestCameraCutRunsInFinalize:
    """
    The hook-to-middle cut is baked into the canonical file during finalize,
    so the preview and the download carry it — not just captioned composites,
    the only place it used to run (which is why changing its magnitude never
    showed on a raw clip). Fresh downloads only: re-running it on an
    already-cut canonical file would punch twice.
    """

    def _persist_with_stubs(self, api, monkeypatch, tmp_path, row, project_id="proj-cut", project_hook=3):
        from pathlib import Path as _Path

        downloaded = tmp_path / "dl.mp4"

        async def fake_download(url, generation_id):
            downloaded.write_bytes(b"x")
            return str(downloaded), None

        async def fake_rescale(path):
            return _Path(path), []

        calls = []

        async def fake_cut(path, at):
            calls.append((_Path(path).name, at))
            return _Path(path), []

        monkeypatch.setattr(api, "_download_generation_video", fake_download)
        monkeypatch.setattr(api.overlays, "rescale_to_canvas", fake_rescale)
        monkeypatch.setattr(api.overlays, "apply_camera_cut", fake_cut)
        monkeypatch.setattr(api.storage_service, "is_configured", lambda: False)
        monkeypatch.setattr(api.storage_service, "is_usable_video", lambda path: False)
        monkeypatch.setattr(
            api.storage_service, "upload_video",
            lambda *args, **kwargs: "https://cdn.example/saved.mp4",
        )
        if project_hook is not None:
            asyncio.run(api._execute(
                "INSERT INTO studio_projects (id, hook_seconds) VALUES (?, ?)",
                (project_id, project_hook),
            ))
        stored, error, _ = asyncio.run(api._persist_generation_clip(row, "anonymous"))
        return stored, error, calls

    def test_cut_runs_once_with_the_project_boundary(self, api, monkeypatch, tmp_path):
        row = provider_row(studio_project_id="proj-cut-1")
        stored, error, calls = self._persist_with_stubs(
            api, monkeypatch, tmp_path, row, project_id="proj-cut-1")
        assert not error
        assert stored == "https://cdn.example/saved.mp4"
        assert calls == [("dl.mp4", 3.0)]

    def test_no_cut_without_a_known_boundary(self, api, monkeypatch, tmp_path):
        row = provider_row(studio_project_id="proj-cut-missing")
        stored, error, calls = self._persist_with_stubs(
            api, monkeypatch, tmp_path, row, project_id="proj-cut-missing", project_hook=None)
        assert not error
        assert stored == "https://cdn.example/saved.mp4"
        assert calls == []

    def test_cut_is_not_rerun_on_an_already_saved_clip(self, api, monkeypatch, tmp_path):
        from pathlib import Path as _Path

        row = provider_row(studio_project_id="proj-cut-2")
        local = api.pipeline.VIDEOS_DIR / "gen-1.mp4"
        local.write_bytes(b"already canonical")
        monkeypatch.setattr(api.storage_service, "is_usable_video", lambda path: True)
        monkeypatch.setattr(api.storage_service, "is_configured", lambda: False)
        monkeypatch.setattr(
            api.storage_service, "upload_video",
            lambda *args, **kwargs: "https://cdn.example/saved.mp4",
        )
        calls = []

        async def fake_cut(path, at):
            calls.append(at)
            return _Path(path), []

        monkeypatch.setattr(api.overlays, "apply_camera_cut", fake_cut)
        asyncio.run(api._execute(
            "INSERT INTO studio_projects (id, hook_seconds) VALUES (?, ?)", ("proj-cut-2", 3),
        ))
        stored, error, _ = asyncio.run(api._persist_generation_clip(row, "anonymous"))
        assert not error
        assert stored == "https://cdn.example/saved.mp4"
        assert calls == []


class TestDryRunVerdict:
    """
    The report used to decide "would repair" from whether a URL string was
    non-empty, which reports a live-looking answer for rows whose only link had
    already expired.
    """

    def test_a_usable_local_copy_needs_no_download(self):
        text, dead = recovery_report.recovery_verdict(True, False, [])
        assert dead is False
        assert "local copy" in text

    def test_a_local_copy_outranks_a_dead_provider(self):
        text, dead = recovery_report.recovery_verdict(True, False, [("stored provider link", "refused")])
        assert dead is False
        assert "local copy" in text

    def test_a_live_source_is_named(self):
        text, dead = recovery_report.recovery_verdict(
            False, False, [("stored provider link", "refused"),
                           ("provider content endpoint", "alive")])
        assert dead is False
        assert "would repair via provider content endpoint" in text

    def test_an_unchecked_source_is_not_treated_as_dead(self):
        """--no-probe must not turn every row into UNRECOVERABLE."""
        text, dead = recovery_report.recovery_verdict(
            False, False, [("stored provider link", None)])
        assert dead is False
        assert "would repair" in text

    def test_sources_that_all_refuse_are_unrecoverable_now(self):
        text, dead = recovery_report.recovery_verdict(
            False, False, [("stored provider link", "refused"),
                           ("provider content endpoint", "missing")])
        assert dead is True
        assert "UNRECOVERABLE NOW" in text
        # Both are named, so the founder can see there was nowhere left to go.
        assert "stored provider link refused" in text
        assert "provider content endpoint missing" in text

    def test_a_native_export_is_unrecoverable_with_its_own_reason(self):
        text, dead = recovery_report.recovery_verdict(False, True, [])
        assert dead is True
        assert "re-export it in the editor" in text

    def test_no_local_copy_and_no_source_is_unrecoverable(self):
        text, dead = recovery_report.recovery_verdict(False, False, [])
        assert dead is True
        assert "no provider source" in text

    def test_a_rate_limited_source_does_not_claim_the_video_is_gone(self):
        """429 is not a verdict on the link."""
        text, dead = recovery_report.recovery_verdict(
            False, False, [("stored provider link", "unknown")])
        assert dead is False


class TestProbeIsBoundedAndHonest:
    def test_the_probe_does_not_read_the_whole_body(self, api, monkeypatch):
        """
        A server that ignores `Range` will start streaming the entire clip. The
        probe must stop after the first chunk or "check the link" becomes
        "download every video twice".
        """
        import httpx

        chunks_read = []
        big_chunk = b"x" * (1024 * 512)

        class FakeStream:
            status_code = 206

            async def aiter_bytes(self):
                for _ in range(50):  # a 25MB "clip"
                    chunks_read.append(len(big_chunk))
                    yield big_chunk

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

        class FakeClient:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            def stream(self, method, url):
                return FakeStream()

        monkeypatch.setattr(api.httpx, "AsyncClient", FakeClient)
        verdict = asyncio.run(api._probe_media_source("https://cdn.example/a.mp4"))
        assert verdict == "alive"
        assert len(chunks_read) == 1, "the probe read the whole body"

    def test_the_probe_sends_the_same_auth_the_downloader_sends(self, api, monkeypatch):
        """
        Without the bearer token a good link answers 403 and the dry run reports
        a recoverable video as lost -- the exact failure it exists to prevent.
        """
        seen = {}

        class FakeStream:
            def __init__(self, status_code):
                self.status_code = status_code

            async def aiter_bytes(self):
                if False:
                    yield b""

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

        class FakeClient:
            def __init__(self, **kwargs):
                seen["headers"] = kwargs.get("headers", {})

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            def stream(self, method, url):
                return FakeStream(200)

        monkeypatch.setattr(api.httpx, "AsyncClient", FakeClient)
        # Hermetic against worker history: ai_service captures OPENROUTER_API_KEY
        # at import time, so a worker that first imported it via a module that
        # sets no env would otherwise run this auth assertion with an empty key.
        monkeypatch.setattr(api.ai_service, "OPENROUTER_API_KEY", "test-key-not-real")
        url = f"{api.ai_service.OPENROUTER_BASE}/videos/job-1/content?index=0"
        asyncio.run(api._probe_media_source(url))
        assert seen["headers"].get("Authorization"), "no bearer token on a provider probe"
        assert seen["headers"].get("Range") == "bytes=0-0"

    def test_the_probe_does_not_leak_the_key_to_a_third_party(self, api, monkeypatch):
        seen = {}

        class FakeStream:
            status_code = 200

            async def aiter_bytes(self):
                if False:
                    yield b""

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

        class FakeClient:
            def __init__(self, **kwargs):
                seen["headers"] = kwargs.get("headers", {})

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            def stream(self, method, url):
                return FakeStream(200)

        monkeypatch.setattr(api.httpx, "AsyncClient", FakeClient)
        asyncio.run(api._probe_media_source("https://cdn.example/a.mp4"))
        assert not seen["headers"].get("Authorization")

    @pytest.mark.parametrize("code,expected", [
        (200, "alive"), (206, "alive"), (403, "refused"), (401, "refused"),
        (404, "missing"), (410, "missing"), (429, "unknown"), (503, "server-error"),
    ])
    def test_statuses_map_to_meaningful_words(self, api, monkeypatch, code, expected):
        class FakeStream:
            status_code = code

            async def aiter_bytes(self):
                if False:
                    yield b""

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

        class FakeClient:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            def stream(self, method, url):
                return FakeStream()

        monkeypatch.setattr(api.httpx, "AsyncClient", FakeClient)
        assert asyncio.run(api._probe_media_source("https://cdn.example/a.mp4")) == expected

    def test_an_unreachable_host_is_distinguished_from_a_refusal(self, api, monkeypatch):
        """
        A DNS or connection failure and a 403 need different conclusions about
        whether to wait.
        """

        class FakeClient:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                raise OSError("no route to host")

            async def __aexit__(self, *exc):
                return False

        monkeypatch.setattr(api.httpx, "AsyncClient", FakeClient)
        assert asyncio.run(api._probe_media_source("https://nowhere.invalid/a.mp4")) == "unreachable"
