/**
 * The Dashboard's one next action, as a pure decision (ADR 0208).
 *
 * The Dashboard is a routing home: it names the single next right thing
 * and nothing else. The precedence is the product's working order —
 * nothing can be made without an App Profile, work already started
 * outranks work not yet begun, a render in flight is watched where it
 * lands, and a finished render's next step is its demo & closing
 * message. Only when none of those is true is the next thing a new
 * video.
 *
 * Pure by design: the page gathers the inputs (profile count, the
 * remembered draft from lib/recentDraft, the newest History rows —
 * which arrive newest first, the order the endpoint serves) and this
 * function only decides, so the precedence is testable without a page.
 *
 * Row statuses are the History vocabulary: "submitted" and
 * "generating" are in flight; "completed" and "archived" are finished
 * renders (an archived clip was finished, so it can still be finished
 * in Demo + CTA); "failed" is neither — a failure is History's to
 * explain, never the Dashboard's next action.
 */

const IN_FLIGHT = new Set(["submitted", "generating"]);
const FINISHED = new Set(["completed", "archived"]);

/** The fallback every empty or unreadable state lands on. */
export const CREATE_ACTION = {
  kind: "create",
  title: "Create a video",
  body: "Plan the hook & script, review them, then render.",
  cta: "Create a video",
  to: "/create",
};

export function pickDashboardAction({ profilesCount = 0, draft = null, draftLink = "", generations = [] } = {}) {
  const rows = Array.isArray(generations) ? generations : [];

  // (1) No App Profile at all: everything else is made from one, and
  // Create Video refuses to run without an approved profile.
  if (!profilesCount) {
    return {
      kind: "profile",
      title: "Set up your App Profile",
      body: "Research your app once — every video is made from its profile.",
      cta: "Set up App Profile",
      to: "/brand",
    };
  }

  // (2) A draft the founder was last inside outranks anything newer:
  // it is the work already begun, in the founder's own hands.
  if (draft && draftLink) {
    return {
      kind: "draft",
      title: draft.appName ? `Continue your draft for ${draft.appName}` : "Continue your draft",
      body: "You left a video part-way through — pick it up where you stopped.",
      cta: "Continue draft",
      to: draftLink,
    };
  }

  // (3) A render in flight: the next thing is to watch it land, and
  // History is where renders land.
  if (rows.some((row) => row && IN_FLIGHT.has(row.status))) {
    return {
      kind: "rendering",
      title: "Your video is rendering",
      body: "It lands in History when it finishes — watch for it there.",
      cta: "Watch in History",
      to: "/history",
    };
  }

  // (4) The newest finished render: its next step in the one journey
  // is the finishing step, Demo + CTA, on that render itself.
  const newestFinished = rows.find((row) => row && FINISHED.has(row.status) && row.id);
  if (newestFinished) {
    return {
      kind: "finish",
      title: "Finish your latest video",
      body: "Your newest render is done — add its demo & closing message.",
      cta: "Finish it in Demo + CTA",
      to: `/demo-cta/${newestFinished.id}`,
    };
  }

  // (5) Nothing pending anywhere: start the next video.
  return CREATE_ACTION;
}
