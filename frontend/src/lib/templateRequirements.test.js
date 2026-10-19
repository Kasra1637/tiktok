import {
  requiredAssetStatus,
  allRequiredAssetsAttached,
  blockingRequirements,
} from "./templateRequirements";

describe("requiredAssetStatus", () => {
  test("matches on kind, ignoring case and whitespace", () => {
    expect(
      requiredAssetStatus(["character_reference"], [{ kind: " Character_Reference " }])
    ).toEqual([{ kind: "character_reference", have: true }]);
  });

  test("missing kinds are named, not dropped", () => {
    expect(requiredAssetStatus(["character_reference"], [])).toEqual([
      { kind: "character_reference", have: false },
    ]);
  });

  test("blank requirements never match", () => {
    expect(requiredAssetStatus(["  "], [{ kind: "character_reference" }])[0].have).toBe(false);
  });

  test("kindless attachments never match", () => {
    expect(requiredAssetStatus(["character_reference"], [{}, { kind: null }])[0].have).toBe(false);
  });

  test("non-array inputs are safe", () => {
    expect(requiredAssetStatus("nonsense", "nonsense")).toEqual([]);
    expect(allRequiredAssetsAttached([], [])).toBe(true);
  });
});

describe("blockingRequirements", () => {
  test("only a missing face blocks generation", () => {
    expect(blockingRequirements(["character_reference"], [])).toHaveLength(1);
    expect(blockingRequirements(["character_reference"], [{ kind: "character_reference" }])).toEqual([]);
  });

  test("a missing retired kind never blocks", () => {
    expect(blockingRequirements(["screenshot"], [])).toEqual([]);
  });
});
