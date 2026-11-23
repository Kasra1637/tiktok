/**
 * ADR 0274: adding a clip or an image in Demo + CTA also files one copy in
 * the Assets library. The upload is a side effect of the add — it must fire
 * exactly once per draft entry, carry the file's own name so library search
 * finds it, and never throw back into the editor when it fails.
 */
import { uploadEntryToLibrary } from "./libraryUpload";

function clipFile(name = "demo.mp4") {
  return new File([new Uint8Array(8)], name, { type: "video/mp4" });
}

describe("uploadEntryToLibrary", () => {
  test("uploads the entry once, under its kind, with the file's own name", async () => {
    const uploadAsset = jest.fn(async () => ({ id: "asset-1" }));
    const sent = new Set();
    const file = clipFile();
    const created = await uploadEntryToLibrary({
      profileId: "p1", entryId: "e1", file, kind: "screen_recording",
      sent, uploadAsset,
    });
    expect(created).toEqual({ id: "asset-1" });
    expect(uploadAsset).toHaveBeenCalledTimes(1);
    const [profileId, sentForm] = uploadAsset.mock.calls[0];
    expect(profileId).toBe("p1");
    expect(sentForm.get("kind")).toBe("screen_recording");
    // The filename rides the append explicitly, so the stored entry is a
    // same-named copy of the picked file rather than the object itself.
    const sentFile = sentForm.get("file");
    expect(sentFile.name).toBe("demo.mp4");
    expect(sentFile.size).toBe(file.size);
    expect(sentFile.type).toBe("video/mp4");

    // The same draft entry never uploads twice.
    const again = await uploadEntryToLibrary({
      profileId: "p1", entryId: "e1", file, kind: "screen_recording",
      sent, uploadAsset,
    });
    expect(again).toBeNull();
    expect(uploadAsset).toHaveBeenCalledTimes(1);
  });

  test("a different entry uploads separately", async () => {
    const uploadAsset = jest.fn(async () => ({ id: "asset-x" }));
    const sent = new Set();
    await uploadEntryToLibrary({
      profileId: "p1", entryId: "e1", file: clipFile("one.mp4"),
      kind: "screen_recording", sent, uploadAsset,
    });
    await uploadEntryToLibrary({
      profileId: "p1", entryId: "e2", file: clipFile("two.mp4"),
      kind: "screen_recording", sent, uploadAsset,
    });
    expect(uploadAsset).toHaveBeenCalledTimes(2);
  });

  test("a failed upload resolves quietly instead of throwing", async () => {
    const uploadAsset = jest.fn(async () => {
      throw new Error("library unavailable");
    });
    const result = await uploadEntryToLibrary({
      profileId: "p1", entryId: "e1", file: clipFile(), kind: "screen_recording",
      sent: new Set(), uploadAsset,
    });
    expect(result).toBeNull();
    expect(uploadAsset).toHaveBeenCalledTimes(1);
  });

  test("a synchronously throwing upload is quiet too", async () => {
    const uploadAsset = jest.fn(() => {
      throw new Error("no FormData here");
    });
    const result = await uploadEntryToLibrary({
      profileId: "p1", entryId: "e1", file: clipFile(), kind: "screen_recording",
      sent: new Set(), uploadAsset,
    });
    expect(result).toBeNull();
  });

  test("even a FormData failure resolves quietly", async () => {
    const uploadAsset = jest.fn(async () => ({ id: "asset-1" }));
    const RealFormData = global.FormData;
    global.FormData = class {
      constructor() {
        throw new Error("no forms");
      }
    };
    try {
      const result = await uploadEntryToLibrary({
        profileId: "p1", entryId: "e9", file: clipFile("shot.png"),
        kind: "screenshot", sent: new Set(), uploadAsset,
      });
      expect(result).toBeNull();
      expect(uploadAsset).not.toHaveBeenCalled();
    } finally {
      global.FormData = RealFormData;
    }
  });

  test("without an app profile nothing is sent and nothing is marked", async () => {
    const uploadAsset = jest.fn(async () => ({ id: "asset-1" }));
    const sent = new Set();
    const result = await uploadEntryToLibrary({
      profileId: "", entryId: "e1", file: clipFile(), kind: "screen_recording",
      sent, uploadAsset,
    });
    expect(result).toBeNull();
    expect(uploadAsset).not.toHaveBeenCalled();
    expect(sent.has("e1")).toBe(false);
  });
});
