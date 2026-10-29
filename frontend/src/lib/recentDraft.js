/**
 * Remembers the draft the founder was last inside, so the shell can say so.
 *
 * Why this exists: the sidebar is a fixed map of destinations, so three steps
 * into a draft it looked exactly like a cold start. Nothing in the frame told
 * the founder where their work was, and the honest fix is memory, not another
 * navigation item: Create Video writes the open project and step here, the
 * sidebar reads it and offers one quiet line back into that draft.
 *
 * Local by design. Asking the server for "the most recent unfinished project"
 * would put a request in the shell on every page and still guess which draft
 * was meant when several are open; this remembers the one actually open. A
 * remembered id can go stale — the project is deleted from History, or a
 * different account signs in — and the link goes straight to Create Video's
 * own deep-link load, which already reports a project it cannot load instead
 * of inventing an empty draft. Stale memory therefore costs one honest error,
 * never a wrong flow. Sign-out forgets it (see AuthTokenBridge).
 *
 * Every access is guarded: localStorage throws in private-mode Safari and is
 * absent during server rendering, and a preference that cannot be stored must
 * never take the shell down with it.
 */

const KEY = "vocolens.recentDraft";
const EVENT = "vocolens:recent-draft";
/** The wizard's own step keys; anything else is not a step this app has. */
const STEP_KEYS = ["profile", "angle", "review"];

function isSaneId(value) {
  return typeof value === "string" && value.trim().length > 0 && value.length <= 128;
}

function announce() {
  try {
    if (typeof window !== "undefined") window.dispatchEvent(new Event(EVENT));
  } catch {
    // A frame without CustomEvent/Event still renders; only live updates are lost.
  }
}

/** Records the draft that is open right now. A missing project clears nothing. */
export function rememberDraft({ projectId, appName, step } = {}) {
  if (!isSaneId(projectId)) return;
  const draft = {
    projectId: projectId.trim(),
    appName: typeof appName === "string" ? appName.trim().slice(0, 80) : "",
    step: STEP_KEYS.includes(step) ? step : "",
  };
  try {
    if (typeof localStorage === "undefined") return;
    localStorage.setItem(KEY, JSON.stringify({ ...draft, at: Date.now() }));
    announce();
  } catch {
    // Same rule as currentApp: losing the memory costs a shortcut, nothing else.
  }
}

/** The remembered draft, or null when there is none or it cannot be trusted. */
export function readRecentDraft() {
  try {
    if (typeof localStorage === "undefined") return null;
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    if (!isSaneId(parsed.projectId)) return null;
    return {
      projectId: parsed.projectId.trim(),
      appName: typeof parsed.appName === "string" ? parsed.appName : "",
      step: STEP_KEYS.includes(parsed.step) ? parsed.step : "",
    };
  } catch {
    return null;
  }
}

/** Forgets the draft — sign-out, or a project the server no longer has. */
export function forgetDraft() {
  try {
    if (typeof localStorage !== "undefined") localStorage.removeItem(KEY);
  } catch {
    // Nothing to do; reading it already tolerates a hostile store.
  }
  announce();
}

/**
 * The link back into the remembered draft.
 *
 * Returns "" for anything unusable so a caller can render nothing rather than
 * a link to `/create?project=` that would open as a blank wizard.
 */
export function draftHref(draft) {
  if (!draft || !isSaneId(draft.projectId)) return "";
  const params = new URLSearchParams({ project: draft.projectId.trim() });
  if (STEP_KEYS.includes(draft.step)) params.set("step", draft.step);
  return `/create?${params.toString()}`;
}

/** Live updates for the shell; returns the unsubscribe. */
export function subscribeRecentDraft(listener) {
  if (typeof window === "undefined") return () => {};
  const onChange = () => listener(readRecentDraft());
  window.addEventListener(EVENT, onChange);
  // Fires when another tab writes, so two open windows agree on the draft.
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}
