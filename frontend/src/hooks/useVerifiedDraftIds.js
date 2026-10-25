import { useEffect, useState } from "react";
import { api } from "../lib/api";

/**
 * Live draft ids for one profile scope, or null while unverified.
 *
 * History and Analytics both link into draft projects, so both verify the
 * link target against the project list before rendering it: a confirmed-gone
 * draft must never be linked. Verification runs only when `needed` names a
 * draft worth checking, and a failed check fails open to null — the entries
 * then link exactly as they did before verification existed.
 *
 * State has one owner per page (this hook), and the fetch has one shape for
 * both callers, so the fail-open rule cannot drift between the two surfaces.
 */
export function useVerifiedDraftIds(profileId, needed) {
  const [draftIds, setDraftIds] = useState(null);
  useEffect(() => {
    let cancelled = false;
    setDraftIds(null);
    if (!needed) return undefined;
    api.getStudioProjects(profileId ? { brand_profile_id: profileId } : {})
      .then((d) => {
        if (!cancelled) setDraftIds(new Set((d.projects || []).map((p) => p.id)));
      })
      .catch(() => {
        if (!cancelled) setDraftIds(null);
      });
    return () => { cancelled = true; };
  }, [profileId, needed]);
  return draftIds;
}
