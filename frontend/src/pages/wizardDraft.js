// One owner for the choices, saved project and unsaved Review fields.
// Network flights, URL navigation and presentation state stay outside this reducer.
export function createWizardDraft({ profile = "", angle = "", template = "" } = {}) {
  return {
    selectedProfileId: profile, angleId: angle, templateId: template,
    objective: "", tone: "", project: null, edits: {},
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
      return { ...state, edits };
    }
    case "project-received":
      return { ...state, project: action.project };
    case "plan-accepted":
      return { ...state, project: action.project, edits: {} };
    default:
      throw new Error(`Unknown wizard draft transition: ${action.type}`);
  }
}
