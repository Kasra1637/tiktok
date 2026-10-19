import { inferHookTemplateCategory, categoryLabel } from "./hookTemplateCategories";

describe("inferHookTemplateCategory", () => {
  test("classifies on signal words without another AI request", () => {
    expect(
      inferHookTemplateCategory({ hook_summary: "A dramatic before and after transformation reveal" })
    ).toBe("reveal");
  });

  test("reads array fields as well as strings", () => {
    expect(
      inferHookTemplateCategory({ replicable_mechanics: ["the founder does a double take", "gasp"] })
    ).toBe("reaction");
  });

  test("nothing recognizable is other, never a guess", () => {
    expect(inferHookTemplateCategory({ hook_summary: "A calm explainer" })).toBe("other");
    expect(inferHookTemplateCategory(null)).toBe("other");
  });

  test("ties are deterministic: first highest score wins", () => {
    const once = inferHookTemplateCategory({ hook_summary: "secret mystery with a sudden jarring cut" });
    const twice = inferHookTemplateCategory({ hook_summary: "secret mystery with a sudden jarring cut" });
    expect(once).toBe(twice);
  });
});

describe("categoryLabel", () => {
  test("unknown keys read as Other", () => {
    expect(categoryLabel("curiosity-gap")).toBe("Curiosity Gap");
    expect(categoryLabel("nope")).toBe("Other");
  });
});
