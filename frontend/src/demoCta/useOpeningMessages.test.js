import React, { act, useState } from "react";
import { createRoot } from "react-dom/client";
import { api } from "../lib/api";
import { useOpeningMessages } from "./useOpeningMessages";

jest.mock("../lib/api", () => ({
  api: { generateOpeningMessages: jest.fn() },
  getErrorMessage: (e) => e.message,
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
let hook;
const messages = (prefix = "Fresh") => Array.from({ length: 20 }, (_, i) => `${prefix} app opening ${i + 1}`);
function Probe({ profileId }) {
  const [text, setText] = useState("Current opening");
  hook = useOpeningMessages({ profileId, text, onText: setText });
  return <textarea readOnly value={text} />;
}
function mount(profileId = "app-1") {
  const div = document.createElement("div");
  const root = createRoot(div);
  const render = (id) => act(() => root.render(<Probe profileId={id} />));
  render(profileId);
  return { div, render, unmount: () => act(() => root.unmount()) };
}
beforeEach(() => jest.resetAllMocks());

test("shows all 20 generated messages in the controlled input without repeats or extra requests", async () => {
  api.generateOpeningMessages.mockResolvedValue({ messages: messages() });
  const { div, unmount } = mount();
  const seen = [];
  for (let i = 0; i < 20; i++) {
    await act(async () => { expect(await hook.surprise()).toBe(true); });
    seen.push(div.querySelector("textarea").value);
  }
  expect(seen).toEqual(messages());
  expect(api.generateOpeningMessages).toHaveBeenCalledTimes(1);
  expect(api.generateOpeningMessages).toHaveBeenCalledWith("app-1", ["Current opening"]);
  api.generateOpeningMessages.mockResolvedValueOnce({ messages: messages("Next") });
  await act(async () => { await hook.surprise(); });
  expect(div.querySelector("textarea").value).toBe(messages("Next")[0]);
  expect(api.generateOpeningMessages).toHaveBeenCalledTimes(2);
  unmount();
});

test("rejects duplicate saved-style messages instead of appearing to do nothing, then allows retry", async () => {
  api.generateOpeningMessages.mockResolvedValueOnce({ messages: Array(20).fill("Current opening") });
  const { div, unmount } = mount();
  await act(async () => { expect(await hook.surprise()).toBe(false); });
  expect(div.querySelector("textarea").value).toBe("Current opening");
  expect(hook.error).toMatch(/20.*distinct/i);
  expect(hook.generating).toBe(false);
  api.generateOpeningMessages.mockResolvedValueOnce({ messages: messages() });
  await act(async () => { await hook.surprise(); });
  expect(hook.error).toBeNull();
  expect(div.querySelector("textarea").value).toBe(messages()[0]);
  unmount();
});

test("deduplicates pending clicks and preserves edits made while waiting", async () => {
  let resolve;
  api.generateOpeningMessages.mockReturnValue(new Promise((r) => { resolve = r; }));
  const { div, unmount } = mount();
  let pending;
  act(() => { pending = hook.surprise(); });
  expect(hook.generating).toBe(true);
  await act(async () => { await hook.surprise(); });
  expect(api.generateOpeningMessages).toHaveBeenCalledTimes(1);
  act(() => hook.updateText("My edit while waiting"));
  await act(async () => { resolve({ messages: messages() }); await pending; });
  expect(div.querySelector("textarea").value).toBe("My edit while waiting");
  expect(hook.generating).toBe(false);
  unmount();
});

test("discards an old app's pending result and requests the newly attached History app", async () => {
  let resolve;
  api.generateOpeningMessages.mockReturnValueOnce(new Promise((r) => { resolve = r; }));
  const { div, render, unmount } = mount();
  let pending;
  act(() => { pending = hook.surprise(); });
  render("app-2");
  await act(async () => { resolve({ messages: messages("Old app") }); await pending; });
  expect(div.querySelector("textarea").value).toBe("Current opening");
  api.generateOpeningMessages.mockResolvedValueOnce({ messages: messages("New app") });
  await act(async () => { await hook.surprise(); });
  expect(api.generateOpeningMessages).toHaveBeenLastCalledWith("app-2", ["Current opening"]);
  expect(div.querySelector("textarea").value).toBe(messages("New app")[0]);
  unmount();
});

test("standalone uses active app resolution and exposes server errors without changing text", async () => {
  api.generateOpeningMessages.mockRejectedValueOnce(new Error("Approve an App Profile first."));
  const { div, unmount } = mount(null);
  await act(async () => { expect(await hook.surprise()).toBe(false); });
  expect(api.generateOpeningMessages).toHaveBeenCalledWith(null, ["Current opening"]);
  expect(hook.error).toMatch(/Approve/);
  expect(div.querySelector("textarea").value).toBe("Current opening");
  expect(hook.generating).toBe(false);
  unmount();
});
