import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { isAwaitingProvider, isThrottlingError } from "./historyRepair";

const POLL_INTERVAL_MS = 10000;
const MAX_POLL_INTERVAL_MS = 60000;

/**
 * How long one row waits before its next check, mirroring the render
 * panel's backoff (ADR 0171): throttling stretches the wait per
 * consecutive 429 (base × (1 + throttles), capped at 60s), a sustained
 * run of other failures (3+) settles at twice the base wait, and
 * anything else waits the base interval. A success resets both
 * counters, so the cadence returns to the base wait.
 */
export function historyPollDelay({ failures, throttles }) {
  if (throttles > 0) return Math.min(POLL_INTERVAL_MS * (1 + throttles), MAX_POLL_INTERVAL_MS);
  if (failures >= 3) return POLL_INTERVAL_MS * 2;
  return POLL_INTERVAL_MS;
}

/**
 * Per-row polling that never retires an awaiting row (ADR 0174,
 * extending ADR 0171's panel rule to History). There is no attempt
 * cap and no error state: failures and throttling only stretch the
 * row's own wait, from the third consecutive failure of either kind
 * the row reports "slowed" so the page can say checks are being
 * slowed down, and polling for a row ends only when the row settles —
 * the finished video lands, or a terminal status arrives. One
 * slow/erroring job cannot hide another's result.
 */
export function useAwaitingHistoryPoll(rows, onUpdated) {
  const [states, setStates] = useState({});
  const jobs = useRef(new Map());
  const flights = useRef(new Set());
  const awaitingKey = rows.filter(isAwaitingProvider).map((r) => r.id).sort().join("|");
  useEffect(() => {
    const ids = awaitingKey ? awaitingKey.split("|") : [];
    for (const id of jobs.current.keys()) {
      if (!ids.includes(id)) jobs.current.delete(id);
    }
    for (const id of ids) {
      if (!jobs.current.has(id)) {
        jobs.current.set(id, { failures: 0, throttles: 0, nextCheckAt: 0, state: "active" });
      }
    }
    setStates(Object.fromEntries(ids.map((id) => [id, jobs.current.get(id).state])));
    if (!ids.length) return undefined;
    let cancelled = false;
    const timer = setInterval(async () => {
      const now = Date.now();
      const pending = ids.filter((id) => {
        const job = jobs.current.get(id);
        return job && job.state !== "settled" && !flights.current.has(id) && now >= job.nextCheckAt;
      });
      if (!pending.length) return;
      pending.forEach((id) => flights.current.add(id));
      const results = await Promise.allSettled(pending.map((id) => api.pollGeneration(id)));
      pending.forEach((id) => flights.current.delete(id));
      if (cancelled) return;
      results.forEach((result, index) => {
        const id = pending[index];
        const job = jobs.current.get(id);
        if (!job) return;
        if (result.status === "fulfilled") {
          job.failures = 0;
          job.throttles = 0;
          job.nextCheckAt = 0;
          job.state = "active";
          const updated = result.value;
          if (updated?.id) {
            if (!isAwaitingProvider(updated)) job.state = "settled";
            onUpdated(updated.id, updated);
          }
        } else {
          if (isThrottlingError(result.reason)) job.throttles += 1;
          else job.failures += 1;
          job.nextCheckAt = Date.now() + historyPollDelay(job);
          job.state = job.failures >= 3 || job.throttles >= 3 ? "slowed" : "active";
        }
      });
      setStates(Object.fromEntries(ids.map((id) => [id, jobs.current.get(id)?.state || "settled"])));
      if (ids.every((id) => jobs.current.get(id)?.state === "settled")) clearInterval(timer);
    }, POLL_INTERVAL_MS);
    return () => { cancelled = true; clearInterval(timer); };
  }, [awaitingKey, onUpdated]);
  return states;
}
