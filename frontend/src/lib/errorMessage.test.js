import { errorMessageFor } from "./errorMessage";

describe("errorMessageFor", () => {
  test("a handler detail wins whenever it says something specific", () => {
    expect(errorMessageFor({ response: { status: 502, data: { detail: "Recovery found no copy." } } })).toBe(
      "Recovery found no copy."
    );
    expect(errorMessageFor({ response: { status: 400, data: { detail: "Too long." } } })).toBe("Too long.");
  });

  test("a bodyless 502 reads as a restart, not a broken action", () => {
    const message = errorMessageFor({ response: { status: 502 } });
    expect(message).toContain("restarted");
    expect(message).toContain("try again");
  });

  test("anything else falls back to the error or a generic line", () => {
    expect(errorMessageFor({ message: "Network Error" })).toBe("Network Error");
    expect(errorMessageFor(null)).toContain("Something went wrong");
  });

  test("a bodyless 413 names the Download-first remedy, not the status code", () => {
    const message = errorMessageFor({ response: { status: 413 }, message: "Request failed with status code 413" });
    expect(message).toContain("Download");
    expect(message).toContain("Save again");
    expect(message).not.toContain("413");
  });

  test("a 413 with a handler detail keeps the handler's remedy", () => {
    expect(
      errorMessageFor({ response: { status: 413, data: { detail: "Those parts would join past the 200 MB save ceiling. Export a shorter clip." } } })
    ).toBe("Those parts would join past the 200 MB save ceiling. Export a shorter clip.");
  });

  test("a bodyless 429 names the retry, not the status code", () => {
    const message = errorMessageFor({ response: { status: 429 }, message: "Request failed with status code 429" });
    expect(message).toContain("try again");
    expect(message).not.toContain("429");
  });

  test("a client timeout says the wait limit was hit, not the raw axios text", () => {
    // What the founder actually saw (Nov 14): "Something went wrong /
    // timeout of 120000ms exceeded" — axios' own message for a request the
    // browser gave up on while the server was still working. The plain
    // reading is that generation outran the wait limit, and the raw
    // milliseconds help nobody.
    const message = errorMessageFor({ code: "ECONNABORTED", message: "timeout of 120000ms exceeded" });
    expect(message).toContain("wait limit");
    expect(message).toContain("try again");
    expect(message).not.toContain("120000");
    expect(message).not.toContain("timeout of");
  });
});
