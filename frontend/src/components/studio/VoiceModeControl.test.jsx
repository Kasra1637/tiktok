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
  test("offers exactly the three choices, in gender-neutral words", async () => {
    // Three stops since the Voiceover removal (Nov 27 2026):
    // App's choice / Character talks / Character stays silent.
    const view = await mount();
    expect(view.q("voice-mode-auto").textContent).toBe("App's choice");
    expect(view.q("voice-mode-voiceover")).toBeNull();
    expect(view.q("voice-mode-talking").textContent).toBe("Character talks");
    expect(view.q("voice-mode-silent").textContent).toBe("Character stays silent");
    expect(view.q("voice-mode-talking").getAttribute("aria-pressed")).toBe("true");
    expect(view.q("voice-mode-silent").getAttribute("aria-pressed")).toBe("false");
    expect(view.q("voice-mode-silent-note")).toBeNull();
    // Nov 27 2026 (Kasra's order): talking mode stands with no
    // line under the pills — the long descriptive sentence that
    // stood there is removed whole, on every caller.
    expect(view.container.textContent).not.toContain("The character speaks the line on camera");
    await view.unmount();
  });

  test("an explicitly unpicked face marks no choice and no note rises on the change onto silent", async () => {
    // ADR 0361: Create passes pickedValue="" for a project standing
    // on its defaults — no button is pressed. The text-to-speech
    // handover note is removed whole (Kasra's order, later Nov 27
    // 2026 — it duplicated what the silent pick already says), so no
    // note stands for the standing state and none rises on the
    // change onto silent either.
    const view = await mount({ value: "silent", pickedValue: "" });
    expect(view.q("voice-mode-talking").getAttribute("aria-pressed")).toBe("false");
    expect(view.q("voice-mode-silent").getAttribute("aria-pressed")).toBe("false");
    expect(view.q("voice-mode-silent-note")).toBeNull();
    await act(async () => { view.q("voice-mode-silent").click(); });
    expect(view.q("voice-mode-silent-note")).toBeNull();
    await view.unmount();
  });

  test("no note stands in either mode — the handover note is removed whole", async () => {
    // The silent note is gone on every caller (Kasra's order,
    // later Nov 27 2026): it duplicated what the silent pick
    // already says, and no explainer line stands either. The buttons and
    // their picked faces are untouched, and talking mode carries
    // no line of its own at all (Nov 27 2026).
    const silent = await mount({ value: "silent" });
    expect(silent.q("voice-mode-silent-note")).toBeNull();
    expect(silent.q("voice-mode-silent").getAttribute("aria-pressed")).toBe("true");
    expect(silent.container.textContent).not.toContain("The character stays silent in this video");
    expect(silent.container.textContent).not.toContain("paste this line");
    await silent.unmount();
    const talking = await mount({ value: "talking" });
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

  test("changing onto silent raises no handover note and shows no line for pasting", async () => {
    // Kasra's order (later Nov 27 2026): the "For a voice on
    // TikTok, paste this line into TikTok's text-to-speech" note
    // is removed whole — it duplicated what the silent pick
    // already says. No explainer line stands under the pick
    // either (pinned in the slider case below).
    const view = await mount({ value: "silent" });
    expect(view.q("voice-mode-silent-note")).toBeNull();
    await act(async () => { view.q("voice-mode-silent").click(); });
    expect(view.q("voice-mode-silent-note")).toBeNull();
    expect(view.container.textContent).not.toContain("paste this line");
    expect(view.container.textContent).not.toContain("will appear here once it is written");
    await view.unmount();
  });

  test("the slider form rests the knob on the standing mode with no pick lit", async () => {
    // Nov 27 2026 (Kasra's order): HookSnap passes asSlider — the
    // choices stand as slider stops. Unpicked (ADR 0361), no
    // stop is pressed, the knob rests on the mode that will
    // render, and its name stands under the track. No note ever
    // stands: the text-to-speech handover note is removed whole
    // (Kasra's order, later Nov 27 2026), for the standing pick
    // and for the change onto silent alike.
    const view = await mount({ value: "silent", pickedValue: "", asSlider: true });
    expect(view.q("voice-mode-slider")).not.toBeNull();
    const knob = view.q("voice-mode-knob");
    expect(knob).not.toBeNull();
    expect(knob.getAttribute("role")).toBe("slider");
    // Silent is the third stop since the Voiceover removal
    // (Nov 27 2026), so the resting knob reads 2.
    expect(knob.getAttribute("aria-valuenow")).toBe("2");
    expect(view.q("voice-mode-talking").getAttribute("aria-pressed")).toBe("false");
    expect(view.q("voice-mode-silent").getAttribute("aria-pressed")).toBe("false");
    expect(view.q("voice-mode-value").textContent).toBe("Character stays silent");
    expect(view.q("voice-mode-silent-note")).toBeNull();
    await act(async () => { view.q("voice-mode-talking").click(); });
    expect(view.onChange).toHaveBeenCalledWith("talking");
    await act(async () => { view.q("voice-mode-silent").click(); });
    expect(view.q("voice-mode-silent-note")).toBeNull();
    await view.unmount();
  });

  test("the default rendering carries no slider", async () => {
    const view = await mount();
    expect(view.q("voice-mode-slider")).toBeNull();
    expect(view.q("voice-mode-knob")).toBeNull();
    await view.unmount();
  });

  test("an unset value reads as talking, the left stop", async () => {
    // Kasra's order (Nov 27 2026): every toggle rests on the left
    // by default — an unset voice value is talking, never silent.
    const view = await mount({ value: undefined });
    expect(view.q("voice-mode-talking").getAttribute("aria-pressed")).toBe("true");
    expect(view.q("voice-mode-silent").getAttribute("aria-pressed")).toBe("false");
    await view.unmount();
  });

  test("the slider carries three stops and no explainer ever stands", async () => {
    // Kasra's orders (Nov 27 2026): the Voiceover stop is removed
    // (three stops remain, inside his 3–4 range), and no explainer
    // line stands under any toggle — standing or after a change,
    // the pick's name is the whole information.
    const view = await mount({ value: "talking", pickedValue: "", asSlider: true });
    const stops = [...view.container.querySelectorAll('[data-testid="voice-mode-slider"] .pick-slider-stop')]
      .map((b) => b.dataset.value);
    expect(stops).toEqual(["auto", "talking", "silent"]);
    expect(view.q("voice-mode-explain")).toBeNull();
    await act(async () => { view.q("voice-mode-silent").click(); });
    expect(view.q("voice-mode-explain")).toBeNull();
    await act(async () => { view.q("voice-mode-talking").click(); });
    expect(view.q("voice-mode-explain")).toBeNull();
    await view.unmount();
  });

  test("a legacy voiceover value reads as talking, never as a dead stop", async () => {
    // Stored projects from the few hours the Voiceover stop
    // stood must not break: the control maps the dead value to
    // talking, the closest standing behavior.
    const view = await mount({ value: "voiceover" });
    expect(view.q("voice-mode-talking").getAttribute("aria-pressed")).toBe("true");
    await view.unmount();
  });
});
