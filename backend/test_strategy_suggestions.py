"""
Direction-change word suggestions on a strategy rebuild (ADR 0133).

The gap (ADR 0090's own note): editing Visual & audio direction after the
plan was written reconciles the strategy's SCENE in the same save, but the
spoken words are deliberately not rewritten — a hook naming the old place
kept shipping against the new scene. Kasra's fix: when the founder clicks
Rebuild strategy and the saved direction differs from the direction the
strategy was built against, the studio first offers a refreshed hook +
script pair in a popup; nothing is applied before the founder chooses.

These pin the endpoint behind the popup:

  * the strategy build stamps the direction it was built against inside
    the strategy record (direction_snapshot) — the diff source, no
    parallel tracker;
  * no direction change -> direction_changed False and NO model call
    (the check is free; only a real change spends a plan generation);
  * a direction change regenerates the words through the plan machinery
    and offers the pair only when the suggested hook scores at least the
    current hook on the craft scorer's hook-stopping-power dimension;
  * a weaker suggested hook degrades to a script-only suggestion, and a
    suggestion identical to the saved words is no suggestion at all;
  * a strategy with no snapshot (built before this shipped) never
    triggers the popup — the diff is unknown, not guessed;
  * a provider failure surfaces as 502 so the client can fall back to
    rebuilding with the saved words, with an honest note.

Craft scores for the canned words, measured on the shipped scorer
(hook 3s, total 20s): WEAK hook 14/20, MID hook 15/20, STRONG hook 19/20.
"""
import asyncio
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000080000000808020000004b6d29dc"
    "0000001149444154789c633821278715310c2d090090bf4101b29f3e2200000000"
    "49454e44ae426082")

CANNED_ANGLES = [
    {
        "kind": "problem_solution",
        "label": "Stop stalling on starts",
        "target_audience": "People who stall on starting",
        "user_problem": "Cannot start without setup friction",
        "hook_promise": "Start in one tap",
        "app_feature": "Task timer",
        "desired_emotion": "relief",
        "claims_to_respect": [],
    },
]

WEAK_HOOK = "Stuff is hard sometimes."
WEAK_SCRIPT = "Things happen and then more things happen after that."
STRONG_HOOK = "Every morning the blank page wins and work never starts."
STRONG_SCRIPT = (
    "The blank page just sits there until one small prompt gives my hands "
    "somewhere to start. I still do not know why the first line is always "
    "the hard one."
)
MID_HOOK = "At 7 a.m. the first line never comes, whatever I try."
GARDEN_SCRIPT = (
    "A different middle entirely, written for the garden at dawn, one "
    "small prompt before the city wakes."
)


def _plan(hook, script, location="Bus stop bench"):
    return {
        "hook_line": hook,
        "script": script,
        "beat_timeline": [
            {"start": 0, "end": 3, "label": "hook", "text": hook},
            {"start": 3, "end": 20, "label": "middle", "text": script},
        ],
        "location": location,
        "visual_direction": "Bench by the window",
        "demo_brief": "Record the first line being written.",
        "voice_direction": "Calm",
        "sound_direction": "Room tone",
        "claims_used": [],
    }


FAKE_STRATEGY = {
    "strategy_summary": "Stop opening a blank page.",
    "audience_problem": "Starting is harder than doing.",
    "emotional_triggers": ["frustration"],
    "hook_concept": "Name the blank page",
    "hook_line": "You do not have a writing problem.",
    "hook_promise": "One prompt gets you going.",
    "hook_action": "Look straight down the lens.",
    "messaging_pillars": ["one prompt at a time"],
    "primary_feature": "Task timer",
    "desired_outcome": "A finished page",
    "differentiation_beat": "It works offline.",
    "cta_strategy": "Try it free",
    "scene": {"environment": "kitchen"},
    "performance": {"movement": "still"},
}


@pytest.fixture(scope="module")
def world():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-suggest-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""
    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(server.init_db())

    state = {"plan": _plan(WEAK_HOOK, WEAK_SCRIPT), "plan_error": None,
             "calls": []}
    orig_log = server._log_model_call

    async def fake_log(operation, modality, model, call, user_id, **refs):
        state["calls"].append(operation)
        if operation == "content_angles":
            return [dict(a) for a in CANNED_ANGLES]
        if operation == "creative_plan":
            if state["plan_error"] is not None:
                raise state["plan_error"]
            return dict(state["plan"])
        if operation == "video_strategy":
            strat = dict(FAKE_STRATEGY)
            proj = await server._fetch_one(
                "SELECT content_angle_id FROM studio_projects WHERE id = ?",
                (refs.get("studio_project_id"),))
            strat["content_angle_id"] = (proj or {}).get("content_angle_id") or ""
            return strat
        if operation == "brand_templates":
            return []
        raise AssertionError(f"unexpected model call: {operation}")

    server._log_model_call = fake_log
    from starlette.testclient import TestClient
    try:
        with TestClient(server.app) as client:
            yield {"client": client, "state": state, "server": server}
    finally:
        server._log_model_call = orig_log
        sys.modules.pop("server", None)


def _ok(resp, path):
    assert resp.status_code in (200, 201, 202), (
        f"{path} -> {resp.status_code}: {resp.text[:400]}"
    )
    return resp.json()


@pytest.fixture(scope="module")
def base(world):
    """One approved profile, one angle, one template, one shared photo."""
    client, state = world["client"], world["state"]
    profile = _ok(client.post("/api/brand", json={
        "brand_name": "Suggest Focus Timer",
        "brand_description": "A focus timer for people who stall on starting.",
        "app_category": "Productivity",
        "core_features": ["Task timer", "Reminders"],
        "usage_moments": ["Starting a task they have been avoiding"],
        "outcome_statements": [{
            "outcome": "Starting without stalling on setup",
            "who_feels_it": "people who stall on starting",
            "from_feature": "Task timer",
            "how_it_helps": "The timer starts in one tap so there is nothing to set up",
        }],
    }), "POST /api/brand")
    pid = profile["id"]
    _ok(client.post(f"/api/app-profiles/{pid}/approve", json={}),
        "POST approve")
    angles = _ok(client.get(f"/api/app-profiles/{pid}/content-angles"),
                 "GET content-angles")
    angle_id = angles["angles"][0]["id"]
    recs = _ok(client.get(
        f"/api/app-profiles/{pid}/template-recommendations",
        params={"angle_id": angle_id, "objective": "demonstrate_feature"}),
        "GET template-recommendations")
    template_id = recs["recommendations"][0]["template"]["id"]
    up = client.post(
        f"/api/app-profiles/{pid}/assets",
        data={"kind": "character_reference", "label": "Founder face",
              "rights_confirmed": "true"},
        files={"file": ("face.png", TINY_PNG, "image/png")})
    asset = _ok(up, "POST asset upload")
    return {"profile_id": pid, "angle_id": angle_id,
            "template_id": template_id, "asset_id": asset["id"]}


def _project_with_strategy(world, base):
    """A project with a plan (WEAK words) and a built strategy."""
    client, state = world["client"], world["state"]
    state["plan"] = _plan(WEAK_HOOK, WEAK_SCRIPT)
    state["plan_error"] = None
    project = _ok(client.post("/api/studio/projects", json={
        "brand_profile_id": base["profile_id"],
        "template_id": base["template_id"],
        "objective": "demonstrate_feature",
    }), "POST /api/studio/projects")
    prid = project["id"]
    _ok(client.patch(f"/api/studio/projects/{prid}",
                     json={"content_angle_id": base["angle_id"]}),
        "PATCH project angle")
    _ok(client.post(f"/api/studio/projects/{prid}/assets",
                    json={"asset_id": base["asset_id"]}),
        "POST attach asset")
    _ok(client.post(f"/api/studio/projects/{prid}/plan", json={}),
        "POST plan")
    _ok(client.post(f"/api/studio/projects/{prid}/ready", json={}),
        "POST ready")
    built = _ok(client.post(f"/api/studio/projects/{prid}/strategy", json={}),
                "POST strategy")
    return prid, built


class TestDirectionSnapshot:
    def test_strategy_build_stamps_the_direction_it_was_built_against(
            self, world, base):
        _, built = _project_with_strategy(world, base)
        snapshot = built["strategy"].get("direction_snapshot")
        assert snapshot == {
            "location": "Bus stop bench",
            "visual_direction": "Bench by the window",
            "voice_direction": "Calm",
            "sound_direction": "Room tone",
        }


class TestSuggestions:
    def test_no_direction_change_offers_nothing_and_spends_nothing(
            self, world, base):
        client, state = world["client"], world["state"]
        prid, _ = _project_with_strategy(world, base)
        calls_before = list(state["calls"])
        body = _ok(client.post(
            f"/api/studio/projects/{prid}/strategy-suggestions", json={}),
            "POST strategy-suggestions")
        assert body["direction_changed"] is False
        assert body["changed_fields"] == []
        assert body["suggestion"] is None
        assert body["current"] == {"hook_line": WEAK_HOOK, "script": WEAK_SCRIPT}
        assert state["calls"] == calls_before, (
            "the no-change check must not spend a model call")

    def test_no_strategy_yet_offers_nothing(self, world, base):
        client, state = world["client"], world["state"]
        state["plan"] = _plan(WEAK_HOOK, WEAK_SCRIPT)
        project = _ok(client.post("/api/studio/projects", json={
            "brand_profile_id": base["profile_id"],
            "template_id": base["template_id"],
            "objective": "demonstrate_feature",
        }), "POST /api/studio/projects")
        body = _ok(client.post(
            f"/api/studio/projects/{project['id']}/strategy-suggestions",
            json={}), "POST strategy-suggestions (no strategy)")
        assert body["direction_changed"] is False
        assert body["suggestion"] is None

    def test_direction_change_offers_the_refreshed_pair(self, world, base):
        client, state = world["client"], world["state"]
        prid, _ = _project_with_strategy(world, base)
        _ok(client.patch(f"/api/studio/projects/{prid}",
                         json={"location": "Rooftop garden at dawn"}),
            "PATCH location")
        state["plan"] = _plan(STRONG_HOOK, STRONG_SCRIPT,
                              location="Rooftop garden at dawn")
        body = _ok(client.post(
            f"/api/studio/projects/{prid}/strategy-suggestions", json={}),
            "POST strategy-suggestions")
        assert body["direction_changed"] is True
        assert "location" in body["changed_fields"]
        assert body["current"] == {"hook_line": WEAK_HOOK, "script": WEAK_SCRIPT}
        assert body["suggestion"] == {
            "hook_line": STRONG_HOOK, "script": STRONG_SCRIPT}

    def test_a_weaker_suggested_hook_degrades_to_script_only(
            self, world, base):
        client, state = world["client"], world["state"]
        prid, _ = _project_with_strategy(world, base)
        # The saved words are the STRONG pair now (19/20 hook).
        _ok(client.patch(f"/api/studio/projects/{prid}", json={
            "hook_line": STRONG_HOOK, "script": STRONG_SCRIPT,
            "location": "Rooftop garden at dawn",
        }), "PATCH strong words + location")
        # The refreshed plan's hook is MID (15/20): below the saved hook,
        # so only its script may be offered.
        state["plan"] = _plan(MID_HOOK, GARDEN_SCRIPT,
                              location="Rooftop garden at dawn")
        body = _ok(client.post(
            f"/api/studio/projects/{prid}/strategy-suggestions", json={}),
            "POST strategy-suggestions")
        assert body["direction_changed"] is True
        assert body["suggestion"] == {"hook_line": None, "script": GARDEN_SCRIPT}

    def test_identical_refreshed_words_are_no_suggestion(self, world, base):
        client, state = world["client"], world["state"]
        prid, _ = _project_with_strategy(world, base)
        _ok(client.patch(f"/api/studio/projects/{prid}",
                         json={"location": "Rooftop garden at dawn"}),
            "PATCH location")
        state["plan"] = _plan(WEAK_HOOK, WEAK_SCRIPT,
                              location="Rooftop garden at dawn")
        body = _ok(client.post(
            f"/api/studio/projects/{prid}/strategy-suggestions", json={}),
            "POST strategy-suggestions")
        assert body["direction_changed"] is True
        assert body["suggestion"] is None

    def test_a_strategy_without_a_snapshot_never_suggests(self, world, base):
        client, state, server = world["client"], world["state"], world["server"]
        prid, built = _project_with_strategy(world, base)
        legacy = {k: v for k, v in built["strategy"].items()
                  if k != "direction_snapshot"}
        asyncio.run(server._execute(
            "UPDATE studio_projects SET strategy = ? WHERE id = ?",
            (json.dumps(legacy), prid)))
        _ok(client.patch(f"/api/studio/projects/{prid}",
                         json={"location": "Rooftop garden at dawn"}),
            "PATCH location")
        calls_before = list(state["calls"])
        body = _ok(client.post(
            f"/api/studio/projects/{prid}/strategy-suggestions", json={}),
            "POST strategy-suggestions")
        assert body["direction_changed"] is False
        assert body["suggestion"] is None
        assert state["calls"] == calls_before

    def test_provider_failure_is_a_502_the_client_can_fall_back_on(
            self, world, base):
        client, state = world["client"], world["state"]
        prid, _ = _project_with_strategy(world, base)
        _ok(client.patch(f"/api/studio/projects/{prid}",
                         json={"location": "Rooftop garden at dawn"}),
            "PATCH location")
        state["plan_error"] = RuntimeError("provider down")
        try:
            resp = client.post(
                f"/api/studio/projects/{prid}/strategy-suggestions", json={})
            assert resp.status_code == 502, (
                f"expected 502, got {resp.status_code}: {resp.text[:200]}")
        finally:
            state["plan_error"] = None
