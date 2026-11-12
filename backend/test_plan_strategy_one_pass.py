"""
One-pass plan + strategy (Part 5, move 4): the founder's single request that
writes the plan and builds the strategy from it.

Plan and strategy used to be two sequential calls — two waits, two failure
surfaces — even though the strategy is built FROM the plan the first call
writes, so the second call could never be made first or independently.
`generate_plan_and_strategy` runs both stages server-side behind one request:
the plan stage is `generate_plan` unchanged, the strategy stage is
`generate_project_strategy` unchanged, and what the founder sees is one wait
and one error. These tests pin that contract against the real handlers with
the model calls replaced, the same way test_studio_api.py pins each stage on
its own.
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
    tmpdir = tempfile.mkdtemp(prefix="tiktok-p5-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""

    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(server.init_db())
    yield server
    sys.modules.pop("server", None)


def _run(coro):
    return asyncio.run(coro)


def _approved_profile(api, name="One Pass App", approve=True):
    from models import BrandProfileCreateRequest, ApproveAppProfileRequest
    profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
        brand_name=name,
        app_category="Productivity",
        brand_description="A focus timer for people who stall on starting.",
        core_features=["Task timer", "Reminders"],
        usage_moments=["Starting a task they have been avoiding"],
        outcome_statements=[{
            "outcome": "Starting without stalling on setup",
            "who_feels_it": "people who stall on starting",
            "from_feature": "Task timer",
            "how_it_helps": "The timer starts in one tap so there is nothing to set up",
        }],
        ctas=["Try it free"],
    ), user_id=ANON))
    if approve:
        _run(api.approve_app_profile(
            profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
        profile = _run(api.get_app_profile(profile["id"], ANON))
    return profile


def _a_template(api, name="Stop Doing This"):
    return _run(api.list_templates(q=name, user_id=ANON))["templates"][0]


def _attach_photo(api, profile, project):
    from models import now_iso
    face = Path(tempfile.mkdtemp(prefix="tiktok-onepass-")) / "face.png"
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
    _run(api._execute(
        "UPDATE studio_projects SET assets = ? WHERE id = ?",
        (json.dumps([{
            "asset_id": asset_id, "kind": "character_reference",
            "label": "Founder face", "file_path": str(face),
        }]), project["id"])))


def _a_project(api, profile, template):
    from models import CreateStudioProjectRequest
    project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
        brand_profile_id=profile["id"],
        template_id=template["id"],
        objective="demonstrate_feature",
    ), user_id=ANON))
    _attach_photo(api, profile, project)
    return _run(api.get_studio_project(project["id"], user_id=ANON))


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
}


def _fake_strategy(**_kwargs):
    return {
        "strategy_summary": "s", "audience_problem": "p",
        "emotional_triggers": ["t"], "hook_concept": "c",
        "hook_line": "You do not have a focus problem.",
        "hook_promise": "p", "hook_action": "a",
        "messaging_pillars": ["m"], "primary_feature": "f",
        "desired_outcome": "o", "mechanism_beat": "mb",
        "payoff_beat": "pb", "differentiation_beat": "b",
        "cta_strategy": "c",
        "scene": {"location": "kitchen"},
        "performance": {"movement": "still"},
        "segments": [{"index": 0, "role": "hook", "seconds": 5,
                      "goal": "g", "script": "You do not have a focus problem.",
                      "action": "a"}],
        "continuity_contract": {
            "established": ["kitchen"],
            "must_not_change": ["shirt"],
            "do_not_repeat": ["the opening line"],
        },
    }


def _patch_both(monkeypatch, api, plan=FAKE_PLAN, strategy_impl=None, plan_impl=None):
    """Replace both model calls; return the list of strategy-call kwargs seen."""
    strategy_calls = []

    async def fake_generate_creative_plan(**kwargs):
        if plan_impl is not None:
            return await plan_impl(**kwargs)
        return dict(plan)

    async def fake_generate_video_strategy(**kwargs):
        strategy_calls.append(kwargs)
        if strategy_impl is not None:
            return await strategy_impl(**kwargs)
        return _fake_strategy(**kwargs)

    monkeypatch.setattr(api, "generate_creative_plan", fake_generate_creative_plan)
    monkeypatch.setattr(api, "generate_video_strategy", fake_generate_video_strategy)
    return strategy_calls


class TestOnePass:
    def test_one_pass_returns_plan_and_strategy_together(self, api, monkeypatch):
        from models import GeneratePlanAndStrategyRequest
        _patch_both(monkeypatch, api)
        profile = _approved_profile(api, "One Pass Together")
        project = _a_project(api, profile, _a_template(api))

        result = _run(api.generate_plan_and_strategy(
            project_id=project["id"],
            payload=GeneratePlanAndStrategyRequest(objective="demonstrate_feature"),
            user_id=ANON))

        # The plan half landed exactly as the plan endpoint writes it.
        assert result["script_version"] == 1
        assert result["hook_line"] == FAKE_PLAN["hook_line"]
        assert "one short prompt" in result["script"]
        # And the strategy half is already there in the SAME response — no
        # second request, and it is stamped against the plan this pass wrote,
        # so the render gate reads it as current.
        assert result["strategy_version"] == 1
        assert result["strategy"]["hook_line"]
        assert result["strategy_script_version"] == result["script_version"]
        assert result["strategy_is_current"] is True

    def test_strategy_stage_reads_the_plan_this_pass_wrote(self, api, monkeypatch):
        from models import GeneratePlanAndStrategyRequest
        strategy_calls = _patch_both(monkeypatch, api)
        profile = _approved_profile(api, "One Pass Reads Fresh Plan")
        project = _a_project(api, profile, _a_template(api))

        _run(api.generate_plan_and_strategy(
            project_id=project["id"],
            payload=GeneratePlanAndStrategyRequest(),
            user_id=ANON))

        # The strategy generator received the approved-plan argument built
        # from the row the plan stage had just written — not a stale plan,
        # not no plan.
        assert len(strategy_calls) == 1
        plan_arg = strategy_calls[0].get("plan")
        assert plan_arg is not None
        assert plan_arg["hook_line"] == FAKE_PLAN["hook_line"]
        assert "one short prompt" in plan_arg["script"]

    def test_plan_failure_is_the_only_error_and_strategy_never_runs(self, api, monkeypatch):
        from models import GeneratePlanAndStrategyRequest

        async def broken_plan(**_kwargs):
            raise RuntimeError("model unavailable")

        strategy_calls = _patch_both(monkeypatch, api, plan_impl=broken_plan)
        profile = _approved_profile(api, "One Pass Plan Fails")
        project = _a_project(api, profile, _a_template(api))

        with pytest.raises(HTTPException) as exc:
            _run(api.generate_plan_and_strategy(
                project_id=project["id"],
                payload=GeneratePlanAndStrategyRequest(),
                user_id=ANON))
        assert exc.value.status_code == 502
        # One failure surface: the plan stage's. The strategy stage is never
        # attempted on a plan that does not exist.
        assert strategy_calls == []
        after = _run(api.get_studio_project(project["id"], user_id=ANON))
        assert after["script_version"] == 0
        assert not after.get("strategy")

    def test_strategy_failure_surfaces_once_and_the_plan_stays(self, api, monkeypatch):
        from models import GeneratePlanAndStrategyRequest

        async def broken_strategy(**_kwargs):
            raise RuntimeError("model unavailable")

        _patch_both(monkeypatch, api, strategy_impl=broken_strategy)
        profile = _approved_profile(api, "One Pass Strategy Fails")
        project = _a_project(api, profile, _a_template(api))

        with pytest.raises(HTTPException) as exc:
            _run(api.generate_plan_and_strategy(
                project_id=project["id"],
                payload=GeneratePlanAndStrategyRequest(),
                user_id=ANON))
        # The founder sees the strategy stage's failure as THE failure of the
        # one pass — not a plan success they must interpret.
        assert exc.value.status_code == 502
        assert "strategy" in str(exc.value.detail).lower()
        # The plan the pass wrote stays written: retrying the pass (or the
        # strategy panel's own rebuild) starts from it rather than from
        # nothing.
        after = _run(api.get_studio_project(project["id"], user_id=ANON))
        assert after["script_version"] == 1
        assert not after.get("strategy")

    def test_unapproved_profile_refuses_before_any_model_call(self, api, monkeypatch):
        from models import GeneratePlanAndStrategyRequest
        strategy_calls = _patch_both(monkeypatch, api)
        plan_calls = []

        async def counting_plan(**kwargs):
            plan_calls.append(kwargs)
            return dict(FAKE_PLAN)

        monkeypatch.setattr(api, "generate_creative_plan", counting_plan)
        profile = _approved_profile(api, "One Pass Draft Profile")
        project = _a_project(api, profile, _a_template(api))
        # Project creation enforces the same gate, so the state this test
        # needs — a project whose profile is no longer approved — is made
        # the way it happens in life: approval withdrawn after the fact.
        _run(api._execute(
            "UPDATE brand_profiles SET status = 'draft' WHERE id = ?",
            (profile["id"],)))

        with pytest.raises(HTTPException) as exc:
            _run(api.generate_plan_and_strategy(
                project_id=project["id"],
                payload=GeneratePlanAndStrategyRequest(),
                user_id=ANON))
        # The approval gate is not weakened by the merge: unapproved facts
        # refuse the pass before either model call, exactly as the plan
        # endpoint refuses on its own.
        assert exc.value.status_code == 409
        assert plan_calls == []
        assert strategy_calls == []

    def test_route_is_registered(self, api):
        paths = {
            (route.path, tuple(sorted(route.methods or ())))
            for route in api.app.routes
            if hasattr(route, "methods")
        }
        assert any(
            path.endswith("/studio/projects/{project_id}/plan-and-strategy")
            and "POST" in methods
            for path, methods in paths
        )
