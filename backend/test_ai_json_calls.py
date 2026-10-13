"""
Tests for the JSON-call failure modes that produced
"Video strategy did not return valid JSON" in production.

The bug: generate_video_strategy asked for the largest JSON schema in the
codebase (~45 values across five nested objects) with a 4000-token budget on
a thinking model whose thought tokens are drawn from the same completion
budget. The reply was cut off mid-object, and the truncated
JSON failed the parser in exactly the same way as a model that wrapped its
answer in prose, so the only clue was "did not return valid JSON" and the real
cause — a too-small budget — went unquestioned.

These pin: truncation is detected and named as such, the retry actually grows
the budget, a formatting slip is retried with a stricter instruction, and a
truncation is never reported as a JSON-formatting problem.
"""
import asyncio
import importlib
import json
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))


class _Response:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.text = json.dumps(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _Recorder:
    """Stands in for httpx.AsyncClient and records the payloads it is given."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.payloads = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, json=None):
        self.payloads.append(json)
        payload = self.responses[min(len(self.payloads) - 1, len(self.responses) - 1)]
        if isinstance(payload, _Response):
            return payload
        return _Response(payload)


def _completion(content, finish_reason="stop"):
    return {"choices": [{"finish_reason": finish_reason,
                         "message": {"content": content}}]}


def _patch_client(monkeypatch, responses):
    import ai_service
    rec = _Recorder(responses)
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", lambda *a, **k: rec)
    monkeypatch.setattr(ai_service, "OPENROUTER_API_KEY", "test")
    return rec


class TestChatJson:
    def test_a_clean_object_parses_on_the_first_attempt(self, monkeypatch):
        import ai_service
        rec = _patch_client(monkeypatch, [_completion('{"hook_line": "Hi"}')])
        result = _run(ai_service._chat_json("sys", "prompt", "Ctx"))
        assert result == {"hook_line": "Hi"}
        assert len(rec.payloads) == 1, "a good reply must not cost a retry"

    def test_fences_and_trailing_prose_are_tolerated(self, monkeypatch):
        import ai_service
        body = 'Sure!\n```json\n{"a": 1, "b": {"c": 2}}\n```\nHope that helps.'
        _patch_client(monkeypatch, [_completion(body)])
        assert _run(ai_service._chat_json("sys", "prompt", "Ctx")) == {"a": 1, "b": {"c": 2}}

    def test_truncation_raises_truncated_not_a_json_error(self, monkeypatch):
        """
        The distinction that was missing. A cut-off reply is a length problem;
        reporting it as "did not return valid JSON" sends you hunting for a
        formatting bug that does not exist.
        """
        import ai_service
        half = '{"hook_line": "It was always this one tap", "character": {"appearance": "a n'
        # Both attempts truncated: the budget is genuinely too small.
        _patch_client(monkeypatch, [_completion(half, finish_reason="length")])
        with pytest.raises(ai_service.TruncatedResponse) as err:
            _run(ai_service._chat_json("sys", "prompt", "Ctx", max_tokens=8192))
        assert "cut off" in str(err.value)
        assert "valid JSON" not in str(err.value)

    def test_the_retry_actually_grows_the_budget(self, monkeypatch):
        """
        Repeating a truncated request at the same size truncates identically,
        so the retry must differ. This asserts the number, not just the count.
        """
        import ai_service
        half = '{"hook_line": "abc'
        rec = _patch_client(
            monkeypatch, [_completion(half, finish_reason="length")])
        with pytest.raises(ai_service.TruncatedResponse):
            _run(ai_service._chat_json("sys", "prompt", "Ctx", max_tokens=8000))
        assert len(rec.payloads) == 2
        first, second = rec.payloads[0]["max_tokens"], rec.payloads[1]["max_tokens"]
        assert first == 8000
        assert second > first, f"retry budget {second} did not grow from {first}"
        # And the retry also asks for shorter values, since a bigger budget
        # alone is not a fix for an over-long schema.
        assert "under 25 words" in rec.payloads[1]["messages"][1]["content"]

    def test_truncation_recovers_when_the_bigger_budget_is_enough(self, monkeypatch):
        """The happy path for the fix: one retry turns a failure into a result."""
        import ai_service
        half = '{"hook_line": "It was always this one tap", "character": {"appear'
        rec = _patch_client(monkeypatch, [
            _completion(half, finish_reason="length"),
            _completion('{"hook_line": "It was always this one tap"}'),
        ])
        result = _run(ai_service._chat_json("sys", "prompt", "Ctx", max_tokens=8000))
        assert result["hook_line"] == "It was always this one tap"
        assert len(rec.payloads) == 2

    def test_a_prose_refusal_is_named_not_a_json_error(self, monkeypatch):
        """
        "I cannot help with that." has no braces at all — it is a refusal,
        not a formatting slip. Reporting it as "did not return valid JSON"
        used to send everyone hunting for a parser or budget problem while
        the model had simply declined the prompt.
        """
        import ai_service
        rec = _patch_client(monkeypatch, [_completion("I cannot help with that.")])
        with pytest.raises(ai_service.ModelRefusal) as err:
            _run(ai_service._chat_json("sys", "prompt", "Ctx"))
        # Retried once (temperature sometimes works), then named as a refusal.
        assert len(rec.payloads) == 2
        assert "prose" in str(err.value) or "declined" in str(err.value)
        assert "valid JSON" not in str(err.value)
        assert not isinstance(err.value, ai_service.TruncatedResponse)

    def test_malformed_json_with_braces_is_still_a_json_error(self, monkeypatch):
        """
        The counterpart: braces present but unparseable is genuinely a format
        problem, and must keep the JSON error rather than being renamed.
        """
        import ai_service
        rec = _patch_client(monkeypatch, [_completion('{"a": 1,')])
        with pytest.raises(RuntimeError) as err:
            _run(ai_service._chat_json("sys", "prompt", "Ctx", attempts=1))
        assert "valid JSON" in str(err.value)
        assert not isinstance(err.value, ai_service.ModelRefusal)

    def test_a_filtered_reply_names_the_finish_reason(self, monkeypatch):
        import ai_service
        rec = _patch_client(monkeypatch, [
            _completion("I can't help with that topic.", finish_reason="content_filter")])
        with pytest.raises(ai_service.ModelRefusal) as err:
            _run(ai_service._chat_json("sys", "prompt", "Ctx", attempts=1))
        assert "content_filter" in str(err.value)

    def test_literal_newlines_inside_strings_are_salvaged(self, monkeypatch):
        """
        The most common model formatting slip: a raw newline inside a string
        value. strict=False accepts it with zero semantic change, so this
        parses on the first attempt instead of costing a retry.
        """
        import ai_service
        rec = _patch_client(monkeypatch, [_completion('{"a": "line one\nline two"}')])
        assert _run(ai_service._chat_json("sys", "prompt", "Ctx")) == {"a": "line one\nline two"}
        assert len(rec.payloads) == 1

    def test_a_formatting_slip_recovers_on_retry(self, monkeypatch):
        import ai_service
        rec = _patch_client(monkeypatch, [
            _completion("Here you go:\n```json\n{'single': 'quotes'}\n```"),
            _completion('{"ok": true}'),
        ])
        assert _run(ai_service._chat_json("sys", "prompt", "Ctx")) == {"ok": True}
        assert len(rec.payloads) == 2
        assert "ONE complete JSON object" in rec.payloads[1]["messages"][1]["content"]

    def test_no_choices_is_its_own_error(self, monkeypatch):
        import ai_service
        _patch_client(monkeypatch, [{"id": "x"}])
        with pytest.raises(RuntimeError) as err:
            _run(ai_service._chat_json("sys", "prompt", "Ctx"))
        assert "no response" in str(err.value)

    def test_empty_content_names_the_finish_reason(self, monkeypatch):
        import ai_service
        _patch_client(monkeypatch, [
            _completion("", finish_reason="content_filter")])
        with pytest.raises(RuntimeError) as err:
            _run(ai_service._chat_json("sys", "prompt", "Ctx", attempts=1))
        assert "content_filter" in str(err.value)


class TestGpt5MiniRequestShape:
    """
    GPT-5 Mini replaces GPT-4o Mini on every chat flow. Two consequences
    travel with the family and are pinned here rather than re-discovered
    as production 400s:

    - temperature other than the default 1 is rejected, so it must never
      be sent (the determinism it bought on 4o-mini is gone with it);
    - max_tokens stays (OpenRouter maps it), and reasoning tokens come out
      of the same budget, which the truncation retry already covers.
    """

    def test_chat_models_point_at_gpt5_mini(self):
        import ai_service
        assert ai_service.TEXT_MODEL == "openai/gpt-5-mini"
        assert ai_service.VISION_MODEL == "openai/gpt-5-mini"

    def test_temperature_is_never_sent(self, monkeypatch):
        import ai_service
        rec = _patch_client(monkeypatch, [_completion('{"a": 1}')])
        assert _run(ai_service._chat_json("sys", "prompt", "Ctx", temperature=0.4)) == {"a": 1}
        assert rec.payloads[0]["model"] == "openai/gpt-5-mini"
        assert "temperature" not in rec.payloads[0]

    def test_no_response_format_without_a_schema(self, monkeypatch):
        import ai_service
        rec = _patch_client(monkeypatch, [_completion('{"a": 1}')])
        _run(ai_service._chat_json("sys", "prompt", "Ctx"))
        assert "response_format" not in rec.payloads[0]

    def test_response_format_carries_a_strict_schema(self, monkeypatch):
        import ai_service
        schema = {
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "required": ["a"],
            "additionalProperties": False,
        }
        rec = _patch_client(monkeypatch, [_completion('{"a": "1"}')])
        _run(ai_service._chat_json("sys", "prompt", "Ctx", json_schema=schema))
        rf = rec.payloads[0]["response_format"]
        assert rf["type"] == "json_schema"
        assert rf["json_schema"]["strict"] is True
        assert rf["json_schema"]["schema"] == schema
        assert rf["json_schema"]["name"] == "ctx"

    def test_every_shipped_schema_is_strict(self):
        """
        Strict mode rejects any object whose properties are not all required
        with nothing else admitted. A helper walks every shipped schema the
        way the provider validates it, so a loose object cannot slip in with
        a new field and fail every call at request time.
        """
        import ai_service

        def check(node, path):
            if isinstance(node, dict) and node.get("type") == "object":
                props = node.get("properties", {})
                assert sorted(node.get("required", [])) == sorted(props), (
                    f"{path}: required must list every property"
                )
                assert node.get("additionalProperties") is False, (
                    f"{path}: additionalProperties must be false"
                )
                for key, sub in props.items():
                    check(sub, f"{path}.{key}")
            elif isinstance(node, dict) and node.get("type") == "array":
                check(node.get("items", {}), f"{path}[]")

        for name in (
            "APP_PROFILE_JSON_SCHEMA",
            "ANGLES_JSON_SCHEMA", "PLAN_JSON_SCHEMA", "STRATEGY_JSON_SCHEMA",
        ):
            check(getattr(ai_service, name), name)

    def test_direct_flows_send_response_format(self, monkeypatch):
        """
        The flows that post httpx directly (not through _chat_json) must
        still carry the envelope: app research, angles, plan.
        """
        import ai_service

        profile_keys = ai_service.REQUIRED_APP_PROFILE_KEYS
        list_keys = set(ai_service.APP_PROFILE_LIST_KEYS) | {
            "outcome_statements", "viewer_objections"}
        profile = {
            k: ([] if k in list_keys else "") for k in profile_keys}
        angle = {
            "kind": "problem_solution", "label": "L",
            "target_audience": "a", "user_problem": "p",
            "hook_promise": "h", "app_feature": "f",
            "desired_emotion": "e", "claims_to_respect": [],
        }
        plan = {
            "hook_line": "h", "script": "s",
            "beat_timeline": [
                {"start": 0, "end": 3, "label": "hook", "text": "t"},
                {"start": 3, "end": 20, "label": "middle", "text": "t"},
            ],
            "visual_direction": "v", "demo_brief": "d",
            "voice_direction": "vd", "sound_direction": "sd",
            "claims_used": [],
        }
        rec = _patch_client(monkeypatch, [
            _completion(json.dumps(profile)),
            _completion(json.dumps({"angles": [angle]})),
            _completion(json.dumps(plan)),
        ])
        _run(ai_service.analyze_app_profile({"app_store": "text"}))
        _run(ai_service.generate_content_angles({"brand_name": "B"}))
        _run(ai_service.generate_creative_plan(
            profile={"brand_name": "B"}, template={"name": "T"}))
        assert len(rec.payloads) == 3
        for payload in rec.payloads:
            assert payload["response_format"]["type"] == "json_schema"
            assert "temperature" not in payload


class TestAngleFeedbackPromptWiring:
    ANGLE = {
        "kind": "problem_solution", "label": "Too many lists",
        "target_audience": "Busy professionals", "user_problem": "Nothing gets finished",
        "hook_promise": "Finish one thing", "app_feature": "Task timer",
        "desired_emotion": "Relief", "claims_to_respect": [],
    }

    def _capture(self, monkeypatch):
        import ai_service
        captured = {}

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            captured["prompt"] = prompt
            return [dict(self.ANGLE)]

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        return captured

    def test_verdicts_reach_the_angle_prompt(self, monkeypatch):
        import ai_service
        import feedback as feedback_mod
        captured = self._capture(monkeypatch)
        summary = feedback_mod.summarize_angle_feedback([
            {"kind": "problem_solution", "objective": "demonstrate_feature",
             "event": "thumb_up", "step": "goal"},
        ])
        _run(ai_service.generate_content_angles(
            {"brand_name": "Taskly"}, angle_feedback=summary))
        assert "problem_solution (1 win(s), 0 flop(s))" in captured["prompt"]

    def test_no_record_reads_as_no_evidence_not_silence(self, monkeypatch):
        import ai_service
        import feedback as feedback_mod
        captured = self._capture(monkeypatch)
        _run(ai_service.generate_content_angles(
            {"brand_name": "Taskly"},
            angle_feedback=feedback_mod.summarize_angle_feedback([])))
        assert "PAST VERDICTS: none recorded" in captured["prompt"]

    def test_omitted_feedback_leaves_the_prompt_untouched(self, monkeypatch):
        import ai_service
        captured = self._capture(monkeypatch)
        _run(ai_service.generate_content_angles({"brand_name": "Taskly"}))
        assert "PAST VERDICTS" not in captured["prompt"]

    def test_generation_caps_at_six_angles(self, monkeypatch):
        """The audience step shows exactly six suggestions: the prompt asks
        for exactly six and the cap holds even when the model overshoots."""
        import ai_service

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            assert "exactly 6" in prompt
            return [dict(self.ANGLE) for _ in range(9)]

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        out = _run(ai_service.generate_content_angles({"brand_name": "Taskly"}))
        assert len(out) == 6


class TestAngleGoalPromptWiring:
    @pytest.mark.parametrize("flow", ["plan", "strategy"])
    def test_an_override_advances_the_goal_without_replacing_the_angle(self, monkeypatch, flow):
        import ai_service

        captured = {}
        plan = {
            "hook_line": "Too many lists?", "script": "Too many lists? Start with one task.",
            "beat_timeline": [{"start": 0, "end": 3, "label": "hook", "text": "Too many lists?"},
                              {"start": 3, "end": 15, "label": "middle", "text": "Start with one task."}],
            "visual_direction": "Desk", "demo_brief": "Record the timer afterwards.",
            "voice_direction": "Calm", "sound_direction": "Room tone", "claims_used": [],
        }
        strategy = {key: "x" for key in ai_service.REQUIRED_STRATEGY_KEYS}
        strategy.update({"scene": {}, "performance": {}, "segments": [],
                         "messaging_pillars": [], "emotional_triggers": []})

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            captured["prompt"] = prompt
            return plan if flow == "plan" else strategy

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        args = {
            "profile": {"id": "profile-1", "brand_name": "Taskly", "core_features": ["Task timer"]},
            "template": {"id": "template-1", "name": "Name the misdiagnosis", "hook_seconds": 3},
            "angle": {"id": "angle-1", "kind": "problem_solution", "label": "Too many lists",
                      "user_problem": "Nothing gets finished", "target_audience": "Busy professionals"},
            "objective": "demonstrate_feature",
        }
        if flow == "plan":
            _run(ai_service.generate_creative_plan(**args, duration_seconds=15))
        else:
            result = _run(ai_service.generate_video_strategy(**args, hook_seconds=3, total_duration=15))
            assert result["objective"] == "demonstrate_feature"
            assert result["content_angle_id"] == "angle-1"

        prompt = captured["prompt"]
        for required in ("ANGLE + GOAL RULE", "Busy professionals", "Nothing gets finished",
                         "demonstrate_feature", "founder's later demo/CTA"):
            assert required in prompt
        assert "NEVER" in prompt and "product demonstration" in prompt


class TestTruncatedResearchRetriesDoubled:
    """
    Production failure, 2026-10-10: app-profile research at max_tokens=4000
    truncated mid-object under GPT-5 Mini (reasoning tokens share the
    budget) and surfaced as "App profile did not return valid JSON" — a
    formatting error for what was a length problem, with no retry. These
    flows now route through _chat_json, so truncation is detected, retried
    doubled, and named as truncation when it persists.
    """

    def _full_profile(self):
        import ai_service
        list_keys = set(ai_service.APP_PROFILE_LIST_KEYS) | {
            "outcome_statements", "viewer_objections"}
        profile = {
            k: ([] if k in list_keys else "x")
            for k in ai_service.REQUIRED_APP_PROFILE_KEYS}
        profile["brand_name"] = "Vocolens"
        return profile

    def test_truncated_research_recovers_on_the_doubled_retry(self, monkeypatch):
        import ai_service
        half = '{"brand_name": "Vocolens", "brand_description": "Voice-first AI journal'
        rec = _patch_client(monkeypatch, [
            _completion(half, finish_reason="length"),
            _completion(json.dumps(self._full_profile())),
        ])
        result = _run(ai_service.analyze_app_profile({"website": "text"}))
        assert result["brand_name"] == "Vocolens"
        assert len(rec.payloads) == 2
        assert rec.payloads[0]["max_tokens"] == 8000
        assert rec.payloads[1]["max_tokens"] == 16000
        for payload in rec.payloads:
            assert payload["response_format"]["type"] == "json_schema"

    def test_persistently_truncated_research_names_truncation(self, monkeypatch):
        import ai_service
        half = '{"brand_name": "Vocolens", "brand_description": "Voice-first AI journal'
        _patch_client(monkeypatch, [_completion(half, finish_reason="length")])
        with pytest.raises(ai_service.TruncatedResponse) as err:
            _run(ai_service.analyze_app_profile({"website": "text"}))
        assert "cut off" in str(err.value)
        assert "valid JSON" not in str(err.value)


class TestScriptVoiceAndTarget:
    """
    The script generation rules: a natural-delivery target rather than a hard
    model ceiling, no padding to reach it, a customer's voice rather than the
    founder's, and a rewrite-to-fit before the video model is called.
    """

    def test_the_spoken_pace_is_150_characters_over_10_seconds(self):
        import ai_service
        assert ai_service.SPOKEN_CHARS_PER_SECOND == 15
        assert ai_service.spoken_budget(10) == 150

    def test_the_prompts_write_from_the_customer_perspective(self):
        src = (BACKEND_DIR / "ai_service.py").read_text(encoding="utf-8")
        assert "CUSTOMER PERSPECTIVE" in src
        assert "satisfied customer" in src
        assert "never the app's founder, owner, developer or marketer" in src

    def test_the_budget_is_a_natural_delivery_target_not_a_hard_ceiling(self):
        src = (BACKEND_DIR / "ai_service.py").read_text(encoding="utf-8")
        assert "natural delivery, not an arbitrary maximum" in src
        assert "NEVER pad with filler words" in src

    def test_an_over_length_script_is_rewritten_by_the_one_rule(self):
        """One arithmetic does the rewriting, not a second one beside it.

        `partition_spoken_words` sizes both spoken lines: the plan arrival clamp
        calls it before the row is written, and the render path calls it (as
        `repair_spoken_story`) before the prompt is built. A separate condensing
        helper existed for a moment and cut the script's TAIL, which is where
        the payoff sentence lives; it is gone.
        """
        src = (BACKEND_DIR / "ai_service.py").read_text(encoding="utf-8")
        assert "def partition_spoken_words" in src
        assert "def repair_spoken_story" in src
        assert "condense_script_to_target" not in src
        server_src = (BACKEND_DIR / "server.py").read_text(encoding="utf-8")
        assert "partition_spoken_words(" in server_src
        assert "repair_spoken_story(" in server_src


class TestStrategyBudget:
    def test_strategy_uses_a_budget_that_fits_its_schema(self):
        """
        Guard the number itself. The strategy object is the largest in the
        codebase, and 4000 tokens is what produced the production failure.
        """
        import re
        src = (BACKEND_DIR / "ai_service.py").read_text(encoding="utf-8")
        match = re.search(
            r"raw = await _chat_json\((?:[^)]*?)max_tokens=(\d+)", src, re.S)
        assert match, "generate_video_strategy should route through _chat_json"
        assert int(match.group(1)) >= 8192, (
            f"strategy max_tokens is {match.group(1)}; the schema needs headroom "
            f"for thinking tokens on top of ~45 JSON values"
        )

    def test_the_prompt_bounds_value_length(self):
        """
        A budget is a backstop, not the fix. The prompt also has to ask for
        concise values, or every strategy costs a retry.

        The opening's physical performance is the one deliberate exemption: it is
        written as ordered timed beats, and a 25-word cap would cut it back to
        the generic gesture this change exists to replace.
        """
        src = (BACKEND_DIR / "ai_service.py").read_text(encoding="utf-8")
        assert "Keep every string value under 25 words" in src
        assert "no markdown fence" in src
        assert "may run to about 45 words" in src

    def test_the_prompt_demands_a_physical_pattern_interrupt_opening(self, monkeypatch):
        """
        The render cannot invent an opening: it films the beats the strategy
        writes. So the strategy prompt has to ask for them by body part, timed,
        with the expression treated as an action rather than as a description of
        the face, which the founder's photograph owns.
        """
        import ai_service

        captured = {}

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            captured["prompt"] = prompt
            return {
                "strategy_summary": "s", "audience_problem": "p",
                "emotional_triggers": ["t"], "hook_concept": "c",
                "hook_line": "h", "hook_promise": "p", "hook_action": "a",
                "messaging_pillars": ["m"], "primary_feature": "f",
                "desired_outcome": "o", "mechanism_beat": "mb",
                "payoff_beat": "pb", "differentiation_beat": "b",
                "scene": {"environment": "kitchen"},
                "performance": {"movement": "still"},
                "segments": [{"index": 0, "role": "hook", "seconds": 3,
                              "goal": "g", "script": "s", "action": "a"},
                             {"index": 1, "role": "middle", "seconds": 17,
                              "goal": "g", "script": "s", "action": "a"}],
            }

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        asyncio.run(ai_service.generate_video_strategy(
            profile={
                "brand_name": "ShiftLog",
                "brand_description": "Shift logging for healthcare workers.",
                "app_category": "Productivity",
                "usage_moments": ["the end of a night shift"],
            },
            template={"name": "T", "hook_seconds": 3},
            hook_seconds=3,
        ))
        prompt = captured["prompt"]

        assert "PATTERN INTERRUPT" in prompt
        for requirement in (
            "first frame must already be moving",
            "first half-second",
            "Never a neutral pose",
            "escalate",
            "posture and shoulders",
            "brows",
            "aimed at the lens",
            "own situation",
            "only the middle closes",
        ):
            assert requirement in prompt, f"opening rule missing: {requirement}"
        # The appearance prohibition still governs: expression is an action, and
        # the photograph is the only authority on who the person is.
        assert "Say what the face does, never what the face is" in prompt
        assert "may run to about 45 words" in prompt

    def test_the_prompt_frames_the_pitch_as_outcomes_not_features(self, monkeypatch):
        """
        The middle earns the download by describing what changes for the
        viewer, not what the app contains. The prompt has to demand the
        translation explicitly -- "focus on benefits" alone kept the feature
        list and appended adjectives -- and it has to scope the outcome
        language to the mechanism and payoff moments, never the hook.
        """
        import ai_service

        captured = {}

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            captured["prompt"] = prompt
            return {
                "strategy_summary": "s", "audience_problem": "p",
                "emotional_triggers": ["t"], "hook_concept": "c",
                "hook_line": "h", "hook_promise": "p", "hook_action": "a",
                "messaging_pillars": ["m"], "primary_feature": "f",
                "desired_outcome": "o", "mechanism_beat": "mb",
                "payoff_beat": "pb", "differentiation_beat": "b",
                "scene": {"environment": "kitchen"},
                "performance": {"movement": "still"},
                "segments": [{"index": 0, "role": "hook", "seconds": 3,
                              "goal": "g", "script": "s", "action": "a"},
                             {"index": 1, "role": "middle", "seconds": 17,
                              "goal": "g", "script": "s", "action": "a"}],
            }

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        asyncio.run(ai_service.generate_video_strategy(
            profile={
                "brand_name": "Sleeply",
                "brand_description": "A sleep app.",
                "app_category": "Health & Fitness",
                "core_features": ["sleep timer"],
                "desired_outcomes": ["Falling asleep faster"],
                "outcome_statements": [{
                    "outcome": "fall asleep without checking your phone",
                    "who_feels_it": "night-time scrollers",
                    "from_feature": "sleep timer",
                    "how_it_helps": "the wind-down starts itself",
                }],
            },
            template={"name": "T", "hook_seconds": 3},
            hook_seconds=3,
        ))
        prompt = captured["prompt"]

        for requirement in (
            # The translate step, with the worked example.
            "Translate every feature",
            "helps you fall asleep",
            "without checking your phone",
            # The two pitch moments, in order, scoped to the middle.
            "MECHANISM moment",
            "PAYOFF moment",
            "the hook has neither",
            "The hook stays attention-only",
            # Source precedence: linked statements first, derivation last.
            "outcome_statements first",
            "Never invent an outcome",
            # Benefits, not promises: the existing guarantee rule governs.
            "Benefits, not promises",
        ):
            assert requirement in prompt, f"pitch rule missing: {requirement}"
        # The schema asks for the moments, so the model must write them back.
        assert '"mechanism_beat"' in prompt
        assert '"payoff_beat"' in prompt
        # primary_feature stays the feature: it grounds the video, it does
        # not pitch it.
        assert '"primary_feature": "the ONE feature this video shows' in prompt

    def test_the_strategy_schema_defaults_to_energetic_delivery(self, monkeypatch):
        """
        Delivery has no numeric knob on any provider — the only lever is the
        prose the strategy model writes into voice_delivery, so the schema
        must ask for fast and energetic up front. Otherwise every strategy
        invents its own pace, usually slow and flat, and the scene lock then
        enforces exactly that.
        """
        import ai_service

        captured = {}

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            captured["prompt"] = prompt
            return {
                "strategy_summary": "s", "audience_problem": "p",
                "emotional_triggers": ["t"], "hook_concept": "c",
                "hook_line": "h", "hook_promise": "p", "hook_action": "a",
                "messaging_pillars": ["m"], "primary_feature": "f",
                "desired_outcome": "o", "mechanism_beat": "mb",
                "payoff_beat": "pb", "differentiation_beat": "b",
                "scene": {"environment": "kitchen"},
                "performance": {"movement": "still"},
                "segments": [{"index": 0, "role": "hook", "seconds": 3,
                              "goal": "g", "script": "s", "action": "a"},
                             {"index": 1, "role": "middle", "seconds": 17,
                              "goal": "g", "script": "s", "action": "a"}],
            }

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        asyncio.run(ai_service.generate_video_strategy(
            profile={"brand_name": "Sleeply"},
            template={"name": "T", "hook_seconds": 3},
            hook_seconds=3,
        ))
        assert "fast, upbeat, high-energy" in captured["prompt"]

    def test_a_fully_populated_prompt_stays_under_a_ceiling(self, monkeypatch):
        """
        The guard I promised and did not write the first time.

        Prompt length is not itself the budget problem -- the prompt is an input
        and 8192 covers the completion. It is a proxy for the thing that actually
        bites: every field the prompt asks for is a value the model must write
        back, so growing the request grows the reply, and the reply is what gets
        truncated. The strategy schema is already the largest in the codebase
        and 4000 tokens produced a real production failure, so this measures a
        worst case -- every field filled to its cap, the approved plan attached,
        feedback history and past performance all present -- and fails with the
        measured number, so raising the ceiling is a decision made with the
        figure in hand rather than a shrug.
        """
        import ai_service

        captured = {}

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            captured["prompt"] = prompt
            return {
                "strategy_summary": "s", "audience_problem": "p",
                "emotional_triggers": ["t"], "hook_concept": "c",
                "hook_line": "h", "hook_promise": "p", "hook_action": "a",
                "messaging_pillars": ["m"], "primary_feature": "f",
                "desired_outcome": "o", "mechanism_beat": "mb",
                "payoff_beat": "pb", "differentiation_beat": "b",
                "cta_strategy": "c", "scene": {"environment": "kitchen"},
                "performance": {"movement": "still"},
                "segments": [{"index": 0, "role": "hook", "seconds": 5,
                              "goal": "g", "script": "s", "action": "a"}],
                "continuity_contract": {
                    "established": [], "must_not_change": [], "do_not_repeat": [],
                },
            }

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)

        # Eight items per list: that is the cap APP_PROFILE_LIST_KEYS applies on
        # the way in, so it is the true worst case rather than a generous one.
        eight = [f"item {i}" for i in range(1, 9)]
        asyncio.run(ai_service.generate_video_strategy(
            profile={
                "brand_name": "ShiftLog",
                "brand_description": "Shift logging for healthcare workers.",
                "app_category": "Productivity",
                "platforms": ["iOS", "Android"],
                "core_features": eight,
                "primary_use_cases": eight,
                "problems_solved": eight,
                "icp_segments": eight,
                "desired_outcomes": eight,
                # Six linked statements: the normalizer's cap, so the worst
                # case rather than a generous one. Leaving this out would
                # understate the real maximum now that every prompt carries it.
                "outcome_statements": [
                    {
                        "outcome": f"Benefit number {i} in the viewer's own terms",
                        "who_feels_it": "hospital nurses working rotating shifts",
                        "from_feature": "item 1",
                        "how_it_helps": f"How the solution works as a benefit, number {i}",
                    }
                    for i in range(6)
                ],
                "known_limitations": "iOS and Android only; no offline mode yet.",
                "must_not_show": eight,
                "usage_moments": eight,
                "proof_moment": "One tap and the shift is on the log",
                # Six is the normalizer's cap, so six is the worst case rather
                # than a generous guess. Leaving this field out of the fixture
                # would have made the ceiling test measure a profile that no
                # real profile resembles.
                "viewer_objections": [
                    {
                        "objection": f"Objection {i}",
                        "what_they_do_now": f"The alternative they use today, number {i}",
                        "honest_answer": f"The honest answer from the facts, number {i}",
                    }
                    for i in range(6)
                ],
                "target_audience": "hospital nurses working rotating shifts",
            },
            template={
                "name": "Stop Doing This", "category": "problem",
                "opening_structure": "Name the mistake.", "hook_seconds": 5,
                "continuation_structure": "Then the fix.", "cta_pattern": "Try it",
                "visual_style": "Talking head.", "camera_pacing": "Steady.",
            "content_slots": {f"slot{i}": f"value{i}" for i in range(1, 9)},
            "required_assets": ["character_reference"],
            # The anonymous trend aggregate a research-published template
            # carries. Part of the worst case: it is a prompt section, and its
            # absence from this fixture would understate the real maximum.
            "trend_evidence": json.dumps({
                "has_signal": True,
                "sample_size": 40,
                "median_view_band": "100K-1M",
                "median_engagement_band": "typical (5-10%)",
                "recency_band": "under 48h",
            }),
        },
            angle={
                "kind": "problem", "label": "Too many lists",
                "target_audience": "nurses", "user_problem": "paperwork",
                "hook_promise": "less admin", "app_feature": "one-tap logging",
                "desired_emotion": "relief", "recommended_cta": "Try it free",
                "claims_to_respect": ["works offline"],
            },
            objective="address_user_problem", hook_seconds=5,
            total_duration=30, tone="calm", brand_voice="plain, tired, warm",
            profile_feedback={
                "total": 200, "template_rejections": 9, "generation_rejections": 12,
                "heavy_script_edits": 2,
                "top_reasons": [{"reason": "hook_too_generic", "count": 7}],
                "selected_template": {},
            },
            plan={
                "hook_line": "h", "cta": "c", "feature_emphasis": "f",
                "visual_direction": "v", "voice_direction": "vd",
                "sound_direction": "sd",
                "beat_timeline": [
                    {"start": i * 5, "end": i * 5 + 5, "beat": f"beat {i}"}
                    for i in range(4)
                ],
            },
        ))

        prompt = captured["prompt"]
        # Measured worst case, with every list at its cap, six viewer objections,
        # six outcome statements and the anonymous trend aggregate: 21,065 chars.
        # The ceiling sits just above at 22,500.
        #
        # The number has moved four times now -- 13,692 before the objections,
        # 15,226 after, 20,675 after the outcome layer (linked statements in
        # every prompt plus the pitch rules that consume them) -- and it moved
        # *because* the fixture was corrected, not because the ceiling was
        # raised. Two earlier versions of this test used a round number picked
        # without measuring and let a real inflation through, so the figure
        # quoted in the failure message is the one to trust.
        #
        # Two things worth recording about the most recent move, because the one
        # before it is the lesson. The 20,675 above had gone stale without anyone
        # noticing: HEAD measured 21,440, which left 60 chars of headroom, so an
        # unmeasured growth of 765 had already slipped past a quoted figure that
        # no longer described reality. What moved it now is deliberate and
        # measured -- 174 chars for the capitalization rule, which is the only
        # thing standing between a lowercase opening sentence and the card it
        # renders on. Measured first, raised second. The move after that is
        # deliberate too -- removing the PAST PERFORMANCE block with the
        # manual-results loop (549 chars), since no hand-typed numbers feed
        # generation anymore.
        CEILING = 22_500
        assert len(prompt) <= CEILING, (
            f"fully-populated strategy prompt is {len(prompt)} chars "
            f"(~{len(prompt) // 4} tokens), over the {CEILING} ceiling (measured "
            f"worst case 21,065). Every field added here is a value the model must "
            f"write back, and a truncated strategy is a 502 the founder cannot fix."
        )

    def test_the_schema_still_asks_for_a_bounded_number_of_values(self):
        """
        The same concern counted directly rather than through prompt length.

        Was pinned on CONTINUATION_BEATS, which was the one part of the schema
        that scaled with a constant: pinning it is what stopped a future edit
        from quietly asking for twenty beats and paying for it in truncation
        retries.

        That constant is gone. A video is ONE render with exactly TWO sections —
        the hook and the middle — so the number is structural rather than a
        budget: a third section would be the product demo, which this workflow
        does not generate. What still has to hold is that the count is exactly
        two, that the two roles are the ones everything downstream reads, and
        that normalization cannot hand back more than the schema asked for.
        """
        import ai_service
        assert ai_service.GENERATED_SECTIONS == 2, (
            f"GENERATED_SECTIONS is {ai_service.GENERATED_SECTIONS}. It used to be "
            f"CONTINUATION_BEATS, a tunable budget; it is now structural — a third "
            f"generated section is a product demo, and the demo is the founder's own "
            f"recording attached afterwards."
        )
        assert ai_service.SECTION_ROLES == ("hook", "middle")
        # Truncation cannot rescue an over-long reply either: anything past the
        # second section is dropped rather than written out.
        assert ai_service.normalize_strategy({
            "hook_line": "h",
            "segments": [
                {"index": i, "role": "hook", "seconds": 3,
                 "goal": f"g{i}", "script": f"s{i}", "action": f"a{i}"}
                for i in range(9)
            ],
        })["segments"] == [
            {"index": 0, "role": "hook", "seconds": 3,
             "goal": "g0", "script": "s0", "action": "a0"},
            {"index": 1, "role": "middle", "seconds": 3,
             "goal": "g1", "script": "s1", "action": "a1"},
        ]


class TestStrategyEndpointError:
    """The endpoint must name truncation rather than leaking a JSON message."""

    @pytest.fixture(scope="class")
    def api(self):
        tmpdir = importlib.import_module("tempfile").mkdtemp(prefix="tiktok-strategy-err-")
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
        original = (server.pipeline.VIDEOS_DIR, server.pipeline.GENERATED_DIR)
        server.pipeline.VIDEOS_DIR = Path(tmpdir) / "videos"
        server.pipeline.GENERATED_DIR = Path(tmpdir) / "generated"
        server.pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        asyncio.run(server.init_db())
        yield server
        server.pipeline.VIDEOS_DIR, server.pipeline.GENERATED_DIR = original

    def _project(self, api):
        from models import (
            ApproveAppProfileRequest, BrandProfileCreateRequest,
            CreateStudioProjectRequest,
        )
        profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
            brand_name="Truncation", app_category="Productivity",
            brand_description="A focus timer for people who stall on starting.",
            core_features=["Task timer", "Reminders"],
            usage_moments=["Starting a task they have been avoiding"],
            outcome_statements=[{
                "outcome": "Starting without stalling on setup",
                "who_feels_it": "people who stall on starting",
                "from_feature": "Task timer",
                "how_it_helps": "The timer starts in one tap so there is nothing to set up",
            }],
        ), user_id="anonymous"))
        _run(api.approve_app_profile(
            profile_id=profile["id"], payload=ApproveAppProfileRequest(),
            user_id="anonymous"))
        template = _run(api.list_templates(user_id="anonymous"))["templates"][0]
        project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"], template_id=template["id"]),
            user_id="anonymous"))
        return project["id"]

    def test_truncation_is_reported_as_a_length_problem(self, api, monkeypatch):
        from fastapi import HTTPException
        from models import GenerateStrategyRequest
        from ai_service import TruncatedResponse

        async def boom(**kwargs):
            raise TruncatedResponse(
                "Video strategy was cut off after 8192 tokens (finish_reason=length) "
                "before the JSON closed"
            )

        monkeypatch.setattr(api, "generate_video_strategy", boom)
        project_id = self._project(api)
        with pytest.raises(HTTPException) as err:
            _run(api.generate_project_strategy(
                project_id=project_id, payload=GenerateStrategyRequest(),
                user_id="anonymous"))
        assert err.value.status_code == 502
        message = str(err.value.detail)
        assert "cut off" in message
        assert "valid JSON" not in message
        assert "length problem" in message

    def test_refusal_is_reported_as_a_refusal(self, api, monkeypatch):
        """
        A model that declines the prompt must not surface as a JSON error:
        the founder would retry a request that fails the same way every
        time, instead of reporting it.
        """
        from fastapi import HTTPException
        from models import GenerateStrategyRequest
        from ai_service import ModelRefusal

        async def boom(**kwargs):
            raise ModelRefusal("Video strategy returned no JSON object")

        monkeypatch.setattr(api, "generate_video_strategy", boom)
        project_id = self._project(api)
        with pytest.raises(HTTPException) as err:
            _run(api.generate_project_strategy(
                project_id=project_id, payload=GenerateStrategyRequest(),
                user_id="anonymous"))
        assert err.value.status_code == 502
        message = str(err.value.detail)
        assert "declined" in message
        assert "valid JSON" not in message

    def test_any_other_failure_still_reports_itself(self, api, monkeypatch):
        from fastapi import HTTPException
        from models import GenerateStrategyRequest

        async def boom(**kwargs):
            raise RuntimeError("Video strategy missing required fields: {'character'}")

        monkeypatch.setattr(api, "generate_video_strategy", boom)
        project_id = self._project(api)
        with pytest.raises(HTTPException) as err:
            _run(api.generate_project_strategy(
                project_id=project_id, payload=GenerateStrategyRequest(),
                user_id="anonymous"))
        assert "missing required fields" in str(err.value.detail)


class TestPlanIsForcedToTwoSections:
    """
    The plan's beat timeline is the video's spine, and it is read straight into
    the render prompt. A video is ONE render with exactly two sections — a hook
    and a middle — so a four-beat hook/problem/demo/cta timeline would render a
    product demonstration and a closing ask in footage that is supposed to stop
    at the moment the presenter reaches for their phone.

    The prompt asks for two beats and the schema names only those two labels.
    This pins that the correction actually happens where the shape is known,
    because a model returning the old four-beat shape is strongly represented in
    its training and nothing downstream would stop it.
    """

    def _plan(self, beats, hook_seconds=3, duration=15):
        import ai_service
        return ai_service._enforce_two_sections(beats, hook_seconds)

    def test_the_old_four_beat_shape_is_folded_down_to_two(self):
        """
        The four-beat hook/problem/demo/cta arc a model returns from habit comes
        back as two sections, so there is no third beat for the render to film
        and no timeline whose length reserves seconds for a demo or a close.

        The SHAPE is corrected, and so are the WORDS of the two beats that were
        only ever a demonstration and a close. Correcting the labels while
        keeping their prose was the earlier behaviour, and it left "Show the
        timer" and "Try it free" sitting in the middle's text — which goes
        verbatim into the render prompt. So a demo gets dropped on the floor
        even while the story beats are kept, because a workflow that must not
        generate a product demo cannot inherit one from a beat's text.
        """
        import ai_service
        beats = ai_service._normalize_beats([
            {"start": 0, "end": 3, "label": "hook", "text": "Open hard"},
            {"start": 3, "end": 7, "label": "problem", "text": "The friction"},
            {"start": 7, "end": 13, "label": "demo", "text": "Show the timer"},
            {"start": 13, "end": 15, "label": "cta", "text": "Try it free"},
        ], 15)
        out = self._plan(beats)
        assert [b["label"] for b in out] == ["hook", "middle"]
        assert out[0]["text"] == "Open hard"
        assert out[0]["start"] == 0 and out[0]["end"] == 3
        assert out[1]["start"] == 3
        # Nothing survives as a separately-timed third or fourth beat.
        assert len(out) == 2
        # The story the model actually told is kept.
        assert "The friction" in out[1]["text"]
        # The demonstration and the call to action are not, in any form.
        blob = " ".join(str(b.get("text") or "") for b in out)
        assert "Show the timer" not in blob
        assert "Try it free" not in blob

    def test_the_middle_absorbs_the_remainder(self):
        out = self._plan([
            {"start": 0, "end": 3, "label": "hook", "text": "h"},
            {"start": 3, "end": 8, "label": "middle", "text": "m"},
            {"start": 8, "end": 15, "label": "extra", "text": "e"},
        ])
        assert len(out) == 2
        assert out[0]["end"] == 3
        assert out[1]["start"] == 3

    def test_a_hook_only_plan_is_left_alone_rather_than_invented(self):
        """
        One section is a real possibility — a model that returned a hook and
        nothing else has said less, not more. Padding the middle with invented
        text would be worse than letting the prompt state what is missing.
        """
        out = self._plan([{"start": 0, "end": 3, "label": "hook", "text": "h"}])
        assert [b["label"] for b in out] == ["hook"]

    def test_an_unlabelled_arc_is_not_thrown_away(self):
        out = self._plan([
            {"start": 0, "end": 2, "label": "", "text": "first"},
            {"start": 2, "end": 15, "label": "", "text": "then this"},
        ])
        assert [b["label"] for b in out] == ["hook", "middle"]
        assert out[1]["text"] == "then this"

    def test_junk_is_survivable(self):
        assert self._plan([]) == []
        assert self._plan(None) == []
        assert self._plan(["not a dict", None]) == []


def _run(coro):
    return asyncio.run(coro)
