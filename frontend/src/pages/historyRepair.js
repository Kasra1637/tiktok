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
 * Whether a History row needs a repair entry: failed renders, stuck
 * generating rows with no bytes, and completed rows with no durable copy.
 * Single owner for the rule the attention banner and the row repair share.
 */
export function needsHistoryRepairRow(row) {
  if (!row) return false;
  if (row.status === "failed") return true;
  if (row.status === "generating" && !row.video_url) return true;
  if (row.status === "completed" && !durableMediaUrl(row)) return true;
  return false;
}
