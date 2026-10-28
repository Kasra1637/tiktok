import {
  __resetPendingSavesForTests,
  clearPendingSave,
  clearPendingSavesFor,
  listPendingSaves,
  recordFailedSave,
  retryPendingSave,
} from "./saveOutbox";

beforeEach(() => {
  __resetPendingSavesForTests();
});

test("a recorded failed save lists newest first with its message", () => {
  recordFailedSave({ generationId: "gen-1", filename: "demo-cta.mp4", size: 9, message: "Too large.", blob: new Blob(["x"]) });
  const entries = listPendingSaves();
  expect(entries).toHaveLength(1);
  expect(entries[0].generationId).toBe("gen-1");
  expect(entries[0].message).toBe("Too large.");
});

test("a successful save clears its matching pending entry", () => {
  const blob = new Blob(["x"]);
  const entry = recordFailedSave({ generationId: "gen-1", filename: "demo-cta.mp4", blob });
  recordFailedSave({ generationId: "gen-2", filename: "other.mp4", blob: new Blob(["y"]) });
  clearPendingSavesFor({ generationId: "gen-1", filename: "demo-cta.mp4", blob });
  expect(listPendingSaves().some((e) => e.id === entry.id)).toBe(false);
  expect(listPendingSaves()).toHaveLength(1);
});

test("retrying re-saves the bytes and clears the entry", async () => {
  const blob = new Blob(["bytes"], { type: "video/mp4" });
  const entry = recordFailedSave({ generationId: "gen-9", filename: "big.mp4", blob });
  const saveFn = jest.fn().mockResolvedValue({ id: "saved-1" });
  const row = await retryPendingSave(entry.id, saveFn);
  expect(row).toEqual({ id: "saved-1" });
  expect(saveFn).toHaveBeenCalledWith("gen-9", blob, "big.mp4");
  expect(listPendingSaves()).toHaveLength(0);
});

test("retrying without bytes names re-export instead of failing silently", async () => {
  const entry = recordFailedSave({ generationId: null, filename: "demo-cta.mp4", message: "Too large." });
  await expect(retryPendingSave(entry.id, jest.fn())).rejects.toThrow(/re-export/i);
  expect(listPendingSaves()).toHaveLength(1);
});

test("a failed retry refreshes the message and keeps the entry", async () => {
  const entry = recordFailedSave({ generationId: "gen-1", filename: "demo-cta.mp4", blob: new Blob(["x"]) });
  const saveFn = jest.fn().mockRejectedValue(new Error("Still too large."));
  await expect(retryPendingSave(entry.id, saveFn)).rejects.toThrow("Still too large.");
  const entries = listPendingSaves();
  expect(entries).toHaveLength(1);
  expect(entries[0].message).toBe("Still too large.");
});

test("dismissing drops the entry", () => {
  const entry = recordFailedSave({ filename: "demo-cta.mp4", blob: new Blob(["x"]) });
  clearPendingSave(entry.id);
  expect(listPendingSaves()).toHaveLength(0);
});
