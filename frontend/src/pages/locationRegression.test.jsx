// Location direction state and History classification; API calls are MOCKED.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { useWizardDirections } from "./useWizardDirections";
import { hasCopyContext } from "./historyRepair";

jest.mock("../lib/api", () => ({
  api: { getDirectionOptions: jest.fn(), refreshDirectionOptions: jest.fn() },
  getErrorMessage: (error) => error.message,
  durableMediaUrl: () => null,
}));
import { api } from "../lib/api";
jest.mock("lucide-react", () => {
  const Icon = () => null;
  return { Loader2: Icon, AlertTriangle: Icon, Info: Icon, MapPin: Icon, ShieldQuestion: Icon, Sparkles: Icon, Target: Icon, ChevronDown: Icon };
});
jest.mock("../components/ui/button", () => ({ Button: ({ children }) => <button>{children}</button> }));
jest.mock("../components/ui/badge", () => ({ Badge: ({ children }) => <span>{children}</span> }));
jest.mock("../components/ui/alert", () => ({
  Alert: ({ children }) => <div>{children}</div>,
  AlertTitle: ({ children }) => <div>{children}</div>,
  AlertDescription: ({ children }) => <div>{children}</div>,
}));
jest.mock("../components/SectionCard", () => ({ GroupLabel: ({ children }) => <span>{children}</span> }));
// The suggestion modal rides the shared Dialog since ADR 0140; the real
// one pulls in the "@/lib/utils" alias jest cannot resolve, and these
// tests never open the modal — a stand-in with the same shape suffices.
jest.mock("../components/ui/dialog", () => ({
  Dialog: ({ children, open }) => (open ? <div>{children}</div> : null),
  DialogContent: ({ children }) => <div>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogFooter: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <div>{children}</div>,
  DialogDescription: ({ children }) => <div>{children}</div>,
}));
import { HookContinuityPanel } from "../components/HookContinuityPanel";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

test("strategy scene renders one Location row and no retired place rows", async () => {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  try {
    await act(async () => { root.render(<HookContinuityPanel project={{
      id: "TEST_scene", status: "draft", content_angle_id: "TEST_angle", assets: [],
      strategy: { hook_line: "Test hook", content_angle_id: "TEST_angle",
        scene: { location: "A city rooftop at noon.", lighting: "Soft light" }, performance: {} },
    }} />); });
    expect(container.querySelectorAll('[data-testid="strategy-location"]').length).toBe(1);
    expect(container.querySelector('[data-testid="strategy-location"]').textContent).toContain("A city rooftop at noon.");
    expect(container.querySelector('[data-testid="strategy-environment"], [data-testid="strategy-background"], [data-testid="strategy-setting"]')).toBeNull();
  } finally {
    await act(async () => { root.unmount(); });
    container.remove();
  }
});

test("Location-only result is classified as containing context", () => {
  expect(hasCopyContext({ location: "A city rooftop at noon." })).toBe(true);
});

test("direction Location selection dispatches the same editable Location field", async () => {
  api.getDirectionOptions.mockResolvedValue({ location: ["Kitchen", "Rooftop"], lighting: [], wardrobe: [], voice: [], tone: [] });
  const dispatchDraft = jest.fn();
  let direction;
  function Harness() {
    direction = useWizardDirections({
      profileId: "TEST_profile", project: { id: "TEST_project", location: "Kitchen" },
      angle: null, dispatchDraft,
    });
    return <span data-testid="location-selection">{direction.dirSel.location}</span>;
  }
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  try {
    await act(async () => { root.render(<Harness />); });
    expect(container.querySelector('[data-testid="location-selection"]').textContent).toBe("Kitchen");
    await act(async () => { direction.pickScenePart("location")("Rooftop"); });
    expect(dispatchDraft).toHaveBeenLastCalledWith({ type: "edit-field", field: "location", value: "Rooftop", omitDefault: true });
    expect(container.querySelector('[data-testid="location-selection"]').textContent).toBe("Rooftop");
    await act(async () => { direction.pickScenePart("lighting")("Soft light"); });
    expect(dispatchDraft).toHaveBeenLastCalledWith({ type: "edit-field", field: "visual_direction", value: "Soft light", omitDefault: true });
    expect(container.querySelector('[data-testid="location-selection"]').textContent).toBe("Rooftop");
  } finally {
    await act(async () => { root.unmount(); });
    container.remove();
  }
});

test("a refresh that returns no options names the failure instead of dying silently", async () => {
  // Kasra's dead button (Nov 21 2026): "New options" for the location
  // produced nothing and said nothing. The endpoint now fails loudly
  // when nothing survives its filters (ADR 0257), and the hook must
  // never swallow an empty success either — an empty list is the same
  // failure wearing a 200, and the section's error line is where it
  // belongs.
  api.getDirectionOptions.mockResolvedValue({ location: ["Kitchen", "Rooftop"], lighting: [], wardrobe: [], voice: [], tone: [] });
  api.refreshDirectionOptions.mockResolvedValue({ field: "location", options: [] });
  const dispatchDraft = jest.fn();
  let direction;
  function Harness() {
    direction = useWizardDirections({
      profileId: "TEST_profile", project: { id: "TEST_project", location: "Kitchen" },
      angle: null, dispatchDraft,
    });
    return <span data-testid="refresh-error">{direction.refreshError}</span>;
  }
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  try {
    await act(async () => { root.render(<Harness />); });
    await act(async () => { await direction.refreshDirectionField("location")(); });
    expect(container.querySelector('[data-testid="refresh-error"]').textContent)
      .toBe("AI direction options failed. Please try again.");
    // The offered list is untouched by the failed refresh.
    expect(direction.directionOptions.location).toEqual(["Kitchen", "Rooftop"]);
  } finally {
    await act(async () => { root.unmount(); });
    container.remove();
  }
});