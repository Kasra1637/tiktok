import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { isAwaitingProvider, isThrottlingError } from "./historyRepair";

/** Bounded per-row polling. One slow/erroring job cannot hide another's result. */
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
      if (!jobs.current.has(id)) jobs.current.set(id, { attempts: 0, state: "active" });
    }
    setStates(Object.fromEntries(ids.map((id) => [id, jobs.current.get(id).state])));
    if (!ids.length) return undefined;
    let cancelled = false;
    const timer = setInterval(async () => {
      const pending = ids.filter((id) => jobs.current.get(id)?.state === "active" && !flights.current.has(id));
      if (!pending.length) return;
      pending.forEach((id) => {
        flights.current.add(id);
        jobs.current.get(id).attempts += 1;
      });
      const results = await Promise.allSettled(pending.map((id) => api.pollGeneration(id)));
      pending.forEach((id) => flights.current.delete(id));
      if (cancelled) return;
      results.forEach((result, index) => {
        const id = pending[index];
        const job = jobs.current.get(id);
        if (!job) return;
        if (result.status === "fulfilled") {
          const updated = result.value;
          if (updated?.id) {
            if (!isAwaitingProvider(updated)) job.state = "settled";
            onUpdated(updated.id, updated);
          }
        } else if (!isThrottlingError(result.reason)) {
          job.state = "error";
        }
        if (job.state === "active" && job.attempts >= 20) job.state = "paused";
      });
      setStates(Object.fromEntries(ids.map((id) => [id, jobs.current.get(id)?.state || "settled"])));
      if (ids.every((id) => jobs.current.get(id)?.state !== "active")) clearInterval(timer);
    }, 10000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [awaitingKey, onUpdated]);
  return states;
}
