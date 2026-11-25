"""ADR 0187: the opening movement is rapid, story-enacting, and unique.

The founder compared two of his own renders frame by frame (Nov 17 2026).
The mural render he loves opens with the story's action already being
performed in front of the camera — counting the days on her fingers,
caught mid-count — and closes with energy. The quad-steps render opened
with a hand resting on her chest for its first seconds: the hook's body
arrived late. His rule: every video opens mid-motion with a rapid,
attention-grabbing movement that physically enacts THIS video's story,
and closes on a sharp beat with the same energy.

Minutes later he refined the channel: NOT always a hand gesture. "Some
human movement or behavior whether it's her face, mouth, hand, camera or
something — all the time should be unique to the video." The channel is
chosen per video (hand or fingers, face or expression, mouth, body, or a
camera move toward the presenter), never the same device by default and
never a fixed gesture; the mural's finger-count is one example of the
shape, not a template.

These tests pin the rule's wording in the surfaces that author or carry
the behavior direction: the shared block, the plan prompt, the strategy
prompt (schema lines included), the two-section schema, and the render
prompt assembly in both its forms. They assert instruction text, never
model output. The Craft check scorer is untouched by the rule
(generator-side only, the founder's standing order), and a test pins
that too.
"""
import asyncio
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent


def _run(coro):
    return asyncio.run(coro)


# The rule's load-bearing phrases. One list, so a wording drift in any
# surface fails against the same standard the founder stated.
RULE_PHRASES = (
    "OPEN MID-MOTION, RAPID",
    "already underway",
    "hand sitting on the chest",
    "slow settle",
    "physically performs the central action of THIS video's script",
    "derived from the script's moment",
    "THE CHANNEL IS THIS VIDEO'S ALONE",
    "a camera move toward the presenter",
    "never the same device by default",
    "CLOSE WITH ENERGY",
    "passive smile hold",
)


def _capture_prompt(monkeypatch, flow):
    """Run one generation flow against a fake model and keep its prompt."""
    import ai_service

    captured = {}
    plan = {
        "hook_line": "Starting is where the setup friction wins.",
        "script": "One timer makes the list feel smaller. "
        "I start the first task without the setup friction, and the "
        "rest of the list waits its turn quietly behind it.",
        "beat_timeline": [
            {"start": 0, "end": 3, "label": "hook",
             "text": "Starting is where the setup friction wins."},
            {"start": 3, "end": 15, "label": "middle",
             "text": "One timer makes the list feel smaller."},
        ],
        "visual_direction": "Desk", "demo_brief": "Record the timer afterwards.",
        "voice_direction": "Calm", "sound_direction": "Room tone",
        "claims_used": [],
    }
    strategy = {key: "x" for key in ai_service.REQUIRED_STRATEGY_KEYS}
    strategy.update({"scene": {}, "performance": {}, "segments": [],
                     "messaging_pillars": [], "emotional_triggers": []})

    async def fake_chat_json(system_message, prompt, context, **kwargs):
        captured["prompt"] = prompt
        return plan if flow == "plan" else strategy

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
    args = {
        "profile": {
            "id": "profile-1", "brand_name": "Taskly",
            "core_features": ["Task timer"],
            "outcome_statements": [{
                "from_feature": "Task timer",
                "outcome": "Starting without setup friction",
            }],
        },
        "template": {"id": "template-1", "name": "Name the misdiagnosis",
                     "hook_seconds": 3},
        "angle": {
            "id": "angle-1", "kind": "problem_solution",
            "label": "Too many lists", "user_problem": "Nothing gets finished",
            "target_audience": "Busy professionals",
            "app_feature": "Task timer",
            "viewer_outcome": "Invented unsupported outcome",
        },
        "objective": "demonstrate_feature",
    }
    if flow == "plan":
        _run(ai_service.generate_creative_plan(**args, duration_seconds=15))
    else:
        _run(ai_service.generate_video_strategy(
            **args, hook_seconds=3, total_duration=15))
    return captured["prompt"]


class TestTheSharedBlock:
    def test_the_block_states_the_whole_rule(self):
        import ai_service

        block = ai_service._behavior_direction_rules_block()
        assert block.startswith("BEHAVIOR DIRECTION")
        for phrase in RULE_PHRASES:
            assert phrase in block, f"the behavior rule is missing {phrase!r}"


class TestPlanPrompt:
    def test_the_plan_prompt_carries_the_rule_verbatim(self, monkeypatch):
        """Plan generation authors the hook beat's action text, so the
        rule rides in the plan prompt itself — the strategy-refresh path
        regenerates through this same prompt, so it is covered by the
        same pin."""
        import ai_service

        prompt = _capture_prompt(monkeypatch, "plan")
        assert ai_service._behavior_direction_rules_block() in prompt
        for phrase in RULE_PHRASES:
            assert phrase in prompt, f"the plan prompt is missing {phrase!r}"


class TestStrategyPrompt:
    def test_the_strategy_prompt_carries_the_rule_verbatim(self, monkeypatch):
        import ai_service

        prompt = _capture_prompt(monkeypatch, "strategy")
        assert ai_service._behavior_direction_rules_block() in prompt
        for phrase in RULE_PHRASES:
            assert phrase in prompt, f"the strategy prompt is missing {phrase!r}"

    def test_the_hook_action_schema_demands_the_derived_movement(self, monkeypatch):
        """The derived-gesture requirement, asserted as instruction text:
        hook_action must be a rapid movement already underway in the
        first frame that performs this script's central action through
        the channel this story calls for — not a move the model invents
        independently of the script, and never the banned resting open."""
        prompt = _capture_prompt(monkeypatch, "strategy")
        assert "ALREADY UNDERWAY in the first frame" in prompt
        assert "physically performs the central action of this video's script" in prompt
        assert "through the channel this story calls for" in prompt

    def test_the_two_section_schema_carries_the_same_demand(self):
        """The hook segment's action line is part of the strategy prompt
        (ai_strategy._two_section_schema), so it states the same rule in
        its own words rather than the old generic first-beat list."""
        import ai_strategy

        schema = ai_strategy._two_section_schema(12)
        assert "already underway in the first frame" in schema
        assert "physically performs the central action" in schema
        assert "never a resting pose or a slow settle" in schema


class TestRenderPrompt:
    """The render assembly phrases movement itself (the opening-interrupt
    directive and the final-beat templates), so the rule is restated
    there as fixed text — the strategy's fields ride verbatim beneath
    it, and this is the standard they are read against."""

    def _prompt(self, budget=None, camera_setup="handheld"):
        import generation_planning as gp

        strategy = {
            "camera_setup": camera_setup,
            "hook_line": "I keep losing count by Thursday.",
            "hook_concept": "She counts the days and loses her place.",
            "hook_action": "She counts on her fingers in front of the camera, pausing mid-count.",
            "segments": [
                {"role": "hook", "goal": "stop the scroll",
                 "script": "I keep losing count by Thursday.",
                 "action": "She counts on her fingers in front of the camera, pausing mid-count."},
                {"role": "middle", "goal": "develop the hook",
                 "script": "One list on the fridge ended the recounting.",
                 "action": "She taps the list once and looks back at the lens."},
            ],
        }
        kwargs = dict(
            strategy=strategy, profile={"brand_name": "ShiftLog"},
            template={}, duration=12, assets={}, plan={"hook_seconds": 3},
        )
        if budget is None:
            # The full form, selected with a roomy budget: the default is
            # HeyGen's tight ceiling itself since ADR 0327, which builds
            # the condensed form these tests do not pin.
            return gp.build_segment_prompt(**kwargs, prompt_budget=20000)
        return gp.build_segment_prompt(**kwargs, prompt_budget=budget)

    def test_the_full_prompt_states_the_enacting_opening(self):
        prompt = self._prompt()
        assert "physically performs this story's central action" in prompt
        assert "a camera move toward the presenter" in prompt
        assert "no hand sitting on the chest" in prompt
        assert "no slow settle" in prompt

    def test_the_full_prompt_closes_with_energy(self):
        prompt = self._prompt()
        assert "no soft fade, no passive smile hold" in prompt

    def test_the_condensed_prompt_keeps_every_constraint(self):
        """Condensing drops examples, never constraints (the house rule
        for the condensed twin)."""
        prompt = self._prompt(budget=4096)
        assert "enacts this story's central action" in prompt
        assert "no resting pose, hand on the chest, or slow settle" in prompt
        assert "no passive smile hold" in prompt

    def test_the_fixed_camera_close_carries_the_openings_energy(self):
        prompt = self._prompt(camera_setup="fixed")
        assert "Sharp, with the opening's energy" in prompt

    def test_the_single_pass_fallback_states_the_rule(self):
        """The no-strategy builder phrases the opening itself, so it
        carries the same rule rather than a thinner one."""
        import generation_planning as gp

        prompt = gp._assemble_single_pass_prompt({}, {}, {}, 10, "full", False)
        assert "physically performs the story's central action" in prompt
        assert "hand sitting on the chest" in prompt
        assert "passive smile hold" in prompt


class TestHalfSecondSnap:
    """ADR 0223: the snap completes inside the first HALF second, the
    action is caught at its sharpest instant, and the voice starts with
    the first frame.

    ADR 0187's wording let the snap complete inside "roughly the first
    second", and renders kept landing the opening's energy near a full
    second in — the retention cliff is at seconds 1-2, so a late snap
    spends the hook's best moment arriving. The founder's settled
    doctrine was always stricter (the snap inside the first half
    second); this tightens every surface that states the timing to say
    it, adds the sharpest-instant tie (the central action caught at its
    peak — not a lead-in to it, not a settle into it), and puts the
    voice on the first frame: she is already speaking when the video
    opens, no lead-in pause, breath or silent beat before the hook's
    first sound. No new element and no on-screen text: movement and
    voice only. Generator-side, like 0187 — the scorer stays untouched.
    """

    def test_the_block_states_the_half_second_snap(self):
        import ai_service

        block = ai_service._behavior_direction_rules_block()
        assert "its snap completes inside the first half second" in block
        assert "(rapid, story-enacting, inside the first half second)" in block
        assert "roughly the first second" not in block

    def test_the_block_catches_the_action_at_its_sharpest_instant(self):
        import ai_service

        block = ai_service._behavior_direction_rules_block()
        assert "at its sharpest instant" in block
        assert "not a lead-in to the action" in block

    def test_the_block_puts_the_voice_on_the_first_frame(self):
        import ai_service

        block = ai_service._behavior_direction_rules_block()
        assert "already speaking from that first frame" in block
        assert "no lead-in pause, breath or silent beat before it" in block

    def test_the_plan_prompt_states_the_half_second_snap(self, monkeypatch):
        prompt = _capture_prompt(monkeypatch, "plan")
        assert "its snap complete inside the first half second" in prompt
        assert "roughly the first second" not in prompt

    def test_the_strategy_prompt_states_the_half_second_snap(self, monkeypatch):
        prompt = _capture_prompt(monkeypatch, "strategy")
        assert "its snap complete inside the first half second" in prompt
        assert "at its sharpest instant" in prompt
        assert "roughly the first second" not in prompt

    def test_the_strategy_prompt_puts_the_voice_on_the_first_frame(self, monkeypatch):
        prompt = _capture_prompt(monkeypatch, "strategy")
        assert "the voice starts with the first frame" in prompt

    def test_the_two_section_schema_states_the_half_second_snap(self):
        import ai_strategy

        schema = ai_strategy._two_section_schema(12)
        assert "its snap complete inside the first half second" in schema
        assert "at its sharpest instant" in schema
        assert "roughly the first second" not in schema

    def _render_prompt(self, budget=None):
        import generation_planning as gp

        strategy = {
            "camera_setup": "handheld",
            "hook_line": "I keep losing count by Thursday.",
            "hook_concept": "She counts the days and loses her place.",
            "hook_action": "She counts on her fingers in front of the camera, pausing mid-count.",
            "segments": [
                {"role": "hook", "goal": "stop the scroll",
                 "script": "I keep losing count by Thursday.",
                 "action": "She counts on her fingers in front of the camera, pausing mid-count."},
                {"role": "middle", "goal": "develop the hook",
                 "script": "One list on the fridge ended the recounting.",
                 "action": "She taps the list once and looks back at the lens."},
            ],
        }
        kwargs = dict(
            strategy=strategy, profile={"brand_name": "ShiftLog"},
            template={}, duration=12, assets={}, plan={"hook_seconds": 3},
        )
        if budget is None:
            # The full form, selected with a roomy budget: the default is
            # HeyGen's tight ceiling itself since ADR 0327, which builds
            # the condensed form these tests do not pin.
            return gp.build_segment_prompt(**kwargs, prompt_budget=20000)
        return gp.build_segment_prompt(**kwargs, prompt_budget=budget)

    def test_the_full_render_prompt_states_the_half_second_snap(self):
        prompt = self._render_prompt()
        assert "snap done inside that half-second" in prompt
        assert "at its sharpest instant" in prompt
        assert "snap done in the first second" not in prompt
        assert "roughly the first second" not in prompt

    def test_the_full_render_prompt_puts_the_voice_on_the_first_frame(self):
        prompt = self._render_prompt()
        assert "already speaking from the first frame" in prompt
        assert "words come second" not in prompt

    def test_the_condensed_render_prompt_keeps_the_tightened_rule(self):
        prompt = self._render_prompt(budget=4096)
        assert "snap inside the first half-second" in prompt
        assert "at its sharpest instant" in prompt
        assert "voice already speaking" in prompt
        assert "snap in the first second" not in prompt

    def test_the_single_pass_prompt_states_the_tightened_rule(self):
        import generation_planning as gp

        plan = {
            "hook_line": "I keep losing count by Thursday.",
            "script": "One list on the fridge ended the recounting.",
        }
        prompt = gp._assemble_single_pass_prompt(plan, {}, {}, 10, "full", False)
        assert "its snap complete inside the first half second" in prompt
        assert "at its sharpest instant" in prompt
        assert "already speaking from the first frame" in prompt
        assert "roughly the first second" not in prompt


class TestScorerUntouched:
    def test_the_rule_never_enters_the_craft_scorer(self):
        """Generator-side only (the founder's standing rule): the Craft
        check scorer's source carries none of the rule's wording."""
        src = (BACKEND_DIR / "creative_quality.py").read_text(encoding="utf-8")
        assert "BEHAVIOR DIRECTION" not in src
        assert "physically performs the central action" not in src
        assert "OPEN MID-MOTION" not in src
