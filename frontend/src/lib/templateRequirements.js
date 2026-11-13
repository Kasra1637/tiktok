/**
 * Matching a template's required assets against what a draft already has.
 *
 * Why this is a helper and not inline JSX: the Audience & template step shows
 * a template's `required_assets` as badges where assets get attached — so
 * without a have/missing state the founder must hold the requirement in
 * memory while picking. The comparison itself is trivial, but
 * pinning it here means the matching rule (case, whitespace, non-array
 * inputs) is asserted in scripts/check-frontend-logic.cjs instead of living
 * untested inside a render branch.
 *
 * A requirement counts as met when ANY attached asset normalizes to the same
 * kind. Attachment rows carry `kind` (see AttachmentRow in CreateVideo.jsx);
 * anything without a readable kind simply never matches.
 */

function normKind(value) {
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}

/**
 * [{ kind, have }] in the template's own order. Unknown or blank entries are
 * kept (the UI still names them) but never match.
 */
export function requiredAssetStatus(requiredAssets, attachedAssets) {
  const required = Array.isArray(requiredAssets) ? requiredAssets : [];
  const attached = Array.isArray(attachedAssets) ? attachedAssets : [];
  const haveKinds = new Set(
    attached.map((a) => normKind(a && a.kind)).filter(Boolean)
  );
  return required.map((raw) => {
    const kind = typeof raw === "string" ? raw.trim() : "";
    return { kind, have: Boolean(kind) && haveKinds.has(normKind(kind)) };
  });
}

/** True when every named requirement is attached. Vacuous truth for none. */
export function allRequiredAssetsAttached(requiredAssets, attachedAssets) {
  return requiredAssetStatus(requiredAssets, attachedAssets).every((r) => r.have);
}

/**
 * Whether a fit note is the character-reference need ("Needs character
 * reference."). The scorer phrases a template's required assets exactly
 * that way (backend/template_recommendations.py), and when every card in
 * a set shares the note it is hoisted above the grid — where it only
 * repeats what the step already handles: each card states the character's
 * look comes from the uploaded photo, the photo section owns attaching
 * it, and generation stays blocked until it is attached
 * (blockingRequirements above). The templates header drops this one note;
 * per-card requirement text and the blocking rule itself are untouched.
 */
export function isCharacterReferenceNeed(note) {
  const text = typeof note === "string"
    ? note.trim().toLowerCase().replace(/\s+/g, " ").replace(/\.+$/, "")
    : "";
  return text === "needs character reference";
}

/**
 * The one requirement that stops generation.
 *
 * Face-only product: the character reference is the single permitted asset
 * kind, and every template requires exactly it. The backend refuses a
 * generation without one in _studio_identity_references, and refuses retired
 * uploads everywhere else — so this stays a named, tested function rather
 * than an inline filter, which is exactly the shape that once shipped a bug
 * where every missing requirement blocked. scripts/check-frontend-logic.cjs
 * asserts the blocking rule.
 */
export function blockingRequirements(requiredAssets, attachedAssets) {
  return requiredAssetStatus(requiredAssets, attachedAssets).filter(
    (r) => !r.have && normKind(r.kind) === "character_reference"
  );
}
