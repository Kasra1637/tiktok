"""
End-to-end test: one founder's whole journey through the real HTTP surface.

Every other backend test calls route functions directly. This module is the
one place that drives the app the way the frontend does — HTTP requests
against the ASGI app with a real SQLite database behind it — walking the
complete studio journey in order:

  health -> profile create/edit/approve -> angles + goals -> templates ->
  project -> photo upload + attach -> plan -> claim-safety gate -> strategy ->
  ready -> generate (+ idempotency, + bad-model refusal) -> poll to completed
  -> history -> feedback + analytics -> demo-cta export + media serving ->
  variations -> duplicate -> delete

External systems are faked at the boundary, exactly as the unit suites do:
the AI model layer answers canned rows and the video provider submits and
polls against canned jobs. Everything else — routing, auth, validation,
orchestration, persistence — is the shipped code.

Numbered tests run in file order on one worker (see pytest.ini: loadscope
pins a module to a single worker), sharing one journey fixture. Each step
depends on the previous one the way the product does: you cannot plan
without a template, render without a strategy, or poll a job that was never
submitted.
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

# A valid 8x8 PNG (solid red: no face). The upload endpoint never blocks on
# face detection (a warning the founder can overrule beats a refusal they
# cannot), so this uploads 201 with a face_warning attached — which is
# itself asserted below.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000080000000808020000004b6d29dc"
    "0000001149444154789c633821278715310c2d090090bf4101b29f3e2200000000"
    "49454e44ae426082")

# Same placeholder the demo-cta unit tests upload: valid by extension and
# non-empty, which is what the endpoint validates.
MP4_BYTES = bytes(range(256)) * 8

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

# The plan the mocked generator returns. Two sections, as the schema
# demands, and a claims_used entry that sits inside claims_approved so the
# claim-safety gate passes on the clean path.
FAKE_PLAN = {
    "hook_line": "Stop writing empty pages",
    "script": "Taskly gives you one short prompt and a reminder. It works offline.",
    "beat_timeline": [
        {"start": 0, "end": 3, "label": "hook", "text": "Stop writing empty pages"},
        {"start": 3, "end": 15, "label": "middle", "text": "The blank page loses its grip"},
    ],
    "visual_direction": "Close on hands, then a real desk with clean space for overlays.",
    "demo_brief": "Record yourself tapping the timer once, hands only.",
    "overlays": [{"start": 0, "end": 3, "text": "one prompt"}],
    "voice_direction": "Warm, unhurried",
    "sound_direction": "Lo-fi bed, rights-safe",
    "claims_used": ["works offline"],
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
def journey():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-e2e-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""
    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(server.init_db())

    orig_log = server._log_model_call
    orig_submit = server.generate_video
    orig_poll = server.poll_video_job

    async def fake_log(operation, modality, model, call, user_id, **refs):
        if operation in ("video_submit", "video_poll"):
            # Provider boundary: run the REAL logging wrapper so model_requests
            # rows are written, with the provider functions faked below.
            return await orig_log(operation, modality, model, call, user_id, **refs)
        if operation == "content_angles":
            return [dict(a) for a in CANNED_ANGLES]
        if operation == "creative_plan":
            return dict(FAKE_PLAN)
        if operation == "video_strategy":
            return dict(FAKE_STRATEGY)
        if operation == "brand_templates":
            # Objective-tailored templates: answer empty so the endpoint takes
            # its graceful-degradation path (curated picks keep working).
            return []
        raise AssertionError(f"unexpected model call: {operation}")

    submit_calls = []

    async def fake_submit(**kwargs):
        submit_calls.append(kwargs)
        return {
            "id": f"job-e2e-{len(submit_calls)}",
            "status": "queued",
            "usage": {"cost": 0.25},
        }

    polls = {"n": 0}

    async def fake_poll(job_id):
        polls["n"] += 1
        if polls["n"] == 1:
            return {"status": "processing"}
        return {
            "status": "completed",
            "unsigned_urls": ["https://example.invalid/e2e-clip.mp4"],
        }

    server._log_model_call = fake_log
    server.generate_video = fake_submit
    server.poll_video_job = fake_poll
    from starlette.testclient import TestClient
    state = {}
    try:
        with TestClient(server.app) as client:
            yield {"client": client, "state": state, "submit_calls": submit_calls}
    finally:
        server._log_model_call = orig_log
        server.generate_video = orig_submit
        server.poll_video_job = orig_poll
        sys.modules.pop("server", None)


def _ok(resp, path):
    assert resp.status_code in (200, 201, 202), (
        f"{path} -> {resp.status_code}: {resp.text[:400]}"
    )
    return resp.json()


class TestE2EFullJourney:
    def test_01_health_reports_the_local_store(self, journey):
        body = _ok(journey["client"].get("/api/health"), "GET /api/health")
        assert body["status"] == "ok"
        assert body["database"] == "local-sqlite"
        assert body["durable"] is False

    def test_02_profile_create_edit_approve(self, journey):
        client, state = journey["client"], journey["state"]
        body = _ok(client.post("/api/brand", json={
            "brand_name": "E2E Focus Timer",
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
            "claims_approved": ["works offline"],
            "claims_review": ["4.8 star rating"],
            "claims_banned": ["cures anxiety", "guaranteed results"],
        }), "POST /api/brand")
        pid = body["id"]
        state["profile_id"] = pid
        assert body["status"] == "draft"

        listed = _ok(client.get("/api/app-profiles"), "GET /api/app-profiles")
        assert any(p["id"] == pid for p in listed["profiles"])

        edited = _ok(client.patch(f"/api/brand/{pid}", json={
            "tone_voice": "direct and plain",
        }), "PATCH /api/brand/{pid}")
        assert edited["tone_voice"] == "direct and plain"

        approved = _ok(client.post(f"/api/app-profiles/{pid}/approve", json={}),
                       "POST /api/app-profiles/{pid}/approve")
        assert approved["status"] == "approved"

    def test_03_angles_goals_templates(self, journey):
        client, state = journey["client"], journey["state"]
        pid = state["profile_id"]
        # Approval auto-generates angles from the (canned) model layer.
        body = _ok(client.get(f"/api/app-profiles/{pid}/content-angles"),
                   "GET content-angles")
        assert len(body["angles"]) >= 1
        angle = body["angles"][0]
        state["angle_id"] = angle["id"]
        assert angle["kind"] == "problem_solution"

        goals = _ok(client.get(
            f"/api/app-profiles/{pid}/content-angles/{angle['id']}/goal-suggestions"),
            "GET goal-suggestions")
        assert len(goals["suggestions"]) == 6
        first_order = [s for s in goals["suggestions"]]

        regen = _ok(client.post(
            f"/api/app-profiles/{pid}/content-angles/{angle['id']}/regenerate-goals"),
            "POST regenerate-goals")
        assert set(regen["suggestions"]) == set(first_order)
        again = _ok(client.get(
            f"/api/app-profiles/{pid}/content-angles/{angle['id']}/goal-suggestions"),
            "GET goal-suggestions after regen")
        assert again["suggestions"] == regen["suggestions"]

        templates = _ok(client.get("/api/templates"), "GET /api/templates")
        assert len(templates["templates"]) >= 1
        recs = _ok(client.get(
            f"/api/app-profiles/{pid}/template-recommendations",
            params={"angle_id": angle["id"], "objective": "demonstrate_feature"}),
            "GET template-recommendations")
        assert len(recs["recommendations"]) >= 1
        state["template_id"] = recs["recommendations"][0]["template"]["id"]

        tailored = _ok(client.post(
            f"/api/app-profiles/{pid}/objective-templates",
            json={"objective": "demonstrate_feature"}),
            "POST objective-templates")
        assert tailored["objective"] == "demonstrate_feature"
        assert isinstance(tailored["templates"], list)

        models = _ok(client.get("/api/studio/video-models"),
                     "GET /api/studio/video-models")
        assert models["default"]
        state["model"] = models["default"]

    def test_04_project_and_photo(self, journey):
        client, state = journey["client"], journey["state"]
        up = client.post(
            f"/api/app-profiles/{state['profile_id']}/assets",
            data={"kind": "character_reference", "label": "Founder face",
                  "rights_confirmed": "true"},
            files={"file": ("face.png", TINY_PNG, "image/png")})
        asset = _ok(up, "POST asset upload")
        state["asset_id"] = asset["id"]
        # A 1x1 PNG carries no face. The upload warns rather than refuses —
        # a warning the founder can overrule beats a refusal they cannot.
        assert asset.get("face_warning")

        listed = _ok(client.get(f"/api/app-profiles/{state['profile_id']}/assets"),
                     "GET assets")
        assert any(a["id"] == asset["id"] for a in listed["assets"])

        project = _ok(client.post("/api/studio/projects", json={
            "brand_profile_id": state["profile_id"],
            "template_id": state["template_id"],
            "objective": "demonstrate_feature",
        }), "POST /api/studio/projects")
        assert project["status"] == "draft"
        state["project_id"] = project["id"]

        patched = _ok(client.patch(f"/api/studio/projects/{project['id']}", json={
            "content_angle_id": state["angle_id"],
        }), "PATCH project angle")
        assert patched["content_angle_id"] == state["angle_id"]

        attached = _ok(client.post(
            f"/api/studio/projects/{project['id']}/assets",
            json={"asset_id": asset["id"]}), "POST attach asset")
        assert any(a.get("asset_id") == asset["id"] for a in attached["assets"])

    def test_05_plan_and_template_gate(self, journey):
        client, state = journey["client"], journey["state"]
        _ok(client.post(f"/api/studio/projects/{state['project_id']}/plan", json={}),
            "POST plan")
        project = _ok(client.get(f"/api/studio/projects/{state['project_id']}"),
                      "GET project after plan")
        assert project["script"].strip()
        assert project["script_version"] == 1

        # A project with no template cannot plan: the template supplies the
        # creative structure the plan adapts.
        bare = _ok(client.post("/api/studio/projects", json={
            "brand_profile_id": state["profile_id"],
        }), "POST bare project")
        r = client.post(f"/api/studio/projects/{bare['id']}/plan", json={})
        assert r.status_code == 400, f"plan without template -> {r.status_code}: {r.text[:200]}"

    def test_06_claims_block_then_ready(self, journey):
        client, state = journey["client"], journey["state"]
        prid = state["project_id"]
        _ok(client.patch(f"/api/studio/projects/{prid}", json={
            "script": "Taskly cures anxiety for good.",
        }), "PATCH banned script")
        blocked = client.post(f"/api/studio/projects/{prid}/ready")
        assert blocked.status_code == 409, (
            f"ready with banned claim -> {blocked.status_code}: {blocked.text[:200]}")
        assert "wording" in blocked.json()["detail"]

        _ok(client.patch(f"/api/studio/projects/{prid}", json={
            "script": FAKE_PLAN["script"],
        }), "PATCH clean script")
        ready = _ok(client.post(f"/api/studio/projects/{prid}/ready"),
                    "POST ready")
        assert ready["status"] == "ready_for_generation"

    def test_07_strategy_generate_poll(self, journey):
        client, state = journey["client"], journey["state"]
        prid = state["project_id"]
        strategy = _ok(client.post(f"/api/studio/projects/{prid}/strategy", json={}),
                       "POST strategy")
        assert strategy["strategy_version"] == 1
        assert "hook_line" in json.dumps(strategy["strategy"])

        bad = client.post(f"/api/studio/projects/{prid}/generate",
                          json={"model": "no-such-model"})
        assert bad.status_code == 400, (
            f"unknown model -> {bad.status_code}: {bad.text[:200]}")

        gen = _ok(client.post(f"/api/studio/projects/{prid}/generate",
                              json={"model": state["model"],
                                    "idempotency_key": "e2e-render-1"}),
                  "POST generate")
        assert gen["status"] == "generating"
        state["generation_id"] = gen["id"]

        again = _ok(client.post(f"/api/studio/projects/{prid}/generate",
                                json={"model": state["model"],
                                      "idempotency_key": "e2e-render-1"}),
                    "POST generate (same key)")
        assert again["id"] == gen["id"]
        assert len(journey["submit_calls"]) == 1

        first = _ok(client.post(f"/api/generations/{gen['id']}/poll"),
                    "POST poll #1")
        assert first["status"] == "generating"
        second = _ok(client.post(f"/api/generations/{gen['id']}/poll"),
                     "POST poll #2")
        assert second["status"] == "completed"
        assert second["video_url"] == "https://example.invalid/e2e-clip.mp4"

        fetched = _ok(client.get(f"/api/generations/{gen['id']}"),
                      "GET generation")
        assert fetched["status"] == "completed"
        scoped = _ok(client.get("/api/generations",
                                params={"studio_project_id": prid}),
                     "GET generations scoped")
        assert any(g["id"] == gen["id"] for g in scoped["generations"])
        history = _ok(client.get("/api/history/generations"),
                      "GET history")
        assert any(g["id"] == gen["id"] for g in history["generations"])

    def test_08_feedback_and_analytics(self, journey):
        client, state = journey["client"], journey["state"]
        pid, prid = state["profile_id"], state["project_id"]
        catalog = _ok(client.get("/api/feedback/catalog"), "GET feedback catalog")
        assert "video_regenerated" in {e["key"] for e in catalog["events"]}

        _ok(client.post("/api/feedback", json={
            "event": "video_regenerated", "reason": "pacing_too_slow",
            "brand_profile_id": pid, "studio_project_id": prid,
        }), "POST feedback reason")
        _ok(client.post("/api/feedback", json={
            "event": "thumb_up", "step": "goal",
            "detail": "objective=demonstrate_feature;kind=problem_solution",
            "brand_profile_id": pid, "studio_project_id": prid,
        }), "POST goal thumb")

        summary = _ok(client.get("/api/feedback", params={"brand_profile_id": pid}),
                      "GET feedback analytics")
        events = [f["event"] for f in summary["feedback"]]
        assert "video_regenerated" in events
        assert "thumb_up" in events
        by_event = summary["summary"]["by_event"]
        assert by_event.get("video_regenerated", 0) >= 1
        assert by_event.get("thumb_up", 0) >= 1

    def test_09_demo_cta_export_and_media(self, journey):
        client, state = journey["client"], journey["state"]
        gid = state["generation_id"]
        export = _ok(client.post(
            f"/api/generations/{gid}/demo-cta-result",
            files={"file": ("demo-cta.mp4", MP4_BYTES, "video/mp4")}),
            "POST demo-cta-result")
        assert export["status"] == "completed"
        assert export["parent_generation_id"] == gid
        state["export_id"] = export["id"]

        history = _ok(client.get("/api/history/generations"), "GET history")
        assert any(g["id"] == export["id"] for g in history["generations"])

        assert export["video_url"].startswith("/api/media/videos/")
        media = client.get(export["video_url"])
        assert media.status_code == 200, f"GET {export['video_url']} -> {media.status_code}"
        assert len(media.content) > 0

    def test_10_variations_duplicate_delete(self, journey):
        client, state = journey["client"], journey["state"]
        gid = state["generation_id"]
        kinds = _ok(client.get("/api/studio/variations"), "GET variation kinds")
        assert any(k["key"] == "hook_line" for k in kinds["variations"])

        var = _ok(client.post(f"/api/generations/{gid}/variations", json={
            "kind": "hook_line", "value": "Stop doing this", "note": "e2e",
        }), "POST variation")
        assert var["project"]["status"] == "draft"
        assert var["parent_generation_id"] == gid
        assert var["project"]["hook_line"] == "Stop doing this"

        dup = _ok(client.post(f"/api/generations/{gid}/duplicate"),
                  "POST duplicate")
        assert dup["parent_generation_id"] == gid
        assert dup["project"]["status"] == "draft"
        assert dup["project"]["script"]

        children = _ok(client.get(f"/api/generations/{gid}/variations"),
                       "GET generation variations")
        assert isinstance(children["variations"], list)

        # Delete the export from test 09 (not the original): deletions target
        # generations, and theJourney keeps the render that spawned them.
        gone = _ok(client.delete(f"/api/generations/{state['export_id']}"),
                   "DELETE export generation")
        assert gone["deleted"] == state["export_id"]
        assert client.get(f"/api/generations/{state['export_id']}").status_code == 404
