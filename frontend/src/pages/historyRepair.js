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
  if (isThrottlingError(err)) {
    return (
      `The provider is rate limiting right now, so History could not ${action} this time. ` +
      `Nothing is lost — wait a moment and try again.`
    );
  }
  return err?.message || `Something went wrong while trying to ${action}. Please try again.`;
}

/**
 * Whether a failure is provider throttling rather than a verdict on the
 * work. Single owner for the 429 check the action error and the awaiting
 * poll share, so a throttled retry never reads as a broken render.
 */
export function isThrottlingError(err) {
  return err?.response?.status === 429;
}

/**
 * Which attention the History banner owes the founder, if any. Repairs
 * first: a failed, awaiting, or undurable row beats a finished render that
 * merely lacks post copy. Single owner for the rule the banner reads, so
 * the two boxes cannot disagree about which one shows.
 */
export function getHistoryAttention(rows) {
  const repair = rows.filter(needsHistoryRepairRow);
  if (repair.length > 0) return { kind: "repair", items: repair, first: repair[0] };
  const kitless = rows.filter(
    (r) => (r.status === "completed" || r.status === "archived") && !r.post_kit
  );
  if (kitless.length > 0) return { kind: "kitless", items: kitless, first: kitless[0] };
  return null;
}

/**
 * The banner's words for one attention: the count, the next step, and the
 * link label. Pure, so the page renders one box driven by data instead of
 * two near-identical boxes differing only in copy.
 */
export function describeHistoryAttention(attention) {
  if (attention.kind === "kitless") {
    const n = attention.items.length;
    return {
      summary:
        n === 1
          ? "1 finished render has no post copy yet. "
          : `${n} finished renders have no post copy yet. `,
      guidance: "Open its card and press Generate post copy.",
      cta: "Review without copy",
    };
  }
  const n = attention.items.length;
  const first = attention.first;
  const many = n > 1;
  let guidance;
  if (first.status === "failed") {
    guidance = many
      ? "Open each card for its provider reason — then re-render from Create Video."
      : "Open its card for the provider reason — then re-render from Create Video.";
  } else if (isAwaitingProvider(first)) {
    guidance = many
      ? "Open each card and press Check again — finished renders are fetched when found."
      : "Open its card and press Check again — the finished render is fetched when found.";
  } else {
    guidance = many
      ? "Open each card and press Retry durable save — fresh copies are re-fetched and filed."
      : "Open its card and press Retry durable save — a fresh copy is re-fetched and filed.";
  }
  return {
    summary: n === 1 ? "1 clip needs attention. " : `${n} clips need attention. `,
    guidance,
    cta: "Review repair",
  };
}

/**
 * Where the banner's link lands: the side holding its first clip, with the
 * hook-text search cleared so the target is never filtered out. Server
 * filters (app, status) are kept; only presentation moves.
 */
export function historyAttentionLink(searchParams, attention) {
  const params = new URLSearchParams(searchParams);
  if (attention.kind === "kitless") {
    params.set("copy", "without");
  } else {
    params.set("copy", hasCopyContext(attention.first) ? "with" : "without");
  }
  params.delete("q");
  return { search: `?${params.toString()}`, hash: `#generation-${attention.first.id}` };
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
