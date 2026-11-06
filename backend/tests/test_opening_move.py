"""The opening must move: ADR 0090's visible-move rule, enforced.

A static or spoken-only first beat never reaches a provider. The validator
covers both camera setups — the rule is unconditional — and the render guard
repairs additively, refusing only an opening that names no action at all.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import opening_move


def _strategy(camera_setup="handheld", hook_action="Steps into frame and turns to the lens"):
    return {
        "camera_setup": camera_setup,
        "hook_action": hook_action,
        "segments": [{"role": "hook", "action": hook_action},
                     {"role": "middle", "action": "Counts on fingers"}],
        "scene": {"location": "A kitchen", "props": "A mug"},
        "performance": {"movement": "Steps, turns, lifts a mug"},
    }


def test_static_opening_is_rejected():
    for text in ("Stands still and looks at the camera",
                 "Neutral pose, eyes on the lens",
                 "Smiles at the camera"):
        verdict = opening_move.validate_opening(_strategy(hook_action=text))
        assert not verdict["ok"], text
        assert "static" in verdict["reason"]


def test_spoken_only_opening_is_rejected():
    verdict = opening_move.validate_opening(
        _strategy(hook_action="She says the line directly to the camera"))
    assert not verdict["ok"]


def test_visible_move_passes_for_both_setups():
    for setup in ("handheld", "fixed"):
        verdict = opening_move.validate_opening(
            _strategy(camera_setup=setup,
                      hook_action="Walks to the desk, sits down and opens the notebook"))
        assert verdict["ok"], setup


def test_move_clause_after_a_static_clause_still_passes():
    verdict = opening_move.validate_opening(
        _strategy(hook_action="Stands still, then steps in and turns"))
    assert verdict["ok"]


def test_empty_opening_is_rejected_and_repair_leads_with_a_move():
    strategy = _strategy(hook_action="")
    strategy["segments"] = []
    verdict = opening_move.validate_opening(strategy)
    assert not verdict["ok"]
    repaired = opening_move.repair(strategy)
    assert repaired["ok"]
    assert opening_move.validate_opening(repaired["strategy"])["ok"]
    assert "steps into frame" in repaired["strategy"]["hook_action"].lower()


def test_repair_keeps_the_founders_words():
    strategy = _strategy(hook_action="Smiles at the camera")
    repaired = opening_move.repair(strategy)
    assert "smiles" in repaired["strategy"]["hook_action"].lower()
    assert opening_move.validate_opening(repaired["strategy"])["ok"]


def test_render_guard_repairs_a_static_opening_before_the_prompt(monkeypatch):
    import server
    strategy = _strategy(hook_action="Stands still and looks at the camera")
    project = {"id": "p1", "location": "A kitchen", "beat_timeline": []}
    patched = server._guard_render_scene(strategy, project, render_index=0)
    assert opening_move.validate_opening(patched)["ok"]
    assert "stands still" in patched["hook_action"].lower()
