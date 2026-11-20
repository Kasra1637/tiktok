"""
Curated Story Types — the formats the Stories page offers (ADR 0227).

A story type is the story's aim: where a hook video picks an objective
and a template, a story picks one of these. The type decides the frame's
default length and, in the phases that follow, how the story plan is
written and which native stickers the story kit prescribes.

The set is settled, not taste, and the lengths were re-settled on
Nov 20 2026 (ADR 0238). Kasra delegated the Stories decisions to
platform research (Nov 19 2026), then ruled the first lengths far too
long: 15 seconds — and even 10 — is a short video, not a story. The
platform evidence (the research report of Nov 20 2026) is that a story
frame is a beat of 3–5 seconds carrying ONE spoken line: Instagram
shows a photo story for 5 seconds by default and accepts story video
from 3 seconds (its publishing API's band is 3–60s); TikTok's story
timer is selectable from 1–15 seconds and 15 seconds is TikTok's
per-segment MAXIMUM, not a typical beat. Natural speech runs about
two and a half words a second, so the frame's seconds also budget its
spoken words (below). Each type carries the default its job wants
inside the page's 3/4/5 pick:

- Hook teaser, 4s: the primary target — one line of 8–9 words: the
  moment, the promise, and the point at the full post.
- Question / poll prompt, 3s: the shortest frame — one short spoken
  question and a tap; the sticker does the work.
- Demo moment, 5s: the ceiling, never a target — the only type that
  must show something happening, so it takes the longest beat.
- Announcement / countdown, 4s: the beat plus the date; on Instagram
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
        "default_seconds": 4,
        "description": (
            "Points at the founder's newest hook video or post: the moment, "
            "the promise, and 'the full one is up' as the closing beat; "
            "the kit carries the link sticker for Instagram — TikTok has "
            "no link sticker, so there it points at the profile."
        ),
    },
    {
        "id": "question_poll",
        "name": "Question / poll prompt",
        "default_seconds": 3,
        "description": (
            "The presenter asks the audience one question drawn from the "
            "angle's tension; the kit carries the poll or question sticker "
            "with the answer labels written out."
        ),
    },
    {
        "id": "demo_moment",
        "name": "Demo moment",
        "default_seconds": 5,
        "description": (
            "One app moment as a presenter beat: the spoken line ends open, "
            "and the kit's checklist walks the founder through attaching "
            "their screen recording as the next frame."
        ),
    },
    {
        "id": "announcement_countdown",
        "name": "Announcement / countdown",
        "default_seconds": 4,
        "description": (
            "A launch, update, or deadline beat; the kit carries the "
            "countdown sticker for Instagram, set to the date the founder "
            "chooses — on TikTok the date rides the text sticker."
        ),
    },
)

STORY_TYPE_IDS = tuple(story_type["id"] for story_type in STORY_TYPES)

# The frame lengths the page offers (ADR 0238): per-type defaults
# above, and the founder's pick is one of these three — a story frame
# is a beat of 3–5 seconds, and 5 seconds is the ceiling, never the
# target.
STORY_FRAME_SECONDS = (3, 4, 5)

# The spoken-word budget per frame length (ADR 0238): natural speech
# runs about two and a half words a second, so a frame's seconds cap
# the words its spoken lines may carry together — 3s holds 7 words,
# 4s holds 9, 5s holds 12. The story plan instructs this budget and
# enforces it (one correction, then a loud refusal); a thought that
# needs more words is a second frame, never a longer line.
STORY_SPOKEN_WORD_BUDGETS = {3: 7, 4: 9, 5: 12}

# The on-screen text caps (research Q3): the text is a native text
# sticker the founder places at posting, and it must read whole inside
# the shortest 3-second frame and carry the whole message alone for
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


def spoken_word_budget(seconds) -> Optional[int]:
    """The spoken-word budget for a frame of `seconds`, or None when
    the length is outside the settled pick (same rule as above)."""
    try:
        secs = int(seconds or 0)
    except (TypeError, ValueError):
        return None
    return STORY_SPOKEN_WORD_BUDGETS.get(secs)
