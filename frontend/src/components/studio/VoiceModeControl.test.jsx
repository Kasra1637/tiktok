import React, { act } from "react";
import { createRoot } from "react-dom/client";
import VoiceModeControl from "./VoiceModeControl";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

async function mount(props = {}) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  const onChange = jest.fn();
  await act(async () => {
    root.render(<VoiceModeControl value="talking" onChange={onChange} {...props} />);
  });
  const q = (id) => container.querySelector(`[data-testid="${id}"]`);
  return {
    container, q, onChange,
    unmount: async () => { await act(async () => root.unmount()); container.remove(); },
  };
}

describe("VoiceModeControl", () => {
  test("offers exactly the two choices, in gender-neutral words", async () => {
    const view = await mount();
    expect(view.q("voice-mode-talking").textContent).toBe("Character talks");
    expect(view.q("voice-mode-silent").textContent).toBe("Character stays silent");
    expect(view.q("voice-mode-talking").getAttribute("aria-pressed")).toBe("true");
    expect(view.q("voice-mode-silent").getAttribute("aria-pressed")).toBe("false");
    expect(view.q("voice-mode-silent-note")).toBeNull();
    await view.unmount();
  });

  test("an explicitly unpicked face marks no choice while the note follows the mode", async () => {
    // ADR 0361: Create passes pickedValue="" for a project standing
    // on its defaults — no button is pressed, and the note still
    // names the mode that will render.
    const view = await mount({ value: "silent", pickedValue: "" });
    expect(view.q("voice-mode-talking").getAttribute("aria-pressed")).toBe("false");
    expect(view.q("voice-mode-silent").getAttribute("aria-pressed")).toBe("false");
    expect(view.q("voice-mode-silent-note")).not.toBeNull();
    await view.unmount();
  });

  test("hideNote stands the pills without the note in either mode", async () => {
    // ADR 0362: Create's direction section carries no descriptive
    // lines, so it passes hideNote — the buttons and their picked
    // faces are untouched, and neither mode's note renders. A
    // caller that passes nothing (HookSnap) keeps the note, as the
    // cases above and below pin.
    const silent = await mount({ value: "silent", hideNote: true, silentText: "A line." });
    expect(silent.q("voice-mode-silent-note")).toBeNull();
    expect(silent.q("voice-mode-silent").getAttribute("aria-pressed")).toBe("true");
    expect(silent.container.textContent).not.toContain("The character stays silent in this video");
    await silent.unmount();
    const talking = await mount({ value: "talking", hideNote: true });
    expect(talking.container.textContent).not.toContain("The character speaks the line on camera");
    expect(talking.q("voice-mode-talking").getAttribute("aria-pressed")).toBe("true");
    await talking.unmount();
  });

  test("picking silent reports the choice", async () => {
    const view = await mount();
    await act(async () => { view.q("voice-mode-silent").click(); });
    expect(view.onChange).toHaveBeenCalledWith("silent");
    await view.unmount();
  });

  test("picking talking from a silent pick reports the choice", async () => {
    const view = await mount({ value: "silent" });
    expect(view.q("voice-mode-silent").getAttribute("aria-pressed")).toBe("true");
    await act(async () => { view.q("voice-mode-talking").click(); });
    expect(view.onChange).toHaveBeenCalledWith("talking");
    await view.unmount();
  });

  test("the silent note names the exact text for TikTok's text-to-speech", async () => {
    const view = await mount({
      value: "silent",
      silentText: "I'm trying to clear my head before bed but my thoughts race.",
      silentTextName: "the hook line",
    });
    const note = view.q("voice-mode-silent-note");
    expect(note).not.toBeNull();
    expect(note.textContent).toContain("The character stays silent in this video");
    expect(note.textContent).toContain("text-to-speech");
    expect(note.textContent).toContain("I'm trying to clear my head before bed but my thoughts race.");
    await view.unmount();
  });

  test("the silent note before any line exists names what will show", async () => {
    const view = await mount({ value: "silent", silentText: "", silentTextName: "the hook line" });
    const note = view.q("voice-mode-silent-note");
    expect(note).not.toBeNull();
    expect(note.textContent).toContain("The hook line will appear here once it is written.");
    await view.unmount();
  });
});
