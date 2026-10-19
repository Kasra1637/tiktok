import { sentenceCase, sentenceCaseTrimmed } from "./copyCase";

describe("sentenceCase", () => {
  test("capitalizes a lowercase model-written sentence", () => {
    expect(sentenceCase("sporadic journaling that fails to reveal patterns")).toBe(
      "Sporadic journaling that fails to reveal patterns"
    );
  });

  test("capitalizes after sentence boundaries only", () => {
    expect(sentenceCase("nothing gets finished. it stays with them")).toBe(
      "Nothing gets finished. It stays with them"
    );
  });

  test("leaves already-correct text alone", () => {
    expect(sentenceCase("Already correct.")).toBe("Already correct.");
  });

  test("never touches addresses or bare domains", () => {
    expect(sentenceCase("privacy@hookforge.app")).toBe("privacy@hookforge.app");
    expect(sentenceCase("taskly.com/sync is where it lives")).toBe(
      "taskly.com/sync is where it lives"
    );
  });

  test("never rewrites brand names with internal capitals", () => {
    expect(sentenceCase("iOS is the platform")).toBe("iOS is the platform");
    expect(sentenceCase("eBay sellers do this")).toBe("eBay sellers do this");
  });

  test("leading whitespace does not stop the match", () => {
    expect(sentenceCase("  indented opener")).toBe("Indented opener");
  });

  test("null, undefined and blank come back empty, never crash", () => {
    expect(sentenceCase(null)).toBe("");
    expect(sentenceCase(undefined)).toBe("");
    expect(sentenceCase("   ")).toBe("   ");
  });

  test("non-prose openers are returned untouched", () => {
    expect(sentenceCase("42 things to try")).toBe("42 things to try");
  });
});

describe("sentenceCaseTrimmed", () => {
  test("trims as well as capitalizes", () => {
    expect(sentenceCaseTrimmed("  padded opener  ")).toBe("Padded opener");
  });
});
