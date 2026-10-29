import { durableMediaUrl } from "../lib/api";

/**
 * Row and page failures name the next step instead of passing the raw
 * request message through.
 *
 * A handler `detail` still wins when it says something specific. A bodyless
 * 413 never came from the app (Cloud Run refuses the oversized request
 * before it runs), so it reads as a too-large file with the Download-first
 * remedy rather than a status code. Anything else keeps the request message
 * with the action attached, so a failed repair never reads as a dead end.
 */
export function historyActionError(err, action = "finish this") {
  const detail = err?.response?.data?.detail;
  if (detail) return detail;
  if (err?.response?.status === 413) {
    return (
      "That file was too large to save, so nothing was filed to History. " +
      "Download the clip where it is so nothing is lost, then try again — " +
      "large exports save in parts — or use a shorter clip."
    );
  }
  if (!err?.response && err?.message === "Network Error") {
    return `The connection dropped before History could ${action}. Check your connection, then try again.`;
  }
  return err?.message || `Something went wrong while trying to ${action}. Please try again.`;
}

/**
 * Whether a render carries anything for the copy/context section: a frozen
 * post kit, an audience, or a demo brief. Single owner for the rule the
 * list filter and the deep-link resolver share, so a linked clip and the
 * side that shows it cannot disagree.
 */
export function hasCopyContext(row) {
  return Boolean(row?.post_kit || row?.audience || row?.demo_brief);
}

/**
 * Whether a queued render is still awaiting the provider: submitted or
 * generating with no bytes yet. A submitted row is not finished work gone
 * missing; it is work that has not reported back, so it gets Check again
 * rather than a finished-clip repair.
 */
export function isAwaitingProvider(row) {
  if (!row) return false;
  return (row.status === "submitted" || row.status === "generating") && !row.video_url;
}

/**
 * Whether a History row needs a repair entry: failed renders, queued rows
 * still awaiting the provider, and completed rows with no durable copy.
 * Single owner for the rule the attention banner and the row repair share.
 */
export function needsHistoryRepairRow(row) {
  if (!row) return false;
  if (row.status === "failed") return true;
  if (isAwaitingProvider(row)) return true;
  if (row.status === "completed" && !durableMediaUrl(row)) return true;
  return false;
}

/**
 * Which copy/context side a deep link must land on. A linked clip forces
 * its own side: a standalone Demo + CTA export carries no copy or context,
 * so the default with-side would hide the very clip the link names.
 * Without a linked target the chosen filter is kept as-is.
 */
export function effectiveCopyFilter(copyParam, targetRow) {
  if (targetRow) return hasCopyContext(targetRow) ? "with" : "without";
  return copyParam === "without" ? "without" : "with";
}

/**
 * Whether a #generation- deep link still needs its one automatic page
 * jump. The jump settles once per anchor so manual pager turns are never
 * pulled back to the linked clip's page.
 */
export function shouldApplyDeepLinkPage(handledHash, hashId) {
  return Boolean(hashId) && handledHash !== hashId;
}

/**
 * One-based pager page for a zero-based row index.
 */
export function pageForRowIndex(index, pageSize = 50) {
  return Math.floor(index / pageSize) + 1;
}

/**
 * Whether the empty-account card may show. A failed load with no rows is
 * a failed load, not proof the account never rendered, so it must never
 * read as "Nothing generated yet" beside the error.
 */
export function shouldShowHistoryEmpty({ loading, error, rowsLength }) {
  return !loading && !error && rowsLength === 0;
}

/**
 * Whether the plan link may show for one render. A draft that is verified
 * gone offers nothing for any render, winner or not; an unverified list
 * fails open to the link exactly as before verification existed.
 */
export function shouldOfferDraftLink(studioProjectId, draftIds) {
  if (!studioProjectId) return false;
  if (draftIds && !draftIds.has(studioProjectId)) return false;
  return true;
}
