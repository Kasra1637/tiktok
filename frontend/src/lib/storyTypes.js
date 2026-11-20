/**
 * The story type catalog, mirrored from `backend/story_types.py`.
 *
 * The backend module is the source of truth: it owns the set, the
 * default frame lengths and the one-line purposes, and the create and
 * plan endpoints validate against it. No endpoint serves the catalog
 * itself — a project payload carries only the picked type's id — so
 * the page reads this mirror instead (ADR 0235). The four entries are
 * copied exactly, wording included; if the catalog changes there, it
 * changes here in the same commit, and the smoke suite pins the ids
 * and lengths the picker renders against this list.
 *
 * The lengths were re-settled by ADR 0238: a story frame is a beat of
 * 3–5 seconds carrying one spoken line, not a short video.
 *
 * Testimonial-style is deliberately absent, here as there: the app
 * has no claim-safety system (ADR 0119) and no source of real user
 * quotes to ground one.
 */
export const STORY_TYPES = [
  {
    id: "hook_teaser",
    name: "Hook teaser",
    defaultSeconds: 4,
    description:
      "Points at the founder's newest hook video or post: the moment, " +
      "the promise, and 'the full one is up' as the closing beat; " +
      "the kit carries the link sticker for Instagram — TikTok has " +
      "no link sticker, so there it points at the profile.",
  },
  {
    id: "question_poll",
    name: "Question / poll prompt",
    defaultSeconds: 3,
    description:
      "The presenter asks the audience one question drawn from the " +
      "angle's tension; the kit carries the poll or question sticker " +
      "with the answer labels written out.",
  },
  {
    id: "demo_moment",
    name: "Demo moment",
    defaultSeconds: 5,
    description:
      "One app moment as a presenter beat: the spoken line ends open, " +
      "and the kit's checklist walks the founder through attaching " +
      "their screen recording as the next frame.",
  },
  {
    id: "announcement_countdown",
    name: "Announcement / countdown",
    defaultSeconds: 4,
    description:
      "A launch, update, or deadline beat; the kit carries the " +
      "countdown sticker for Instagram, set to the date the founder " +
      "chooses — on TikTok the date rides the text sticker.",
  },
];

/** The frame lengths the page offers: a story frame is one render of
 *  3, 4 or 5 seconds (backend `STORY_FRAME_SECONDS`, ADR 0238). */
export const STORY_FRAME_SECONDS = [3, 4, 5];

/** The catalog entry for an id, or null — an unknown id is a data
 *  error to surface, never a reason to substitute another type. */
export function storyTypeById(id) {
  return STORY_TYPES.find((t) => t.id === id) || null;
}

/** The settled default frame length for a type, or null for an
 *  unknown id (the same no-invented-fallback rule as the backend). */
export function defaultFrameSeconds(id) {
  const entry = storyTypeById(id);
  return entry ? entry.defaultSeconds : null;
}
