/**
 * Pure helpers for the length of the generated piece and its two sections.
 *
 * A video here is ONE render containing exactly two sections: a hook, and a
 * middle that develops it and stops at the moment the presenter would reach
 * for their phone. The founder records the product demo themselves and adds the
 * call to action in their own editor. So there is no chain to extend, nothing
 * to approve per segment, and nothing to join — and with those gone there is
 * also no total length for the founder to choose. A template declares a
 * `default_duration`, the project seeds from it, and the render is that long.
 *
 * What is left is the arithmetic the UI has to get right before it lets anyone
 * render, which is the same reason these helpers existed when the workflow was a
 * chain. `npm run build` type-checks and lints but never evaluates a comparison
 * at runtime, and the backend suite cannot see frontend code at all. That gap
 * is exactly how `project.extend_intent === 0` survived against a boolean return
 * (the toggle could never turn off) and how a length longer than one render
 * used to be discovered at the extend button rather than before it.
 *
 * So the rules live here, with no React and no DOM, and are asserted directly
 * by scripts/check-frontend-logic.cjs against this real source file.
 *
 * The rules mirror template_library.clamp_duration(), the hook clamp in
 * update_studio_project, and the single-pass ceiling the backend refuses a
 * generate request over. The backend still decides; this only predicts, so the
 * UI can say what will happen before the render runs.
 */

/**
 * How long a fresh project is when nothing states a length.
 *
 * 15s is the single-pass ceiling of the studio-eligible model (minimax-h3 caps
 * at 15s). It is the top of the supported set, so a fresh project always fits
 * in one render.
 */
export const DEFAULT_DURATION = 15;

// The hook is a boundary, not a render length. The whole piece is rendered at
// one duration and the hook is simply where the middle begins, so these are
// the same 2-4s the backend clamps `hook_seconds` to: a hook that needs longer
// to land is not a hook. DEFAULT_HOOK_SECONDS is the value a project carries
// before any template has spoken, matching the fallback in create_studio_project.
export const MIN_HOOK_SECONDS = 2;
export const MAX_HOOK_SECONDS = 4;
export const DEFAULT_HOOK_SECONDS = 3;

/**
 * Clamp a hook boundary the way the PATCH endpoint now does.
 *
 * Clamping rather than raising is the point: an out-of-range value moves the
 * boundary to a length a hook can actually land in instead of failing the whole
 * save, because a 9s "hook" would leave the middle with nothing to film. Zero
 * is preserved as zero rather than clamped up — zero means "follow the
 * template", which is a real answer and not a boundary of MIN_HOOK_SECONDS.
 */
export function clampHookSeconds(value) {
  const want = Number(value) || 0;
  if (want <= 0) return 0;
  return Math.max(MIN_HOOK_SECONDS, Math.min(MAX_HOOK_SECONDS, Math.round(want)));
}

/**
 * The length of the generated piece, as far as the client can know it.
 *
 * The project is the authority once one exists — it is the number the plan's
 * beat timeline was written to, and the number the render is asked for. Before
 * that, the selected template's `default_duration` is what the project WILL be
 * seeded from, so showing it is a prediction of the same value rather than a
 * separate choice. Anything unusable falls back to the library default instead
 * of rendering "NaN seconds" or leaving a hole in the copy.
 */
export function readPieceSeconds(project, template) {
  const fromProject = Number(project?.duration_seconds);
  if (Number.isFinite(fromProject) && fromProject > 0) return fromProject;
  const fromTemplate = Number(template?.default_duration);
  if (Number.isFinite(fromTemplate) && fromTemplate > 0) return fromTemplate;
  return DEFAULT_DURATION;
}

/**
 * Split the piece into its two sections.
 *
 * Before a strategy exists the only numbers available are the total and the
 * hook boundary, so the middle is whatever is left. The middle is never
 * allowed to go negative: a hand-edited boundary longer than the piece would
 * otherwise produce a middle of -2s that reads as though the product had
 * already filmed a section it does not have.
 */
export function sectionSplit(pieceSeconds, hookSeconds) {
  const piece = Math.max(0, Number(pieceSeconds) || 0);
  const hook = Math.max(0, Math.min(Number(hookSeconds) || 0, piece));
  return { hookSeconds: hook, middleSeconds: Math.max(0, piece - hook) };
}

/**
 * The longest single render the selected model can produce, or 0 for unknown.
 *
 * 0 rather than a guess on purpose. A hard-coded fallback would let the UI
 * refuse a render the model would in fact accept, which is the worse of the two
 * mistakes: the founder is told their video is impossible when it is not. The
 * backend has the same number and is the authority; this only has to stay out
 * of the way until the capability list has loaded.
 */
export function singlePassCeiling(capability) {
  const max = Number(capability?.max_duration);
  return Number.isFinite(max) && max > 0 ? max : 0;
}

/**
 * Whether a length is longer than the model can render in one pass.
 *
 * This is the check that replaced the extend lock. The lock used to answer
 * "how much is left, and can one pass cover it" and returned null past the
 * ceiling, so a founder was told to extend in two steps. There is no second
 * step now: one render is the whole product, and
 * `POST /studio/projects/{id}/generate` answers 400 for anything past the
 * ceiling rather than splitting or quietly shortening it. So the honest place
 * for the same knowledge is "this will be refused", shown before the click,
 * with the failure still belonging to the endpoint.
 *
 * Fails open on an unknown ceiling, for the reason above: the one thing this
 * must never do is block a render that would have worked.
 */
export function exceedsSinglePass(seconds, capability) {
  const ceiling = singlePassCeiling(capability);
  if (ceiling <= 0) return false;
  const want = Number(seconds) || 0;
  return want > ceiling;
}

// The two generated sections, in the order they are rendered. The role is
// assigned by POSITION and never read off the model, exactly as
// ai_service._normalize_sections does: a strategy written by a model that
// remembered the old eight-beat shape would otherwise hand back a "cta" role,
// and the render prompt reads the role.
export const SECTION_ROLES = ["hook", "middle"];

/**
 * The strategy's two sections, normalised.
 *
 * Roles come from position and the list is truncated to two, so a strategy
 * saved before this change — or one where a model ignored the schema and
 * returned eight beats ending in a call to action — reads as the hook and the
 * middle it actually becomes instead of as a beat list the founder would read
 * as a promise of a chain. Missing sections come back present and empty rather
 * than absent, so the review surface never has a branch that renders one row.
 */
export function plannedSections(strategy) {
  const raw = Array.isArray(strategy?.segments) ? strategy.segments : [];
  return SECTION_ROLES.map((role, index) => {
    const section = raw[index] && typeof raw[index] === "object" ? raw[index] : {};
    return {
      index,
      role,
      seconds: Math.max(0, Number(section.seconds) || 0),
      goal: String(section.goal || ""),
      script: String(section.script || ""),
      action: String(section.action || ""),
    };
  });
}
