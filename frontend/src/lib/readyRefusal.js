import { errorMessageFor } from "./errorMessage";

// What a save should say about the ready check that follows it.
//
// Every content save re-marks the project ready (the approval describes
// the words just saved), and a refusal is normally the founder's to
// read: it is why the render button stands disabled. The one exception
// is a project with no script yet. It cannot be ready and has done
// nothing wrong — it simply has no plan — so the check's "Generate or
// write a script before marking this ready." refusal stays quiet
// instead of flashing as an error over an ordinary pick, like the
// camera setup on the step before the plan exists, whose autosave
// rides the same handler. The server checks the script before
// anything else, so a refusal on a script-less project is always that
// one; the rule keys on the project's state, never on the refusal's
// sentence.
export function readyRefusalMessage(project, readyError) {
  if (!readyError) return null;
  if (!String(project?.script || "").trim()) return null;
  return errorMessageFor(readyError);
}
