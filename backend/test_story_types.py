"""
The v1 story-type catalog (ADR 0227): four types, data only.

Kasra delegated the Stories decisions to platform research (Nov 19 2026);
the settled set is these four types with per-type default frame lengths —
teaser 10s, question/poll 5s, demo moment 15s, announcement 10s — inside
the page's 5/10/15 pick. Testimonial-style is deliberately absent: the app
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
        assert story_types.default_frame_seconds("hook_teaser") == 10
        assert story_types.default_frame_seconds("question_poll") == 5
        assert story_types.default_frame_seconds("demo_moment") == 15
        assert story_types.default_frame_seconds("announcement_countdown") == 10

    def test_every_default_fits_the_single_pass_cap(self):
        # A story frame is one render of 5-15 seconds: the catalog models
        # cap a single pass at 15s and the page offers a 5/10/15 pick, so
        # no default may sit outside that band.
        for story_type in story_types.STORY_TYPES:
            assert 5 <= story_type["default_seconds"] <= 15

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
        assert entry["default_seconds"] == 15
