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
