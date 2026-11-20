"""
Curated Story Types — the formats the Stories page offers (ADR 0227).

A story type is the story's aim: where a hook video picks an objective
and a template, a story picks one of these. The type decides the frame's
default length and, in the phases that follow, how the story plan is
written and which native stickers the story kit prescribes.

The set and the lengths are settled, not taste. Kasra delegated the
Stories decisions to platform research (Nov 19 2026; the research file
and the plan's section 6 record the evidence): a story frame is one
render of 5–15 seconds — every catalog model caps a single pass at 15s
and TikTok caps a story segment at 15s — and no platform prescribes one
length for all stories, so each type carries the default its job wants
inside the page's 5/10/15 pick:

- Hook teaser, 10s: the middle of TikTok's 9–15s recommended band —
  long enough for the moment and the promise, short enough to point.
- Question / poll prompt, 5s: one spoken question and a tap; the
  sticker does the work, and top stories creative uses short scenes.
- Demo moment, 15s: the only type that must show something happening,
  so it takes the full segment length.
- Announcement / countdown, 10s: the beat plus the date; on Instagram
  the countdown sticker carries the deadline after the clip ends.

Testimonial-style is deliberately NOT here. The app has no claim-safety
system (ADR 0119) and no source of real user quotes to ground one;
inventing a testimonial would be an invented lookalike. It can be added
when the founder supplies the quote text themselves.

Kept separate from server.py, like template_library: this is curated
content, not request handling. Pure data — no generation, no endpoints;
later phases read it. Tests assert it.
"""

from typing import Optional

# The v1 catalog, in the order the page offers it. `description` is one
# line saying what the type is for; the plan's feature set
# (hookforge-stories-plan.md, section 2) is the source wording.
STORY_TYPES = (
    {
        "id": "hook_teaser",
        "name": "Hook teaser",
        "default_seconds": 10,
        "description": (
            "Points at the founder's newest hook video or post: the moment, "
            "the promise, and 'the full one is up' as the closing beat; "
            "the kit carries the link sticker."
        ),
    },
    {
        "id": "question_poll",
        "name": "Question / poll prompt",
        "default_seconds": 5,
        "description": (
            "The presenter asks the audience one question drawn from the "
            "angle's tension; the kit carries the poll or question sticker "
            "with the answer labels written out."
        ),
    },
    {
        "id": "demo_moment",
        "name": "Demo moment",
        "default_seconds": 15,
        "description": (
            "One app moment as a presenter beat: the spoken line ends open, "
            "and the kit's checklist walks the founder through attaching "
            "their screen recording as the next frame."
        ),
    },
    {
        "id": "announcement_countdown",
        "name": "Announcement / countdown",
        "default_seconds": 10,
        "description": (
            "A launch, update, or deadline beat; the kit carries the "
            "countdown sticker set to the date the founder chooses."
        ),
    },
)

STORY_TYPE_IDS = tuple(story_type["id"] for story_type in STORY_TYPES)

# The frame lengths the page offers (research Q4): per-type defaults
# above, and the founder's pick is one of these three — a story frame
# is one render of 5–15 seconds, and no platform prescribes a length
# between them.
STORY_FRAME_SECONDS = (5, 10, 15)

# The on-screen text caps (research Q3): the text is a native text
# sticker the founder places at posting, and it must read whole inside
# the shortest 5-second frame and carry the whole message alone for
# the muted minority. Derived from TikTok's 5–10 words-per-second
# pacing rule — a build number, not a published platform limit.
STORY_TEXT_MAX_CHARS = 80
STORY_TEXT_MAX_WORDS = 14

_BY_ID = {story_type["id"]: story_type for story_type in STORY_TYPES}


def get_story_type(type_id: Optional[str]) -> Optional[dict]:
    """The catalog entry for an id, or None — an unknown id is a caller
    error to surface, never a reason to substitute another type."""
    return _BY_ID.get((type_id or "").strip())


def default_frame_seconds(type_id: Optional[str]) -> Optional[int]:
    """The settled default frame length for a type, or None for an
    unknown id (same rule as get_story_type: no invented fallback)."""
    story_type = get_story_type(type_id)
    return story_type["default_seconds"] if story_type else None
