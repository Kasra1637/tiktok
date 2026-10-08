"""
Reconciling renders stranded by a dead container.

The bug this exists for
-----------------------
A render is resolved only by polling -- poll_generation is the single path that
downloads the clip, uploads it to R2 and flips the row to `completed`. Polling
lived only in the studio GenerationPanel, on a project page, for that project's
newest row. So a render whose container died mid-flight was never polled again by
anything: the provider finished it, the bytes existed, the money was spent, and
the row sat at `generating` forever with no error and no repair affordance. Two
paid renders (HeyGen, Grok Lite) sat that way for four days.

These pin the properties that make the startup sweep safe rather than a new way
to break the box:

  It only touches rows that are genuinely stranded. A render still in flight is
  not polled early -- that spends provider calls for no gain and races the real
  thing.
  It never runs alongside a repair the founder asked for, and never runs two
  passes over one clip. _FFMPEG_SLOT already serializes the encodes; the
  single-flight guard stops them fighting over the same local file.
  One bad row cannot abandon the rest, and cannot fail a deploy.
"""

import asyncio
import importlib
import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

OWNER = "owner-user"


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-sweep-")
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
    server.pipeline.ASSETS_DIR = server.pipeline.STORAGE_DIR / "assets"
    server.pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    server.pipeline.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    asyncio.run(server.init_db())
    yield server
    sys.modules.pop("server", None)


def _run(coro):
    return asyncio.run(coro)


async def _insert(api, *, status, job_id, age_seconds, user_id=OWNER):
    """A generation row with its age set explicitly, since the sweep filters on it."""
    gen_id = str(uuid.uuid4())
    created = (datetime.now(timezone.utc) - timedelta(seconds=age_seconds)).isoformat()
    await api._execute(
        "INSERT INTO generations (id, status, openrouter_job_id, user_id, created_at, "
        "requested_at, started_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (gen_id, status, job_id, user_id, created, created, created, created),
    )
    return gen_id


@pytest.fixture(autouse=True)
def clean_generations(api):
    """
    Clear the generations table around each test.

    The fixture's database is module-scoped, and the sweep reads the WHOLE table
    by design -- that is the point of it. So a row left behind by an earlier test
    is a candidate row, and any test asserting "the sweep found nothing" would see
    a neighbour's stranded render and fail for the wrong reason. Each test has to
    see only the rows it created.
    """
    _run(api._execute("DELETE FROM generations"))
    yield
    _run(api._execute("DELETE FROM generations"))


class TestWhatCountsAsStranded:
    def test_a_long_lived_in_flight_row_is_reconciled(self, api, monkeypatch):
        """The actual bug: provider finished, container died, row never updated."""
        gen_id = _run(_insert(api, status="generating", job_id="gen-vid-1", age_seconds=7200))
        seen = []

        async def fake_poll(generation_id, user_id=None):
            seen.append((generation_id, user_id))
            return {"status": "completed"}

        monkeypatch.setattr(api, "poll_generation", fake_poll)
        assert _run(api._sweep_stranded_generations()) == 1
        assert seen == [(gen_id, OWNER)]

    def test_a_fresh_render_is_left_alone(self, api, monkeypatch):
        """
        A render that is genuinely still going must not be polled early. The
        threshold sits far above the slowest render on purpose.
        """
        _run(_insert(api, status="generating", job_id="gen-vid-fresh", age_seconds=60))
        monkeypatch.setattr(
            api, "poll_generation",
            lambda *a, **k: pytest.fail("a fresh in-flight render must not be polled"),
        )
        assert _run(api._sweep_stranded_generations()) == 0

    def test_a_never_submitted_row_is_skipped(self, api, monkeypatch):
        """
        No openrouter_job_id means nothing was ever submitted, so there is nothing
        at the provider to reconcile. Polling it would fail forever and burn a slot.
        """
        _run(_insert(api, status="generating", job_id=None, age_seconds=7200))
        monkeypatch.setattr(
            api, "poll_generation",
            lambda *a, **k: pytest.fail("a row with no provider job must not be polled"),
        )
        assert _run(api._sweep_stranded_generations()) == 0

    def test_finished_and_failed_rows_are_untouched(self, api, monkeypatch):
        """Only in-flight statuses are candidates; everything else is already settled."""
        for status in ("completed", "failed", "expired", "archived"):
            _run(_insert(api, status=status, job_id=f"gen-vid-{status}", age_seconds=7200))
        monkeypatch.setattr(
            api, "poll_generation",
            lambda *a, **k: pytest.fail(f"a {status} row must not be polled"),
        )
        assert _run(api._sweep_stranded_generations()) == 0

    def test_the_rows_owner_is_used_not_the_caller(self, api, monkeypatch):
        """
        poll_generation scopes its row lookup by user_id, so passing the wrong
        owner finds nothing and the row silently fails to reconcile.
        """
        gen_id = _run(
            _insert(api, status="generating", job_id="gen-vid-owner", age_seconds=7200,
                    user_id="someone-else")
        )
        seen = []

        async def fake_poll(generation_id, user_id=None):
            seen.append(user_id)
            return {"status": "completed"}

        monkeypatch.setattr(api, "poll_generation", fake_poll)
        _run(api._sweep_stranded_generations())
        assert seen == ["someone-else"]
        assert gen_id


class TestTheSweepStaysBounded:
    def test_the_pass_is_capped(self, api, monkeypatch):
        """
        A single cold start firing dozens of repairs at once is the exact overload
        the ffmpeg gate exists to prevent. A backlog drains across restarts.
        """
        for i in range(6):
            _run(_insert(api, status="generating", job_id=f"gen-vid-cap-{i}", age_seconds=7200 + i))
        polled = []

        async def fake_poll(generation_id, user_id=None):
            polled.append(generation_id)
            return {"status": "generating"}

        monkeypatch.setattr(api, "poll_generation", fake_poll)
        _run(api._sweep_stranded_generations(limit=3))
        assert len(polled) == 3

    def test_oldest_first(self, api, monkeypatch):
        """
        A row stranded longest is most likely to have lost its provider link, so
        the limited passes go to the rows most at risk.
        """
        older = _run(_insert(api, status="generating", job_id="gen-vid-older", age_seconds=9000))
        newer = _run(_insert(api, status="generating", job_id="gen-vid-newer", age_seconds=3601))
        polled = []

        async def fake_poll(generation_id, user_id=None):
            polled.append(generation_id)
            return {"status": "generating"}

        monkeypatch.setattr(api, "poll_generation", fake_poll)
        _run(api._sweep_stranded_generations(limit=1))
        assert polled == [older]

    def test_repeated_polls_do_not_keep_a_row_permanently_eligible(self, api, monkeypatch):
        """
        Ordering is on created_at, never updated_at. A poll bumps updated_at, so
        ordering on it would make a repeatedly-polled row look fresh forever and
        it could never age out -- a sweep that silently stops working.
        """
        gen_id = _run(_insert(api, status="generating", job_id="gen-vid-age", age_seconds=7200))
        _run(api._execute(
            "UPDATE generations SET updated_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), gen_id),
        ))
        polled = []

        async def fake_poll(generation_id, user_id=None):
            polled.append(generation_id)
            return {"status": "generating"}

        monkeypatch.setattr(api, "poll_generation", fake_poll)
        _run(api._sweep_stranded_generations())
        assert polled == [gen_id], "an updated_at bump must not reset the age clock"


class TestTheSweepCannotMakeThingsWorse:
    def test_a_row_being_repaired_by_hand_is_skipped(self, api, monkeypatch):
        """
        A founder clicking "Retry durable save" and a startup sweep landing on the
        same clip at once is how a good download becomes a half-written file.
        """
        gen_id = _run(_insert(api, status="generating", job_id="gen-vid-busy", age_seconds=7200))

        async def fake_poll(generation_id, user_id=None):
            pytest.fail("must not poll a row already being repaired")

        monkeypatch.setattr(api, "poll_generation", fake_poll)
        api._storage_repairs_in_flight.add(gen_id)
        try:
            assert _run(api._sweep_stranded_generations()) == 0
        finally:
            api._storage_repairs_in_flight.discard(gen_id)

    def test_the_single_flight_guard_is_released(self, api, monkeypatch):
        """
        A guard leaked by the sweep would permanently block the founder's own
        "Retry durable save" for that clip, and there is no error to explain why.
        """
        gen_id = _run(_insert(api, status="generating", job_id="gen-vid-leak", age_seconds=7200))

        async def fake_poll(generation_id, user_id=None):
            return {"status": "completed"}

        monkeypatch.setattr(api, "poll_generation", fake_poll)
        _run(api._sweep_stranded_generations())
        assert gen_id not in api._storage_repairs_in_flight

    def test_the_guard_is_released_even_when_a_row_raises(self, api, monkeypatch):
        gen_id = _run(_insert(api, status="generating", job_id="gen-vid-raise", age_seconds=7200))

        async def boom(generation_id, user_id=None):
            raise RuntimeError("provider unreachable")

        monkeypatch.setattr(api, "poll_generation", boom)
        _run(api._sweep_stranded_generations())
        assert gen_id not in api._storage_repairs_in_flight

    def test_one_bad_row_does_not_abandon_the_rest(self, api, monkeypatch):
        """
        A single unreachable row must not cost every other stranded render its
        chance on the same boot.
        """
        first = _run(_insert(api, status="generating", job_id="gen-vid-a1", age_seconds=9000))
        second = _run(_insert(api, status="generating", job_id="gen-vid-a2", age_seconds=8900))
        polled = []

        async def fake_poll(generation_id, user_id=None):
            polled.append(generation_id)
            if generation_id == first:
                raise RuntimeError("provider unreachable")
            return {"status": "completed"}

        monkeypatch.setattr(api, "poll_generation", fake_poll)
        assert _run(api._sweep_stranded_generations()) == 1
        assert polled == [first, second]

    def test_a_row_still_rendering_at_the_provider_is_not_counted_as_fixed(self, api, monkeypatch):
        """The common harmless case: the provider is simply still working on it."""
        _run(_insert(api, status="generating", job_id="gen-vid-live", age_seconds=7200))

        async def fake_poll(generation_id, user_id=None):
            return {"status": "generating"}

        monkeypatch.setattr(api, "poll_generation", fake_poll)
        assert _run(api._sweep_stranded_generations()) == 0

    def test_a_sweep_that_cannot_run_never_breaks_startup(self, api, monkeypatch):
        """
        The startup wrapper has to swallow everything. An exception escaping here
        would fail the deploy over a reconciliation nicety, which is a far worse
        outcome than skipping the sweep.
        """
        async def boom(*_a, **_k):
            raise RuntimeError("sweep exploded")

        monkeypatch.setattr(api, "_sweep_stranded_generations", boom)
        _run(api._sweep_stranded_generations_safely())  # must not raise

    def test_the_sweep_goes_through_poll_generation(self, api):
        """
        Structural, not behavioural: the sweep must reuse the one resolve path so
        it cannot drift from it. A lighter private copy here would skip the ffmpeg
        gate and the durable-save fallbacks the real poll performs.

        Checked against the compiled code object rather than the source text: the
        comments and docstrings in that function name both _persist_generation_clip
        and _FFMPEG_SLOT in order to explain why they are NOT called from here, so
        a text search would match the explanation and fail for the wrong reason.

        Every name the body references is in co_names (attribute and global lookups
        alike). Scanning only co_consts finds nested code objects but no
        identifiers at all, which made this assert vacuous the first time.
        """
        names = set(api._sweep_stranded_generations.__code__.co_names)
        # Nested comprehensions/lambdas are compiled separately.
        for const in api._sweep_stranded_generations.__code__.co_consts:
            inner = getattr(const, "co_code", None)
            if inner is not None:
                names.update(inner.co_names)

        assert "poll_generation" in names, \
            "the sweep must delegate to poll_generation, not re-implement the save"
        assert "_persist_generation_clip" not in names, \
            "the sweep must not re-implement the durable save path"
        assert "_eager_poster" not in names, \
            "poster work belongs to poll_generation's own scheduling"
        assert "_FFMPEG_SLOT" not in names, \
            "poll_generation already takes the slot; taking it again would deadlock"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))