import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { ExportFailureNote } from "./ExportFailureNote";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

async function renderNote(entry) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<ExportFailureNote entry={entry} />);
  });
  const text = container.textContent;
  await act(async () => { root.unmount(); });
  container.remove();
  return text;
}

test("a failed save names its stage in the banner", async () => {
  const text = await renderNote({
    stage: "save",
    message: "No.",
    at: new Date("2026-10-24T19:00:00.000Z").toISOString(),
  });
  expect(text).toMatch(/Failed during save/);
});

test("no entry renders no note", async () => {
  const text = await renderNote(null);
  expect(text).toBe("");
});
