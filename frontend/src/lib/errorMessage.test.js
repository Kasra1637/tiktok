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
});
