import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { useEditSession } from "./editSession";
import { writeDraft } from "./draftStorage";

jest.mock("./draftStorage", () => ({ writeDraft: jest.fn(async () => {}) }));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let root, host, session, current, apply;
function Probe() {
  const [edit, setEdit] = React.useState({ text: "Original", start: 0 });
  current = edit;
  apply = setEdit;
  session = useEditSession({ draftKey: "anonymous:standalone", snapshot: edit, restore: setEdit, enabled: true });
  return null;
}
beforeEach(async () => {
  jest.useFakeTimers();
  writeDraft.mockClear();
  host = document.createElement("div");
  root = createRoot(host);
  await act(async () => root.render(<Probe />));
});
afterEach(async () => {
  await act(async () => root.unmount());
  jest.useRealTimers();
});

test("edits autosave the latest document and undo/redo restore whole edits", async () => {
  await act(async () => apply({ text: "New caption", start: 2 }));
  await act(async () => jest.advanceTimersByTime(600));
  expect(writeDraft).toHaveBeenLastCalledWith("anonymous:standalone", { text: "New caption", start: 2 });
  expect(session.canUndo).toBe(true);
  await act(async () => session.undo());
  expect(current).toEqual({ text: "Original", start: 0 });
  await act(async () => session.redo());
  expect(current).toEqual({ text: "New caption", start: 2 });
  await act(async () => session.undo());
  await act(async () => apply({ text: "Another direction", start: 0 }));
  expect(session.canRedo).toBe(false);
});

test("continuous typing is one undo step and unmount flushes the latest edit", async () => {
  await act(async () => apply({ text: "N", start: 0 }));
  await act(async () => jest.advanceTimersByTime(100));
  await act(async () => apply({ text: "New", start: 0 }));
  await act(async () => session.undo());
  expect(current.text).toBe("Original");
  await act(async () => apply({ text: "Last keystroke", start: 0 }));
  await act(async () => root.unmount());
  expect(writeDraft).toHaveBeenLastCalledWith("anonymous:standalone", { text: "Last keystroke", start: 0 });
  root = createRoot(host);
});

test("storage failures are visible and retry saves the current edit", async () => {
  writeDraft.mockRejectedValueOnce(new Error("Quota exceeded"));
  await act(async () => apply({ text: "Keep this", start: 0 }));
  await act(async () => jest.advanceTimersByTime(600));
  expect(session.saveStatus).toMatch(/not saved/i);
  await act(async () => session.saveNow());
  expect(session.saveStatus).toMatch(/saved/i);
});
