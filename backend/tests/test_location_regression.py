"""Location consolidation: normalization, legacy reads, edits and generation snapshots."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_service
import generation_planning
from test_influencer_workflow import (
    api as api_fixture, _make_project, _store_strategy, _mark_ready, _mock_submit,
    NURSE_APP, NURSE_PERSONA, NURSE_SCENE, ANON,
)
from models import UpdateStudioProjectRequest, StudioGenerationRequest


def run(coro):
    return asyncio.run(coro)


def legacy_project(api_fixture):  # noqa: F811 - imported pytest fixture injection
    project, _, _ = _make_project(api_fixture, {**NURSE_APP, "brand_name": "TEST_Location"})
    raw = {"hook_line": "Test hook", "scene": {
        "environment": "A quiet kitchen at night.",
        "background": "A wooden table.", "setting": "A quiet kitchen at night.",
    }}
    run(api_fixture._execute("UPDATE studio_projects SET strategy = ? WHERE id = ?",
                     (json.dumps(raw), project["id"])))
    return project["id"]


def test_scene_json_has_only_unified_location():
    scene = ai_service.normalize_strategy({"scene": {
        "environment": "Kitchen", "background": "Table", "setting": "Kitchen",
    }})["scene"]
    assert scene["location"] == "Kitchen. Table."
    assert set(scene).isdisjoint({"environment", "background", "setting"})


def test_deduplication_handles_case_whitespace_and_subsumed_values():
    value = ai_service.merge_legacy_location({
        "location": "A quiet kitchen with a wooden table.",
        "environment": "  A QUIET kitchen  ", "background": "wooden table",
    })
    assert value == "A quiet kitchen with a wooden table."


def test_normalization_is_idempotent():
    normalized = ai_service.normalize_strategy({"scene": {"environment": "Kitchen", "background": "Table"}})
    assert ai_service.normalize_strategy(normalized) == normalized


def test_non_english_distinct_place_details_are_preserved():
    value = ai_service.merge_legacy_location({"environment": "東京の公園", "background": "桜の木"})
    assert "東京の公園" in value and "桜の木" in value


def test_legacy_saved_project_read_returns_one_location(api_fixture):  # noqa: F811
    project = run(api_fixture.get_studio_project(legacy_project(api_fixture), ANON))
    assert project["location"] == "A quiet kitchen at night. A wooden table."
    assert project["strategy"]["scene"]["location"] == project["location"]
    assert set(project["strategy"]["scene"]).isdisjoint({"environment", "background", "setting"})


def test_explicit_location_replaces_legacy_scene_place(api_fixture):  # noqa: F811
    project_id = legacy_project(api_fixture)
    run(api_fixture.update_studio_project(project_id, UpdateStudioProjectRequest(
        strategy={"scene": {"location": "A city rooftop at noon."}}), ANON))
    project = run(api_fixture.get_studio_project(project_id, ANON))
    assert project["strategy"]["scene"]["location"] == "A city rooftop at noon."


def test_review_location_edit_persists_and_invalidates_strategy(api_fixture):  # noqa: F811
    project_id = legacy_project(api_fixture)
    run(api_fixture._execute("UPDATE studio_projects SET script_version = 1, strategy_script_version = 1 WHERE id = ?", (project_id,)))
    run(api_fixture.update_studio_project(project_id, UpdateStudioProjectRequest(location="A city rooftop at noon."), ANON))
    project = run(api_fixture.get_studio_project(project_id, ANON))
    assert project["location"] == "A city rooftop at noon."
    assert project["strategy_is_current"] is False


def test_render_prompt_uses_unified_location_without_legacy_labels():
    strategy = ai_service.normalize_strategy({"hook_line": "Test hook", "scene": {
        "environment": "Kitchen", "background": "Wooden table", "setting": "Kitchen",
    }})
    prompt = generation_planning.build_segment_prompt(strategy, {"brand_name": "TEST_App"}, duration=12)
    assert "Location: Kitchen. Wooden table." in prompt
    for label in ("Environment:", "Background:", "Setting:"):
        assert label.lower() not in prompt.lower()


def test_selected_plan_location_wins_over_generated_scene_drift(monkeypatch):
    async def fake_chat(**_kwargs):
        return {
            "strategy_summary": "Test strategy",
            "audience_problem": "Test problem",
            "emotional_triggers": ["relief"],
            "hook_concept": "Test concept",
            "hook_line": "Test hook",
            "hook_promise": "Test promise",
            "hook_action": "Test action",
            "messaging_pillars": ["Test benefit"],
            "primary_feature": "Test feature",
            "desired_outcome": "Test outcome",
            "mechanism_beat": "Test mechanism",
            "payoff_beat": "Test payoff",
            "differentiation_beat": "Test difference",
            "scene": {"location": "A generic kitchen."},
            "performance": {"movement": "Still", "voice_delivery": "Direct"},
            "segments": [
                {"index": 0, "role": "hook", "seconds": 4, "script": "Test hook"},
                {"index": 1, "role": "middle", "seconds": 8, "script": "Test story"},
            ],
        }

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat)
    strategy = run(ai_service.generate_video_strategy(
        profile={"brand_name": "TEST_App"},
        template={},
        total_duration=12,
        plan={
            "hook_line": "Test hook",
            "script": "Test story",
            "location": "A city rooftop at noon.",
        },
    ))
    assert strategy["scene"]["location"] == "A city rooftop at noon."


def test_generation_detail_snapshots_location(api_fixture, monkeypatch):  # noqa: F811
    project, _, _ = _make_project(api_fixture, {**NURSE_APP, "brand_name": "TEST_Snapshot"})
    _store_strategy(api_fixture, project["id"], "A long shift.", NURSE_PERSONA, NURSE_SCENE,
                    problem="Shift paperwork", feature="One-tap shift logging", cta="")
    _mark_ready(api_fixture, project["id"])
    calls = _mock_submit(api_fixture, monkeypatch)  # MOCKED provider: no paid video job is started.
    generation = run(api_fixture.submit_project_generation(project["id"], StudioGenerationRequest(), ANON))
    expected = ai_service.normalize_strategy({"scene": {"location": NURSE_SCENE["location"]}})["scene"]["location"]
    detail = run(api_fixture.get_generation(generation["id"], ANON))
    assert calls and detail["location"] == expected
    run(api_fixture.update_studio_project(project["id"], UpdateStudioProjectRequest(location="A changed room."), ANON))
    assert run(api_fixture.get_generation(generation["id"], ANON))["location"] == expected


def test_history_api_returns_generation_location_snapshot(api_fixture):  # noqa: F811
    from models import now_iso
    project, _, _ = _make_project(api_fixture, {**NURSE_APP, "brand_name": "TEST_History"})
    run(api_fixture._execute("INSERT INTO generations (id, studio_project_id, user_id, status, location, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                     ("TEST_location_history", project["id"], ANON, "failed", "A city rooftop at noon.", now_iso())))
    rows = run(api_fixture.generation_history(user_id=ANON))["generations"]
    row = next(row for row in rows if row["id"] == "TEST_location_history")
    assert row.get("location") == "A city rooftop at noon."