import pytest
from fastapi import HTTPException

import server


def _project(**overrides):
    base = {
        "script_version": 1,
        "strategy_script_version": 1,
        "camera_setup": "handheld",
        "content_angle_id": "a1",
        "objective": "demonstrate_feature",
        "template_id": "t1",
        "template_version": 1,
    }
    base.update(overrides)
    return base


def _strategy(**overrides):
    base = {
        "camera_setup": "handheld",
        "content_angle_id": "a1",
        "objective": "demonstrate_feature",
        "template_id": "t1",
        "template_version": 1,
        "hook_line": "x",
    }
    base.update(overrides)
    return base


def test_strategy_matching_the_project_passes():
    project = _project()
    project["strategy"] = _strategy()
    got = server._require_current_strategy(project)
    assert got["objective"] == "demonstrate_feature"
    assert got["template_id"] == "t1"
    assert got["template_version"] == 1


def test_goal_change_after_the_strategy_build_is_refused():
    project = _project(objective="address_user_problem")
    project["strategy"] = _strategy(objective="demonstrate_feature")
    with pytest.raises(HTTPException) as exc:
        server._require_current_strategy(project)
    assert exc.value.status_code == 409


def test_template_change_after_the_strategy_build_is_refused():
    project = _project(template_id="t2")
    project["strategy"] = _strategy(template_id="t1")
    with pytest.raises(HTTPException) as exc:
        server._require_current_strategy(project)
    assert exc.value.status_code == 409


def test_template_version_change_after_the_strategy_build_is_refused():
    project = _project(template_version=2)
    project["strategy"] = _strategy(template_version=1)
    with pytest.raises(HTTPException) as exc:
        server._require_current_strategy(project)
    assert exc.value.status_code == 409


def test_pre_stamp_strategy_is_missing_history_not_a_mismatch():
    # A strategy whose objective/template stamps never landed (None, pre-stamp
    # build) is unstamped, not mismatched. It must not be refused here. The
    # normalizer may fill empty defaults, so assert policy, not identity.
    project = _project()
    project["strategy"] = _strategy(objective=None, template_id=None, template_version=None)
    got = server._require_current_strategy(project)
    assert got.get("objective") in ("", None, "demonstrate_feature")
    assert got.get("template_id") in ("", None, "t1")


def test_public_project_provenance_missing_history():
    row = {
        "id": "p1",
        "script_version": 1,
        "strategy_script_version": 1,
        "camera_setup": "handheld",
        "content_angle_id": "a1",
        "objective": "demonstrate_feature",
        "template_id": "t1",
        "template_version": 1,
        "hook_seconds": 3,
        "status": "ready_for_generation",
    }
    strategy = {"hook_line": "x", "camera_setup": "handheld"}  # no stamps at all
    row["strategy"] = __import__("json").dumps(strategy)
    out = server._public_project(row)
    assert out["strategy_is_current"] is True
