"""One fixed temperature for every text generation (founder's ruling).

Kasra ruled on Nov 17 2026 that the app speaks with one sampling
temperature — 0.4, the shared CHAT_TEMPERATURE — so the words sound
solid and consistent through every video's copy. Seven creative
flows used to override it per flow (cover text 0.6, brand templates
0.5, hook rewrite 0.6, spoken-line rewrite 0.6, hook bake-off
0.7/0.6, video strategy 0.5); those overrides are gone, and every
one of those flows rides the shared helper default (ADR 0199).

Out of scope, by the same ruling: the hook frame-analysis vision
call keeps its 0.3 (video-side, not text generation), and the
app-profile research flow — which never carried an override —
keeps its existing call path untouched.
"""
import inspect
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ai_service

# The seven flows whose explicit overrides the ruling removed.
RULED_FLOWS = (
    ai_service.generate_cover_text,
    ai_service.generate_brand_templates,
    ai_service.rewrite_hook_line,
    ai_service.rewrite_spoken_line,
    ai_service._hook_bake_off,
    ai_service.generate_video_strategy,
)


class TestOneTemperature:
    def test_the_shared_constant_is_the_ruling_value(self):
        assert ai_service.CHAT_TEMPERATURE == 0.4

    def test_the_chat_helper_defaults_to_the_constant(self):
        default = inspect.signature(ai_service._chat_json).parameters["temperature"].default
        assert default == ai_service.CHAT_TEMPERATURE

    def test_no_ruled_flow_passes_an_explicit_temperature(self):
        for flow in RULED_FLOWS:
            source = inspect.getsource(flow)
            assert not re.search(r"temperature\s*=\s*[\d.]", source), (
                f"{flow.__name__} still overrides the shared temperature"
            )

    def test_no_numeric_temperature_kwarg_anywhere_in_the_module(self):
        # The whole-module net: after the overrides came out, the only
        # temperature=<number> left in the file would be a new override
        # sneaking back. (The vision call passes 0.3 positionally through
        # _temperature_param, not as a temperature= kwarg.)
        source = Path(ai_service.__file__).read_text(encoding="utf-8")
        assert not re.search(r"temperature\s*=\s*[\d.]", source)

    def test_the_vision_call_keeps_its_own_temperature(self):
        source = inspect.getsource(ai_service.analyze_hook)
        assert "_temperature_param(VISION_MODEL, 0.3)" in source
