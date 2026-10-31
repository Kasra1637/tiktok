import { useEffect } from "react";
import { api } from "../lib/api";
import { isAwaitingProvider, isThrottlingError } from "./historyRepair";

/**
 * Rows still awaiting the provider poll themselves, every ten seconds for
 * up to twenty rounds, so a render that finishes while History is open
 * arrives on its own. A 429 is throttling, not failure, so it never stops
 * the loop; any other error does, quietly, leaving the manual Check.
 */
export function useAwaitingHistoryPoll(rows, onUpdated) {
  const awaitingKey = rows
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
      if (attempts > 20) {
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
    }, 10000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [awaitingKey, onUpdated]);
}
