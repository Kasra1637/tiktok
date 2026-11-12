"""Performance loop: stored craft score, dated result snapshots, joined steering.

Seams:
- submit freezes the craft score on the generation row (ADR 0117);
- POST /generations/{id}/performance-snapshot stores a dated snapshot and
  History reads show the latest one;
- feedback.summarize_posted_performance joins stored scores to snapshots
  and only steers generation prompts at 3+ posted clips.
"""
import asyncio
import importlib
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

ANON = "anonymous"


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="perf-loop-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""
    os.environ.pop("VIDEO_MODEL_DEFAULT", None)
    os.environ.pop("VIDEO_MODEL_ALLOWLIST", None)

    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    original_dirs = (server.pipeline.VIDEOS_DIR, server.pipeline.GENERATED_DIR)
    server.pipeline.VIDEOS_DIR = Path(tmpdir) / "videos"
    server.pipeline.GENERATED_DIR = Path(tmpdir) / "generated"
    server.pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    server.pipeline.GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    asyncio.run(server.init_db())
    try:
        yield server
    finally:
        server.pipeline.VIDEOS_DIR, server.pipeline.GENERATED_DIR = original_dirs
        sys.modules.pop("server", None)


def _run(coro):
    return asyncio.run(coro)


def _insert_generation(api, user_id=ANON, **fields):
    from models import now_iso

    generation_id = str(uuid.uuid4())
    now = now_iso()
    columns = {"id": generation_id, "user_id": user_id, "status": "completed",
               "created_at": now, "updated_at": now}
    columns.update(fields)
    names = ", ".join(columns)
    marks = ", ".join("?" for _ in columns)
    _run(api._execute(
        f"INSERT INTO generations ({names}) VALUES ({marks})",
        tuple(columns.values()),
    ))
    return generation_id


def _record(api, generation_id, user_id=ANON, **fields):
    from models import PerformanceSnapshotRequest

    return _run(api.set_generation_performance_snapshot(
        generation_id, PerformanceSnapshotRequest(**fields), user_id))


class TestPerformanceSnapshots:
    def test_snapshot_round_trips_in_detail_and_history(self, api):
        generation_id = _insert_generation(
            api, tiktok_url="https://www.tiktok.com/@founder/video/1")
        updated = _record(api, generation_id, views=1200,
                          retention_3s_pct=71, avg_watch_pct=38, saves=12, shares=3)
        snap = updated.get("performance_snapshot") or {}
        assert snap.get("views") == 1200
        assert snap.get("retention_3s_pct") == 71
        assert snap.get("avg_watch_pct") == 38
        assert snap.get("saves") == 12
        assert snap.get("shares") == 3
        assert snap.get("recorded_at")

        detail = _run(api.get_generation(generation_id, ANON))
        assert detail.get("performance_snapshot") == snap
        history = _run(api.generation_history(user_id=ANON))
        row = next(g for g in history["generations"] if g["id"] == generation_id)
        assert (row.get("performance_snapshot") or {}).get("retention_3s_pct") == 71

    def test_latest_snapshot_wins_and_snapshots_accumulate(self, api):
        generation_id = _insert_generation(api)
        _record(api, generation_id, views=100, retention_3s_pct=40)
        updated = _record(api, generation_id, views=250, retention_3s_pct=55)
        snap = updated["performance_snapshot"]
        assert snap["views"] == 250
        assert snap["retention_3s_pct"] == 55
        # Reads show only the latest; both dated readings stay stored.
        rows = _run(api._fetch_all(
            "SELECT * FROM performance_snapshots WHERE generation_id = ?",
            (generation_id,)))
        assert len(rows) == 2

    def test_snapshot_views_write_through_to_the_row(self, api):
        generation_id = _insert_generation(api)
        _record(api, generation_id, views=4321, saves=1)
        detail = _run(api.get_generation(generation_id, ANON))
        assert detail.get("tiktok_views") == 4321
        assert detail.get("tiktok_views_at")

    def test_snapshot_without_views_inherits_the_stored_count(self, api):
        from models import TikTokViewsRequest

        generation_id = _insert_generation(api)
        _run(api.set_generation_tiktok_views(
            generation_id, TikTokViewsRequest(tiktok_views=777), ANON))
        updated = _record(api, generation_id, retention_3s_pct=60)
        assert updated["performance_snapshot"]["views"] == 777
        # The stored count itself is untouched by a views-less snapshot.
        assert _run(api.get_generation(generation_id, ANON)).get("tiktok_views") == 777

    def test_out_of_range_values_are_refused_not_stored(self, api):
        generation_id = _insert_generation(api)
        for fields in ({"retention_3s_pct": 101}, {"retention_3s_pct": -1},
                       {"avg_watch_pct": 101}, {"avg_watch_pct": -5},
                       {"views": -1}, {"views": 10_000_000_001},
                       {"saves": -2}, {"shares": -3}):
            with pytest.raises(HTTPException) as exc:
                _record(api, generation_id, **fields)
            assert exc.value.status_code == 400, fields
        detail = _run(api.get_generation(generation_id, ANON))
        assert detail.get("performance_snapshot") is None

    def test_empty_snapshot_is_refused(self, api):
        generation_id = _insert_generation(api)
        with pytest.raises(HTTPException) as exc:
            _record(api, generation_id)
        assert exc.value.status_code == 400

    @pytest.mark.parametrize("payload", [
        {"retention_3s_pct": 71.5}, {"views": "1200"}, {"saves": True},
    ])
    def test_http_refuses_coerced_numbers(self, api, payload):
        import httpx

        generation_id = _insert_generation(api)

        async def request():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=api.app), base_url="http://test"
            ) as client:
                return await client.post(
                    f"/api/generations/{generation_id}/performance-snapshot",
                    json=payload)

        assert _run(request()).status_code == 422

    def test_another_users_render_is_not_found(self, api):
        generation_id = _insert_generation(api)
        with pytest.raises(HTTPException) as exc:
            _record(api, generation_id, user_id="someone-else", views=10)
        assert exc.value.status_code == 404

    def test_missing_generation_is_not_found(self, api):
        with pytest.raises(HTTPException) as exc:
            _record(api, "no-such-generation", views=10)
        assert exc.value.status_code == 404


def _report(dim_scores):
    """A stored-quality-report-shaped dict from {dimension_key: (score, max)}."""
    labels = {
        "hook_stopping_power": "Hook stopping power",
        "audience_truth": "Audience truth / customer voice",
        "clarity": "Clarity / one thought",
        "concreteness": "Concreteness",
        "story_arc": "Story arc / payoff",
        "spoken_naturalness": "Spoken naturalness",
        "demo_handoff": "Demo handoff",
        "trust_compliance": "Trust & compliance",
    }
    dimensions = {}
    for key, (score, maximum) in dim_scores.items():
        dimensions[key] = {
            "key": key, "label": labels[key], "weight": maximum,
            "score": score, "max": maximum, "evidence": [], "next_step": "",
        }
    return {"total": 70, "grade": "B", "band": "strong", "dimensions": dimensions,
            "next_steps": []}


def _joined(report, retention=None, avg_watch=None, views=1000):
    return {
        "quality_report": report,
        "performance": {
            "views": views, "retention_3s_pct": retention,
            "avg_watch_pct": avg_watch, "saves": 1, "shares": 0,
            "recorded_at": "2026-11-11T00:00:00+00:00",
        },
    }


class TestPostedPerformanceSummary:
    def test_below_three_clips_never_steers(self):
        import feedback as feedback_mod

        rows = [
            _joined(_report({"hook_stopping_power": (20, 20)}), retention=90),
            _joined(_report({"hook_stopping_power": (4, 20)}), retention=20),
        ]
        summary = feedback_mod.summarize_posted_performance(rows)
        assert summary["clips"] == 2
        assert summary["ready"] is False
        assert feedback_mod.build_performance_section(summary) == ""
        section = feedback_mod.build_profile_feedback_section(
            {"total": 0, "performance": summary})
        assert "Posted results so far" not in section

    def test_rows_missing_either_half_do_not_count(self):
        import feedback as feedback_mod

        rows = [
            _joined(_report({"hook_stopping_power": (20, 20)}), retention=90),
            {"quality_report": _report({"hook_stopping_power": (20, 20)}),
             "performance": None},
            {"quality_report": None,
             "performance": {"views": 5, "retention_3s_pct": 50}},
            _joined(_report({"hook_stopping_power": (18, 20)}), retention=80),
        ]
        summary = feedback_mod.summarize_posted_performance(rows)
        assert summary["clips"] == 2
        assert summary["ready"] is False

    def test_three_clips_produce_a_note_with_the_real_numbers(self):
        import feedback as feedback_mod

        rows = [
            _joined(_report({"hook_stopping_power": (20, 20)}), retention=80),
            _joined(_report({"hook_stopping_power": (18, 20)}), retention=62),
            _joined(_report({"hook_stopping_power": (4, 20)}), retention=30),
            _joined(_report({"hook_stopping_power": (6, 20)}), retention=40),
        ]
        summary = feedback_mod.summarize_posted_performance(rows)
        assert summary["clips"] == 4
        assert summary["ready"] is True
        dims = {d["key"]: d for d in summary["dimensions"]}
        hook = dims["hook_stopping_power"]["retention"]
        assert hook["high_avg"] == 71  # (80 + 62) / 2
        assert hook["low_avg"] == 35   # (30 + 40) / 2
        assert hook["high_clips"] == 2
        assert hook["low_clips"] == 2
        note = feedback_mod.build_performance_section(summary)
        assert "Posted results so far" in note
        assert "Hook stopping power" in note
        assert "71%" in note and "35%" in note
        section = feedback_mod.build_profile_feedback_section(
            {"total": 0, "performance": summary})
        assert "Posted results so far" in section


async def _fake_generate_video(**kwargs):
    return {"id": "job-perf", "status": "queued"}


async def _fake_poll(job_id):
    return {"status": "completed",
            "unsigned_urls": ["https://example.invalid/clip.mp4"]}


def _ready_project(api, name="Performance App"):
    from models import (
        BrandProfileCreateRequest, ApproveAppProfileRequest,
        CreateStudioProjectRequest, now_iso,
    )
    profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
        brand_name=name,
        app_category="Productivity",
        brand_description="A focus timer for people who stall on starting.",
        core_features=["Task timer"],
        usage_moments=["Starting a task they have been avoiding"],
        outcome_statements=[{
            "outcome": "Starting without stalling on setup",
            "who_feels_it": "people who stall on starting",
            "from_feature": "Task timer",
            "how_it_helps": "The timer starts in one tap so there is nothing to set up",
        }],
        claims_approved=["3-day free trial"],
        claims_banned=["cures anxiety"],
    ), user_id=ANON))
    _run(api.approve_app_profile(
        profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
    template = _run(api.list_templates(q="Stop Doing This", user_id=ANON))["templates"][0]
    project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
        brand_profile_id=profile["id"],
        template_id=template["id"],
        duration_seconds=20,
        objective="demonstrate_feature",
    ), user_id=ANON))
    strategy = {
        "strategy_summary": "Stop opening a blank page.",
        "hook_line": "Stop writing empty pages",
        "hook_promise": "One prompt gets you going.",
        "hook_action": "Look straight down the lens.",
        "messaging_pillars": ["one prompt at a time"],
        "primary_feature": "Task timer",
        "cta_strategy": "Try it free",
        "scene": {"environment": "kitchen"},
        "performance": {"movement": "still"},
        "segments": [{"index": 0, "role": "hook", "seconds": 5,
                      "goal": "name the problem",
                      "script": "Stop writing empty pages",
                      "action": "hold the look"}],
        "continuity_contract": {"established": ["kitchen"]},
    }
    face = Path(tempfile.mkdtemp(prefix="perf-face-")) / "face.png"
    face.write_bytes(bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c626001000000ffff0300000600055d3866680000000049454e44ae426082"))
    asset_id = str(uuid.uuid4())
    now = now_iso()
    _run(api._execute(
        "INSERT INTO assets (id, brand_profile_id, kind, name, file_path, label,"
        " created_at, updated_at, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (asset_id, profile["id"], "character_reference", "Founder face",
         str(face), "Founder face", now, now, ANON)))
    assets = [{"asset_id": asset_id, "kind": "character_reference",
               "label": "Founder face", "file_path": str(face)}]
    _run(api._execute(
        """UPDATE studio_projects SET assets = ?, hook_line = ?, script = ?,
              status = 'ready_for_generation', script_version = 1,
              strategy = ?, strategy_version = 1, strategy_script_version = 1
           WHERE id = ?""",
        (json.dumps(assets), "Stop writing empty pages",
         "A short script for the app.", json.dumps(strategy), project["id"])))
    return _run(api.get_studio_project(project["id"], ANON))


class TestPerformanceSteeringWiring:
    """The join must reach the prompt path, not just exist as functions.

    Seam: generations with stored scores + snapshots -> the posted-rows
    fetch the studio router uses -> summarize_profile_feedback -> the
    section ai_service embeds in plan and strategy prompts.
    """

    def _seed_posted_clip(self, api, profile_id, score, retention):
        generation_id = _insert_generation(
            api,
            brand_profile_id=profile_id,
            tiktok_url="https://www.tiktok.com/@founder/video/x",
            quality_report=json.dumps(_report({"hook_stopping_power": score})),
        )
        _record(api, generation_id, views=1000, retention_3s_pct=retention)
        return generation_id

    def test_three_seeded_clips_put_the_note_in_the_prompt_section(self, api):
        import feedback as feedback_mod

        profile_id = str(uuid.uuid4())
        self._seed_posted_clip(api, profile_id, (20, 20), retention=80)
        self._seed_posted_clip(api, profile_id, (18, 20), retention=62)
        self._seed_posted_clip(api, profile_id, (4, 20), retention=30)
        self._seed_posted_clip(api, profile_id, (6, 20), retention=40)

        rows = _run(api._posted_performance_rows(profile_id, ANON))
        assert len(rows) == 4
        assert all(isinstance(r["quality_report"], dict) for r in rows)
        assert all(isinstance(r["performance"], dict) for r in rows)

        summary = feedback_mod.summarize_profile_feedback([], "", posted_rows=rows)
        assert summary["performance"]["clips"] == 4
        assert summary["performance"]["ready"] is True
        section = feedback_mod.build_profile_feedback_section(summary)
        assert "Posted results so far" in section
        assert "Hook stopping power" in section

    def test_two_seeded_clips_stay_silent(self, api):
        import feedback as feedback_mod

        profile_id = str(uuid.uuid4())
        self._seed_posted_clip(api, profile_id, (20, 20), retention=80)
        self._seed_posted_clip(api, profile_id, (4, 20), retention=30)

        rows = _run(api._posted_performance_rows(profile_id, ANON))
        summary = feedback_mod.summarize_profile_feedback([], "", posted_rows=rows)
        assert summary["performance"]["clips"] == 2
        assert summary["performance"]["ready"] is False
        assert "Posted results so far" not in feedback_mod.build_profile_feedback_section(summary)

    def test_history_list_carries_the_analytics_join(self, api):
        profile_id = str(uuid.uuid4())
        seeded = [
            self._seed_posted_clip(api, profile_id, (20, 20), retention=80),
            self._seed_posted_clip(api, profile_id, (18, 20), retention=62),
            self._seed_posted_clip(api, profile_id, (4, 20), retention=30),
            self._seed_posted_clip(api, profile_id, (6, 20), retention=40),
        ]
        history = _run(api.generation_history(user_id=ANON))
        rows = {g["id"]: g for g in history["generations"]}
        for generation_id in seeded:
            entry = rows[generation_id]
            assert isinstance(entry.get("quality_report"), dict)
            assert entry["quality_report"]["grade"]
            assert entry["performance_snapshot"]["retention_3s_pct"] is not None
        summary = history["performance_summary"]
        assert summary["clips"] >= 4
        assert summary["ready"] is True
        dims = {d["key"]: d for d in summary["dimensions"]}
        assert dims["hook_stopping_power"]["retention"] is not None

    def test_legacy_posted_rows_teach_the_join_nothing(self):
        import feedback as feedback_mod

        summary = feedback_mod.summarize_profile_feedback(
            [], "", posted_rows=[{"tiktok_url": "https://www.tiktok.com/@f/v/1",
                                  "tiktok_views": 900}])
        assert summary["posted_clips"] == 1
        assert summary["performance"]["clips"] == 0
        assert summary["performance"]["ready"] is False


class TestQualityReportFrozenAtSubmit:
    def test_submit_freezes_the_craft_score_and_reads_return_it(self, api, monkeypatch):
        from models import StudioGenerationRequest

        monkeypatch.setattr(api, "generate_video", _fake_generate_video)
        monkeypatch.setattr(api, "poll_video_job", _fake_poll)

        project = _ready_project(api)
        gen = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        # The score is frozen at submit, on the words the render speaks —
        # the submit response already carries it (ADR 0117).
        report = gen.get("quality_report")
        assert isinstance(report, dict)
        assert "total" in report and "grade" in report
        assert "hook_stopping_power" in report.get("dimensions", {})

        completed = _run(api.poll_generation(gen["id"], ANON))
        assert completed["status"] == "completed"
        assert completed.get("quality_report") == report

        stored = _run(api._fetch_one(
            "SELECT quality_report FROM generations WHERE id = ?", (gen["id"],)))
        assert json.loads(stored["quality_report"]) == report

        detail = _run(api.get_generation(gen["id"], ANON))
        assert detail.get("quality_report") == report

    def test_frozen_score_survives_later_project_edits(self, api, monkeypatch):
        from models import StudioGenerationRequest

        monkeypatch.setattr(api, "generate_video", _fake_generate_video)
        monkeypatch.setattr(api, "poll_video_job", _fake_poll)

        project = _ready_project(api, "Performance Frozen")
        gen = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        completed = _run(api.poll_generation(gen["id"], ANON))
        frozen = completed.get("quality_report")
        assert frozen

        # The founder rewrites the project's words after the render. The
        # render's stored score describes the words it was rendered from,
        # so a later read must not silently re-score it.
        _run(api._execute(
            "UPDATE studio_projects SET hook_line = ?, script = ? WHERE id = ?",
            ("A completely different opening line",
             "A completely different script body.", project["id"])))
        again = _run(api.poll_generation(gen["id"], ANON))
        assert again.get("quality_report") == frozen
        assert _run(api.get_generation(gen["id"], ANON)).get("quality_report") == frozen
