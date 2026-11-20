import { readyRefusalMessage } from "./readyRefusal";

// The save handler re-marks the project ready after every content save,
// and a server refusal is normally stated so the founder can read why the
// render button is disabled. The one refusal that must stay quiet is the
// no-script one: a project with no plan yet is simply not ready, and
// flashing "Generate or write a script before marking this ready." as an
// error over an ordinary pick — the camera setup, on the step before the
// plan exists — reads as the app breaking when nothing is wrong. The
// server checks the script first, so a refusal on a script-less project
// is always that one; the rule keys on the project's state, never on the
// sentence.
const NO_SCRIPT_REFUSAL = {
  response: {
    status: 400,
    data: { detail: "Generate or write a script before marking this ready." },
  },
};
const PHOTO_REFUSAL = {
  response: {
    status: 400,
    data: {
      detail:
        "This template puts a person on camera, so it needs a character " +
        "reference. The video is generated from your photograph, so " +
        "without one the model would invent someone who looks nothing " +
        "like you. Attach a character reference on the Template & photo " +
        "step, then mark this ready again.",
    },
  },
};

describe("readyRefusalMessage", () => {
  test("no refusal means no message", () => {
    expect(readyRefusalMessage({ script: "The words." }, null)).toBeNull();
    expect(readyRefusalMessage({}, null)).toBeNull();
  });

  test("a save on a project with no script yet shows no error", () => {
    expect(readyRefusalMessage({ script: "" }, NO_SCRIPT_REFUSAL)).toBeNull();
    expect(readyRefusalMessage({ script: "   " }, NO_SCRIPT_REFUSAL)).toBeNull();
    expect(readyRefusalMessage({}, NO_SCRIPT_REFUSAL)).toBeNull();
  });

  test("a refusal on a project with a script is still stated in full", () => {
    expect(readyRefusalMessage({ script: "The words." }, PHOTO_REFUSAL)).toBe(
      PHOTO_REFUSAL.response.data.detail
    );
  });

  test("the rule keys on the project's state, not the refusal's sentence", () => {
    // A scripted project states even the script sentence rather than
    // hiding a refusal by matching its words.
    expect(readyRefusalMessage({ script: "The words." }, NO_SCRIPT_REFUSAL)).toBe(
      "Generate or write a script before marking this ready."
    );
  });
});
