import {
  partitionProfiles,
  resolveActiveProfileId,
  isProfileSelectable,
  profileLabel,
  describeUnapprovedCount,
  describeUnapprovedNames,
  describeEmptySelection,
} from "./profileSelection";

const APPROVED = { id: "a", brand_name: "Threadly", status: "approved" };
const WAITING = { id: "b", brand_name: "Vocolens", status: "pending" };

describe("partitionProfiles", () => {
  test("names the excluded instead of dropping them", () => {
    const { approved, unapproved } = partitionProfiles([APPROVED, WAITING]);
    expect(approved).toEqual([APPROVED]);
    expect(unapproved).toEqual([WAITING]);
  });

  test("an unrecognised status is unapproved, the safe direction", () => {
    expect(partitionProfiles([{ id: "x", status: "weird" }]).approved).toEqual([]);
  });

  test("non-arrays are safe", () => {
    expect(partitionProfiles(null)).toEqual({ approved: [], unapproved: [] });
  });
});

describe("resolveActiveProfileId", () => {
  const profiles = [APPROVED, WAITING];

  test("explicit beats everything, in prop-param-query order", () => {
    expect(resolveActiveProfileId({ propId: "p", paramId: "q", queryId: "r", profiles })).toBe("p");
    expect(resolveActiveProfileId({ paramId: "q", queryId: "r", profiles })).toBe("q");
    expect(resolveActiveProfileId({ queryId: "r", profiles })).toBe("r");
  });

  test("a remembered id is honoured only while it still exists", () => {
    expect(resolveActiveProfileId({ rememberedId: "b", profiles })).toBe("b");
    expect(resolveActiveProfileId({ rememberedId: "gone", profiles })).toBe("a");
  });

  test("falls back to newest approved, then newest profile, then empty", () => {
    expect(resolveActiveProfileId({ profiles })).toBe("a");
    expect(resolveActiveProfileId({ profiles: [WAITING] })).toBe("b");
    expect(resolveActiveProfileId({ profiles: [] })).toBe("");
  });
});

describe("labels and empty states", () => {
  test("selectability is the approval comparison, nothing else", () => {
    expect(isProfileSelectable(APPROVED)).toBe(true);
    expect(isProfileSelectable(WAITING)).toBe(false);
  });

  test("a blank name falls back rather than rendering blank", () => {
    expect(profileLabel({})).toBe("Untitled app");
  });

  test("counts pluralize and vanish at zero", () => {
    expect(describeUnapprovedCount(0)).toBe("");
    expect(describeUnapprovedCount(1)).toBe("1 profile waiting for approval");
    expect(describeUnapprovedCount(3)).toBe("3 profiles waiting for approval");
  });

  test("the waiting are named so they read as pending, not missing", () => {
    expect(describeUnapprovedNames([APPROVED, WAITING])).toEqual(["Vocolens"]);
  });

  test("the empty state names the blockers or the next step", () => {
    expect(describeEmptySelection([WAITING])).toContain("Vocolens");
    expect(describeEmptySelection([])).toContain("approve");
  });
});
