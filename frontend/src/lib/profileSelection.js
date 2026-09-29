/**
 * Splitting an App Profile list into what the studio may use and what it may
 * not.
 *
 * Why this is a helper and not inline JSX: the studio's first step used to map
 * `profiles.filter(approved)` and render nothing else, so a profile you had
 * already created but not yet approved simply did not exist as far as the
 * picker was concerned. Someone with five apps and two approvals saw two, with
 * no indication the other three were sitting there — which reads as "my App
 * Profile isn't in the list" rather than "it needs approving".
 *
 * The approval gate itself is a safety property and stays strict: a video must
 * only ever build on facts the founder reviewed. What changed is that the
 * excluded ones are now named instead of dropped. Both halves of that promise
 * live here, together, so they cannot drift apart — a later edit cannot make
 * the picker permissive while leaving the explanation intact, or hide the
 * explanation while staying strict.
 *
 * The status string is compared exactly, matching what
 * `POST /app-profiles/{id}/approve` writes (backend/server.py) and what
 * `brand_profiles.status` defaults to. A profile in any other state is treated
 * as unapproved, which is the safe direction: an unrecognised status must not
 * silently become selectable.
 */

/** Profiles the studio will let you pick, and the rest, which it will name. */
export function partitionProfiles(profiles) {
  const list = Array.isArray(profiles) ? profiles : [];
  return {
    approved: list.filter((p) => p?.status === "approved"),
    unapproved: list.filter((p) => p?.status !== "approved"),
  };
}

/**
 * Which App Profile a profile-scoped page should show.
 *
 * The Asset Library is reachable three ways: embedded in the studio, which
 * already knows the profile; as `/app-profiles/:id/assets`, which carries it in
 * the path; and from the sidebar at plain `/assets`, which carries nothing at
 * all. That last one is why the page used to dead-end on "Choose an App Profile
 * first" with no way to choose one, even with an app already selected elsewhere
 * in the app.
 *
 * Precedence, highest first:
 *
 *   1. the `profileId` prop   embedded in the studio — it is mid-task, never guess
 *   2. the `:profileId` param  an explicit /app-profiles/:id/assets link
 *   3. `?profile=`             an explicit choice, and shareable
 *   4. the remembered id       the app last used in the editor, if it still exists
 *   5. the newest approved     the API already orders by updated_at DESC
 *   6. the newest profile      so a single unapproved app is still usable
 *
 * Anything explicit is trusted even when it is not in `profiles`: the caller may
 * still be loading, and a wrong-but-explicit id is a real profile the picker can
 * then correct. Only the *remembered* id is validated, because that one is stale
 * by nature — it refers to an app the user used in another session.
 *
 * Falling back to an unapproved profile is deliberate. `GET
 * /app-profiles/{id}/assets` only requires that the profile is the caller's, not
 * that it is approved, so an unapproved app can already hold uploads. Returning
 * "" for that case would re-create the dead end for exactly the founder who has
 * one app and has not approved it yet.
 */
export function resolveActiveProfileId({
  propId = "",
  paramId = "",
  queryId = "",
  rememberedId = "",
  profiles = [],
} = {}) {
  const clean = (v) => (typeof v === "string" ? v.trim() : "");
  const explicit = [clean(propId), clean(paramId), clean(queryId)].find(Boolean);
  if (explicit) return explicit;

  const list = Array.isArray(profiles) ? profiles : [];
  const remembered = clean(rememberedId);
  if (remembered && list.some((p) => p?.id === remembered)) return remembered;

  const { approved } = partitionProfiles(list);
  if (approved.length > 0) return approved[0].id;
  if (list.length > 0) return list[0].id;
  return "";
}

/**
 * A profile is usable only once it has been approved, and only the approval
 * endpoint can do that. This is deliberately the same comparison the picker
 * uses, so a profile can never be rendered as selectable and then rejected.
 */
export function isProfileSelectable(profile) {
  return profile?.status === "approved";
}

/** A display name, falling back rather than rendering a blank row. */
export function profileLabel(profile) {
  const name = typeof profile?.brand_name === "string" ? profile.brand_name.trim() : "";
  return name || "Untitled app";
}

/**
 * "3 profiles waiting for approval", for the panel under the picker.
 */
export function describeUnapprovedCount(count) {
  const n = Number(count) || 0;
  if (n <= 0) return "";
  return `${n} profile${n === 1 ? "" : "s"} waiting for approval`;
}

/**
 * The names of the profiles still waiting, for the same panel and for the
 * empty state. This is what makes an excluded profile visible instead of
 * missing, so it must always name them.
 */
export function describeUnapprovedNames(profiles) {
  const { unapproved } = partitionProfiles(profiles);
  return unapproved.map(profileLabel);
}

/**
 * The empty-state copy when nothing is selectable. With profiles waiting, the
 * useful sentence is which ones and why; without them, the useful sentence is
 * what to do next.
 */
export function describeEmptySelection(profiles) {
  const names = describeUnapprovedNames(profiles);
  if (names.length === 0) {
    return "Research an app and approve the profile before creating a video.";
  }
  const count = names.length;
  const noun = count === 1 ? "profile" : "profiles";
  const verb = count === 1 ? "approves" : "approve";
  return `You have ${count} ${noun} waiting for approval: ${names.join(", ")}. Review and ${verb} one to start.`;
}
