// One owner for the choices, saved project and unsaved Review fields.
// Network flights, URL navigation and presentation state stay outside this reducer.
export function createWizardDraft({ profile = "", angle = "", template = "" } = {}) {
  return {
    selectedProfileId: profile, angleId: angle, templateId: template,
    objective: "", tone: "", project: null, edits: {}, picks: {},
  };
}

export function wizardDraftReducer(state, action) {
  switch (action.type) {
    case "profile-selected":
      return createWizardDraft({ profile: action.id });
    case "profile-loaded":
      return { ...state, selectedProfileId: action.id };
    case "draft-resumed": {
      const project = action.project;
      return {
        ...createWizardDraft({
          profile: project.brand_profile_id || "",
          angle: project.content_angle_id || "",
          template: project.template_id || "",
        }),
        objective: project.objective || "", tone: project.tone || "", project,
      };
    }
    case "angle-selected":
      return { ...state, angleId: action.id };
    case "template-selected":
      return { ...state, templateId: action.id };
    case "goal-selected":
      return { ...state, objective: action.value };
    case "tone-edited":
      return { ...state, tone: action.value, edits: { ...state.edits, tone: action.value } };
    case "edit-field": {
      const edits = { ...state.edits, [action.field]: action.value };
      if (action.omitDefault && (!action.value || action.value === (state.project?.[action.field] || action.fallback || ""))) {
        delete edits[action.field];
      }
      // The pick record (ADR 0373): a pick-shaped edit (omitDefault)
      // is remembered as a pick even when it restates the saved
      // value and so stores no edit above. The click happened, and
      // the direction groups' faces read this record first (see
      // editPick in CreateVideo) — without it, a click on the
      // standing default (Character stays silent on a fresh
      // project, Handheld selfie) changed nothing anywhere and the
      // button read as dead. Save adoptions keep the record; only
      // a fresh draft (resume, profile switch) clears it, which is
      // what keeps an untouched project showing no pick (ADR 0361)
      // while a clicked default stands picked.
      const picks = action.omitDefault && action.value
        ? { ...state.picks, [action.field]: action.value }
        : state.picks;
      return { ...state, edits, picks };
    }
    case "project-received":
      return { ...state, project: action.project };
    case "plan-accepted": {
      // A save flight snapshots `edits` when it starts. Keystrokes that land
      // while the flight is in the air are newer than that snapshot and must
      // survive the adoption — clearing everything would silently drop them.
      // Without a snapshot (legacy callers) the adoption still clears all.
      const saved = action.savedEdits;
      if (!saved || typeof saved !== "object") {
        return { ...state, project: action.project, edits: {} };
      }
      const edits = {};
      for (const [field, value] of Object.entries(state.edits || {})) {
        if (!(field in saved) || saved[field] !== value) {
          edits[field] = value;
        }
      }
      return { ...state, project: action.project, edits };
    }
    default:
      throw new Error(`Unknown wizard draft transition: ${action.type}`);
  }
}
