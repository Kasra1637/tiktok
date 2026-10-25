import { verdictFor } from "./feedback";

/**
 * The winner rule both surfaces share (ADR 0032): a thumbs up on the render
 * plus its posted link. A link alone carries no weight, and a vote alone is
 * judgment without proof of shipping — only the pair counts, everywhere.
 */
export function isWinnerRow(row) {
  return verdictFor(row?.verdicts, "video") > 0 && !!row?.tiktok_url;
}

/**
 * The one row the ledger earns the right to advise on: a finished winner
 * with a recorded count. Archived clips are shelved on purpose, so they
 * stay comparison and never become the suggestion.
 */
export function pickNextTake(renders) {
  return (renders || [])
    .filter((row) => row.status === "completed" && row.tiktok_views != null && isWinnerRow(row))
    .sort((a, b) => (b.tiktok_views ?? -1) - (a.tiktok_views ?? -1))[0] || null;
}

/**
 * One click onward from a finished clip, through the draft when it resolves.
 *
 * A present-and-verified draft reopens in Create Video — named for what a
 * winner reuses. A draft that is verified gone — or a row that never had
 * one — falls through to styling the finished clip, and an archived row to
 * reviewing it, so the action never links a project that no longer resolves.
 * An unverified list fails open to the draft link: what the page linked
 * before verification existed.
 */
export function nextTakeFor(row, historyHref, draftIds) {
  if (row.studio_project_id && (!draftIds || draftIds.has(row.studio_project_id))) {
    return {
      label: isWinnerRow(row) ? "Another take like this" : "Reuse draft",
      to: `/create?project=${encodeURIComponent(row.studio_project_id)}`,
    };
  }
  if (row.status === "completed") return { label: "Style clip", to: `/demo-cta/${row.id}` };
  return { label: "Review clip", to: `${historyHref}#generation-${row.id}` };
}
