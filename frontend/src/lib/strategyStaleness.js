// Whether the saved direction has drifted from the direction the strategy
// was built against. One implementation shared by the two panels that gate
// on it — the strategy panel (which shows the rebuild button) and the
// render panel (which hides Generate while a rebuild is owed) — so the
// button the founder sees and the gate the render obeys can never disagree
// about whether a rebuild is owed (ADR 0142).
//
// The comparison mirrors the server's own diff (backend/routers/studio.py,
// _strategy_direction_changes, ADR 0133): the strategy build stamps the
// direction it was built against as strategy.direction_snapshot, and a
// saved direction that no longer matches the stamp is a manual update like
// a plan or angle change. A strategy with no snapshot (built before the
// stamp existed) is missing history, not drifted: it is never owed on this
// ground alone.
//
// The comparison is raw against raw (ADR 0146): the payload's top-level
// direction fields are display text — `location` above all, whose object
// clauses the backend strips and whose fragments it repairs before
// display — so diffing them against the raw stamp read as drift forever
// whenever a plan-written Location carried an object clause. The payload
// therefore also carries `direction_saved`, the row values untouched, and
// that is what the stamp is diffed against; older payloads without it
// fall back to the top-level fields.
export const DIRECTION_FIELDS = [
  "location",
  "visual_direction",
  "voice_direction",
  "sound_direction",
];

export function directionDrifted(project) {
  const strategy = project?.strategy;
  const snapshot = strategy?.direction_snapshot;
  if (!snapshot || typeof snapshot !== "object" || Array.isArray(snapshot)) {
    return false;
  }
  const saved = project?.direction_saved;
  const hasSaved =
    saved && typeof saved === "object" && !Array.isArray(saved);
  return DIRECTION_FIELDS.some((field) => {
    const stamped = String(snapshot[field] || "").trim();
    const current = String(
      (hasSaved ? saved[field] : project?.[field]) || ""
    ).trim();
    if (!hasSaved && field === "location" && !stamped && current) {
      // Legacy payloads only: the payload fills an empty saved location
      // from the strategy's own scene for display (backend
      // _public_project); the saved value is still empty, exactly as the
      // server's diff sees it. Display text alone is not a founder edit,
      // so it cannot owe a rebuild. With direction_saved present the
      // saved value speaks for itself and this excuse is unnecessary.
      if (current === String(strategy?.scene?.location || "").trim()) {
        return false;
      }
    }
    return current !== stamped;
  });
}
