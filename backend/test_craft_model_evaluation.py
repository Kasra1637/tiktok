"""ADR 0312: the Craft check is evaluated by the app's own model.

The deterministic checklist stops being the only judge: its eight
categories, caps, cue vocabularies and lift texts are handed to the
app's text model (Muse Ember) as a rubric, and the model returns
per-category scores, findings and lifts in the same report shape the
app already stores and renders. The deterministic scorer stays as
the fallback — a failed, timed-out or unusable model reply scores
the pair the way it always did, so no page can break because the
evaluator is a model.
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

import ai_service
import creative_quality

HOOK = "I'm trying to keep count, Saturday afternoon and I keep losing count"
SCRIPT = (
    "I press my palm to my stomach and count the breaths out loud. "
    "It is always the third one where it slips away from me."
)

# One score per category, inside every reachable cap, mixed strong and
# weak so the total, grade and next-steps rule are all exercised.
SCORES = {
    "hook_stopping_power": 14,
    "audience_truth": 11,
    "clarity": 9,
    "concreteness": 8,
    "story_arc": 12,
    "spoken_naturalness": 9,
    "demo_handoff": 4,
    "trust_compliance": 10,
}


def _payload(scores=None, evidence=None, next_step=None):
    scores = SCORES if scores is None else scores
    return {
        "dimensions": {
            key: {
                "score": score,
                "evidence": evidence or [f"Finding for {key} on this clip."],
                "next_step": next_step or f"Lift for {key}.",
            }
            for key, score in scores.items()
        }
    }


def _run(coro):
    return asyncio.run(coro)


class TestRubric:
    def test_rubric_carries_every_category_with_its_caps(self):
        rubric = creative_quality.evaluation_rubric()
        for key, label, weight in creative_quality._DIMENSIONS:
            assert label in rubric
            assert f"worth {weight} points" in rubric
        # The honest caps (ADR 0300): Hook can actually award 17 of
        # its 20, Audience truth 13 of its 15, and the eight together
        # reach 95, not 100.
        assert "can actually award 17" in rubric
        assert "can actually award 13" in rubric
        assert "95" in rubric

    def test_rubric_carries_the_checklists_own_lifts_verbatim(self):
        # The lift handed to the model for each category is the exact
        # sentence the deterministic scorer returns for that category.
        rubric = creative_quality.evaluation_rubric()
        probe = creative_quality.assess_spoken_quality(HOOK, SCRIPT)
        for dimension in probe["dimensions"].values():
            assert dimension["next_step"] in rubric

    def test_rubric_carries_the_checklists_cue_vocabularies(self):
        rubric = creative_quality.evaluation_rubric()
        # Words straight out of the scorer's own cue constants.
        assert "download" in rubric  # promotion cues
        assert "game changer" in rubric  # founder cues
        assert "look back" in rubric  # app-behavior cues
        assert "i ve been" in rubric  # journal-entry openers

    def test_rubric_states_the_grade_bands_the_app_computes(self):
        rubric = creative_quality.evaluation_rubric()
        assert "85" in rubric and "70" in rubric and "55" in rubric

    def test_evaluation_prompt_hands_the_model_the_pair_and_the_rubric(self):
        prompt = creative_quality.evaluation_prompt(
            HOOK, SCRIPT, cover_text="Losing count again", app_name="Countly"
        )
        assert creative_quality.evaluation_rubric() in prompt
        assert HOOK in prompt and SCRIPT in prompt
        assert "Losing count again" in prompt
        assert "Countly" in prompt


class TestReportFromEvaluation:
    def test_report_matches_the_stored_shape(self):
        report = creative_quality.report_from_evaluation(
            _payload(), cover_text="Losing count again", hook_line=HOOK
        )
        deterministic = creative_quality.assess_spoken_quality(
            HOOK, SCRIPT, cover_text="Losing count again"
        )
        assert set(report) == set(deterministic)
        assert set(report["dimensions"]) == set(deterministic["dimensions"])
        for key, dimension in report["dimensions"].items():
            assert set(dimension) == set(deterministic["dimensions"][key])

    def test_total_grade_and_score10_flow_through_the_existing_math(self):
        report = creative_quality.report_from_evaluation(_payload())
        total = sum(SCORES.values())
        assert report["total"] == total
        assert report["max"] == 100
        assert report["achievable_max"] == 95
        assert report["grade"] == creative_quality._grade(total)[0]
        assert report["band"] == creative_quality._grade(total)[1]
        assert report["score10"] == round(total / 95 * 10, 1)
        # A category's 0-10 reading divides by what it can award:
        # Hook's 14 of a reachable 17, not of its nominal 20.
        hook = report["dimensions"]["hook_stopping_power"]
        assert hook["achievable_max"] == 17
        assert hook["score10"] == round(14 / 17 * 10, 1)

    def test_findings_and_lifts_pass_through(self):
        report = creative_quality.report_from_evaluation(
            _payload(evidence=["The hook names a cost."],
                     next_step="Cut the second clause.")
        )
        hook = report["dimensions"]["hook_stopping_power"]
        assert hook["evidence"] == ["The hook names a cost."]
        assert hook["next_step"] == "Cut the second clause."

    def test_next_steps_are_the_weak_categories_lifts(self):
        report = creative_quality.report_from_evaluation(_payload())
        # Demo handoff scored 4 of 10 — the one weak category — so its
        # lift leads the report's next steps, as in the deterministic
        # report's rule.
        assert report["next_steps"] == ["Lift for demo_handoff."]

    def test_scores_are_clamped_to_the_cap_each_category_can_award(self):
        scores = dict(SCORES, hook_stopping_power=99, audience_truth=-4)
        report = creative_quality.report_from_evaluation(_payload(scores))
        assert report["dimensions"]["hook_stopping_power"]["score"] == 17
        assert report["dimensions"]["audience_truth"]["score"] == 0
        expected = (
            sum(SCORES.values())
            - SCORES["hook_stopping_power"] - SCORES["audience_truth"] + 17
        )
        assert report["total"] == expected

    @pytest.mark.parametrize("bad", [
        {},
        {"dimensions": {}},
        {"dimensions": {"hook_stopping_power": {"score": 3, "evidence": ["x"], "next_step": "y"}}},
        _payload({**SCORES, "clarity": "high"}),
        _payload(evidence="not a list"),
        {"dimensions": {key: {"score": 1, "evidence": [], "next_step": "x"}
                        for key in SCORES}},
        {"dimensions": {key: {"score": 1, "evidence": ["x"], "next_step": ""}
                        for key in SCORES}},
        "not even a dict",
    ])
    def test_unusable_output_is_rejected(self, bad):
        with pytest.raises(ValueError):
            creative_quality.report_from_evaluation(bad)


class TestModelEvaluation:
    def _install_fake_chat(self, monkeypatch, *, result=None, error=None):
        calls = []

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            calls.append({
                "system_message": system_message, "prompt": prompt,
                "context": context, "kwargs": kwargs,
            })
            if error is not None:
                raise error
            return result

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        return calls

    def test_mocked_model_reply_becomes_the_report(self, monkeypatch):
        calls = self._install_fake_chat(monkeypatch, result=_payload())
        report = _run(ai_service.assess_spoken_quality_with_model(
            HOOK, SCRIPT, cover_text="Losing count again",
        ))
        assert report["total"] == sum(SCORES.values())
        assert report["dimensions"]["story_arc"]["score"] == 12
        # The model was handed the checklist's rubric and the pair,
        # under a structured-output schema, on the app's text model.
        assert len(calls) == 1
        assert creative_quality.evaluation_rubric() in calls[0]["prompt"]
        assert HOOK in calls[0]["prompt"]
        assert calls[0]["kwargs"].get("json_schema") is not None
        assert calls[0]["kwargs"].get("model") in (None, ai_service.TEXT_MODEL)

    def test_over_cap_model_scores_are_clamped(self, monkeypatch):
        self._install_fake_chat(
            monkeypatch, result=_payload({**SCORES, "hook_stopping_power": 20}))
        report = _run(ai_service.assess_spoken_quality_with_model(HOOK, SCRIPT))
        assert report["dimensions"]["hook_stopping_power"]["score"] == 17

    def test_failed_model_call_falls_back_to_the_deterministic_report(self, monkeypatch):
        self._install_fake_chat(monkeypatch, error=RuntimeError("provider down"))
        report = _run(ai_service.assess_spoken_quality_with_model(HOOK, SCRIPT))
        deterministic = creative_quality.assess_spoken_quality(HOOK, SCRIPT)
        assert report["total"] == deterministic["total"]
        assert report["dimensions"] == deterministic["dimensions"]

    def test_garbage_model_reply_falls_back_to_the_deterministic_report(self, monkeypatch):
        self._install_fake_chat(monkeypatch, result={"dimensions": {"nope": 1}})
        report = _run(ai_service.assess_spoken_quality_with_model(HOOK, SCRIPT))
        deterministic = creative_quality.assess_spoken_quality(HOOK, SCRIPT)
        assert report["total"] == deterministic["total"]
        assert report["dimensions"] == deterministic["dimensions"]

    def test_empty_lines_never_call_the_model(self, monkeypatch):
        def forbidden(*args, **kwargs):
            raise AssertionError("the model must not be called for empty lines")

        monkeypatch.setattr(ai_service, "_chat_json", forbidden)
        report = _run(ai_service.assess_spoken_quality_with_model("", ""))
        assert report["total"] == 0


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-craft-model-")
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
    asyncio.run(server.init_db())
    try:
        yield server
    finally:
        sys.modules.pop("server", None)


class TestReportReaders:
    def test_history_read_accepts_a_stored_model_report(self, api):
        report = creative_quality.report_from_evaluation(
            _payload(), cover_text="Losing count again", hook_line=HOOK
        )
        row = {"quality_report": json.dumps(report), "hook_line": HOOK,
               "script": SCRIPT}
        read = api._quality_report_for_row(row)
        assert read["total"] == report["total"]
        assert read["score10"] == report["score10"]
        assert set(read["dimensions"]) == set(report["dimensions"])
        assert read["dimensions"]["hook_stopping_power"]["evidence"] == (
            report["dimensions"]["hook_stopping_power"]["evidence"]
        )
