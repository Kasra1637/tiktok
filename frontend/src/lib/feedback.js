/**
 * Automatic feedback capture.
 *
 * The backend can aggregate `feedback_events`, but nothing populates it unless
 * the UI records something at the moment it happens. These helpers are the
 * automatic half of that loop: they record a factual trigger, never a judgment.
 *
 * Why triggers and not reasons: a trigger is knowable without asking the
 * founder anything, because it is just a record of what the software did. A
 * reason is a judgment, and nothing here can infer one — guessing "hook too
 * weak" from a regenerate would poison the aggregate that "common
 * regeneration reasons" depends on. Reasons stay optional and founder-supplied.
 *
 * Every call is fire-and-forget and swallows its own errors. Feedback is
 * observability, not a step in the founder's work: a failure to record must
 * never surface as an error, block a save, or interrupt a download.
 */

import { api } from "./api";

// Must stay in step with `classify_script_edit` in backend/feedback.py, which
// also publishes these thresholds via GET /feedback/catalog so the number is
// auditable rather than buried in a constant. Both copies return the same
// label for the same edit, and the signal records which side of the line it
// fell on.
const HEAVY_EDIT_RATIO = 0.25;
const HEAVY_EDIT_MIN_CHARS = 40;

/**
 * Classify a script change as heavy or light.
 *
 * "Heavy" means at least 25% of the script's length changed, or at least 40
 * characters. Length is measured on the longer of the two texts so a rewrite
 * from short to long counts as substantial rather than as a small delta.
 *
 * @returns {string} "script_edited_heavy", "script_edited_light", or "" when
 *                   the script did not change at all.
 */
export function classifyScriptEdit(before, after) {
  const a = before || "";
  const b = after || "";
  if (a === b) return "";
  const changed = Math.abs(b.length - a.length);
  const longest = Math.max(a.length, b.length, 1);
  if (changed >= HEAVY_EDIT_MIN_CHARS || changed / longest >= HEAVY_EDIT_RATIO) {
    return "script_edited_heavy";
  }
  return "script_edited_light";
}

/**
 * Record one factual trigger.
 *
 * @param {string} event  What happened, e.g. "video_regenerated".
 * @param {string} signal The trigger that implies it, e.g. "regenerated".
 * @param {object} refs   Optional brand_profile_id / studio_project_id /
 *                        generation_id / template_id to attribute it to.
 * @returns {Promise<boolean>} whether it was recorded.
 */
export async function recordSignal(event, signal, refs = {}) {
  try {
    await api.recordFeedback({
      event,
      signal,
      brand_profile_id: refs.brand_profile_id || "",
      studio_project_id: refs.studio_project_id || "",
      generation_id: refs.generation_id || "",
      template_id: refs.template_id || "",
    });
    return true;
  } catch {
    // Deliberately silent. See the note above.
    return false;
  }
}

/**
 * Record a thumbs verdict on one component of the video (or the video itself).
 *
 * Thumbs are standalone judgments: no signal, no reason. Each component's
 * votes only steer the AI step that produces it. Detail optionally names
 * the item version (e.g. "plan v3").
 *
 * @param {string} step One of goal | template | plan | script | video.
 * @param {number} verdict 1 for up, -1 for down, 0 clears without recording.
 * @returns {Promise<boolean>} whether it was recorded.
 */
/**
 * A generation's saved vote for one component, as the thumb control reads it.
 *
 * The server attaches `verdicts` ({component: 1|-1}) to generation rows; a
 * missing entry, a stale shape, or no verdicts at all all read as unvoted
 * rather than crashing the highlight.
 *
 * @returns {number} 1 for up, -1 for down, 0 for unvoted.
 */
export function verdictFor(verdicts, component) {
  const v = verdicts?.[component];
  return v > 0 ? 1 : v < 0 ? -1 : 0;
}

/**
 * Record implicit behavior on one component: what the founder moved forward
 * with (adopted), produced or picked then dropped without proceeding
 * (abandoned), or was shown but never picked (generated).
 *
 * Same shape as thumbs — a component plus an optional detail naming the item —
 * and likewise carrying no signal or reason, because the behavior itself is
 * the fact. The video rating stays thumbs-only; nothing here records one.
 *
 * @param {string} event One of adopted | abandoned | generated.
 * @param {string} step One of goal | template | plan | script | video.
 * @param {object} refs Optional detail + brand_profile_id / studio_project_id /
 *                       generation_id / template_id to attribute it to.
 * @returns {Promise<boolean>} whether it was recorded.
 */
export async function recordBehavior(event, step, refs = {}) {
  if (event !== "adopted" && event !== "abandoned" && event !== "generated") return false;
  if (!step) return false;
  try {
    await api.recordFeedback({
      event,
      step,
      detail: refs.detail || "",
      brand_profile_id: refs.brand_profile_id || "",
      studio_project_id: refs.studio_project_id || "",
      generation_id: refs.generation_id || "",
      template_id: refs.template_id || "",
    });
    return true;
  } catch {
    // Deliberately silent. See the note above.
    return false;
  }
}

export async function recordThumb(step, verdict, refs = {}) {
  if (verdict !== 1 && verdict !== -1) return false;
  try {
    await api.recordFeedback({
      event: verdict === 1 ? "thumb_up" : "thumb_down",
      step,
      detail: refs.detail || "",
      brand_profile_id: refs.brand_profile_id || "",
      studio_project_id: refs.studio_project_id || "",
      generation_id: refs.generation_id || "",
      template_id: refs.template_id || "",
    });
    return true;
  } catch {
    return false;
  }
}
