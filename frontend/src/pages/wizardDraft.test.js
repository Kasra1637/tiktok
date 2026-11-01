import { createWizardDraft, wizardDraftReducer } from "./wizardDraft";

const project = {
  id: "draft-1", brand_profile_id: "app-1", content_angle_id: "angle-1",
  template_id: "template-1", objective: "create_curiosity", tone: "Warm",
  script: "Saved words", script_version: 2,
};

const resume = () => wizardDraftReducer(createWizardDraft(), { type: "draft-resumed", project });

test("resuming a draft adopts all selections and discards edits together", () => {
  const dirty = { ...createWizardDraft(), edits: { script: "Old edits" } };
  expect(wizardDraftReducer(dirty, { type: "draft-resumed", project })).toEqual({
    selectedProfileId: "app-1", angleId: "angle-1", templateId: "template-1",
    objective: "create_curiosity", tone: "Warm", project, edits: {},
  });
});

test("switching apps clears the previous draft and creative selections atomically", () => {
  const dirty = wizardDraftReducer(resume(), { type: "edit-field", field: "script", value: "New words" });
  expect(wizardDraftReducer(dirty, { type: "profile-selected", id: "app-2" })).toEqual({
    selectedProfileId: "app-2", angleId: "", templateId: "", objective: "", tone: "",
    project: null, edits: {},
  });
});

test("tone edits update the next plan input and current draft in one transition", () => {
  const state = wizardDraftReducer(resume(), { type: "tone-edited", value: "Direct" });
  expect(state.tone).toBe("Direct");
  expect(state.edits).toEqual({ tone: "Direct" });
  expect(state.project).toBe(project);
});

test("successive field edits compose without depending on a render snapshot", () => {
  const state = wizardDraftReducer(resume(), { type: "edit-field", field: "hook_line", value: "Opening" });
  expect(wizardDraftReducer(state, { type: "edit-field", field: "script", value: "Body" }).edits)
    .toEqual({ hook_line: "Opening", script: "Body" });
  expect(state.edits).toEqual({ hook_line: "Opening" });
});

test("background project updates retain draft edits; accepted saves clear them", () => {
  const dirty = wizardDraftReducer(resume(), { type: "edit-field", field: "script", value: "Unsaved" });
  const fresh = { ...project, status: "ready_for_generation" };
  expect(wizardDraftReducer(dirty, { type: "project-received", project: fresh }).edits).toEqual({ script: "Unsaved" });
  expect(wizardDraftReducer(dirty, { type: "plan-accepted", project: fresh }).edits).toEqual({});
});

test("returning a direction to the saved/default value removes only its pending edit", () => {
  const dirty = { ...resume(), edits: { camera_setup: "fixed", script: "Keep this" } };
  const state = wizardDraftReducer(dirty, {
    type: "edit-field", field: "camera_setup", value: "handheld", omitDefault: true, fallback: "handheld",
  });
  expect(state.edits).toEqual({ script: "Keep this" });
});

test("selection edits do not silently adopt or alter the saved project", () => {
  let state = resume();
  for (const action of [
    { type: "angle-selected", id: "angle-2" },
    { type: "template-selected", id: "template-2" },
    { type: "goal-selected", value: "address_user_problem" },
  ]) state = wizardDraftReducer(state, action);
  expect(state.angleId).toBe("angle-2");
  expect(state.templateId).toBe("template-2");
  expect(state.objective).toBe("address_user_problem");
  expect(state.project).toBe(project);
});

test("keystrokes typed during a save flight survive the adoption", () => {
  const savedEdits = { script: "Saving this" };
  const dirty = { ...resume(), edits: { script: "Saving this", hook_line: "Typed mid-flight" } };
  const fresh = { ...project, script_version: 3 };
  const state = wizardDraftReducer(dirty, { type: "plan-accepted", project: fresh, savedEdits });
  expect(state.project).toBe(fresh);
  expect(state.edits).toEqual({ hook_line: "Typed mid-flight" });
});

test("edited-same-value during a save flight still clears (no phantom edit)", () => {
  const savedEdits = { script: "Same words" };
  const dirty = { ...resume(), edits: { ...savedEdits } };
  const fresh = { ...project, script_version: 3 };
  expect(wizardDraftReducer(dirty, { type: "plan-accepted", project: fresh, savedEdits }).edits).toEqual({});
});

test("deep-link picks initialize without inventing a project or goal", () => {
  expect(createWizardDraft({ profile: "app", angle: "angle", template: "template" })).toEqual({
    selectedProfileId: "app", angleId: "angle", templateId: "template", objective: "", tone: "",
    project: null, edits: {},
  });
});
