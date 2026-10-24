import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { useExportErrors } from "./useExportErrors";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

function Probe({ onHook }) {
  const hook = useExportErrors();
  onHook(hook);
  return <span data-count={hook.exportErrors.length} />;
}

async function mountProbe() {
  let hook = null;
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<Probe onHook={(h) => { hook = h; }} />);
  });
  return {
    hook: () => hook,
    count: () => container.querySelector("span").getAttribute("data-count"),
    unmount: async () => {
      await act(async () => { root.unmount(); });
      container.remove();
    },
  };
}

test("recording logs the failure to the console with its stage", async () => {
  const warned = jest.spyOn(console, "warn").mockImplementation(() => {});
  try {
    const probe = await mountProbe();
    await act(async () => {
      probe.hook().recordExportError("save", new Error("No."));
    });
    expect(warned).toHaveBeenCalledWith("[HookForge] Export failed:", "save", "No.");
    await probe.unmount();
  } finally {
    warned.mockRestore();
  }
});

test("starts with no recorded errors", async () => {
  const probe = await mountProbe();
  expect(probe.hook().exportErrors).toEqual([]);
  await probe.unmount();
});

test("records the stage and message of each failure", async () => {
  const probe = await mountProbe();
  let entry;
  await act(async () => {
    entry = probe.hook().recordExportError("encode", new Error("The encoder failed."));
  });
  expect(entry.stage).toBe("encode");
  expect(entry.message).toBe("The encoder failed.");
  expect(typeof entry.at).toBe("string");
  expect(probe.hook().exportErrors).toHaveLength(1);
  expect(probe.count()).toBe("1");
  await probe.unmount();
});

test("recording never throws and keeps prior entries", async () => {
  const probe = await mountProbe();
  await act(async () => {
    probe.hook().recordExportError("save", new Error("No."));
    probe.hook().recordExportError("export", undefined);
  });
  const errors = probe.hook().exportErrors;
  expect(errors).toHaveLength(2);
  expect(errors[0].stage).toBe("save");
  expect(typeof errors[1].message).toBe("string");
  await probe.unmount();
});

test("clearing empties the history", async () => {
  const probe = await mountProbe();
  await act(async () => {
    probe.hook().recordExportError("save", new Error("No."));
    probe.hook().clearExportErrors();
  });
  expect(probe.hook().exportErrors).toEqual([]);
  await probe.unmount();
});
