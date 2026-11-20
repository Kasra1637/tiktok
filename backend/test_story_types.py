"""
The v1 story-type catalog (ADR 0227): four types, data only.

Kasra delegated the Stories decisions to platform research (Nov 19 2026)
and ruled on Nov 20 2026 that the first lengths were far too long — a
story frame is a beat, not a short video (ADR 0238). The settled set is
these four types with per-type default frame lengths — teaser 4s,
question/poll 3s, demo moment 5s, announcement 4s — inside the page's
3/4/5 pick. Testimonial-style is deliberately absent: the app
has no source of real user quotes to ground one, and inventing a quote is
not a type, it is a fabrication. These tests pin the catalog so a later
phase cannot quietly add, drop, rename, or re-time a type.
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

import story_types


class TestStoryTypeCatalog:
    def test_exactly_the_four_settled_types_in_order(self):
        assert story_types.STORY_TYPE_IDS == (
            "hook_teaser",
            "question_poll",
            "demo_moment",
            "announcement_countdown",
        )
        assert len(story_types.STORY_TYPES) == 4

    def test_display_names_are_the_settled_ones(self):
        names = {t["id"]: t["name"] for t in story_types.STORY_TYPES}
        assert names == {
            "hook_teaser": "Hook teaser",
            "question_poll": "Question / poll prompt",
            "demo_moment": "Demo moment",
            "announcement_countdown": "Announcement / countdown",
        }

    def test_default_frame_lengths_are_the_researched_ones(self):
        assert story_types.default_frame_seconds("hook_teaser") == 4
        assert story_types.default_frame_seconds("question_poll") == 3
        assert story_types.default_frame_seconds("demo_moment") == 5
        assert story_types.default_frame_seconds("announcement_countdown") == 4

    def test_the_frame_pick_is_three_four_five(self):
        # ADR 0238: the page offers exactly the beat lengths — 5s is the
        # ceiling (Instagram's photo hold), never a default to grow into.
        assert story_types.STORY_FRAME_SECONDS == (3, 4, 5)

    def test_every_default_fits_the_frame_pick(self):
        for story_type in story_types.STORY_TYPES:
            assert story_type["default_seconds"] in story_types.STORY_FRAME_SECONDS

    def test_spoken_word_budgets_scale_with_the_frame(self):
        # Natural speech runs about two and a half words a second
        # (ADR 0238): 3s holds 7 words, 4s holds 9, 5s holds 12.
        assert story_types.spoken_word_budget(3) == 7
        assert story_types.spoken_word_budget(4) == 9
        assert story_types.spoken_word_budget(5) == 12
        assert story_types.spoken_word_budget(10) is None

    def test_every_type_says_what_it_is_for_in_one_line(self):
        for story_type in story_types.STORY_TYPES:
            description = story_type["description"]
            assert description and description.strip()
            assert "\n" not in description

    def test_testimonial_is_not_a_v1_type(self):
        assert "testimonial" not in story_types.STORY_TYPE_IDS
        assert story_types.get_story_type("testimonial") is None

    def test_unknown_type_resolves_to_nothing_not_a_fallback(self):
        assert story_types.get_story_type("nope") is None
        assert story_types.get_story_type("") is None
        assert story_types.default_frame_seconds("nope") is None

    def test_lookup_returns_the_catalog_entry(self):
        entry = story_types.get_story_type("demo_moment")
        assert entry["name"] == "Demo moment"
        assert entry["default_seconds"] == 5
