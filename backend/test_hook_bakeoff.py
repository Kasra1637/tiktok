"""
The hook bake-off (ADR 0130) and the rewrite length rule.

Kasra's directive: every generation should land hook and script around
8-9/10. The mechanism he approved is choice, not more rules — after the
plan's draft passes the hard gates, THREE alternative hooks are written
for the same story, the existing deterministic gates filter them (a
candidate that breaks a gate is out however well it would score, and the
certified outcome is a hard requirement, not a bonus), and the existing
craft scorer picks the strongest survivor. The draft hook is the
incumbent: a candidate ships only when it scores strictly higher, so
the bake-off can never make a plan worse than the single-hook flow.

Length is part of the same directive: a suggestion or candidate over
its line's set character length is never accepted — over-length spoken
lines overlap when rendered, because the words are laid over the video,
so generation is sized by the set lengths rather than checked after the
fact. The hook rewrite therefore takes the hook's set length as a hard
acceptance rule, like the script-line rewrite already took its share of
the script's ceiling.

The provider is scripted by prompt marker: the base plan prompt, the
bake-off prompt ("HOOK BAKE-OFF"), the bake-off correction prompt
("BAKE-OFF CORRECTION") and the craft correction ("CRAFT CORRECTION")
each get their canned reply, so the call sequence is the evidence.
"""
import asyncio
import json as _json
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))


def _run(coro):
    return asyncio.run(coro)


class _Response:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.text = _json.dumps(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def _completion(content, finish_reason="stop"):
    return {"choices": [{"finish_reason": finish_reason,
                         "message": {"content": content}}]}


class _ScriptedProvider:
    """Stands in for httpx.AsyncClient; replies by prompt marker."""

    def __init__(self, plan, candidates=None, correction=None, truncate_candidates=False):
        self.plan = plan
        self.candidates = candidates
        self.correction = correction
        self.truncate_candidates = truncate_candidates
        self.payloads = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, json=None):
        self.payloads.append(json)
        prompt = json["messages"][1]["content"]
        if "HOOK BAKE-OFF" in prompt and "BAKE-OFF CORRECTION" not in prompt:
            if self.truncate_candidates:
                return _Response(_completion("", finish_reason="length"))
            return _Response(_completion(_json.dumps({"hooks": self.candidates or []})))
        if "BAKE-OFF CORRECTION" in prompt:
            return _Response(_completion(_json.dumps({"hook_line": self.correction})))
        return _Response(_completion(_json.dumps(self.plan)))


def _patch_provider(monkeypatch, provider):
    import ai_service
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", lambda *a, **k: provider)
    monkeypatch.setattr(ai_service, "OPENROUTER_API_KEY", "test")
    return provider


# --- World 1: FocusApp, no certified outcome. Craft totals against this
# script, measured on the shipped scorer: draft 79, low 78, gated star 83
# (bare place), over-ceiling star 82, best clean 86. The gated lines
# outscore every clean line but the draft — that is what makes the gate,
# not the score, the decider in test (a).
SCRIPT_1 = (
    "The blank page just sits there until one small prompt gives my hands "
    "somewhere to start. I still do not know why the first line is always the hard one."
)
DRAFT_HOOK = "Starting is hard for me every single morning at my desk."
LOW_CLEAN = "At 7 a.m. the first line never comes, whatever I try."
BEST_CLEAN = "Every morning the blank page wins and work never starts."
GATED_STAR = "At bus stop the blank page wins again, every morning."
GATED_OFFICE = "At office the blank page wins again, every morning."
OVER_LONG = (
    "Every morning the blank page wins, the work never starts, and the "
    "first line never comes before the coffee goes cold."
)


def _plan(hook, script):
    return {
        "hook_line": hook,
        "script": script,
        "beat_timeline": [
            {"start": 0, "end": 3, "label": "hook", "text": hook},
            {"start": 3, "end": 20, "label": "middle", "text": script},
        ],
        "visual_direction": "Desk by a window",
        "demo_brief": "Record the first line being written.",
        "voice_direction": "Calm",
        "sound_direction": "Room tone",
        "claims_used": [],
    }


def _generate_1(monkeypatch, provider):
    import ai_service
    _patch_provider(monkeypatch, provider)
    return _run(ai_service.generate_creative_plan(
        profile={"brand_name": "FocusApp"},
        template={"name": "T", "hook_seconds": 3},
        duration_seconds=20,
    ))


class TestHookBakeOff:
    def test_a_gated_candidate_is_never_picked_even_when_it_would_score_highest(self, monkeypatch):
        """The bare-place star (83) and the over-ceiling star (82) both
        outscore the draft (79) and the one clean candidate (78). The
        gates run first, so neither can ship — and with no clean
        candidate above the draft, the draft itself stays."""
        provider = _ScriptedProvider(
            _plan(DRAFT_HOOK, SCRIPT_1),
            candidates=[GATED_STAR, LOW_CLEAN, OVER_LONG],
        )
        result = _generate_1(monkeypatch, provider)
        assert result["hook_line"] == DRAFT_HOOK

    def test_the_certified_outcome_is_a_hard_requirement_not_a_bonus(self, monkeypatch):
        """In the certified world the highest-scoring candidate (81)
        promises something else and is filtered; the carrying candidate
        only ties the draft (76), so the draft stays."""
        import ai_service
        script = (
            "The list just sits there until the timer starts and the first task feels "
            "small enough to touch. I still do not know why starting always feels bigger than the work."
        )
        plan = {
            "hook_line": "Starting is where the setup friction wins.",
            "script": script,
            "beat_timeline": [
                {"start": 0, "end": 3, "label": "hook", "text": "Starting is where the setup friction wins."},
                {"start": 3, "end": 15, "label": "middle", "text": script},
            ],
            "visual_direction": "Desk", "demo_brief": "Record the timer afterwards.",
            "voice_direction": "Calm", "sound_direction": "Room tone", "claims_used": [],
        }
        provider = _ScriptedProvider(plan, candidates=[
            "Every morning the list wins and nothing gets finished.",
            "One tap, no setup, and starting loses its friction.",
            "At 7 a.m. the list wins again and nothing gets finished.",
        ])
        _patch_provider(monkeypatch, provider)
        result = _run(ai_service.generate_creative_plan(
            profile={
                "brand_name": "Taskly", "core_features": ["Task timer"],
                "outcome_statements": [
                    {"from_feature": "Task timer", "outcome": "Starting without setup friction"}
                ],
            },
            template={"name": "T", "hook_seconds": 3},
            angle={
                "kind": "problem_solution", "label": "Too many lists",
                "user_problem": "Nothing gets finished", "target_audience": "Busy professionals",
                "app_feature": "Task timer", "viewer_outcome": "Invented unsupported outcome",
            },
            objective="demonstrate_feature",
            duration_seconds=15,
        ))
        assert result["hook_line"] == "Starting is where the setup friction wins."

    def test_b_among_clean_candidates_the_craft_highest_is_picked(self, monkeypatch):
        provider = _ScriptedProvider(
            _plan(DRAFT_HOOK, SCRIPT_1),
            candidates=[LOW_CLEAN, GATED_STAR, BEST_CLEAN],
        )
        result = _generate_1(monkeypatch, provider)
        assert result["hook_line"] == BEST_CLEAN
        # The candidates call carries the bake-off budget (ADR 0129's
        # rule, applied to the new family in ADR 0130).
        import ai_service
        bakeoff_payloads = [
            p for p in provider.payloads
            if "HOOK BAKE-OFF" in p["messages"][1]["content"]
        ]
        assert len(bakeoff_payloads) == 1
        assert bakeoff_payloads[0]["max_tokens"] == ai_service.HOOK_CANDIDATES_MAX_TOKENS

    def test_c_all_broken_candidates_fall_back_to_one_correction(self, monkeypatch):
        provider = _ScriptedProvider(
            _plan(DRAFT_HOOK, SCRIPT_1),
            candidates=[GATED_STAR, OVER_LONG, GATED_OFFICE],
            correction=BEST_CLEAN,
        )
        result = _generate_1(monkeypatch, provider)
        assert result["hook_line"] == BEST_CLEAN
        corrections = [
            p for p in provider.payloads
            if "BAKE-OFF CORRECTION" in p["messages"][1]["content"]
        ]
        assert len(corrections) == 1, "exactly one bounded correction may fire"

    def test_c_a_failed_correction_keeps_the_draft_hook(self, monkeypatch):
        provider = _ScriptedProvider(
            _plan(DRAFT_HOOK, SCRIPT_1),
            candidates=[GATED_STAR, OVER_LONG, GATED_OFFICE],
            correction=GATED_STAR,
        )
        result = _generate_1(monkeypatch, provider)
        assert result["hook_line"] == DRAFT_HOOK

    def test_d_a_failed_candidates_call_reproduces_todays_plan_exactly(self, monkeypatch):
        control = _generate_1(monkeypatch, _ScriptedProvider(
            _plan(DRAFT_HOOK, SCRIPT_1), candidates=[]))
        failed = _generate_1(monkeypatch, _ScriptedProvider(
            _plan(DRAFT_HOOK, SCRIPT_1), truncate_candidates=True))
        assert failed == control
        assert failed["hook_line"] == DRAFT_HOOK


class TestRewriteLengthRule:
    """A clearer-line suggestion over its line's set length is rejected
    and retried inside the existing bounded attempts; when no in-length
    suggestion lands, the failure is the typed honest one (ADR 0130)."""

    OVER_HOOK = "Every single morning the blank page wins and the first line never comes."
    IN_HOOK = "The blank page wins every morning before coffee."

    def _fake_chat(self, monkeypatch, replies):
        import ai_service
        calls = []

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            calls.append({"prompt": prompt, "context": context, "kwargs": kwargs})
            return replies[min(len(calls) - 1, len(replies) - 1)]

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        return calls

    def test_an_over_length_hook_suggestion_is_replaced_by_an_in_length_one(self, monkeypatch):
        import ai_service
        calls = self._fake_chat(monkeypatch, [
            {"hook_line": self.OVER_HOOK}, {"hook_line": self.IN_HOOK},
        ])
        line = _run(ai_service.rewrite_hook_line(
            {}, None, "Starting is hard every morning.", max_chars=60))
        assert line == self.IN_HOOK
        assert len(calls) == 2
        assert "CORRECTION" in calls[1]["prompt"]

    def test_a_hook_rewrite_that_stays_over_length_fails_honestly(self, monkeypatch):
        import ai_service
        self._fake_chat(monkeypatch, [{"hook_line": self.OVER_HOOK}])
        with pytest.raises(ai_service.RewriteRefusal) as err:
            _run(ai_service.rewrite_hook_line(
                {}, None, "Starting is hard every morning.", max_chars=60))
        assert "running long" in str(err.value)
        assert "60" in str(err.value)

    def test_an_over_length_script_line_suggestion_is_replaced_by_an_in_length_one(self, monkeypatch):
        import ai_service
        calls = self._fake_chat(monkeypatch, [
            {"line": "The page sits there and nothing moves at all this morning."},
            {"line": "The page sits there, unmoving."},
        ])
        line = _run(ai_service.rewrite_spoken_line(
            {}, None, "The page just sits there this morning.", "middle",
            hook_line=DRAFT_HOOK, script=SCRIPT_1, max_chars=40))
        assert line == "The page sits there, unmoving."
        assert len(calls) == 2

    def test_a_script_line_rewrite_that_stays_over_length_fails_honestly(self, monkeypatch):
        import ai_service
        self._fake_chat(monkeypatch, [
            {"line": "The page sits there and nothing moves at all this morning."},
        ])
        with pytest.raises(ai_service.RewriteRefusal) as err:
            _run(ai_service.rewrite_spoken_line(
                {}, None, "The page just sits there this morning.", "middle",
                hook_line=DRAFT_HOOK, script=SCRIPT_1, max_chars=40))
        assert "running long" in str(err.value)
