import { useEffect } from "react";
import { api } from "../lib/api";
import { isAwaitingProvider, isThrottlingError } from "./historyRepair";

export const HISTORY_AWAIT_POLL_MS = 10000;
export const HISTORY_AWAIT_POLL_ROUNDS = 20;

/**
 * Rows still awaiting the provider poll themselves: a render that finishes
 * while History is open arrives on its own instead of sitting generating
 * until someone opens the card and presses Check again. Only the awaiting
 * few are polled, every ten seconds, up to twenty rounds — a stuck job
 * stops burning requests and keeps its manual Check. A 429 is throttling,
 * not failure, so it never stops the loop; any other error does, quietly.
 *
 * Single owner for the loop the page used to inline: rows flow in, finished
 * rows flow out through onUpdated, and the page owns nothing of the timer.
 */
export function useAwaitingHistoryPoll(rows, onUpdated) {
  const awaitingKey = (Array.isArray(rows) ? rows : [])
    .filter(isAwaitingProvider)
    .map((r) => r.id)
    .join("|");
  useEffect(() => {
    if (!awaitingKey) return undefined;
    const ids = awaitingKey.split("|");
    let cancelled = false;
    let attempts = 0;
    const timer = setInterval(async () => {
      attempts += 1;
      if (attempts > HISTORY_AWAIT_POLL_ROUNDS) {
        clearInterval(timer);
        return;
      }
      try {
        const results = await Promise.all(ids.map((id) => api.pollGeneration(id)));
        if (cancelled) return;
        results.forEach((updated) => {
          if (updated && updated.id) onUpdated(updated.id, updated);
        });
      } catch (err) {
        if (isThrottlingError(err)) return;
        clearInterval(timer);
      }
    }, HISTORY_AWAIT_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [awaitingKey, onUpdated]);
}
